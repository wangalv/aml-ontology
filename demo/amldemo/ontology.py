"""Load the AMLO schema and the AMLTRIX data into one in-memory graph and check the pinned release.

The graph is a read-only copy of the Turtle files; nothing is written back.
"""
from functools import lru_cache

from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF, SKOS

from . import config

AMLO = Namespace("https://example.org/amlo#")
AMX = Namespace("https://example.org/amltrix/")
SCHEME = AMX["scheme/amltrix-ml"]
INV = Namespace("https://example.org/investigation#")
DATA = Namespace("https://example.org/investigation/data/")


class VersionMismatch(RuntimeError):
    pass


def check_version(g):
    pinned = config.AMLTRIX_VERSION
    schema_info = " ".join(str(o) for o in g.objects(None, OWL.versionInfo))
    scheme_label = str(g.value(SCHEME, SKOS.prefLabel) or "")
    for where, text in (("ontology/amlo.ttl (owl:versionInfo)", schema_info), ("data/amltrix.ttl (scheme label)", scheme_label)):
        if pinned not in text:
            raise VersionMismatch(f"{where} does not mention AMLTRIX {pinned}: {text!r}")


@lru_cache(maxsize=1)
def load_graph():
    g = Graph()
    g.parse(config.AMLO_TTL, format="turtle")
    g.parse(config.AMLTRIX_TTL, format="turtle")
    check_version(g)
    return g


def version():
    load_graph()
    return config.AMLTRIX_VERSION


@lru_cache(maxsize=1)
def load_vocab():
    return Graph().parse(config.INVESTIGATION_TTL, format="turtle")


@lru_cache(maxsize=1)
def load_shapes():
    return Graph().parse(config.INVESTIGATION_SHAPES, format="turtle")


def defined_terms(g):
    """Classes and properties a graph declares."""
    return {s for kind in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty) for s in g.subjects(RDF.type, kind)}
