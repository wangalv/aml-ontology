"""The R2RML mapping and the FinCrime data ontology of the payments table (demo/mapping/obda/), read for scenario 3.

This is an OBDA design, not an OBDA engine: nothing here executes the mapping. Scenario 3 gives a language model the ontology and the mapping, lets
it stand in for an engine such as Ontop, and uses this module to check the model's work against them: which ontology terms a query uses, and which
columns of the table those terms stand for.
"""
import re

from rdflib import Graph, Namespace, RDF, RDFS

from . import config

OBDA_DIR = config.MAPPING_DIR / "obda"
FCD = "https://example.org/fincrime-data#"
RR = Namespace("http://www.w3.org/ns/r2rml#")
XSD = "http://www.w3.org/2001/XMLSchema#"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load():
    """(text of the ontology, text of the R2RML mapping, the ontology as a graph, the mapping as a graph)."""
    onto = (OBDA_DIR / "transaction_ontology.ttl").read_text(encoding="utf-8")
    r2rml = (OBDA_DIR / "txs.r2rml.ttl").read_text(encoding="utf-8")
    return onto, r2rml, Graph().parse(data=onto, format="turtle"), Graph().parse(data=r2rml, format="turtle")


def curie(uri):
    uri = str(uri)
    return "fcd:" + uri[len(FCD):] if uri.startswith(FCD) else "xsd:" + uri.replace(XSD, "")


def defined_terms(onto):
    """The classes and properties the ontology defines, as curies."""
    return {curie(s) for s in set(onto.subjects(RDF.type, None)) if str(s).startswith(FCD)}


def ontology_block(onto):
    """The ontology as plain text for a prompt: each class and property with what it means in words."""
    def comment(term):
        return str(onto.value(term, RDFS.comment) or "")
    classes = sorted(s for s in set(onto.subjects(RDF.type, None)) if str(s).startswith(FCD) and (s, RDFS.domain, None) not in onto)
    props = sorted(s for s in set(onto.subjects(RDFS.domain, None)))
    lines = ["Prefix: fcd = <" + FCD + ">", "Classes:"]
    lines += [f"{curie(c)}: {comment(c)}" for c in classes]
    lines.append("Properties:")
    for p in props:
        lines.append(f"{curie(p)} ({curie(onto.value(p, RDFS.domain))} -> {curie(onto.value(p, RDFS.range))}): {comment(p)}")
    return "<ontology>\n" + "\n".join(lines) + "\n</ontology>"


def _source_columns(name, sql, columns):
    """The table columns a name in the mapping stands for: the column itself, or the columns behind an alias in the SQL."""
    if name in columns:
        return [name]
    found = set()
    for m in re.finditer(r"(CASE\b.*?\bEND|\w+)\s+AS\s+" + re.escape(name) + r"\b", sql, re.S):
        found |= {c for c in columns if re.search(r"\b%s\b" % c, m.group(1))}
    return sorted(found, key=list(columns).index)


def term_columns(r2rml, columns):
    """{curie of a class or property: [columns of the table it is built from]}, read from the mapping. `columns` lists the table's columns in order."""
    out = {}
    for tm in r2rml.subjects(RDF.type, RR.TriplesMap):
        sql = str(r2rml.value(r2rml.value(tm, RR.logicalTable), RR.sqlQuery))
        subject = r2rml.value(tm, RR.subjectMap)
        out[curie(r2rml.value(subject, RR["class"]))] = _source_columns(PLACEHOLDER.search(str(r2rml.value(subject, RR.template))).group(1), sql, columns)
        for pom in r2rml.objects(tm, RR.predicateObjectMap):
            om = r2rml.value(pom, RR.objectMap)
            column, template = r2rml.value(om, RR.column), r2rml.value(om, RR.template)
            name = str(column) if column is not None else PLACEHOLDER.search(str(template)).group(1)
            out[curie(r2rml.value(pom, RR.predicate))] = _source_columns(name, sql, columns)
    return out
