"""Turn plain source records (a business system's own field names) into JSON-LD node objects.

Source field names are kept as they are; the @context maps them to ontology terms. The adapters only do
what JSON-LD cannot do by itself: mint identifiers, turn bare ids into IRIs, and link records to each other.
Fields they do not know pass through untouched, so that validation can report them as unmapped.
"""
import itertools
import re

SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")


class SourceError(ValueError):
    """A source record cannot be linked, for example because an identifier is unusable or missing."""


def _safe(value, what):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise SourceError(f"{what}: {value!r} is not a usable identifier")
    return value


def _amx(value):
    """"T0039" becomes the compact IRI "amx:T0039". Whether it exists is the validator's question."""
    return f"amx:{_safe(value, 'AMLTRIX id')}"


def _ref(kind):
    return lambda value: f"data:{kind}/{_safe(value, kind + ' id')}"


def _apply(value, fn):
    return [fn(v) for v in value] if isinstance(value, list) else fn(value)


def _require(record, key, what):
    if key not in record:
        raise SourceError(f"{what} has no {key}")
    return record[key]


def _node(item, kind, type_, id_key, transforms, blanks):
    ident = item.get(id_key)
    node_id = _ref(kind)(ident) if ident is not None else f"_:{kind}{next(blanks)}"
    node = {"@id": node_id, "@type": type_}
    for key, value in item.items():
        node[key] = _apply(value, transforms[key]) if key in transforms else value
    return node


def alert_doc(src):
    blanks = itertools.count(1)
    rest = {k: v for k, v in src.items() if k not in ("evidence", "checklist")}
    alert = _node(rest, "alert", "inv:Alert", "alert_id", {"suspected_technique": _amx}, blanks)
    graph = [alert]

    evidence = src.get("evidence", [])
    if evidence:
        alert["evidence"] = [_ref("evidence")(_require(e, "evidence_id", "evidence")) for e in evidence]
        graph += [_node(e, "evidence", "inv:Evidence", "evidence_id", {"record_type": _amx}, blanks) for e in evidence]

    for item in src.get("checklist", []):
        _require(item, "item_id", "checklist item")
        node = _node(item, "check", "inv:ChecklistItem", "item_id",
                     {"indicator": _amx, "needs_record_type": _amx, "check_with": _ref("evidence")}, blanks)
        node["for_alert"] = alert["@id"]
        graph.append(node)
    return {"@graph": graph}


def case_doc(src):
    blanks = itertools.count(1)
    rest = {k: v for k, v in src.items() if k not in ("evidence", "findings", "report_draft")}
    case = _node(rest, "case", "inv:Case", "case_id", {"hypothesis": _amx}, blanks)
    graph = [case]
    graph += [_node(e, "evidence", "inv:Evidence", "evidence_id", {"record_type": _amx}, blanks) for e in src.get("evidence", [])]

    findings = src.get("findings", [])
    if findings:
        case["findings"] = [_ref("finding")(_require(f, "finding_id", "finding")) for f in findings]
        graph += [
            _node(f, "finding", "inv:Finding", "finding_id",
                  {"technique": _amx, "indicator": _amx, "supported_by": _ref("evidence")}, blanks)
            for f in findings
        ]

    draft = src.get("report_draft")
    if draft:
        report = _node({k: v for k, v in draft.items() if k != "paragraphs"}, "report", "inv:ReportDraft", "draft_id", {}, blanks)
        report["for_case"] = case["@id"]
        if "paragraphs" in draft:
            report["paragraphs"] = [
                {"@type": "inv:Paragraph", **{k: _apply(v, _ref("finding")) if k == "based_on" else v for k, v in p.items()}}
                for p in draft["paragraphs"]
            ]
        graph.append(report)
    return {"@graph": graph}
