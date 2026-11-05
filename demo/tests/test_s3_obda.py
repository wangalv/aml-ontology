"""Tests for scenario 3 as an OBDA design (SPARQL step, then a rewrite to SQL). Run from the demo/ directory:

    ../.venv/bin/python -m unittest discover -s tests -v

No test calls a real model or opens the real database: a fake model returns the text a test needs, and the functions that talk to the
database (dbrun.run_query and dbrun.score) are replaced by fakes, so every outcome is repeatable.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amldemo import dbrun, obda  # noqa: E402
from amldemo.scenarios import s3_hunting, s3_obda  # noqa: E402

DICTIONARY = s3_hunting.load_dictionary()
COLUMNS = [c["name"] for c in DICTIONARY["columns"]]
ONTOLOGY_TEXT, R2RML_TEXT, ONTOLOGY, R2RML = obda.load()
DEFINED = obda.defined_terms(ONTOLOGY)
TERM_COLUMNS = obda.term_columns(R2RML, COLUMNS)
LOOP_SPARQL = """SELECT ?t1 ?t2 ?t3 WHERE {
  ?t1 fcd:fromAccount ?a ; fcd:toAccount ?b ; fcd:timestamp ?ts1 .
  ?t2 fcd:fromAccount ?b ; fcd:toAccount ?c ; fcd:timestamp ?ts2 .
  ?t3 fcd:fromAccount ?c ; fcd:toAccount ?a ; fcd:timestamp ?ts3 .
  FILTER (?ts1 < ?ts2 && ?ts2 < ?ts3 && ?a != ?b && ?b != ?c)
}"""
# Three payments that close a loop, in time order, each paying from a different account.
LOOP_SQL = ("WITH loops AS (SELECT t1.tx_id AS a, t2.tx_id AS b, t3.tx_id AS c FROM txs t1 "
            "JOIN txs t2 ON t2.from_account = t1.to_account AND t2.ts > t1.ts "
            "JOIN txs t3 ON t3.from_account = t2.to_account AND t3.ts > t2.ts AND t3.to_account = t1.from_account "
            "WHERE t1.from_account <> t2.from_account AND t2.from_account <> t3.from_account) "
            "SELECT a AS tx_id FROM loops UNION SELECT b FROM loops UNION SELECT c FROM loops LIMIT 10000")
# Any chain of three payments: it never checks that the last one returns to the start.
CHAIN_SQL = ("SELECT t1.tx_id FROM txs t1 JOIN txs t2 ON t2.from_account = t1.to_account AND t2.ts > t1.ts "
             "JOIN txs t3 ON t3.from_account = t2.to_account AND t3.ts > t2.ts LIMIT 10000")
# A correct loop that also reads a column no term of the SPARQL stands for.
EXTRA_COLUMN_SQL = LOOP_SQL.replace("WHERE t1.from_account <> t2.from_account", "WHERE NOT t1.is_self_transfer AND t1.from_account <> t2.from_account")


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(self, sparql_replies, rewrite_replies):
        self.replies = {"s3-sparql": list(sparql_replies), "s3-rewrite": list(rewrite_replies)}
        self.prompts = []

    def complete(self, system, user, task):
        self.prompts.append((task, user))
        return self.replies[task].pop(0)


def sparql_reply(text):
    return json.dumps({"sparql": text, "patterns": [{"pattern": "?t1 fcd:fromAccount ?a", "from_indicator": "Cyclical patterns in funds or asset transfers"}]})


def sql_reply(sql):
    return json.dumps({"sql": sql, "steps": [{"sparql": "?t1 fcd:fromAccount ?a", "sql": "t1.from_account", "mapping": "fcd:fromAccount to from_account"}]})


def run_rows(ids):
    return {"columns": ["tx_id"], "rows": [[i] for i in ids], "truncated": False, "seconds": 0.5}


class MappingTests(unittest.TestCase):
    def test_terms_map_to_the_columns_of_the_table(self):
        self.assertEqual(TERM_COLUMNS["fcd:fromAccount"], ["from_account"])
        self.assertEqual(TERM_COLUMNS["fcd:timestamp"], ["ts"])
        self.assertEqual(TERM_COLUMNS["fcd:Transaction"], ["tx_id"])
        self.assertEqual(len(TERM_COLUMNS["fcd:paymentFormat"]), 7)

    def test_the_ontology_text_describes_each_term_without_column_names(self):
        block = obda.ontology_block(ONTOLOGY)
        self.assertIn("fcd:fromAccount", block)
        self.assertNotIn("from_account", block)


class SparqlCheckTests(unittest.TestCase):
    def test_a_loop_query_over_ontology_terms_passes(self):
        problems, used = s3_obda.check_sparql(LOOP_SPARQL, DEFINED)
        self.assertEqual(problems, [])
        self.assertEqual(used, {"fcd:fromAccount", "fcd:toAccount", "fcd:timestamp"})

    def test_a_term_the_ontology_does_not_define_is_refused(self):
        problems, _ = s3_obda.check_sparql(LOOP_SPARQL.replace("fcd:toAccount ?c", "fcd:destination ?c"), DEFINED)
        self.assertTrue(any("fcd:destination" in p for p in problems))

    def test_a_property_path_is_refused(self):
        problems, _ = s3_obda.check_sparql("SELECT ?t WHERE { ?t fcd:fromAccount+ ?a }", DEFINED)
        self.assertTrue(any("property paths" in p for p in problems))

    def test_a_query_that_does_not_select_a_transaction_is_refused(self):
        problems, _ = s3_obda.check_sparql("SELECT ?a WHERE { ?t fcd:fromAccount ?a }", DEFINED)
        self.assertTrue(any("transaction variable" in p for p in problems))

    def test_text_that_is_not_sparql_is_refused(self):
        problems, _ = s3_obda.check_sparql("SELEC ?a", DEFINED)
        self.assertTrue(any("cannot be parsed" in p for p in problems))


class FidelityTests(unittest.TestCase):
    TERMS = {"fcd:fromAccount", "fcd:toAccount", "fcd:timestamp"}

    def test_sql_that_reads_the_columns_of_the_terms_passes(self):
        self.assertEqual(s3_obda.check_fidelity(LOOP_SQL, self.TERMS, TERM_COLUMNS, COLUMNS), [])

    def test_sql_that_reads_another_column_is_refused(self):
        found = s3_obda.check_fidelity(EXTRA_COLUMN_SQL, self.TERMS, TERM_COLUMNS, COLUMNS)
        self.assertTrue(any("is_self_transfer" in p for p in found))

    def test_sql_that_leaves_a_term_out_is_refused(self):
        found = s3_obda.check_fidelity("SELECT tx_id FROM txs WHERE from_account <> to_account LIMIT 5", self.TERMS, TERM_COLUMNS, COLUMNS)
        self.assertTrue(any("ts" in p for p in found))


class RunTests(unittest.TestCase):
    def go(self, llm):
        with mock.patch.object(dbrun, "run_query", side_effect=lambda sql, **kw: run_rows([7, 8, 9]) if "WHERE tx_id IN" not in sql else
                               {"columns": ["tx_id", "ts", "from_account", "to_account", "amount_log"], "rows": [[7, "t", "a", "b", 1.0]], "truncated": False, "seconds": 0.1}), \
                mock.patch.object(dbrun, "score", return_value={"flagged": {"rows": 3, "laundering": 1}, "window": {"rows": 10}}):
            return s3_obda.run(llm)

    def test_a_good_run_goes_through_both_steps_and_returns_a_result(self):
        result = self.go(FakeLLM([sparql_reply(LOOP_SPARQL)], [sql_reply(LOOP_SQL)]))
        self.assertTrue(result["sparql"]["accepted"] and result["rewrite"]["accepted"])
        self.assertEqual(result["result"]["n_rows"], 3)
        self.assertEqual(result["rewrite"]["expected_columns"], result["rewrite"]["used_columns"] and sorted(result["rewrite"]["used_columns"]))

    def test_the_prompts_carry_the_ontology_then_the_mapping_but_never_the_dictionary(self):
        llm = FakeLLM([sparql_reply(LOOP_SPARQL)], [sql_reply(LOOP_SQL)])
        self.go(llm)
        first, second = llm.prompts
        self.assertEqual((first[0], second[0]), ("s3-sparql", "s3-rewrite"))
        self.assertIn("fcd:fromAccount", first[1])
        self.assertNotIn("from_account", first[1])
        self.assertIn("rr:TriplesMap", second[1])
        self.assertNotIn("data_dictionary", first[1] + second[1])

    def test_a_sparql_with_an_unknown_term_is_sent_back_once(self):
        bad = LOOP_SPARQL.replace("fcd:toAccount ?c", "fcd:destination ?c")
        llm = FakeLLM([sparql_reply(bad), sparql_reply(LOOP_SPARQL)], [sql_reply(LOOP_SQL)])
        result = self.go(llm)
        self.assertEqual(len(result["sparql"]["attempts"]), 2)
        self.assertIn("fcd:destination", " ".join(result["sparql"]["attempts"][0]["problems"]))
        self.assertTrue(result["rewrite"]["accepted"])

    def test_a_chain_that_never_returns_is_refused_and_the_rewrite_is_retried(self):
        llm = FakeLLM([sparql_reply(LOOP_SPARQL)], [sql_reply(CHAIN_SQL), sql_reply(LOOP_SQL)])
        result = self.go(llm)
        self.assertEqual(len(result["rewrite"]["attempts"]), 2)
        self.assertTrue(result["rewrite"]["attempts"][0]["problems"])
        self.assertTrue(result["rewrite"]["accepted"])

    def test_sql_that_drifts_from_the_sparql_is_refused(self):
        llm = FakeLLM([sparql_reply(LOOP_SPARQL)], [sql_reply(EXTRA_COLUMN_SQL), sql_reply(LOOP_SQL)])
        result = self.go(llm)
        self.assertIn("is_self_transfer", " ".join(result["rewrite"]["attempts"][0]["problems"]))

    def test_three_bad_sparql_attempts_stop_the_run_before_any_sql(self):
        llm = FakeLLM([sparql_reply("SELEC")] * 3, [])
        result = self.go(llm)
        self.assertFalse(result["sparql"]["accepted"])
        self.assertIsNone(result["rewrite"])
        self.assertIsNone(result["result"])


if __name__ == "__main__":
    unittest.main()
