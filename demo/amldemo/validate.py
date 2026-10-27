"""Validation of a JSON-LD investigation document, in five separate layers.

1. syntax        the text is JSON
2. unmapped      every field has a term in the @context (JSON-LD silently drops fields that do not)
3. iris          every term and AMLTRIX individual the data uses is actually defined
4. shacl         the shape of the records (cardinality, datatypes, classes, allowed values)
5. consistency   links across records make sense (for example, an indicator belongs to the suspected technique)

None of this is OWL reasoning: JSON-LD only maps names to IRIs, SHACL only checks shapes, and no reasoner is run.
"""
import json
from dataclasses import dataclass, field

from pyshacl import validate as shacl_validate
from rdflib import Graph, Namespace, RDF, URIRef

from .jsonld_build import to_graph
from .ontology import AMLO, AMX, INV, defined_terms, load_graph, load_shapes, load_vocab

SH = Namespace("http://www.w3.org/ns/shacl#")

PREFIXES = """
PREFIX inv:  <https://example.org/investigation#>
PREFIX amlo: <https://example.org/amlo#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""

# Each query returns the offending rows. A technique's indicators may also sit on its sub-techniques.
CONSISTENCY_QUERIES = {
    "a checklist item's indicator does not belong to the alert's suspected technique": PREFIXES + """
        SELECT ?item ?ind WHERE {
          ?item a inv:ChecklistItem ; inv:forAlert ?alert ; inv:indicator ?ind .
          FILTER NOT EXISTS { ?alert inv:suspectedTechnique ?t .
            { ?t amlo:isIndicatedBy ?ind } UNION { ?sub skos:broader ?t . ?sub amlo:isIndicatedBy ?ind } } }""",
    "a checklist item suggests a data source that AMLTRIX does not list for the alert's suspected technique": PREFIXES + """
        SELECT ?item ?ds WHERE {
          ?item a inv:ChecklistItem ; inv:forAlert ?alert ; inv:suggestedDataSource ?ds .
          FILTER NOT EXISTS { ?alert inv:suspectedTechnique ?t .
            { { ?link amlo:technique ?t } UNION { ?sub skos:broader ?t . ?link amlo:technique ?sub } }
            ?link a amlo:DataSourceLink ; amlo:dataSource ?ds } }""",
    "a finding's indicator does not belong to the finding's technique": PREFIXES + """
        SELECT ?f ?ind WHERE {
          ?f a inv:Finding ; inv:technique ?t ; inv:indicator ?ind .
          FILTER NOT EXISTS { { ?t amlo:isIndicatedBy ?ind } UNION { ?sub skos:broader ?t . ?sub amlo:isIndicatedBy ?ind } } }""",
    "a finding is made under a technique the case is not investigating": PREFIXES + """
        SELECT ?f ?t WHERE {
          ?case inv:hasFinding ?f . ?f inv:technique ?t .
          FILTER NOT EXISTS { ?case inv:hypothesis ?h . ?t skos:broader? ?h } }""",
    "a report paragraph rests on a finding that is not part of the report's case": PREFIXES + """
        SELECT ?report ?f WHERE {
          ?report a inv:ReportDraft ; inv:forCase ?case ; inv:paragraphs/rdf:rest*/rdf:first ?p .
          ?p inv:basedOn ?f .
          FILTER NOT EXISTS { ?case inv:hasFinding ?f } }""",
}


@dataclass
class Report:
    syntax: list = field(default_factory=list)
    unmapped: list = field(default_factory=list)
    iris: list = field(default_factory=list)
    shacl: list = field(default_factory=list)
    consistency: list = field(default_factory=list)

    @property
    def ok(self):
        return not (self.syntax or self.unmapped or self.iris or self.shacl or self.consistency)

    def summary(self):
        lines = []
        for name in ("syntax", "unmapped", "iris", "shacl", "consistency"):
            issues = getattr(self, name)
            lines.append(f"  {name:12} {'ok' if not issues else str(len(issues)) + ' problem(s)'}")
            lines += [f"      - {i}" for i in issues]
        return "\n".join(lines)


def check_syntax(text):
    try:
        return json.loads(text), []
    except json.JSONDecodeError as e:
        return None, [f"not valid JSON: {e.msg} (line {e.lineno}, column {e.colno})"]


def unmapped_fields(doc):
    """Fields with no term in the @context. rdflib drops these without a word, so they must be found here."""
    context = doc.get("@context", {})
    found = []

    def walk(node, where):
        if isinstance(node, list):
            for item in node:
                walk(item, where)
        elif isinstance(node, dict):
            label = node.get("@id", where)
            for key, value in node.items():
                if not key.startswith("@") and key not in context:
                    found.append(f"field {key!r} in {label} has no term in the @context, so it would be dropped")
                walk(value, label)

    walk(doc.get("@graph", []), "document")
    return found


def check_iris(graph):
    dictionary = load_graph()
    known_inv = defined_terms(load_vocab())
    known_amlo = defined_terms(dictionary)
    problems = set()
    for s, p, o in graph:
        if p == RDF.type:
            terms = [("class", o)]
        elif p in (RDF.first, RDF.rest):
            terms = []
        else:
            terms = [("property", p)]
        for kind, term in terms:
            if str(term).startswith(str(INV)) and term not in known_inv:
                problems.add(f"{kind} {term} is not defined in the Investigation Ontology (Demo)")
            elif str(term).startswith(str(AMLO)) and term not in known_amlo:
                problems.add(f"{kind} {term} is not defined in AMLO")
            elif not str(term).startswith((str(INV), str(AMLO))):
                problems.add(f"{kind} {term} comes from an unexpected vocabulary")
        if isinstance(o, URIRef) and str(o).startswith(str(AMX)) and (o, RDF.type, None) not in dictionary:
            problems.add(f"{o} is not an AMLTRIX individual in release {_pinned()}")
    return sorted(problems)


def _pinned():
    from . import config
    return config.AMLTRIX_VERSION


def merged(graph):
    both = Graph()
    both += load_graph()
    both += graph
    return both


def check_shacl(both):
    _, results, _ = shacl_validate(both, shacl_graph=load_shapes(), ont_graph=load_vocab(), inference="none")
    issues = []
    for r in results.subjects(RDF.type, SH.ValidationResult):
        message = results.value(r, SH.resultMessage)
        focus = results.value(r, SH.focusNode)
        path = results.value(r, SH.resultPath)
        issues.append(f"{_short(focus)}{' / ' + _short(path) if path is not None else ''}: {message}")
    return sorted(issues)


def check_consistency(both):
    issues = []
    for description, query in CONSISTENCY_QUERIES.items():
        for row in both.query(query):
            issues.append(f"{description}: " + ", ".join(_short(v) for v in row))
    return issues


def _short(term):
    text = str(term)
    for prefix in (str(INV), str(AMLO), str(AMX), "https://example.org/investigation/data/"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def validate_doc(doc):
    report = Report()
    report.unmapped = unmapped_fields(doc)
    try:
        graph = to_graph(doc)
    except Exception as e:  # rdflib raises several exception types for invalid JSON-LD
        report.syntax.append(f"not valid JSON-LD: {e}")
        return report
    report.iris = check_iris(graph)
    both = merged(graph)
    report.shacl = check_shacl(both)
    report.consistency = check_consistency(both)
    return report


def validate_text(text):
    doc, errors = check_syntax(text)
    if errors:
        return Report(syntax=errors)
    return validate_doc(doc)
