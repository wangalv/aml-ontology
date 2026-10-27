"""Questions to ask the dictionary. Every function returns plain dicts that carry the dictionary version.

A technique is identified by its AMLTRIX id ("T0039", "T0016.001") or by its key (the last part of its IRI).
Two techniques share the id T0098 in the source data; that id is ambiguous and must be given as a key.
"""
from rdflib import Literal, RDF, RDFS
from rdflib.namespace import DCTERMS, SKOS

from .ontology import AMLO, AMX, load_graph, version


class UnknownTechnique(KeyError):
    pass


class AmbiguousTechnique(ValueError):
    pass


def _text(g, node, predicate):
    value = g.value(node, predicate)
    return str(value) if value is not None else ""


def _key(node):
    return str(node)[len(str(AMX)):]


def _is_technique(g, node):
    return (node, RDF.type, AMLO.Technique) in g or (node, RDF.type, AMLO.SubTechnique) in g


def _resolve(ident):
    g = load_graph()
    node = AMX[ident]
    if _is_technique(g, node):
        return node
    matches = sorted(
        {s for cls in (AMLO.Technique, AMLO.SubTechnique) for s in g.subjects(RDF.type, cls) if (s, SKOS.notation, Literal(ident)) in g}
    )
    if not matches:
        raise UnknownTechnique(ident)
    if len(matches) > 1:
        raise AmbiguousTechnique(f"{ident} matches {len(matches)} techniques; use one of: {', '.join(_key(m) for m in matches)}")
    return matches[0]


def _entry(g, node, **extra):
    return {"key": _key(node), "id": _text(g, node, SKOS.notation), "name": _text(g, node, SKOS.prefLabel), **extra, "version": version()}


def get_technique(ident):
    g = load_graph()
    node = _resolve(ident)
    parent = g.value(node, SKOS.broader)
    return {
        "key": _key(node),
        "id": _text(g, node, SKOS.notation),
        "name": _text(g, node, SKOS.prefLabel),
        "kind": "subtechnique" if (node, RDF.type, AMLO.SubTechnique) in g else "technique",
        "parent": _text(g, parent, SKOS.notation) if parent is not None else None,
        "definition": _text(g, node, SKOS.definition),
        "short": _text(g, node, AMLO.shortDescription),
        "url": _text(g, node, RDFS.seeAlso),
        "tactics": sorted(
            ({"id": _text(g, t, SKOS.notation), "name": _text(g, t, SKOS.prefLabel)} for t in g.subjects(AMLO.isAchievedBy, node)),
            key=lambda t: t["id"],
        ),
        "sub_techniques": sorted(_text(g, s, SKOS.notation) for s in g.subjects(SKOS.broader, node)),
        "indicator_count": sum(1 for _ in g.objects(node, AMLO.isIndicatedBy)),
        "version": version(),
    }


def list_indicators(ident):
    g = load_graph()
    node = _resolve(ident)
    items = [_entry(g, i, text=_text(g, i, SKOS.definition)) for i in g.objects(node, AMLO.isIndicatedBy)]
    for item in items:
        item.pop("name")
    return sorted(items, key=lambda i: i["id"])


def _linked(ident, link_class, target_predicate):
    """Targets reached through the Link nodes of a technique, with the note AMLTRIX wrote for that pair."""
    g = load_graph()
    node = _resolve(ident)
    found = {}
    for link in g.subjects(AMLO.technique, node):
        if (link, RDF.type, link_class) not in g:
            continue
        target = g.value(link, target_predicate)
        if target is not None and target not in found:
            found[target] = _entry(g, target, note=_text(g, link, DCTERMS.description))
    return sorted(found.values(), key=lambda e: e["id"])


def data_sources_for(ident):
    return _linked(ident, AMLO.DataSourceLink, AMLO.dataSource)


def mitigations_for(ident):
    return _linked(ident, AMLO.MitigationLink, AMLO.mitigation)
