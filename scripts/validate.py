"""Validate data/amltrix.ttl against shapes/amlo-shapes.ttl, then prove the
shapes actually bite by validating deliberately broken copies.

Run:  .venv/bin/python scripts/validate.py
"""
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, SKOS

ROOT = Path(__file__).resolve().parent.parent
AMLO = Namespace("https://example.org/amlo#")
AMX = Namespace("https://example.org/amltrix/")

data = Graph().parse(ROOT / "data" / "amltrix.ttl")
shapes = Graph().parse(ROOT / "shapes" / "amlo-shapes.ttl")
onto = Graph().parse(ROOT / "ontology" / "amlo.ttl")


def run(g):
    conforms, _, report_text = validate(g, shacl_graph=shapes, ont_graph=onto, inference="none")
    return conforms, report_text


ok, report = run(data)
print("REAL DATA conforms:", ok)
if not ok:
    print(report[:3000])

# Negative tests: each mutation must be caught.
def mutate(name, fn):
    g = Graph()
    for t in data:
        g.add(t)
    fn(g)
    ok, _ = run(g)
    print(f"  {name:55} -> {'MISSED (bad)' if ok else 'caught'}")

print("NEGATIVE TESTS")
sub = next(data.subjects(RDF.type, AMLO.SubTechnique))
tech = next(data.subjects(RDF.type, AMLO.Technique))
orphan = AMX["T9999"]
mutate("sub-technique loses its parent", lambda g: g.remove((sub, SKOS.broader, None)))
mutate("sub-technique gets a second parent", lambda g: g.add((sub, SKOS.broader, tech)))
mutate("technique with malformed ID", lambda g: g.set((tech, SKOS.notation, Literal("X1"))))
def new_tech(g):
    g.add((orphan, RDF.type, AMLO.Technique))
    g.add((orphan, SKOS.prefLabel, Literal("Orphan", lang="en")))
    g.add((orphan, SKOS.notation, Literal("T9999")))
    g.add((orphan, AMLO.stixId, Literal("x")))
mutate("technique with no tactic/indicator/mitigation", new_tech)
mutate("indicator shared by two techniques",
       lambda g: g.add((tech, AMLO.isIndicatedBy, next(data.subjects(RDF.type, AMLO.Indicator)))) )
mutate("link without a technique", lambda g: g.remove((next(data.subjects(RDF.type, AMLO.MitigationLink)), AMLO.technique, None)))
