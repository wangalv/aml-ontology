"""The checks of amldemo/claims.py: sentences that claim more than the text they rest on says."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amldemo import claims
from amldemo.scenarios import s4_reason

RULE = ("Rule engine: rule_high_risk_country fired. What this rule detects: Payment currency is Ruble or Mexican Peso, used as a jurisdiction proxy "
        "because the dataset has no country field.")
GRAPH = "Transaction graph: this payment closes a verified time-ordered cycle of 3 payments that returns to the originating account."


class UnstatedPlace(unittest.TestCase):
    def test_a_claim_of_cross_border_transfers_the_evidence_never_mentions_is_caught(self):
        reason = "The evidence shows frequent cross-border inter-bank transfers involving convoluted routing paths."
        self.assertTrue(claims.unstated_place(reason, GRAPH))

    def test_the_word_the_evidence_itself_uses_is_fine(self):
        self.assertEqual(claims.unstated_place("The rule engine uses the Ruble as a jurisdiction proxy, which the evidence states.", RULE), [])

    def test_a_suggestion_of_where_to_look_is_not_an_assertion(self):
        self.assertEqual(claims.unstated_place("Cross-border routing records would show whether the path is unusual.", GRAPH), [])

    def test_multiple_jurisdictions_needs_the_evidence_to_say_so(self):
        self.assertTrue(claims.unstated_place("The alert indicates transfers between different accounts and multiple jurisdictions.", RULE))


class AddedUp(unittest.TestCase):
    def test_totalling_amounts_is_caught(self):
        self.assertTrue(claims.added_up("The amounts were 1.00, 2.00 and 3.00, totaling a significant sum that reverted to the initial account.", GRAPH))

    def test_listing_amounts_separately_is_fine(self):
        self.assertEqual(claims.added_up("The three payments were 68,647.24, 100,578.47 and 196,999.50, and they form a closed path between accounts.", GRAPH), [])

    def test_a_word_the_source_uses_is_fine(self):
        self.assertEqual(claims.added_up("The total is stated.", "the finding gives a total of 5"), [])


class AdmittedAbsence(unittest.TestCase):
    def test_a_reason_that_says_the_evidence_does_not_show_it_is_caught(self):
        self.assertTrue(claims.admitted_absence("The currency is Ruble, though specific invoicing discrepancies are not shown."))

    def test_does_not_clearly_demonstrate_and_cannot_establish_are_caught(self):
        self.assertTrue(claims.admitted_absence("the 6.92-day span does not clearly demonstrate the rapid movement"))
        self.assertTrue(claims.admitted_absence("though the data cannot establish that the accounts are related"))

    def test_cannot_by_itself_establish_and_not_clearly_are_caught(self):
        self.assertTrue(claims.admitted_absence("a single closed cycle cannot by itself establish repeated cycling"))
        self.assertTrue(claims.admitted_absence("though the multi-day gaps between legs are not clearly rapid"))

    def test_a_plain_reason_is_fine(self):
        self.assertEqual(claims.admitted_absence("An inflow was followed within 3 days by an outflow of at least 85% of it."), [])


class ProxyForPlace(unittest.TestCase):
    def test_a_place_indicator_supported_only_by_a_proxy_is_caught(self):
        self.assertTrue(claims.proxy_for_place("Multiple cross-border transactions with sanctioned or high-risk jurisdictions.", [RULE]))

    def test_an_indicator_that_is_not_about_places_is_fine(self):
        self.assertEqual(claims.proxy_for_place("An inflow followed by a rapid outflow.", [RULE]), [])

    def test_evidence_that_is_not_a_proxy_is_fine(self):
        self.assertEqual(claims.proxy_for_place("Cross-border transfers.", [GRAPH]), [])


class DropUnsupportedMatches(unittest.TestCase):
    EVIDENCE = [{"id": "E1", "kind": "graph", "text": GRAPH}, {"id": "E2", "kind": "rule", "text": RULE}]

    def drop(self, support, reason, indicator="IND1", evidence=("E1",), texts=None):
        reply = {"matches": [{"indicator": indicator, "support": support, "evidence": list(evidence), "reason": reason}]}
        return s4_reason.drop_unsupported(reply, self.EVIDENCE, texts or {})

    def test_a_partly_that_says_what_is_missing_is_kept(self):
        kept, dropped = self.drop("partly", "E1 shows a cycle over 6.92 days, though the gaps between legs are not clearly rapid.")
        self.assertEqual((len(kept["matches"]), dropped), (1, []))

    def test_a_yes_that_says_the_evidence_does_not_show_it_is_dropped(self):
        kept, dropped = self.drop("yes", "E1 shows a cycle, though the rapid movement is not shown.")
        self.assertEqual((kept["matches"], len(dropped)), ([], 1))

    def test_a_place_indicator_supported_only_by_a_proxy_is_dropped_even_when_partly(self):
        kept, dropped = self.drop("partly", "The currency is a proxy for a jurisdiction.", "IND2", ("E2",), {"IND2": "Transfers to high-risk jurisdictions."})
        self.assertEqual((kept["matches"], len(dropped)), ([], 1))

    def test_a_claim_about_cross_border_transfers_the_evidence_does_not_mention_is_dropped(self):
        kept, dropped = self.drop("yes", "The evidence shows frequent cross-border inter-bank transfers.")
        self.assertEqual((kept["matches"], len(dropped)), ([], 1))


if __name__ == "__main__":
    unittest.main()
