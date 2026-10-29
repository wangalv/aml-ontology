"""A guard for SQL written by a language model. Nothing here runs the query: it parses the text and returns the reasons
to refuse it, so a refused query is never sent to the database.

The parser is DuckDB's own (json_serialize_sql turns a statement into a syntax tree, and only accepts a SELECT). The guard
asks four things of the tree:
  - one statement, and it is a SELECT (a write, a PRAGMA or two statements are refused by the parser or by the count);
  - it reads only the table in the data dictionary (or a WITH name defined in the query), never a table function;
  - it names only columns the dictionary lists (or names the query itself defines), and never `SELECT *`;
  - it ends in a LIMIT of at most MAX_ROWS, returns a tx_id column, and uses the time column ts at least once.
The database is a second line of defence: the query runs on a view that holds only the listed columns, so a column the
guard missed still does not exist there. The laundering label is not in that view at all.
"""
import json

import duckdb

MAX_ROWS = 10000
FORBIDDEN_NOTE = {"label": "the laundering label is the answer key and is used only to judge a query, never to write one"}


def _walk(node):
    """Every dict in a tree of dicts and lists, depth first."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def check(sql, dictionary, max_rows=MAX_ROWS):
    """The problems found in `sql`, as a list of sentences. An empty list means the query may be run."""
    if not isinstance(sql, str) or not sql.strip():
        return ["the query is empty"]
    try:
        if len(duckdb.extract_statements(sql)) != 1:
            return ["the reply must contain exactly one SQL statement"]
        parsed = json.loads(duckdb.connect().execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    except duckdb.Error as e:
        return [f"the SQL cannot be parsed: {str(e).splitlines()[0]}"]
    if parsed.get("error"):
        message = parsed.get("error_message", "")
        return ["only a read-only SELECT query is allowed" if "SELECT" in message else f"the SQL cannot be read: {message}"]

    allowed_columns = {c["name"] for c in dictionary["columns"]}
    allowed_table = dictionary["table"]
    tree = parsed["statements"][0]["node"]
    nodes = list(_walk(tree))
    problems = []

    ctes = {entry["key"] for n in nodes for entry in (n.get("cte_map") or {}).get("map", [])}
    defined = {n["alias"] for n in nodes if n.get("alias")} | ctes
    for n in nodes:
        for entry in (n.get("cte_map") or {}).get("map", []):
            defined.update(entry["value"].get("aliases") or [])

    for n in nodes:
        if n.get("type") == "BASE_TABLE" and n.get("table_name") not in ({allowed_table} | ctes):
            problems.append(f"table {n.get('table_name')!r} is not available: the only table is {allowed_table!r}")
        elif n.get("type") == "TABLE_FUNCTION":
            problems.append("table functions are not allowed")
        if n.get("class") == "STAR":
            problems.append("SELECT * is not allowed: name the columns you need")
        if n.get("class") == "COLUMN_REF":
            name = n["column_names"][-1]
            if name in FORBIDDEN_NOTE:
                problems.append(f"column {name!r} is not allowed: {FORBIDDEN_NOTE[name]}")
            elif name not in allowed_columns and name not in defined:
                problems.append(f"column {name!r} is not in the data dictionary")

    limits = [m for m in tree.get("modifiers", []) if m.get("type") == "LIMIT_MODIFIER"]
    limit = limits[0]["limit"].get("value", {}).get("value") if limits and limits[0].get("limit") else None
    if not limits:
        problems.append(f"the query needs a LIMIT of at most {max_rows}")
    elif not isinstance(limit, int) or limit > max_rows:
        problems.append(f"the LIMIT must be a number no larger than {max_rows}")

    outputs = tree.get("select_list", [])
    names = {item.get("alias") or (item["column_names"][-1] if item.get("class") == "COLUMN_REF" else "") for item in outputs}
    if "tx_id" not in names:
        problems.append("the query must return a tx_id column: the transactions it flags")
    if not any(n.get("class") == "COLUMN_REF" and n["column_names"][-1] == "ts" for n in nodes):
        problems.append("the query never uses the time column ts: the payments of a pattern have to be tied together in time")
    return list(dict.fromkeys(problems))
