"""Scenario 3 in an OBDA design: typology-driven query, as the two steps of an ontology-based data access setup.

An analyst picks an AMLTRIX technique and one of its indicators. The model does two jobs, one after the other:
  1. query: read the indicator and write a SPARQL query over the terms of the FinCrime data ontology (fcd:Transaction, fcd:fromAccount, ...).
     It never sees a column name.
  2. rewrite: given the SPARQL and the R2RML mapping, write the SQL for the payments table that does the same. This is what an OBDA engine such
     as Ontop does; here a language model stands in for it. No engine is installed and nothing executes the mapping.
Code checks each step. The SPARQL must parse and use only terms the ontology defines. The SQL must pass the guard (sqlguard.py), flag the
payments of a loop and not a chain (for an indicator about funds returning to their origin), and read exactly the columns that the
SPARQL's terms stand for according to the mapping. An accepted query runs on the test period of the database.

run() returns plain dicts and lists and prints nothing, so a UI can call it directly.
"""
import json
import re

from rdflib import URIRef
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import traverse

from .. import dbrun, obda, sqlguard
from ..llm import LLMError
from ..replies import parse_reply
from . import s1_advisor, s3_hunting

MAX_ATTEMPTS = 3
DETAIL_ROWS = 20
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

SYSTEM = ("You help a financial-crime analyst turn a typology into database queries. "
          "Use only the reference material you are given. Answer with one JSON object and nothing else.")

SPARQL_FORMAT = (
    'Reply with JSON of this shape: {"sparql": "SELECT ...", "patterns": [{"pattern": "a triple pattern or filter of the query", '
    '"from_indicator": "the words of the indicator it comes from"}]}. Write one SPARQL query and quote the words of the indicator exactly.'
)
REWRITE_FORMAT = (
    'Reply with JSON of this shape: {"sql": "SELECT ...", "steps": [{"sparql": "a triple pattern or filter of the SPARQL query", '
    '"sql": "the part of the SQL it became", "mapping": "the rule of the mapping that was used, for example fcd:fromAccount to from_account"}]}. '
    "Write exactly one SQL statement."
)
LOOP_NOTE = ("The indicator says the funds come back to where they started. The query must therefore match a chain only when its last transaction "
             "pays into the account that the first transaction paid from.\n")


def sparql_prompt(context, indicator, ontology_text, problems=None, previous=None):
    task = ("Write a SPARQL SELECT query over the FinCrime data ontology that returns the transactions that take part in the pattern described by the "
            "indicator below. Use only the classes and properties listed in the ontology, with the prefix fcd. SELECT the variable of every "
            "transaction that is part of the pattern; each such variable must be a fcd:Transaction with a fcd:fromAccount. Compare times with FILTER. "
            "Use only triple patterns and FILTER: no property paths, no OPTIONAL, no aggregates, no subqueries.\n"
            f"<wanted>\n{indicator['id']}: {indicator['text']}\n</wanted>\n")
    if s3_hunting.returns_to_origin(indicator["text"]):
        task += LOOP_NOTE
    retry = f"\nYour previous query was:\n{previous}\nIt could not be used: {'; '.join(problems)}. Write a corrected query.\n" if problems else ""
    return f"{s3_hunting.technique_block(context)}{ontology_text}\n\n{task}{retry}{SPARQL_FORMAT}"


def rewrite_prompt(sparql, r2rml_text, table, indicator, problems=None, previous=None):
    task = ("You are standing in for an ontology-based data access engine such as Ontop. Rewrite the SPARQL query below into one DuckDB SQL query "
            f"over the table {table} that returns the same transactions, using the R2RML mapping. Each transaction variable stands for one row of the "
            "table: its IRI is built from tx_id. A triple pattern with fcd:fromAccount, fcd:toAccount or fcd:timestamp stands for the column the mapping "
            "gives for that property. A variable shared by two patterns becomes an equality join. Read only the columns the mapping gives for the terms the "
            "query uses, plus tx_id. The SQL must end with LIMIT 10000 or less, return a tx_id column holding the tx_id of every transaction variable the "
            "SPARQL selects, and use the time column ts.\n"
            f"<sparql>\n{sparql}\n</sparql>\n")
    if s3_hunting.returns_to_origin(indicator["text"]):
        task += LOOP_NOTE.replace("The query must therefore match", "The SQL must therefore flag the payments of")
    retry = f"\nYour previous SQL was:\n{previous}\nIt could not be used: {'; '.join(problems)}. Write a corrected query.\n" if problems else ""
    return f"<mapping format=\"R2RML\" table=\"{table}\">\n{r2rml_text}\n</mapping>\n\n{task}{retry}{REWRITE_FORMAT}"


def _patterns_and_terms(algebra):
    """The triple patterns of a SPARQL algebra tree."""
    found = []

    def visit(node):
        if getattr(node, "name", None) == "BGP":
            found.extend(node.triples)
    traverse(algebra, visitPost=visit)
    return found


def check_sparql(text, defined):
    """(problems, used terms) for a SPARQL query. `defined` is the set of curies the ontology defines. An empty problem list means it may be used."""
    try:
        query = prepareQuery(text, initNs={"fcd": obda.FCD})
    except Exception as e:  # rdflib raises several parser errors
        return [f"the SPARQL cannot be parsed: {str(e).splitlines()[0][:160]}"], set()
    if query.algebra.name != "SelectQuery":
        return ["only a SELECT query is allowed"], set()
    triples = _patterns_and_terms(query.algebra)
    problems, used, foreign, transactions = [], set(), set(), set()
    for s, p, o in triples:
        if not isinstance(p, URIRef):
            problems.append("property paths are not allowed: use plain triple patterns")
            continue
        if str(p) == RDF_TYPE:
            if isinstance(o, URIRef):
                used.add(obda.curie(o))
            continue
        (used if str(p).startswith(obda.FCD) else foreign).add(obda.curie(p))
        if str(p) == obda.FCD + "fromAccount":
            transactions.add(s)
    undefined = sorted(t for t in used if t not in defined)
    if undefined:
        problems.append("terms not in the ontology: " + ", ".join(undefined))
    if foreign:
        problems.append("only terms of the fcd ontology may be used, not: " + ", ".join(sorted(foreign)))
    projected = list(query.algebra.PV or [])
    if not projected:
        problems.append("the query must SELECT the transaction variables")
    elif not any(v in transactions for v in projected):
        problems.append("the SELECT must include a transaction variable (one that has a fcd:fromAccount)")
    return list(dict.fromkeys(problems)), used


def used_columns(sql, columns):
    """The columns of the table that a SQL text reads, in the order of the table."""
    return [c for c in columns if re.search(rf"\b{re.escape(c)}\b", sql)]


def check_fidelity(sql, used_terms, term_columns, columns):
    """Problems if the SQL does not read exactly the columns that the SPARQL's terms stand for in the mapping (plus tx_id)."""
    expected = {"tx_id"}
    for term in used_terms:
        expected |= set(term_columns.get(term, []))
    read = set(used_columns(sql, columns))
    problems = []
    if read - expected:
        problems.append("the SQL reads columns that no term of the SPARQL stands for: " + ", ".join(sorted(read - expected)))
    if expected - read:
        problems.append("the SQL does not read the columns the SPARQL's terms stand for: " + ", ".join(sorted(expected - read)))
    return problems


def quoted(words, indicator_text):
    return s3_hunting.quoted(words, indicator_text)


def _read(raw, key, item_key, indicator_text=None):
    """The text under `key` and the list under `item_key` of a reply. Raises ValueError if there is no text."""
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("the reply contains no JSON object")
        try:
            data = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"the reply is not valid JSON: {e.msg}") from e
    text = data.get(key) if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f'the reply has no "{key}"')
    items = [i for i in (data.get(item_key) or []) if isinstance(i, dict)]
    return text.strip().rstrip(";"), items


def _payment_ids(run):
    index = run["columns"].index("tx_id")
    ids, others = set(), []
    for row in run["rows"]:
        v = row[index]
        (ids.add(v) if isinstance(v, int) and not isinstance(v, bool) else others.append(v))
    return ids, others


def _details(ids, table):
    """The first transactions of a result, fetched by code (not by the model), so the page can show what was returned."""
    chosen = sorted(ids)[:DETAIL_ROWS]
    if not chosen:
        return {"columns": [], "rows": []}
    run = dbrun.run_query(f"SELECT tx_id, ts, from_account, to_account, amount_log FROM {table} WHERE tx_id IN ({', '.join(str(i) for i in chosen)}) "
                          "ORDER BY ts, tx_id LIMIT 1000")
    return {"columns": run.get("columns", []), "rows": run.get("rows", [])} if "error" not in run else {"columns": [], "rows": [], "error": run["error"]}


def run(llm, technique_id="T0039", indicator_id="IND02191", dictionary=None):
    """Run scenario 3 for one indicator. Returns a dict with the SPARQL step, the rewrite step, the result and the checks."""
    dictionary = dictionary or s3_hunting.load_dictionary()
    context = s1_advisor.dictionary_context(technique_id)
    indicator = next(i for i in context["indicators"] if i["id"] == indicator_id)
    columns = [c["name"] for c in dictionary["columns"]]
    onto_text, r2rml_text, onto, r2rml = obda.load()
    defined, term_cols = obda.defined_terms(onto), obda.term_columns(r2rml, columns)
    closed_loop = s3_hunting.returns_to_origin(indicator["text"])
    result = {"technique": {k: context["technique"][k] for k in ("id", "name", "short")}, "indicator": indicator,
              "provider": llm.name, "model": llm.model, "sparql": None, "rewrite": None, "result": None, "raw": {"sparql": [], "rewrite": []}}

    # step 1: the SPARQL query, over the terms of the ontology
    attempts, problems, previous, accepted = [], None, None, None
    for _ in range(MAX_ATTEMPTS):
        raw = llm.complete(SYSTEM, sparql_prompt(context, indicator, obda.ontology_block(onto), problems, previous), "s3-sparql")
        result["raw"]["sparql"].append(raw)
        try:
            text, items = _read(raw, "sparql", "patterns")
        except ValueError as e:
            attempts.append({"sparql": "", "problems": [str(e)]})
            problems, previous = [str(e)], ""
            continue
        found, used = check_sparql(text, defined)
        patterns = [{"pattern": str(i.get("pattern", "")), "from_indicator": str(i.get("from_indicator", "")),
                     "quote_found": quoted(i.get("from_indicator", ""), indicator["text"])} for i in items]
        attempts.append({"sparql": text, "problems": found})
        if not found:
            accepted = {"text": text, "patterns": patterns, "terms": sorted(used)}
            break
        problems, previous = found, text
    result["sparql"] = {"attempts": attempts, "accepted": accepted is not None, **(accepted or {})}
    if not accepted:
        return result

    # step 2: the SQL, which a language model writes the way an OBDA engine would
    attempts, problems, previous, final = [], None, None, None
    for _ in range(MAX_ATTEMPTS):
        raw = llm.complete(SYSTEM, rewrite_prompt(accepted["text"], r2rml_text, dictionary["table"], indicator, problems, previous), "s3-rewrite")
        result["raw"]["rewrite"].append(raw)
        try:
            sql, steps = _read(raw, "sql", "steps")
        except ValueError as e:
            attempts.append({"sql": "", "problems": [str(e)], "run": None})
            problems, previous = [str(e)], ""
            continue
        tried = s3_hunting._try(sql, dictionary, closed_loop)
        failure = list(tried["guard"])
        if not failure:
            failure = check_fidelity(sql, accepted["terms"], term_cols, columns)
        ran = tried["run"]
        if not failure and ran and "error" in ran:
            failure = [sqlguard.explain_error(ran["error"])]
        if not failure and ran:
            _, others = _payment_ids(ran)
            if others:
                failure = [f"the tx_id column must hold payment ids from the tx_id column of {dictionary['table']}, but it returned {', '.join(repr(v) for v in others[:3])}"]
        attempts.append({"sql": sql, "problems": failure, "run": s3_hunting._summary(ran) if ran else None})
        if not failure:
            final = {"sql": sql, "steps": [{"sparql": str(s.get("sparql", "")), "sql": str(s.get("sql", "")), "mapping": str(s.get("mapping", ""))} for s in steps],
                     "ids": _payment_ids(ran)[0], "run": ran}
            break
        problems, previous = failure, sql
    result["rewrite"] = {"attempts": attempts, "accepted": final is not None}
    if final:
        ids = final["ids"]
        result["rewrite"].update({"sql": final["sql"], "steps": final["steps"],
                                  "expected_columns": sorted({"tx_id"} | {c for t in accepted["terms"] for c in term_cols.get(t, [])}),
                                  "used_columns": used_columns(final["sql"], columns)})
        scored = dbrun.score(ids)
        result["result"] = {"n_rows": len(final["run"]["rows"]), "truncated": final["run"]["truncated"], "seconds": final["run"]["seconds"],
                            "details": _details(ids, dictionary["table"]),
                            "evaluation": scored.get("flagged") if "error" not in scored else {"error": scored["error"]},
                            "window": scored.get("window") if "error" not in scored else None}
    return result
