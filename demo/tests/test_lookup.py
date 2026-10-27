"""Acceptance tests for milestone M1. Run from the demo/ directory:

    ../.venv/bin/python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amldemo import config, lookup, ontology  # noqa: E402


class OntologyTests(unittest.TestCase):
    def test_version_is_pinned(self):
        self.assertEqual(ontology.version(), "1.0-beta.4")

    def test_version_mismatch_is_detected(self):
        with mock.patch.object(config, "AMLTRIX_VERSION", "9.9"):
            with self.assertRaises(ontology.VersionMismatch):
                ontology.check_version(ontology.load_graph())

    def test_graph_is_loaded_once(self):
        self.assertIs(ontology.load_graph(), ontology.load_graph())


class LookupTests(unittest.TestCase):
    def test_t0039_has_nine_indicators(self):
        t = lookup.get_technique("T0039")
        self.assertEqual(t["name"], "Circular Transactions")
        self.assertEqual(t["version"], "1.0-beta.4")
        self.assertEqual(t["indicator_count"], 9)
        indicators = lookup.list_indicators("T0039")
        self.assertEqual([i["id"] for i in indicators], [f"IND0219{n}" for n in range(1, 10)])
        self.assertTrue(indicators[0]["text"].startswith("Cyclical patterns in funds"))
        self.assertTrue(all(i["version"] == "1.0-beta.4" for i in indicators))

    def test_t0011_counts(self):
        t = lookup.get_technique("T0011")
        self.assertEqual(len(t["sub_techniques"]), 3)
        self.assertEqual(len(lookup.list_indicators("T0011")), 9)
        self.assertEqual(len(lookup.mitigations_for("T0011")), 8)
        self.assertEqual(len(lookup.data_sources_for("T0011")), 5)

    def test_notes_come_from_link_nodes(self):
        for item in lookup.mitigations_for("T0016") + lookup.data_sources_for("T0016"):
            self.assertTrue(item["note"], f"{item['id']} has no note")
        self.assertIn("M0004", [m["id"] for m in lookup.mitigations_for("T0016")])

    def test_tactics_follow_the_stored_direction(self):
        names = [t["name"] for t in lookup.get_technique("T0016")["tactics"]]
        self.assertEqual(names, ["Placement", "Layering", "Integration"])  # ordered by tactic id, i.e. by laundering stage

    def test_sub_technique(self):
        t = lookup.get_technique("T0016.001")
        self.assertEqual((t["kind"], t["parent"]), ("subtechnique", "T0016"))
        self.assertEqual(lookup.get_technique("T0016")["sub_techniques"], [f"T0016.00{n}" for n in range(1, 6)])

    def test_duplicate_id_is_ambiguous(self):
        with self.assertRaises(lookup.AmbiguousTechnique) as ctx:
            lookup.get_technique("T0098")
        self.assertIn("T0098-55728728", str(ctx.exception))
        self.assertIn("T0098-608080a4", str(ctx.exception))
        self.assertEqual(lookup.get_technique("T0098-55728728")["id"], "T0098")

    def test_unknown_technique(self):
        with self.assertRaises(lookup.UnknownTechnique):
            lookup.get_technique("T9999")

    def test_an_indicator_belongs_to_one_technique(self):
        ids = [i["id"] for t in ("T0039", "T0011", "T0016") for i in lookup.list_indicators(t)]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
