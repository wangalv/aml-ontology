"""Scenario 3: typology-driven query.

An analyst picks an AMLTRIX technique. The model is given that technique's indicators and a data dictionary of the payments table,
and does two things:
  1. coverage: for each indicator, can this table show it at all? ("yes", "partly" or "no", with the columns it would use);
  2. query: for the indicators it says it can see, write one SQL query that returns the payments that fit the pattern.
Code then takes over. The guard (sqlguard.py) refuses anything that is not a read-only query over the listed columns; a refused or
failing query gets the reason back once or twice and may be rewritten; an accepted query runs on the test period of the
database and is judged with the labels, which the model never sees (dbrun.py -> sqlrun.py).

hunt() returns plain dicts and lists and prints nothing, so a UI can call it directly.
"""
import json
import re

from .. import config, dbrun, lookup, sqlguard
from ..llm import LLMError
from ..replies import parse_reply
from . import s1_advisor

QUERYABLE = ("yes", "partly", "no")
MAX_QUERIES = 2        # indicators turned into a query in one run
MAX_ATTEMPTS = 3       # first try plus rewrites after a refusal or an error
SAMPLE_ROWS = 10

SYSTEM = (
    "You help a financial-crime analyst turn a typology into database queries. "
    "Use only the reference material you are given. Answer with one JSON object and nothing else."
)

COVERAGE_FORMAT = (
    'Reply with JSON of this shape: {"indicators": [{"indicator": "IND#####", "queryable": "yes", "columns": ["tx_id"], '
    '"reason": "one sentence"}]}. queryable is "yes" (a query over this table can find it), "partly" (only a rough or '
    'incomplete version can be found) or "no" (the data it needs is not in this table). columns lists the columns a query would '
    'use, and is empty when queryable is "no". Include every indicator exactly once.'
)

QUERY_FORMAT = (
    'Reply with JSON of this shape: {"queries": [{"indicator": "IND#####", "sql": "SELECT ...", "conditions": '
    '[{"condition": "what this part of the SQL checks", "from_indicator": "the words of the indicator it comes from"}]}]}. '
    "Write exactly one query for each indicator listed, as one SQL statement."
)


def load_dictionary():
    return json.loads((config.MAPPING_DIR / "data_dictionary.json").read_text(encoding="utf-8"))


def dictionary_block(dictionary):
    columns = "\n".join(f"{c['name']} ({c['type']}): {c['meaning']}" for c in dictionary["columns"])
    notes = "\n".join(f"- {n}" for n in dictionary["notes"])
    example = dictionary.get("example")
    shown = (f"\nExample query over this table, only to show the syntax and the expected output:\npattern: {example['pattern']}\n{example['sql']}\n"
             if example else "")
    return (f"<data_dictionary>\nTable {dictionary['table']}: {dictionary['description']}\nColumns:\n{columns}\nNotes:\n{notes}{shown}</data_dictionary>")


def technique_block(context):
    t = context["technique"]
    indicators = "\n".join(f"{i['id']}: {i['text']}" for i in context["indicators"])
    return (f'<technique id="{t["id"]}" name="{t["name"]}" dictionary="AMLTRIX {t["version"]}">\n{t["short"]}\n</technique>\n'
            f"<indicators>\n{indicators}\n</indicators>\n")


def coverage_prompt(context, dictionary):
    task = ("For each indicator above, decide whether the payments table in the data dictionary can show it. Only the columns "
            "listed there exist; do not assume any other data. ")
    return f"{technique_block(context)}{dictionary_block(dictionary)}\n\n{task}{COVERAGE_FORMAT}"


def query_prompt(context, dictionary, indicators, problems=None, previous_sql=None):
    wanted = "\n".join(f"{i['id']}: {i['text']}" for i in indicators)
    task = (f"Write a DuckDB SQL query over the table {dictionary['table']} that returns the tx_id of every payment that takes part in "
            "the pattern described by each indicator below, using only the listed columns. The query must end with LIMIT 10000 or "
            "less, return a tx_id column, and use the time column ts. In conditions, say what each part of the SQL checks and "
            f"quote the words of the indicator it comes from.\n<wanted>\n{wanted}\n</wanted>\n")
    retry = ""
    if problems:
        retry = (f"\nYour previous query was:\n{previous_sql}\nIt could not be used: {'; '.join(problems)}. Write a corrected query.\n")
    return f"{technique_block(context)}{dictionary_block(dictionary)}\n\n{task}{retry}{QUERY_FORMAT}"


def _read_coverage(raw, context, dictionary):
    """The coverage list, one entry per indicator of the technique, each with the problems found in the model's answer."""
    valid = {i["id"]: i["text"] for i in context["indicators"]}
    columns = {c["name"] for c in dictionary["columns"]}
    answers = {}
    for item in parse_reply(raw, "indicators"):
        if isinstance(item, dict) and item.get("indicator") in valid and item["indicator"] not in answers:
            answers[item["indicator"]] = item
    rows = []
    for ind, text in valid.items():
        item = answers.get(ind)
        problems = []
        if item is None:
            rows.append({"indicator": ind, "indicator_text": text, "queryable": "not-answered", "columns": [], "reason": "", "problems": ["the model did not answer for this indicator"]})
            continue
        queryable = item.get("queryable")
        if queryable not in QUERYABLE:
            problems.append(f"queryable must be one of {', '.join(QUERYABLE)}")
            queryable = "not-answered"
        used = [c for c in (item.get("columns") or []) if isinstance(c, str)]
        unknown = [c for c in used if c not in columns]
        if unknown:
            problems.append("columns not in the data dictionary: " + ", ".join(unknown))
        if queryable == "no" and used:
            problems.append("said no but still names columns")
        rows.append({"indicator": ind, "indicator_text": text, "queryable": queryable, "columns": [c for c in used if c in columns],
                     "reason": str(item.get("reason") or ""), "problems": problems})
    return rows


def quoted(words, indicator_text):
    """True when the words the model quotes from an indicator really occur in it. "..." in a quote stands for words left out."""
    def norm(text):
        return " ".join(str(text).lower().replace("\u201c", '"').replace("\u201d", '"').strip(" \"'").split())
    parts = [norm(p) for p in re.split(r"\.{2,}|\u2026", str(words))]
    parts = [p for p in parts if p]
    return bool(parts) and all(p in norm(indicator_text) for p in parts)


def _first_query(raw, indicator, indicator_text):
    """The query the model wrote for `indicator`: (sql, conditions). Raises ValueError if there is none.
    Each condition says whether the words it quotes from the indicator really occur in it."""
    for item in parse_reply(raw, "queries"):
        if isinstance(item, dict) and item.get("indicator") == indicator and isinstance(item.get("sql"), str):
            conditions = [c for c in (item.get("conditions") or []) if isinstance(c, dict)]
            return item["sql"].strip().rstrip(";"), [
                {"condition": str(c.get("condition", "")), "from_indicator": str(c.get("from_indicator", "")),
                 "quote_found": quoted(c.get("from_indicator", ""), indicator_text)} for c in conditions]
    raise ValueError(f"the reply has no query for {indicator}")


def _try(sql, dictionary):
    """Guard, then run. Returns {"guard": [...], "run": {...} or None}."""
    problems = sqlguard.check(sql, dictionary)
    if problems:
        return {"guard": problems, "run": None}
    result = dbrun.run_query(sql, max_rows=sqlguard.MAX_ROWS)
    return {"guard": [], "run": result}


def _payment_ids(run):
    """The tx_id values of a run as whole numbers, and the values that are not (the model may return account ids under that name)."""
    index = run["columns"].index("tx_id")
    ids, others = set(), []
    for row in run["rows"]:
        value = row[index]
        if isinstance(value, int) and not isinstance(value, bool):
            ids.add(value)
        else:
            others.append(value)
    return ids, others


def _summary(run):
    """What is kept of a run: the error, or the row count, the time and a few rows."""
    if "error" in run:
        return {"error": run["error"]}
    return {"n_rows": len(run["rows"]), "truncated": run["truncated"], "seconds": run["seconds"], "columns": run["columns"],
            "sample": run["rows"][:SAMPLE_ROWS]}


def hunt(technique_id, llm, dictionary=None):
    """Run scenario 3 for one technique.

    Returns {"technique", "provider", "model", "coverage", "queries", "window", "raw"}.
    "coverage" has one entry per indicator (indicator, indicator_text, queryable, columns, reason, problems).
    "queries" has one entry per indicator the model said it can see (at most MAX_QUERIES), with every attempt, the final query
    and its evaluation. "window" describes the test period the queries ran on.
    """
    dictionary = dictionary or load_dictionary()
    context = s1_advisor.dictionary_context(technique_id)
    technique = {k: context["technique"][k] for k in ("id", "name", "short")}
    raw_coverage = llm.complete(SYSTEM, coverage_prompt(context, dictionary), "s3-coverage")
    try:
        coverage = _read_coverage(raw_coverage, context, dictionary)
    except ValueError as e:
        raise LLMError(f"could not read the model's coverage answer: {e}") from e
    result = {"technique": technique, "provider": llm.name, "model": llm.model, "coverage": coverage, "queries": [], "window": None,
              "raw": {"coverage": raw_coverage, "queries": []}}

    chosen = [r for r in coverage if r["queryable"] in ("yes", "partly") and not r["problems"]]
    chosen.sort(key=lambda r: r["queryable"] != "yes")
    for entry in chosen[:MAX_QUERIES]:
        indicator = {"id": entry["indicator"], "text": entry["indicator_text"]}
        attempts, problems, previous = [], None, None
        for _ in range(MAX_ATTEMPTS):
            raw = llm.complete(SYSTEM, query_prompt(context, dictionary, [indicator], problems, previous), "s3-sql")
            result["raw"]["queries"].append(raw)
            try:
                sql, conditions = _first_query(raw, entry["indicator"], entry["indicator_text"])
            except ValueError as e:
                attempts.append({"sql": "", "conditions": [], "guard": [str(e)], "run": None})
                problems, previous = [str(e)], ""
                continue
            tried = _try(sql, dictionary)
            attempts.append({"sql": sql, "conditions": conditions, "guard": tried["guard"],
                             "run": _summary(tried["run"]) if tried["run"] else None, "_rows": tried["run"]})
            failure = tried["guard"] or ([tried["run"]["error"]] if tried["run"] and "error" in tried["run"] else None)
            if not failure:
                _, others = _payment_ids(tried["run"])
                if others:
                    failure = [f"the tx_id column must hold payment ids (whole numbers taken from the tx_id column of {dictionary['table']}), "
                               f"but it returned values such as {', '.join(repr(v) for v in others[:3])}"]
                    attempts[-1]["run"] = {**attempts[-1]["run"], "error": failure[0]}
            if not failure:
                break
            problems, previous = failure, sql
        final = attempts[-1]
        ok = bool(final["run"]) and "error" not in final["run"] and not final["guard"]
        record = {"indicator": entry["indicator"], "indicator_text": entry["indicator_text"], "queryable": entry["queryable"],
                  "attempts": [{k: v for k, v in a.items() if k != "_rows"} for a in attempts], "accepted": ok, "evaluation": None}
        if ok:
            rows = final["_rows"]
            ids, _ = _payment_ids(rows)
            scored = dbrun.score(ids)
            if "error" in scored:
                record["evaluation"] = {"error": scored["error"]}
            else:
                record["evaluation"] = scored["flagged"]
                result["window"] = scored["window"]
        result["queries"].append(record)
    if result["window"] is None:
        scored = dbrun.score([])
        result["window"] = None if "error" in scored else scored["window"]
    return result
