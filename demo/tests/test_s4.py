"""Tests for scenario 4 (consolidating alerts into cases by account). Run from the demo/ directory:

    ../.venv/bin/python -m unittest discover -s tests -v

No test calls a real model. A fake model returns the text a test needs. The database actions of sqlrun.py are tried on a
tiny database built in a temporary file, so the grouping, the sampling and the judging are checked end to end.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb  # noqa: E402

from amldemo import config  # noqa: E402
from amldemo.scenarios import s4_cases  # noqa: E402

RUNNER = config.DEMO_DIR / "amldemo" / "sqlrun.py"
SOURCES = s4_cases.load_sources()


def alert(tx_id, role="received", amount=1000.0, sources=("rule",), flags=("rule_fan_in",), ml=0.5):
    return {"tx_id": tx_id, "ts": "2022-09-09 10:00:00", "amount": amount, "role": role, "other": "B", "sources": list(sources),
            "flags": list(flags), "ml_proba": ml}


def case(account="A", alerts=None, flags=None, n_sources=1, max_ml=0.5, link_class="account_only"):
    alerts = alerts if alerts is not None else [alert(1), alert(2, amount=500.0)]
    return {"links": {"class": link_class, "payments": {"all": 0, "rule+ml": 0, "rule+graph": 0, "ml+graph": 0, "two_or_more": 0},
                      "counterparties": {"total": 1, "rule+ml": 0, "rule+graph": 0, "ml+graph": 0, "all": 0}},
            "account": account, "n_alerts": len(alerts), "n_sources": n_sources, "sources": {"rule": len(alerts), "ml": 0, "graph": 0},
            "flags": flags if flags is not None else {"rule_fan_in": len(alerts)}, "max_ml": max_ml,
            "total_amount": sum(a["amount"] for a in alerts), "first": "2022-09-09 10:00:00", "last": "2022-09-09 11:00:00", "alerts": alerts}


def note(**changes):
    base = {"relation": "Only the rule engine alerted.",
            "by_source": {"rule": "Two fan-in alerts.", "ml": "No alert.", "graph": "no alert"}, "agreement": "single_source",
            "links": [{"fact": "L3", "text": "No payment was raised by two sources.", "alerts": [1, 2]}],
            "gaps": "Nothing on who B is."}
    return {**base, **changes}


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user, task):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)


class NoteCheckTests(unittest.TestCase):
    def problems(self, reply, c=None):
        c = c or case()
        return s4_cases._problems_in(reply, c, set(s4_cases.case_techniques(c, SOURCES)))

    def two_sources(self):
        c = case(n_sources=2)
        c["sources"] = {"rule": 2, "ml": 1, "graph": 0}
        c["links"]["payments"].update({"rule+ml": 1, "two_or_more": 1})
        said = note(by_source={"rule": "Fan-in.", "ml": "Scored high.", "graph": "no alert"}, agreement="partial")
        return c, said

    def test_a_good_note_passes(self):
        self.assertEqual(self.problems(note()), [])

    def test_a_link_must_cite_a_fact_that_was_given(self):
        self.assertTrue(any("L9" in p for p in self.problems(note(links=[{"fact": "L9", "text": "x"}]))))
        self.assertTrue(any("no links" in p for p in self.problems(note(links=[]))))

    def test_a_link_may_only_use_numbers_from_its_fact(self):
        c = case()
        c["links"]["payments"]["two_or_more"] = 7
        self.assertEqual(self.problems(note(links=[{"fact": "L3", "text": "Only 7 payments were shared.", "alerts": []}]), c), [])
        found = self.problems(note(links=[{"fact": "L3", "text": "Only 42 payments were shared.", "alerts": []}]), c)
        self.assertTrue(any("number 42" in p for p in found))

    def test_a_number_written_as_a_word_is_checked_too(self):
        c = case()
        c["links"]["payments"]["rule+ml"] = 1
        said = note(links=[{"fact": "L2", "text": "Two payments were raised by both the rule engine and the ML model.", "alerts": []}])
        self.assertTrue(any("number 2" in p for p in self.problems(said, c)))
        ok = note(links=[{"fact": "L2", "text": "One payment was raised by both, and zero by the rule engine and graph.", "alerts": []}])
        self.assertEqual(self.problems(ok, c), [])
        three = note(links=[{"fact": "L2", "text": "All three sources alerted on this account.", "alerts": []}])
        self.assertEqual(self.problems(three, c), [])

    def test_a_link_must_cite_alerts_of_the_case(self):
        found = self.problems(note(links=[{"fact": "L3", "text": "x", "alerts": [99]}]))
        self.assertTrue(any("not in the list shown" in p for p in found))
        self.assertTrue(any("whole numbers" in p for p in self.problems(note(links=[{"fact": "L3", "text": "x", "alerts": ["1"]}]))))

    def test_a_technique_must_be_one_the_case_was_given(self):
        c = case(flags={"rule_fan_in": 2})
        given = next(iter(s4_cases.case_techniques(c, SOURCES)))
        self.assertEqual(self.problems(note(relation=f"Looks like {given}."), c), [])
        self.assertTrue(any("T0039" in p for p in self.problems(note(relation="Looks like T0039."), c)))

    def test_an_amount_must_be_shown_or_summed(self):
        self.assertEqual(self.problems(note(relation="They total $1,500.00.")), [])
        self.assertEqual(self.problems(note(relation="About $1.5K came in.")), [])
        self.assertTrue(any("$9,999" in p for p in self.problems(note(relation="They total $9,999."))))

    def test_a_source_without_alerts_must_be_written_up_as_no_alert(self):
        said = note(by_source={"rule": "Fan-in.", "ml": "Scored high.", "graph": "no alert"})
        self.assertTrue(any("ml, which raised no alert" in p for p in self.problems(said)))
        said = note(by_source={"rule": "No alert.", "ml": "no alert", "graph": "no alert"})
        self.assertTrue(any("for rule, which raised 2 alert" in p for p in self.problems(said)))
        self.assertTrue(any("by_source needs" in p for p in self.problems(note(by_source={"rule": "x"}))))

    def test_single_source_is_used_exactly_when_one_source_alerted(self):
        self.assertTrue(any("single_source" in p for p in self.problems(note(agreement="agree"))))
        c, said = self.two_sources()
        self.assertEqual(self.problems(said, c), [])
        self.assertTrue(any("single_source" in p for p in self.problems({**said, "agreement": "single_source"}, c)))
        self.assertTrue(any("agreement must be" in p for p in self.problems({**said, "agreement": "mixed"}, c)))

    def test_a_missing_field_or_too_many_links_is_a_problem(self):
        self.assertTrue(any("gaps" in p for p in self.problems({k: v for k, v in note().items() if k != "gaps"})))
        many = note(links=[{"fact": "L3", "text": "x", "alerts": []}] * (s4_cases.MAX_LINKS + 1))
        self.assertTrue(any("more than" in p for p in self.problems(many)))


class LinkFactTests(unittest.TestCase):
    def test_the_facts_hold_the_numbers_code_computed(self):
        c = case(n_sources=3, link_class="same_payment", alerts=[alert(1, sources=("rule", "ml", "graph")), alert(2)])
        c["links"]["payments"].update({"all": 1, "rule+ml": 1, "rule+graph": 1, "ml+graph": 1, "two_or_more": 1})
        facts = {f["id"]: f["text"] for f in s4_cases.link_facts(c)}
        self.assertIn("all three sources: 1 (alerts shown: 1)", facts["L1"])
        self.assertIn("1 of 2 alerted payments", facts["L3"])
        self.assertIn("same_payment", facts["L5"])


class ConsultTests(unittest.TestCase):
    def test_an_accepted_note_keeps_only_its_fields(self):
        result = s4_cases.consult(case(), FakeLLM(note(extra="ignore me", merge_with="B")), SOURCES)
        self.assertEqual(set(result["note"]), {"relation", "by_source", "agreement", "links", "gaps"})
        self.assertEqual(len(result["attempts"]), 1)

    def test_a_refused_note_is_retried_once_with_the_reasons(self):
        llm = FakeLLM(note(agreement="mixed"), note())
        result = s4_cases.consult(case(), llm, SOURCES)
        self.assertEqual(result["note"]["agreement"], "single_source")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertIn("agreement must be one of", llm.prompts[1])

    def test_a_note_that_still_fails_is_not_kept(self):
        result = s4_cases.consult(case(), FakeLLM("not json at all", note(agreement="mixed")), SOURCES)
        self.assertIsNone(result["note"])
        self.assertEqual(len(result["attempts"]), s4_cases.MAX_ATTEMPTS)

    def test_a_reply_wrapped_in_a_code_fence_is_read(self):
        result = s4_cases.consult(case(), FakeLLM("```json\n" + json.dumps(note()) + "\n```"), SOURCES)
        self.assertIsNotNone(result["note"])

    def test_without_the_dictionary_no_technique_reaches_the_prompt_and_none_may_be_named(self):
        c = case(flags={"rule_fan_in": 2})
        withd, without = FakeLLM(note()), FakeLLM(note())
        s4_cases.consult(c, withd, SOURCES)
        result = s4_cases.consult(c, without, SOURCES, with_dictionary=False)
        self.assertIn("<techniques>", withd.prompts[0])
        self.assertNotIn("<techniques>", without.prompts[0])
        self.assertNotIn("T0", without.prompts[0])
        self.assertIn("do not name any technique", without.prompts[0])
        self.assertFalse(result["with_dictionary"])
        self.assertEqual(result["techniques"], [])
        named = FakeLLM(note(relation="Looks like T0011."), note(relation="Looks like T0011."))
        self.assertIsNone(s4_cases.consult(c, named, SOURCES, with_dictionary=False)["note"])

    def test_the_prompt_never_contains_the_label_or_a_route(self):
        llm = FakeLLM(note())
        s4_cases.consult(case(), llm, SOURCES)
        prompt = llm.prompts[0].lower()
        for word in ("label", "laundering", "baseline", "suggest"):
            self.assertNotIn(word, prompt)


class EvaluateTests(unittest.TestCase):
    def test_accounts_are_grouped_by_link_class_and_by_the_models_agreement(self):
        cases = [case("A", link_class="same_payment"), case("B", link_class="same_payment"), case("C", link_class="pairwise"),
                 case("D", link_class="pairwise")]
        labels = {"A": True, "B": False, "C": True, "D": False}
        notes = {"A": note(agreement="agree"), "B": note(agreement="agree"), "C": note(agreement="partial"), "D": None}
        e = s4_cases.evaluate(cases, notes, labels)
        self.assertEqual(e["notes"], {"accepted": 3, "not_accepted": 1})
        self.assertEqual(e["by_class"], {"pairwise": {"cases": 2, "laundering": 1}, "same_payment": {"cases": 2, "laundering": 1}})
        self.assertEqual(e["by_agreement"]["agree"], {"cases": 2, "laundering": 1})
        self.assertEqual(e["by_agreement"]["none"], {"cases": 1, "laundering": 0})
        self.assertEqual(e["class_by_agreement"]["pairwise | partial"], {"cases": 1, "laundering": 1})


class DatabaseActionTests(unittest.TestCase):
    """sqlrun.py on a small database: three accounts, A is alerted by two sources, B by one, C by three."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.dir.name) / "mini.duckdb")
        con = duckdb.connect(cls.path)
        # every column the runner's `txs` view selects, plus split, tail flag, label and round-trip flag
        con.execute("CREATE TABLE tx_features (tx_id BIGINT, ts TIMESTAMP, from_account VARCHAR, to_account VARCHAR, amount_log DOUBLE, "
                    "is_cross_currency INTEGER, is_self_transfer INTEGER, is_same_bank INTEGER, fmt_wire INTEGER, fmt_ach INTEGER, "
                    "fmt_cheque INTEGER, fmt_cash INTEGER, fmt_credit_card INTEGER, fmt_bitcoin INTEGER, fmt_reinvestment INTEGER, "
                    "split VARCHAR, is_tail_period BOOLEAN, label INTEGER, graph_roundtrip INTEGER)")
        columns = ("tx_id BIGINT, ts TIMESTAMP, amount DOUBLE, from_account VARCHAR, to_account VARCHAR, label INTEGER, "
                   "rule_structuring INTEGER, rule_money_mule INTEGER, rule_fan_in INTEGER, rule_pep INTEGER, "
                   "rule_high_risk_business INTEGER, rule_high_risk_country INTEGER, graph_roundtrip INTEGER, ml_proba DOUBLE")
        for table in ("alert_rule", "alert_ml", "alert_graph"):
            con.execute(f"CREATE TABLE {table} ({columns})")
        # tx 1: A -> B, laundering, all three sources. tx 2: A -> B, rule only. tx 3: C -> B in the tail, rule only (must be ignored).
        rows = [(1, "2022-09-09 10:00:00", 100.0, "A", "B", 1, 0, 1, 0, 0, 0, 0, 1, 0.9),
                (2, "2022-09-09 11:00:00", 50.0, "A", "B", 0, 0, 0, 1, 0, 0, 0, 0, 0.1),
                (3, "2022-09-18 11:00:00", 70.0, "C", "B", 0, 0, 0, 1, 0, 0, 0, 0, 0.1)]
        for r in rows:
            con.execute("INSERT INTO tx_features VALUES (?, ?, ?, ?, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'test', ?, ?, ?)",
                        [r[0], r[1], r[3], r[4], r[0] == 3, r[5], r[12]])
        con.executemany("INSERT INTO alert_rule VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO alert_ml VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows[:1])
        con.executemany("INSERT INTO alert_graph VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows[:1])
        con.close()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def call(self, request):
        done = subprocess.run([sys.executable, str(RUNNER)], input=json.dumps(request), capture_output=True, text=True,
                              env={**os.environ, "AML_DB": self.path})
        return json.loads(done.stdout)

    def test_population_counts_accounts_by_source_and_ignores_the_tail(self):
        p = self.call({"action": "population"})
        self.assertEqual(p["payments"]["alerted"], 2)
        self.assertEqual(p["accounts"], 2)
        self.assertEqual({t["sources"]: (t["accounts"], t["laundering"]) for t in p["by_sources"]}, {3: (2, 2)})
        self.assertEqual(p["linkage"]["by_class"], [{"sources": 3, "link": "same_payment", "accounts": 2, "laundering": 2}])
        all3 = next(f for f in p["linkage"]["facts"] if f["fact"] == "p_all")
        self.assertEqual((all3["present"], all3["absent"]), ({"accounts": 2, "laundering": 2}, {"accounts": 0, "laundering": 0}))

    def test_a_sample_has_the_alerts_of_each_account_and_never_the_label(self):
        out = self.call({"action": "sample", "seed": "x", "per_sources": {"3": 5}, "max_alerts": 5})
        self.assertEqual(sorted(c["account"] for c in out["cases"]), ["A", "B"])
        a = next(c for c in out["cases"] if c["account"] == "A")
        self.assertEqual(a["n_alerts"], 2)
        self.assertEqual(a["sources"], {"rule": 2, "ml": 1, "graph": 1})
        self.assertEqual([x["tx_id"] for x in a["alerts"]], [1, 2])
        self.assertEqual(a["alerts"][0]["sources"], ["rule", "ml", "graph"])
        self.assertNotIn("label", json.dumps(out))
        self.assertEqual(a["links"]["class"], "same_payment")
        self.assertEqual(a["links"]["payments"], {"all": 1, "rule+ml": 1, "rule+graph": 1, "ml+graph": 1, "two_or_more": 1})
        self.assertEqual(a["links"]["counterparties"], {"total": 1, "rule+ml": 1, "rule+graph": 1, "ml+graph": 1, "all": 1})

    def test_judge_says_which_accounts_hold_a_laundering_payment(self):
        out = self.call({"action": "judge", "accounts": ["A", "B"]})
        self.assertEqual(out["accounts"]["A"], {"laundering": True, "laundering_payments": 1})
        self.assertEqual(out["accounts"]["B"], {"laundering": True, "laundering_payments": 1})


if __name__ == "__main__":
    unittest.main()
