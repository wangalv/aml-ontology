"""Tests for scenario 4 (why did the monitoring systems alert on this payment). Run from the demo/ directory:

    ../.venv/bin/python -m unittest discover -s tests -v

No test calls a real model or opens the real database: a fake model returns the text a test needs.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amldemo.scenarios import s4_reason  # noqa: E402

SOURCES = s4_reason.load_sources()
PAYMENT = {
    "tx_id": 77, "ts": "2022-09-10 15:19:00", "amount": 196999.5, "from": "A1", "to": "B2", "sources": ["rule", "ml", "graph"],
    "rule_flags": ["rule_money_mule"], "ml_proba": 0.695, "cross_currency": False, "self_transfer": False, "same_bank": False,
    "currency": "Ruble", "format": "ACH",
    "cycle": {"accounts": ["B2", "C3", "A1", "B2"], "span_days": 6.92,
              "legs": [{"tx_id": 1, "ts": "2022-09-03 17:09:00", "from": "B2", "to": "C3", "amount": 68647.24},
                       {"tx_id": 2, "ts": "2022-09-08 15:50:00", "from": "C3", "to": "A1", "amount": 100578.47},
                       {"tx_id": 77, "ts": "2022-09-10 15:19:00", "from": "A1", "to": "B2", "amount": 196999.5}]}}
EVIDENCE = s4_reason.evidence_of(PAYMENT, SOURCES)
TECHNIQUES = s4_reason.techniques_of(PAYMENT, SOURCES)
INDICATORS = {i["id"] for t in TECHNIQUES.values() for i in t["indicators"]}
CYCLE_IND = "IND02191"   # a T0039 indicator
KIND = {e["id"]: e["kind"] for e in EVIDENCE}
E_RULE = next(e["id"] for e in EVIDENCE if e["kind"] == "rule")
E_GRAPH = next(e["id"] for e in EVIDENCE if e["kind"] == "graph")


def note(**changes):
    base = {"summary": "A pass-through and a cycle.",
            "matches": [{"indicator": CYCLE_IND, "support": "yes", "evidence": [E_GRAPH], "reason": "The payment closes a cycle of 3 payments over 6.92 days."}],
            "not_shown": "Documents are not in this data."}
    return {**base, **changes}


def match(**changes):
    return note(matches=[{**note()["matches"][0], **changes}])


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user, task):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)


class EvidenceTests(unittest.TestCase):
    def test_evidence_has_one_item_per_rule_flag_the_score_the_cycle_and_the_payment(self):
        self.assertEqual([e["kind"] for e in EVIDENCE], ["rule", "ml", "graph", "payment"])
        self.assertEqual([e["id"] for e in EVIDENCE], ["E1", "E2", "E3", "E4"])

    def test_the_rule_evidence_carries_the_rules_own_definition(self):
        self.assertIn("An inflow of at least $3,000", EVIDENCE[0]["text"])

    def test_the_graph_evidence_lists_the_legs_with_their_amounts(self):
        self.assertIn("100,578.47", EVIDENCE[2]["text"])
        self.assertIn("cycle of 3 payments", EVIDENCE[2]["text"])

    def test_techniques_follow_the_fired_flags_and_the_graph_check(self):
        self.assertIn("T0039", TECHNIQUES)
        self.assertIn("T0011", TECHNIQUES)
        self.assertIn(CYCLE_IND, INDICATORS)

    def test_the_prompt_lists_indicators_and_evidence_but_never_the_label(self):
        prompt = s4_reason.build_prompt(PAYMENT, TECHNIQUES, EVIDENCE).lower()
        self.assertIn(CYCLE_IND.lower(), prompt)
        self.assertIn("e3:", prompt)
        for word in ("label", "laundering", "suggest"):
            self.assertNotIn(word, prompt)


class NoteCheckTests(unittest.TestCase):
    def problems(self, reply):
        return s4_reason._problems_in(reply, EVIDENCE, INDICATORS, set(TECHNIQUES))

    def test_a_good_note_passes(self):
        self.assertEqual(self.problems(note()), [])

    def test_an_empty_list_of_matches_is_allowed(self):
        self.assertEqual(self.problems(note(matches=[])), [])

    def test_an_indicator_must_be_one_that_was_listed(self):
        self.assertTrue(any("IND99999" in p for p in self.problems(match(indicator="IND99999"))))

    def test_support_must_be_yes_or_partly(self):
        self.assertTrue(any("support must be" in p for p in self.problems(match(support="maybe"))))

    def test_a_match_must_cite_evidence_that_exists(self):
        self.assertTrue(any("cites no evidence" in p for p in self.problems(match(evidence=[]))))
        self.assertTrue(any("E9" in p for p in self.problems(match(evidence=["E9"]))))

    def test_numbers_must_appear_in_the_cited_evidence(self):
        self.assertTrue(any("number 9" in p for p in self.problems(match(reason="A cycle of 9 payments."))))
        self.assertTrue(any("number 4" in p for p in self.problems(match(reason="A cycle of four payments."))))
        self.assertEqual(self.problems(match(reason="It spans 6.92 days.")), [])

    def test_amounts_must_be_in_the_cited_evidence(self):
        self.assertTrue(any("$5,000" in p for p in self.problems(match(reason="It moved $5,000 back."))))
        self.assertEqual(self.problems(match(reason="The last leg was $196,999.50.")), [])

    def test_a_technique_must_be_one_that_was_listed(self):
        self.assertTrue(any("T0001" in p for p in self.problems(note(summary="Looks like T0001."))))
        self.assertEqual(self.problems(note(summary="Looks like T0039.")), [])

    def test_a_missing_field_or_too_many_matches_is_a_problem(self):
        self.assertTrue(any("not_shown" in p for p in self.problems({k: v for k, v in note().items() if k != "not_shown"})))
        many = note(matches=[{**note()["matches"][0], "indicator": i} for i in sorted(INDICATORS)[:s4_reason.MAX_MATCHES + 1]])
        self.assertTrue(any("more than" in p for p in self.problems(many)))

    def test_the_same_indicator_cannot_be_listed_twice(self):
        twice = note(matches=[note()["matches"][0]] * 2)
        self.assertTrue(any("repeats" in p for p in self.problems(twice)))


class ChainTests(unittest.TestCase):
    def listed(self):
        return list(TECHNIQUES.values())

    def test_a_match_names_the_technique_its_indicator_belongs_to(self):
        chain = s4_reason.chain_of(CYCLE_IND, [E_GRAPH], EVIDENCE, self.listed())
        self.assertEqual(chain["technique"]["id"], "T0039")
        self.assertEqual(chain["technique"]["links"][0]["flag"], "graph_roundtrip")
        self.assertTrue(chain["technique"]["links"][0]["basis"])

    def test_the_cited_evidence_is_linked_when_its_flag_points_to_that_technique(self):
        self.assertTrue(s4_reason.chain_of(CYCLE_IND, [E_GRAPH], EVIDENCE, self.listed())["linked"])
        self.assertFalse(s4_reason.chain_of(CYCLE_IND, [E_RULE], EVIDENCE, self.listed())["linked"])

    def test_an_indicator_of_no_listed_technique_has_no_chain(self):
        self.assertEqual(s4_reason.chain_of("IND99999", [E_RULE], EVIDENCE, self.listed()), {"technique": None, "linked": False})

    def test_evidence_saved_without_a_flag_is_read_from_its_text(self):
        old = [{k: v for k, v in e.items() if k != "flag"} for e in EVIDENCE]
        self.assertEqual([s4_reason.flag_of(e) for e in old], ["rule_money_mule", None, "graph_roundtrip", None])

    def test_the_note_carries_the_chain(self):
        result = s4_reason.explain(PAYMENT, FakeLLM(note()), SOURCES)
        m = result["note"]["matches"][0]
        self.assertEqual(m["technique"]["id"], "T0039")
        self.assertTrue(m["linked"])


MULE_IND = TECHNIQUES["T0011"]["indicators"][0]["id"]


def lane_note(indicator, evidence, support="yes", reason="It matches."):
    return note(matches=[{"indicator": indicator, "support": support, "evidence": evidence, "reason": reason}])


class LaneTests(unittest.TestCase):
    def run_lanes(self, *replies):
        llm = FakeLLM(*replies)
        return s4_reason.explain_lanes(PAYMENT, llm, SOURCES), llm

    def test_each_system_is_asked_on_its_own_and_the_ml_model_is_not_asked(self):
        result, llm = self.run_lanes(lane_note(MULE_IND, [E_RULE]), lane_note(CYCLE_IND, [E_GRAPH]))
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("evidence from the rule engine only", llm.prompts[0])
        self.assertIn("evidence from the transaction graph only", llm.prompts[1])
        self.assertNotIn("E3:", llm.prompts[0])       # the graph's evidence is not in the rule engine's request
        self.assertNotIn("E1:", llm.prompts[1])
        self.assertIsNone(result["lanes"]["ml"]["note"])
        self.assertIn("names no reason", result["lanes"]["ml"]["skipped"])

    def test_a_system_that_did_not_alert_is_not_asked(self):
        payment = {**PAYMENT, "sources": ["rule"], "cycle": None}
        llm = FakeLLM(lane_note(MULE_IND, ["E1"]))
        result = s4_reason.explain_lanes(payment, llm, SOURCES)
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(result["lanes"]["graph"]["skipped"], "This system did not alert on the payment.")

    def test_lamps_say_which_systems_support_which_technique(self):
        result, _ = self.run_lanes(lane_note(MULE_IND, [E_RULE]), lane_note(MULE_IND, [E_GRAPH], support="partly"))
        row = next(r for r in s4_reason.lamps(result) if r["id"] == "T0011")
        self.assertEqual([row["cells"][k]["state"] for k in ("rule", "ml", "graph")], ["yes", "n/a", "partly"])
        self.assertEqual(row["systems"], ["rule", "graph"])
        self.assertTrue(row["cells"]["rule"]["pointed"])
        self.assertFalse(row["cells"]["graph"]["pointed"])       # the graph flag does not point to T0011: this is the model's reading

    def test_a_technique_no_system_supports_has_no_lit_lamp(self):
        result, _ = self.run_lanes(lane_note(MULE_IND, [E_RULE]), lane_note(CYCLE_IND, [E_GRAPH]))
        row = next(r for r in s4_reason.lamps(result) if r["id"] == "T0083")
        self.assertEqual(row["systems"], [])
        self.assertEqual(row["cells"]["rule"]["state"], "no")

    def test_a_refused_lane_is_not_lit_and_the_others_are_unaffected(self):
        bad = lane_note("IND99999", [E_RULE])
        result, _ = self.run_lanes(bad, bad, lane_note(CYCLE_IND, [E_GRAPH]))
        self.assertIsNone(result["lanes"]["rule"]["note"])
        self.assertEqual(len(result["lanes"]["rule"]["attempts"]), s4_reason.MAX_ATTEMPTS)
        rows = {r["id"]: r for r in s4_reason.lamps(result)}
        self.assertEqual(rows["T0011"]["cells"]["rule"]["state"], "n/a")
        self.assertEqual(rows["T0039"]["cells"]["graph"]["state"], "yes")


class ExplainTests(unittest.TestCase):
    def test_an_accepted_note_says_which_systems_each_match_rests_on(self):
        reply = note(matches=[{"indicator": CYCLE_IND, "support": "yes", "evidence": [E_GRAPH, E_RULE], "reason": "A cycle."}])
        result = s4_reason.explain(PAYMENT, FakeLLM(reply), SOURCES)
        self.assertEqual(result["note"]["matches"][0]["systems"], ["rule", "graph"])
        self.assertEqual(len(result["attempts"]), 1)

    def test_only_the_notes_own_fields_are_kept(self):
        result = s4_reason.explain(PAYMENT, FakeLLM(note(verdict="laundering")), SOURCES)
        self.assertEqual(set(result["note"]), {"summary", "matches", "not_shown"})

    def test_a_refused_note_is_retried_once_with_the_reasons(self):
        llm = FakeLLM(match(indicator="IND99999"), note())
        result = s4_reason.explain(PAYMENT, llm, SOURCES)
        self.assertIsNotNone(result["note"])
        self.assertIn("not an indicator listed", llm.prompts[1])

    def test_a_note_that_still_fails_is_not_kept(self):
        result = s4_reason.explain(PAYMENT, FakeLLM("not json", match(indicator="IND99999")), SOURCES)
        self.assertIsNone(result["note"])
        self.assertEqual(len(result["attempts"]), s4_reason.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
