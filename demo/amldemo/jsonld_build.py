"""Attach a mapping (@context) to adapted records, and turn the JSON-LD into an RDF graph."""
import json

from rdflib import Graph

from . import config


def load_context(name):
    return json.loads((config.MAPPING_DIR / name).read_text(encoding="utf-8"))["@context"]


def attach_context(doc, context):
    return {"@context": context, **doc}


def to_graph(doc):
    return Graph().parse(data=json.dumps(doc), format="json-ld")


def write_json(doc, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
