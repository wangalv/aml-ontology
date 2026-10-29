"""Tests for scenario 3 (typology-driven query). Run from the demo/ directory:

    ../.venv/bin/python -m unittest discover -s tests -v

No test calls a real model or opens the real database: a fake model returns the text a test needs, and the two functions
that talk to the database (dbrun.run_query and dbrun.score) are replaced by fakes, so every outcome is repeatable.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amldemo import dbrun, sqlguard  # noqa: E402
from amldemo.scenarios import s3_hunting  # noqa: E402

DICTIONARY = s3_hunting.load_dictionary()
GOOD = "SELECT tx_id FROM txs WHERE ts >= '2022-09-09' AND is_self_transfer LIMIT 100"
WINDOW = {"rows": 1000, "laundering": 10, "from": "a", "to": "b", "in_verified_cycles": 20, "in_verified_cycles_laundering": 5}


def problems(sql):
    return sqlguard.check(sql, DICTIONARY)


class GuardTests(unittest.TestCase):
    def test_a_plain_read_only_query_passes(self):
        self.assertEqual(problems(GOOD), [])

    def test_a_cycle_query_with_a_with_clause_and_aliases_passes(self):
        sql = ("WITH legs AS (SELECT tx_id, ts, from_account AS a, to_account AS b FROM txs) "
               "SELECT l1.tx_id FROM legs l1 JOIN legs l2 ON l2.a = l1.b AND l2.ts > l1.ts WHERE l2.b = l1.a LIMIT 50")
        self.assertEqual(problems(sql), [])

    def test_writes_and_other_statements_are_refused(self):
        for sql in ("DELETE FROM txs", "DROP TABLE txs", "PRAGMA version", "ATTACH 'x.db'", "COPY txs TO 'x.csv'"):
            self.assertTrue(problems(sql), sql)

    def test_two_statements_are_refused(self):
        self.assertTrue(any("exactly one" in p for p in problems(GOOD + "; " + GOOD)))

    def test_the_label_is_refused_with_a_reason(self):
        found = problems("SELECT tx_id, label FROM txs WHERE ts > '2022-09-09' LIMIT 5")
        self.assertTrue(any("label" in p and "answer key" in p for p in found))

    def test_columns_outside_the_dictionary_are_refused(self):
        self.assertTrue(any("graph_roundtrip" in p for p in problems("SELECT tx_id FROM txs WHERE graph_roundtrip = 1 AND ts > 'x' LIMIT 5")))
        self.assertTrue(any("split" in p for p in problems("SELECT tx_id FROM txs WHERE split = 'test' AND ts > 'x' LIMIT 5")))

    def test_select_star_is_refused(self):
        self.assertTrue(any("SELECT *" in p for p in problems("SELECT * FROM txs WHERE ts > 'x' LIMIT 5")))

    def test_other_tables_and_table_functions_are_refused(self):
        self.assertTrue(any("tx_features" in p for p in problems("SELECT tx_id FROM tx_features WHERE ts > 'x' LIMIT 5")))
        self.assertTrue(any("table functions" in p for p in problems("SELECT tx_id FROM read_csv('x.csv') WHERE ts > 'x' LIMIT 5")))

    def test_a_limit_is_required_and_capped(self):
        self.assertTrue(any("LIMIT" in p for p in problems("SELECT tx_id FROM txs WHERE ts > 'x'")))
        self.assertTrue(any("LIMIT" in p for p in problems("SELECT tx_id FROM txs WHERE ts > 'x' LIMIT 99999999")))

    def test_the_query_must_return_tx_id_and_use_ts(self):
        self.assertTrue(any("tx_id" in p for p in problems("SELECT from_account FROM txs WHERE ts > 'x' LIMIT 5")))
        self.assertTrue(any("ts" in p for p in problems("SELECT tx_id FROM txs LIMIT 5")))

    def test_unparseable_and_empty_text_is_refused(self):
        self.assertTrue(problems("SELEKT tx_id FROM"))
        self.assertTrue(problems("   "))


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(self, coverage, queries):
        self.coverage, self.queries, self.calls = coverage, list(queries), []

    def complete(self, system, user, task):
        self.calls.append((task, user))
        if task == "s3-coverage":
            return json.dumps(self.coverage)
        return json.dumps(self.queries.pop(0) if len(self.queries) > 1 else self.queries[0])


def coverage(overrides=None):
    """A coverage answer for T0039: IND02191 is queryable, everything else is not."""
    ids = [f"IND0219{n}" for n in range(1, 10)]
    rows = [{"indicator": i, "queryable": "no", "columns": [], "reason": "not in the table"} for i in ids]
    rows[0] = {"indicator": "IND02191", "queryable": "yes", "columns": ["tx_id", "ts"], "reason": "cycles can be joined"}
    for index, change in (overrides or {}).items():
        rows[index] = {**rows[index], **change}
    return {"indicators": rows}


def query(sql=GOOD):
    return {"queries": [{"indicator": "IND02191", "sql": sql, "conditions": [{"condition": "c", "from_indicator": "f"}]}]}


def fake_run(rows=None, error=None):
    def run_query(sql, max_rows=10000, timeout=120):
        if error:
            return {"error": error}
        return {"columns": ["tx_id"], "rows": rows if rows is not None else [[1], [2], [3]], "truncated": False, "seconds": 0.1}
    return run_query


def fake_score(tx_ids):
    ids = list(tx_ids)
    return {"window": WINDOW, "flagged": {"rows": len(ids), "laundering": 1, "in_verified_cycles": 2, "in_verified_cycles_laundering": 1, "outside_window": 0}}


class HuntTests(unittest.TestCase):
    def hunt(self, llm, run=None):
        with mock.patch.object(dbrun, "run_query", run or fake_run()), mock.patch.object(dbrun, "score", fake_score):
            return s3_hunting.hunt("T0039", llm)

    def test_the_coverage_has_one_entry_per_indicator(self):
        result = self.hunt(FakeLLM(coverage(), [query()]))
        self.assertEqual([c["indicator"] for c in result["coverage"]], [f"IND0219{n}" for n in range(1, 10)])
        self.assertEqual([c["queryable"] for c in result["coverage"]].count("yes"), 1)

    def test_only_the_indicators_the_model_can_see_get_a_query(self):
        llm = FakeLLM(coverage(), [query()])
        result = self.hunt(llm)
        self.assertEqual([q["indicator"] for q in result["queries"]], ["IND02191"])
        self.assertEqual([t for t, _ in llm.calls], ["s3-coverage", "s3-sql"])

    def test_an_accepted_query_is_judged_with_the_labels(self):
        result = self.hunt(FakeLLM(coverage(), [query()]))
        q = result["queries"][0]
        self.assertTrue(q["accepted"])
        self.assertEqual(q["evaluation"]["rows"], 3)
        self.assertEqual(result["window"]["in_verified_cycles"], 20)

    def test_the_model_is_never_told_about_the_label_or_the_answers(self):
        llm = FakeLLM(coverage(), [query()])
        self.hunt(llm)
        for _, prompt in llm.calls:
            for word in ("label", "graph_roundtrip", "verified", "is_tail_period"):
                self.assertNotIn(word, prompt.lower(), word)

    def test_a_refused_query_is_sent_back_with_the_reason_and_may_be_rewritten(self):
        bad = "SELECT tx_id, label FROM txs WHERE ts > 'x' LIMIT 5"
        llm = FakeLLM(coverage(), [query(bad), query(GOOD)])
        result = self.hunt(llm)
        attempts = result["queries"][0]["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertTrue(attempts[0]["guard"])
        self.assertIsNone(attempts[0]["run"])
        self.assertEqual(attempts[1]["guard"], [])
        self.assertTrue(result["queries"][0]["accepted"])
        self.assertIn("answer key", llm.calls[-1][1])  # the reason went back to the model

    def test_a_query_that_never_gets_past_the_guard_is_not_run_and_not_judged(self):
        bad = "SELECT * FROM txs"
        ran = mock.Mock(side_effect=fake_run())
        result = self.hunt(FakeLLM(coverage(), [query(bad)]), run=ran)
        q = result["queries"][0]
        self.assertFalse(q["accepted"])
        self.assertEqual(len(q["attempts"]), s3_hunting.MAX_ATTEMPTS)
        self.assertIsNone(q["evaluation"])
        ran.assert_not_called()

    def test_a_database_error_is_reported_and_retried(self):
        result = self.hunt(FakeLLM(coverage(), [query()]), run=fake_run(error="Binder Error: something"))
        q = result["queries"][0]
        self.assertFalse(q["accepted"])
        self.assertEqual(q["attempts"][-1]["run"], {"error": "Binder Error: something"})

    def test_a_tx_id_column_that_holds_account_ids_is_sent_back(self):
        calls = []

        def run_query(sql, max_rows=10000, timeout=120):
            calls.append(sql)
            rows = [["80308DE40"], ["80308F520"]] if len(calls) == 1 else [[11], [12]]
            return {"columns": ["tx_id"], "rows": rows, "truncated": False, "seconds": 0.1}

        llm = FakeLLM(coverage(), [query(), query(GOOD + " ")])
        result = self.hunt(llm, run=run_query)
        q = result["queries"][0]
        self.assertEqual(len(q["attempts"]), 2)
        self.assertIn("80308DE40", q["attempts"][0]["run"]["error"])
        self.assertIn("80308DE40", llm.calls[-1][1])
        self.assertTrue(q["accepted"])
        self.assertEqual(q["evaluation"]["rows"], 2)

    def test_made_up_indicators_and_columns_in_the_coverage_are_flagged(self):
        answer = coverage()
        answer["indicators"].append({"indicator": "IND99999", "queryable": "yes", "columns": ["tx_id"], "reason": "made up"})
        answer["indicators"][1] = {"indicator": "IND02192", "queryable": "yes", "columns": ["invoice_id"], "reason": "x"}
        result = self.hunt(FakeLLM(answer, [query()]))
        self.assertNotIn("IND99999", [c["indicator"] for c in result["coverage"]])
        flagged = next(c for c in result["coverage"] if c["indicator"] == "IND02192")
        self.assertTrue(any("invoice_id" in p for p in flagged["problems"]))
        self.assertNotIn("IND02192", [q["indicator"] for q in result["queries"]])  # a flagged answer is not trusted

    def test_a_missing_indicator_is_marked_not_answered(self):
        answer = coverage()
        del answer["indicators"][3]
        result = self.hunt(FakeLLM(answer, [query()]))
        self.assertEqual(next(c for c in result["coverage"] if c["indicator"] == "IND02194")["queryable"], "not-answered")

    def test_a_bad_queryable_value_is_flagged(self):
        result = self.hunt(FakeLLM(coverage({2: {"queryable": "maybe"}}), [query()]))
        self.assertTrue(next(c for c in result["coverage"] if c["indicator"] == "IND02193")["problems"])


class QuoteTests(unittest.TestCase):
    TEXT = "Cyclical patterns in funds or asset transfers that ultimately revert to the same origin across multiple accounts"

    def test_words_that_occur_in_the_indicator_are_found(self):
        self.assertTrue(s3_hunting.quoted("ultimately revert to the same origin", self.TEXT))
        self.assertTrue(s3_hunting.quoted("Cyclical patterns ... across multiple accounts", self.TEXT))

    def test_words_that_do_not_occur_are_not_found(self):
        self.assertFalse(s3_hunting.quoted("rapidly cycling funds", self.TEXT))
        self.assertFalse(s3_hunting.quoted("", self.TEXT))

    def test_every_condition_of_a_query_says_whether_its_quote_is_real(self):
        with mock.patch.object(dbrun, "run_query", fake_run()), mock.patch.object(dbrun, "score", fake_score):
            result = s3_hunting.hunt("T0039", FakeLLM(coverage(), [{"queries": [{"indicator": "IND02191", "sql": GOOD, "conditions": [
                {"condition": "c1", "from_indicator": "revert to the same origin"}, {"condition": "c2", "from_indicator": "made up words"}]}]}]))
        self.assertEqual([c["quote_found"] for c in result["queries"][0]["attempts"][0]["conditions"]], [True, False])


class DictionaryTests(unittest.TestCase):
    def test_the_example_query_passes_the_guard_and_is_not_the_pattern_being_asked_about(self):
        self.assertEqual(problems(DICTIONARY["example"]["sql"]), [])
        self.assertIn("different pattern", DICTIONARY["example"]["pattern"])

    def test_the_dictionary_lists_no_answer_bearing_column(self):
        names = {c["name"] for c in DICTIONARY["columns"]}
        for hidden in ("label", "graph_roundtrip", "split", "is_tail_period") + tuple(n for n in names if n.startswith("rule_")):
            self.assertNotIn(hidden, names)

    def test_the_amount_trap_is_written_down(self):
        meaning = next(c for c in DICTIONARY["columns"] if c["name"] == "amount_log")["meaning"]
        self.assertIn("NOT the amount", meaning)


if __name__ == "__main__":
    unittest.main()
