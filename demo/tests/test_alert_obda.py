"""The alerts of a payment read through the R2RML mapping and the alert ontology (amldemo/alert_obda.py), and that scenario 4 asks the model the same
thing whether the flags and techniques come from here or from alert_sources.json. No database and no model: the rows the mapping's SQL would
return are given by hand."""
import itertools
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from amldemo import alert_obda
from amldemo.scenarios import s4_reason
from amldemo import sqlrun

ALL = ["rule_structuring", "rule_money_mule", "rule_fan_in", "rule_pep", "rule_high_risk_business", "rule_high_risk_country", "graph_roundtrip"]
SOURCES = s4_reason.load_sources()


def rows_for(tx, rule=(), graph=True, ml=0.695):
    """What the SQL of each TriplesMap would return for payment `tx`: which flags fired, whether the graph and the ML model alerted."""
    def rows_of(tx_id, statements):
        out = []
        for sql in statements:
            if "FROM alert_rule" in sql:
                flag = sql.split("WHERE")[-1].split("=")[0].strip() if "WHERE" in sql else None
                out.append([{"tx_id": tx_id}] if (flag is None or flag in rule) and (flag is not None or rule) else [])
            elif "FROM alert_ml" in sql:
                out.append([{"tx_id": tx_id, "ml_proba": ml}] if ml is not None else [])
            else:
                out.append([{"tx_id": tx_id}] if graph else [])
        return out
    return rows_of


def payment_with(flags, ml=None):
    rule = [f for f in flags if f.startswith("rule")]
    return {"tx_id": 77, "ts": "2022-09-10 15:19:00", "amount": 1000.0, "from": "A1", "to": "B2", "currency": "US Dollar", "format": "Wire",
            "sources": (["rule"] if rule else []) + (["ml"] if ml is not None else []) + (["graph"] if "graph_roundtrip" in flags else []),
            "rule_flags": rule, "ml_proba": ml, "cross_currency": False, "self_transfer": False, "same_bank": False,
            "cycle": {"accounts": ["A1"], "span_days": 1.0, "legs": [{"ts": "2022-09-10 15:19", "from": "A1", "to": "B2", "amount": 1000.0}]}}


class AlertsOfPayment(unittest.TestCase):
    def test_the_mapping_gives_each_system_its_flags_and_score(self):
        view = alert_obda.alerts_of(77, rows_for(77, rule=("rule_money_mule", "rule_high_risk_country")))
        self.assertEqual(view["systems"]["rule"]["flags"], ["rule_money_mule", "rule_high_risk_country"])
        self.assertEqual(view["systems"]["ml"], {"flags": [], "score": 0.695})
        self.assertEqual(view["systems"]["graph"]["flags"], ["graph_roundtrip"])

    def test_a_system_that_did_not_alert_is_not_in_the_view(self):
        view = alert_obda.alerts_of(77, rows_for(77, rule=("rule_pep",), graph=False, ml=None))
        self.assertEqual(sorted(view["systems"]), ["rule"])

    def test_each_flag_carries_what_it_detects_and_its_links_with_their_strength(self):
        view = alert_obda.alerts_of(77, rows_for(77, rule=("rule_money_mule",)))
        mule = view["flags"]["rule_money_mule"]
        self.assertEqual(mule["detects"], SOURCES["sources"]["rule"]["flags"]["rule_money_mule"]["detects"])
        self.assertEqual([(l["id"], l["strength"]) for l in mule["links"]], [("T0011", "strong"), ("T0083", "medium"), ("T0140", "weak")])

    def test_the_ontology_carries_every_link_of_the_draft_mapping_and_no_other(self):
        onto, _ = alert_obda.load()
        for source in SOURCES["sources"].values():
            for flag, entry in source["flags"].items():
                got = alert_obda.flags_info(onto, [flag])[flag]
                self.assertEqual({(l["id"], l["strength"]) for l in got["links"]}, {(l["id"], l["strength"]) for l in entry["techniques"]}, flag)
                self.assertEqual(got["detects"], entry["detects"], flag)


class DisagreementWithTheTables(unittest.TestCase):
    def test_agreement_is_no_problem(self):
        view = alert_obda.alerts_of(77, rows_for(77, rule=("rule_money_mule",)))
        self.assertEqual(alert_obda.problems_with(payment_with(["rule_money_mule", "graph_roundtrip"], ml=0.695), view), [])

    def test_a_flag_the_mapping_does_not_give_is_a_problem(self):
        view = alert_obda.alerts_of(77, rows_for(77, rule=("rule_money_mule",)))
        self.assertTrue(alert_obda.problems_with(payment_with(["rule_money_mule", "rule_pep", "graph_roundtrip"], ml=0.695), view))

    def test_a_different_score_is_a_problem(self):
        view = alert_obda.alerts_of(77, rows_for(77, rule=("rule_money_mule",), ml=0.5))
        self.assertTrue(alert_obda.problems_with(payment_with(["rule_money_mule", "graph_roundtrip"], ml=0.695), view))


class SameQuestionToTheModel(unittest.TestCase):
    def test_every_combination_of_flags_gives_the_same_prompt_from_the_mapping_as_from_the_json_file(self):
        onto, _ = alert_obda.load()
        for n in range(len(ALL) + 1):
            for combo in itertools.combinations(ALL, n):
                payment = payment_with(list(combo), ml=0.5)
                mapped = alert_obda.as_sources(alert_obda.flags_info(onto, combo), SOURCES["status"])
                old_t, new_t = s4_reason.techniques_of(payment, SOURCES), s4_reason.techniques_of(payment, mapped)
                old_e, new_e = s4_reason.evidence_of(payment, SOURCES), s4_reason.evidence_of(payment, mapped)
                self.assertEqual(old_e, new_e, combo)
                self.assertEqual(s4_reason.build_prompt(payment, old_t, old_e), s4_reason.build_prompt(payment, new_t, new_e), combo)

    def test_a_saved_result_stands_only_if_the_model_would_be_asked_the_same(self):
        payment = payment_with(["rule_money_mule", "graph_roundtrip"], ml=0.5)
        onto, _ = alert_obda.load()
        mapped = alert_obda.as_sources(alert_obda.flags_info(onto, ["rule_money_mule", "graph_roundtrip"]), SOURCES["status"])
        saved = {"evidence": s4_reason.evidence_of(payment, mapped),
                 "techniques": [{"id": t["id"], "indicators": t["indicators"]} for t in s4_reason.techniques_of(payment, mapped).values()]}
        self.assertTrue(s4_reason.same_prompt(saved, payment, mapped))
        self.assertFalse(s4_reason.same_prompt({**saved, "evidence": saved["evidence"][:-1]}, payment, mapped))
        self.assertFalse(s4_reason.same_prompt({**saved, "techniques": saved["techniques"][:-1]}, payment, mapped))


class FakeModel:
    name, model = "fake", "fake-1"

    def __init__(self):
        self.calls = 0

    def complete(self, system, prompt, tag):
        self.calls += 1
        return '{"summary": "s", "matches": [], "not_shown": "n"}'


class RunThroughTheMapping(unittest.TestCase):
    FLAGS = ["rule_money_mule", "graph_roundtrip"]

    def run_with(self, payment, reuse=None, rows=None):
        rows = rows or rows_for(payment["tx_id"], rule=payment["rule_flags"], graph="graph" in payment["sources"], ml=payment["ml_proba"])
        model = FakeModel()
        with mock.patch.object(s4_reason.dbrun, "population", return_value={"payments_by_sources": []}), \
                mock.patch.object(s4_reason.dbrun, "sample_payments", return_value={"payments": [payment]}), \
                mock.patch.object(s4_reason.dbrun, "judge_payments", return_value={"payments": {str(payment["tx_id"]): False}}), \
                mock.patch.object(alert_obda.dbrun, "mapping_rows", side_effect=lambda tx, sql: {"rows": rows(tx, sql)}):
            return s4_reason.run(model, "s", reuse=reuse), model

    def test_the_result_carries_what_the_mapping_gave(self):
        result, model = self.run_with(payment_with(self.FLAGS, ml=0.695))
        self.assertEqual(result["results"][0]["mapping"]["systems"]["graph"]["flags"], ["graph_roundtrip"])
        self.assertEqual(model.calls, 2)  # the rule engine's and the graph's evidence, each on its own; the ML model is not asked

    def test_a_saved_run_is_kept_when_the_model_would_be_asked_the_same_and_so_is_its_model(self):
        payment = payment_with(self.FLAGS, ml=0.695)
        first, _ = self.run_with(payment)
        first["provider"], first["model"] = "ollama", "qwen"
        again, model = self.run_with(payment, reuse=first)
        self.assertEqual(model.calls, 0)
        self.assertEqual((again["provider"], again["model"]), ("ollama", "qwen"))

    def test_a_saved_run_is_not_kept_when_the_evidence_changed(self):
        payment = payment_with(self.FLAGS, ml=0.695)
        first, _ = self.run_with(payment)
        first["results"][0]["evidence"] = first["results"][0]["evidence"][:-1]
        _, model = self.run_with(payment, reuse=first)
        self.assertEqual(model.calls, 2)

    def test_it_stops_when_the_mapping_and_the_tables_disagree(self):
        payment = payment_with(self.FLAGS, ml=0.695)
        with self.assertRaises(s4_reason.dbrun.DatabaseError):
            self.run_with(payment, rows=rows_for(77, rule=("rule_pep",), graph=True, ml=0.695))


class RunnerRefusesWhatIsNotTheMapping(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE TABLE alert_rule (tx_id BIGINT, rule_pep INT, label INT)")
        self.con.execute("INSERT INTO alert_rule VALUES (1, 1, 0), (2, 0, 1)")

    def test_it_gives_the_rows_of_the_payment_only(self):
        out = sqlrun.mapping(self.con, {"tx_id": 1, "statements": ["SELECT tx_id FROM alert_rule WHERE rule_pep = 1"]})
        self.assertEqual(out["rows"], [[{"tx_id": 1}]])

    def test_a_statement_that_names_the_label_is_refused(self):
        with self.assertRaises(ValueError):
            sqlrun.mapping(self.con, {"tx_id": 1, "statements": ["SELECT tx_id, label FROM alert_rule"]})

    def test_only_a_single_select_is_run(self):
        for sql in ("DROP TABLE alert_rule", "SELECT 1; DROP TABLE alert_rule"):
            with self.assertRaises(ValueError):
                sqlrun.mapping(self.con, {"tx_id": 1, "statements": [sql]})


if __name__ == "__main__":
    unittest.main()
