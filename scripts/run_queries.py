"""Competency questions for the AMLTRIX ontology, answered with SPARQL.

Run:  .venv/bin/python scripts/run_queries.py
"""
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent
g = Graph().parse(ROOT / "data" / "amltrix.ttl")

PREFIXES = """
PREFIX amlo: <https://example.org/amlo#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dct:  <http://purl.org/dc/terms/>
PREFIX amx:  <https://example.org/amltrix/>
"""

QUERIES = [
    ("Q1. How many techniques and sub-techniques serve each tactic?",
     """SELECT ?tactic (COUNT(DISTINCT ?t) AS ?n) WHERE {
          ?tac a amlo:Tactic ; skos:prefLabel ?tactic ; amlo:isAchievedBy ?t .
        } GROUP BY ?tactic ORDER BY DESC(?n)"""),

    ("Q2. Which techniques serve more than one tactic, and which tactics? (first 6)",
     """SELECT ?id ?name (GROUP_CONCAT(DISTINCT ?tactic; separator=", ") AS ?tactics) WHERE {
          ?t skos:notation ?id ; skos:prefLabel ?name . ?tac amlo:isAchievedBy ?t .
          ?tac skos:prefLabel ?tactic .
        } GROUP BY ?id ?name HAVING (COUNT(DISTINCT ?tac) > 1) ORDER BY ?id LIMIT 6"""),

    ("Q3. Which sub-techniques sit in a tactic that their parent does NOT? (count)",
     """SELECT (COUNT(DISTINCT ?sub) AS ?n) WHERE {
          ?sub a amlo:SubTechnique ; skos:broader ?parent . ?tac amlo:isAchievedBy ?sub .
          FILTER NOT EXISTS { ?tac amlo:isAchievedBy ?parent }
        }"""),

    ("Q4. Which data sources can reveal the most techniques? (top 5)",
     """SELECT ?source (COUNT(DISTINCT ?t) AS ?techniques) WHERE {
          ?ds a amlo:DataSource ; skos:prefLabel ?source .
          ?t amlo:isIdentifiedIn ?ds .
        } GROUP BY ?source ORDER BY DESC(?techniques) LIMIT 5"""),

    ("Q5. For 'Hawala' (T0013.004): its parent, tactics, and the first 2 mitigations with their context text",
     """SELECT ?parentName ?tactic ?mitigation (SUBSTR(?text, 1, 140) AS ?advice) WHERE {
          amx:T0013.004 skos:broader ?p . ?p skos:prefLabel ?parentName .
          ?tac amlo:isAchievedBy amx:T0013.004 ; skos:prefLabel ?tactic .
          ?l a amlo:MitigationLink ; amlo:technique amx:T0013.004 ; amlo:mitigation ?m ; dct:description ?text .
          ?m skos:prefLabel ?mitigation .
        } LIMIT 2"""),

    ("Q6. Which techniques have indicators mentioning 'round-trip', 'circular' or 'funnel'? (techniques, count of matching indicators)",
     """SELECT ?id ?name (COUNT(?i) AS ?matches) WHERE {
          ?t skos:notation ?id ; skos:prefLabel ?name ; amlo:isIndicatedBy ?i .
          ?i skos:definition ?d .
          FILTER regex(?d, "round[- ]trip|circular|funnel", "i")
        } GROUP BY ?id ?name ORDER BY DESC(?matches) LIMIT 8"""),

    ("Q7. Data-quality: IDs that map to more than one technique",
     """SELECT ?id (GROUP_CONCAT(?name; separator=" | ") AS ?names) WHERE {
          ?t a amlo:Technique ; skos:notation ?id ; skos:prefLabel ?name .
        } GROUP BY ?id HAVING (COUNT(?t) > 1)"""),
]

for title, q in QUERIES:
    print(f"\n{title}")
    res = g.query(PREFIXES + q)
    cols = [str(v) for v in res.vars]
    print("  " + " | ".join(cols))
    for row in res:
        print("  " + " | ".join(str(x) for x in row))
