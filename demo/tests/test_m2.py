"""Acceptance tests for milestone M2 (scenarios S1 and S2). Run from the demo/ directory:

    ../.venv/bin/python -m unittest discover -s tests -v

The valid samples must pass, and every deliberately broken variant must be caught by the layer that owns the problem.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rdflib import RDF  # noqa: E402

from amldemo import adapters, config, jsonld_build, ontology, validate  # noqa: E402

ALERT = json.loads((config.SAMPLES_DIR / "alert_source.json").read_text())
CASE = json.loads((config.SAMPLES_DIR / "case_source.json").read_text())


def alert_report(src):
    doc = jsonld_build.attach_context(adapters.alert_doc(src), jsonld_build.load_context("context_alert.jsonld"))
    return validate.validate_doc(doc)


def case_report(src):
    doc = jsonld_build.attach_context(adapters.case_doc(src), jsonld_build.load_context("context_case.jsonld"))
    return validate.validate_doc(doc)


def edited(src, change):
    clone = copy.deepcopy(src)
    change(clone)
    return clone


def mentions(issues, text):
    return any(text in issue for issue in issues)


class ValidSamples(unittest.TestCase):
    def test_alert_sample_is_valid(self):
        report = alert_report(ALERT)
        self.assertTrue(report.ok, report.summary())

    def test_case_sample_is_valid(self):
        report = case_report(CASE)
        self.assertTrue(report.ok, report.summary())

    def test_alert_points_into_the_dictionary(self):
        doc = jsonld_build.attach_context(adapters.alert_doc(ALERT), jsonld_build.load_context("context_alert.jsonld"))
        graph = jsonld_build.to_graph(doc)
        alert = ontology.DATA["alert/ALT-1001"]
        self.assertIn((alert, ontology.INV.suspectedTechnique, ontology.AMX.T0039), graph)
        self.assertIn((alert, RDF.type, ontology.INV.Alert), graph)
        items = list(graph.subjects(RDF.type, ontology.INV.ChecklistItem))
        self.assertEqual(len(items), 3)

    def test_paragraph_order_is_kept(self):
        doc = jsonld_build.attach_context(adapters.case_doc(CASE), jsonld_build.load_context("context_case.jsonld"))
        graph = jsonld_build.to_graph(doc)
        head = graph.value(ontology.DATA["report/RD-0007"], ontology.INV.paragraphs)
        from rdflib.collection import Collection
        first, second = [graph.value(p, ontology.INV.basedOn) for p in Collection(graph, head)]
        self.assertEqual((first, second), (ontology.DATA["finding/F-1"], ontology.DATA["finding/F-2"]))

    def test_validation_does_not_change_the_dictionary(self):
        before = len(ontology.load_graph())
        alert_report(ALERT)
        self.assertEqual(len(ontology.load_graph()), before)


class BrokenAlerts(unittest.TestCase):
    def test_invalid_json_text(self):
        report = validate.validate_text('{"@context": {')
        self.assertTrue(report.syntax)

    def test_unknown_technique_is_caught_as_an_undefined_iri(self):
        report = alert_report(edited(ALERT, lambda a: a.update(suspected_technique="T9999")))
        self.assertTrue(mentions(report.iris, "T9999"), report.summary())

    def test_unknown_indicator_is_caught_as_an_undefined_iri(self):
        report = alert_report(edited(ALERT, lambda a: a["checklist"][0].update(indicator="IND99999")))
        self.assertTrue(mentions(report.iris, "IND99999"), report.summary())

    def test_unmapped_field_is_reported_not_silently_dropped(self):
        report = alert_report(edited(ALERT, lambda a: a.update(risk_score=7)))
        self.assertTrue(mentions(report.unmapped, "risk_score"), report.summary())

    def test_missing_alert_id(self):
        report = alert_report(edited(ALERT, lambda a: a.pop("alert_id")))
        self.assertTrue(mentions(report.shacl, "alert id"), report.summary())

    def test_missing_suspected_technique(self):
        report = alert_report(edited(ALERT, lambda a: a.pop("suspected_technique")))
        self.assertTrue(mentions(report.shacl, "suspected technique"), report.summary())

    def test_badly_typed_timestamp(self):
        report = alert_report(edited(ALERT, lambda a: a.update(raised_at="yesterday afternoon")))
        self.assertTrue(report.shacl, report.summary())

    def test_can_assess_now_needs_evidence(self):
        report = alert_report(edited(ALERT, lambda a: a["checklist"][0].pop("check_with")))
        self.assertTrue(mentions(report.shacl, "must name the evidence"), report.summary())

    def test_needs_more_data_must_say_what(self):
        def change(a):
            a["checklist"][1].pop("needs_record_type")
            a["checklist"][1].pop("needs_record_note")
        report = alert_report(edited(ALERT, change))
        self.assertTrue(mentions(report.shacl, "must say which records are needed"), report.summary())

    def test_assessability_has_a_fixed_vocabulary(self):
        report = alert_report(edited(ALERT, lambda a: a["checklist"][0].update(assessability="maybe")))
        self.assertTrue(mentions(report.shacl, "assessability must be"), report.summary())

    def test_indicator_of_another_technique(self):
        # IND01341 is a real indicator, but of Structuring (T0016), not of the suspected T0039
        report = alert_report(edited(ALERT, lambda a: a["checklist"][0].update(indicator="IND01341")))
        self.assertTrue(report.iris == [] and mentions(report.consistency, "does not belong to the alert's suspected technique"), report.summary())

    def test_evidence_that_is_not_part_of_the_alert(self):
        report = alert_report(edited(ALERT, lambda a: a["checklist"][0].update(check_with="EV-OTHER")))
        self.assertTrue(report.shacl or report.consistency, report.summary())

    def test_unusable_identifier_is_refused_by_the_adapter(self):
        with self.assertRaises(adapters.SourceError):
            adapters.alert_doc(edited(ALERT, lambda a: a.update(suspected_technique="T 0039")))


class BrokenCases(unittest.TestCase):
    def test_supported_finding_without_evidence(self):
        report = case_report(edited(CASE, lambda c: c["findings"][0].pop("supported_by")))
        self.assertTrue(mentions(report.shacl, "must cite the evidence"), report.summary())

    def test_status_has_a_fixed_vocabulary(self):
        report = case_report(edited(CASE, lambda c: c["findings"][1].update(status="probably")))
        self.assertTrue(mentions(report.shacl, "status must be"), report.summary())

    def test_finding_indicator_of_another_technique(self):
        report = case_report(edited(CASE, lambda c: c["findings"][0].update(indicator="IND01341")))
        self.assertTrue(mentions(report.consistency, "finding's indicator does not belong"), report.summary())

    def test_finding_under_a_technique_the_case_is_not_investigating(self):
        def change(c):
            c["findings"][0].update(technique="T0016", indicator="IND01341")
        report = case_report(edited(CASE, change))
        self.assertTrue(mentions(report.consistency, "the case is not investigating"), report.summary())

    def test_paragraph_resting_on_a_finding_that_does_not_exist(self):
        report = case_report(edited(CASE, lambda c: c["report_draft"]["paragraphs"][0].update(based_on=["F-99"])))
        self.assertTrue(report.shacl or report.consistency, report.summary())

    def test_paragraph_without_a_source(self):
        report = case_report(edited(CASE, lambda c: c["report_draft"]["paragraphs"][0].pop("based_on")))
        self.assertTrue(mentions(report.shacl, "based on at least one finding"), report.summary())

    def test_report_without_review_status(self):
        report = case_report(edited(CASE, lambda c: c["report_draft"].pop("review_status")))
        self.assertTrue(mentions(report.shacl, "review status"), report.summary())

    def test_case_without_hypothesis(self):
        report = case_report(edited(CASE, lambda c: c.pop("hypothesis")))
        self.assertTrue(mentions(report.shacl, "hypothesis"), report.summary())


if __name__ == "__main__":
    unittest.main()
