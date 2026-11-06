"""The alerts of one payment, read through the R2RML mapping of the three alert tables (demo/mapping/obda/alerts.r2rml.ttl) and the alert ontology.

This is the integration layer of scenario 4. It is not an OBDA engine such as Ontop: a small piece of code applies the mapping. For one
payment it runs the SQL of each TriplesMap on the database, restricted to that payment, fills the templates, and gets the triples the mapping
describes; a SPARQL question over those triples and the ontology then says which systems alerted, with which flags and score, and which AML
typology techniques each flag points to (and how strongly). What the agent is given comes from here, not from the alert tables directly.

What the mapping does not carry is the detail of a round trip: the amounts and times of its legs live in a JSON file of the graph analysis,
not in a table, so the agent's evidence adds them from there.
"""
import re

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from . import config, dbrun

OBDA_DIR = config.MAPPING_DIR / "obda"
FCD = Namespace("https://example.org/fincrime-data#")
AMX = "https://example.org/amltrix/"
RR = Namespace("http://www.w3.org/ns/r2rml#")
SYSTEMS = {"rule engine": "rule", "ML model": "ml", "transaction graph": "graph"}
LINKS = {FCD.strongLink: "strong", FCD.mediumLink: "medium", FCD.weakLink: "weak"}
PLACEHOLDER = re.compile(r"\{(\w+)\}")
QUESTION = """PREFIX fcd:  <https://example.org/fincrime-data#>
SELECT ?system ?flag ?technique ?score WHERE {{
  ?alert fcd:alertedTransaction <https://example.org/transaction/{tx}> ;
         fcd:sourceSystem ?system .
  OPTIONAL {{ ?alert fcd:firedFlag ?flag . ?flag fcd:strongLink|fcd:mediumLink ?technique }}
  OPTIONAL {{ ?alert fcd:mlScore ?score }}
}}"""


def load():
    """(the alert ontology, the R2RML mapping) as graphs."""
    return (Graph().parse(OBDA_DIR / "alert_ontology.ttl", format="turtle"), Graph().parse(OBDA_DIR / "alerts.r2rml.ttl", format="turtle"))


def read_maps(mapping):
    """Each TriplesMap of the mapping: its SQL, its subject template and its predicate-object maps."""
    maps = []
    for tm in mapping.subjects(RDF.type, RR.TriplesMap):
        subject = mapping.value(tm, RR.subjectMap)
        poms = []
        for pom in mapping.objects(tm, RR.predicateObjectMap):
            om, obj = mapping.value(pom, RR.objectMap), mapping.value(pom, RR.object)
            kind, value = (("object", obj) if obj is not None else
                           ("constant", mapping.value(om, RR.constant)) if mapping.value(om, RR.constant) is not None else
                           ("template", mapping.value(om, RR.template)) if mapping.value(om, RR.template) is not None else
                           ("column", mapping.value(om, RR.column)))
            poms.append({"predicate": mapping.value(pom, RR.predicate), "kind": kind, "value": value,
                         "datatype": mapping.value(om, RR.datatype) if om is not None else None})
        maps.append({"name": str(tm).rsplit("#", 1)[-1], "sql": str(mapping.value(mapping.value(tm, RR.logicalTable), RR.sqlQuery)),
                     "template": str(mapping.value(subject, RR.template)), "poms": poms})
    return maps


def materialise(maps, tx_id, rows_of=None):
    """The triples (as a graph) the mapping gives for one payment. rows_of(tx_id, statements) returns the rows of each statement; the default
    asks the database through dbrun."""
    answer = (rows_of or (lambda tx, sql: dbrun.mapping_rows(tx, sql)["rows"]))(tx_id, [m["sql"] for m in maps])
    fill = lambda template, row: PLACEHOLDER.sub(lambda g: str(row[g.group(1)]), str(template))
    graph = Graph()
    for tm, found in zip(maps, answer):
        for row in found:
            subject = URIRef(fill(tm["template"], row))
            for p in tm["poms"]:
                kind, value = p["kind"], p["value"]
                obj = (value if kind == "object" else
                       URIRef(fill(value, row)) if kind == "template" else
                       Literal(str(value)) if kind == "constant" else
                       Literal(row[str(value)], datatype=p["datatype"]))
                graph.add((subject, p["predicate"], obj))
    return graph


def alerts_of(tx_id, rows_of=None):
    """What the mapping and the ontology say about a payment:
    {"systems": {"rule": {"flags": [flag ids], ...}, "ml": {"score": ...}, "graph": {...}}, "flags": {flag id: {"label", "detects", "links": [{"id", "strength"}]}}}.
    Flag ids are the names the alert tables use (rule_money_mule, graph_roundtrip). Links are those of the ontology, weak ones included."""
    ontology, mapping = load()
    data = materialise(read_maps(mapping), tx_id, rows_of)
    rows = (data + ontology).query(QUESTION.format(tx=tx_id))
    systems = {}
    for system, flag, _technique, score in rows:
        entry = systems.setdefault(SYSTEMS[str(system)], {"flags": []})
        if flag is not None and flag_id(flag) not in entry["flags"]:
            entry["flags"].append(flag_id(flag))
        if score is not None:
            entry["score"] = round(float(score), 3)
    used = {f for entry in systems.values() for f in entry["flags"]}
    for entry in systems.values():
        entry["flags"].sort(key=flag_order)
    return {"systems": systems, "flags": flags_info(ontology, used)}


def listing():
    """The order the ontology file lists things in, which a graph does not keep: ([flag names], {flag name: [technique ids]})."""
    text = (OBDA_DIR / "alert_ontology.ttl").read_text(encoding="utf-8")
    blocks = re.findall(r"^fcd:flag_(\w+) a fcd:Flag ;(.*?)\.\s*$", text, re.M | re.S)
    return [n for n, _ in blocks], {n: re.findall(r"amx:(T\d+)", body) for n, body in blocks}


def flag_order(flag):
    """Position of a flag among the flags the ontology lists (the six rules, then the round trip)."""
    return listing()[0].index(flag.replace("rule_", "").replace("graph_", ""))


def flags_info(ontology, flags):
    """For each flag (named as the alert tables name it), what the ontology says: its label, what it detects, and the techniques it points to,
    strongest first. In the order the ontology lists the flags."""
    info, listed = {}, listing()[1]
    for f in sorted(flags, key=flag_order):
        term = FCD["flag_" + f.replace("rule_", "").replace("graph_", "")]
        info[f] = {"label": str(ontology.value(term, RDFS.label)), "detects": str(ontology.value(term, RDFS.comment)),
                   "links": sorted(({"id": str(o).rsplit("/", 1)[-1], "strength": LINKS[p]} for p, o in ontology.predicate_objects(term) if p in LINKS),
                                   key=lambda l: (list(LINKS.values()).index(l["strength"]), listed[f.replace("rule_", "").replace("graph_", "")].index(l["id"])))}
    return info


def flag_id(flag):
    """The alert table's name for a flag term: fcd:flag_money_mule is rule_money_mule, fcd:flag_roundtrip is graph_roundtrip."""
    name = str(flag).rsplit("flag_", 1)[-1]
    return "graph_roundtrip" if name == "roundtrip" else "rule_" + name


def as_sources(flags, status):
    """The flags of alerts_of() in the shape scenario 4 reads (the shape of alert_sources.json), so that the evidence and the techniques of a payment
    come from the mapping and the ontology instead of the JSON file. `status` is carried over (the mapping is a draft)."""
    out = {"status": status, "sources": {"rule": {"flags": {}}, "ml": {"flags": {}}, "graph": {"flags": {}}}}
    for f, info in flags.items():
        out["sources"]["graph" if f.startswith("graph") else "rule"]["flags"][f] = {
            "label": info["label"], "detects": info["detects"], "techniques": [{**link, "basis": ""} for link in info["links"]]}
    return out


def problems_with(payment, view):
    """Where what the mapping gives for a payment differs from what the payment says (from the alert tables read directly). Empty when they agree."""
    problems = []
    if sorted(view["systems"]) != sorted(payment["sources"]):
        problems.append(f"the mapping gives alerts from {sorted(view['systems'])}, the payment says {sorted(payment['sources'])}")
    rule = sorted(view["systems"].get("rule", {}).get("flags", []))
    if rule != sorted(payment["rule_flags"]):
        problems.append(f"the mapping gives the rule flags {rule}, the payment says {sorted(payment['rule_flags'])}")
    if ("graph_roundtrip" in view["systems"].get("graph", {}).get("flags", [])) != ("graph" in payment["sources"]):
        problems.append("the mapping and the payment disagree on the round-trip flag")
    score = view["systems"].get("ml", {}).get("score")
    if score != payment.get("ml_proba"):
        problems.append(f"the mapping gives the ML score {score}, the payment says {payment.get('ml_proba')}")
    return problems
