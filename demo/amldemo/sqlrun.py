"""Runs one request against the read-only transaction database and prints the answer as JSON.

This file is a standalone script: it imports nothing from this package, only the standard library and duckdb, so it can be run
by any Python that has a duckdb able to read the database file (the file may have been written by a newer DuckDB than the one in
this project's own environment). dbrun.py starts it as a subprocess. Request on stdin, answer on stdout:

  {"action": "run",        "sql": "...", "max_rows": 10000, "timeout": 120}   run a query on the view `txs`
  {"action": "score",      "tx_ids": [...]}                                    judge a set of flagged transactions with the label
  {"action": "population"}                                                     how the three alert sources overlap, by account
  {"action": "sample",     "seed": "...", "per_sources": {"1": 40, ...}}        accounts with their alerts, without the label
  {"action": "judge",      "accounts": [...]}                                  which of those accounts hold a laundering payment
  {"action": "payments",   "seed": "...", "n_sources": 3, "count": 1}          alerted payments raised by n sources, with their evidence
  {"action": "judge_payments", "tx_ids": [...]}                                which of those payments are laundering

`txs` is a view of the test period (not the tail) with only the columns the data dictionary lists. The laundering label and
the round-trip flag are not in it; only "score" reads them, and only to judge a query that has already been written.
The alert actions work on the three alert tables, limited to the same period. "sample" never returns the label; "judge" and
"population" read it, and only to judge accounts that have already been written about.
"""
import json
import math
import os
import sys
import threading
import time

import duckdb

COLUMNS = ("tx_id, ts, from_account, to_account, amount_log, is_cross_currency, is_self_transfer, is_same_bank, "
           "fmt_wire, fmt_ach, fmt_cheque, fmt_cash, fmt_credit_card, fmt_bitcoin, fmt_reinvestment")
WINDOW = "split = 'test' AND NOT is_tail_period"
LINK_FACTS = (
    ("p_all", "a payment raised by all three sources"), ("p_rm", "a payment raised by both the rules and the ML model"),
    ("p_rg", "a payment raised by both the rules and the graph"), ("p_mg", "a payment raised by both the ML model and the graph"),
    ("cp_rm", "a counterparty that both the rules and the ML model alerted on"),
    ("cp_rg", "a counterparty that both the rules and the graph alerted on"),
    ("cp_mg", "a counterparty that both the ML model and the graph alerted on"))
RULES = ("rule_structuring", "rule_money_mule", "rule_fan_in", "rule_pep", "rule_high_risk_business", "rule_high_risk_country")


def connect():
    con = duckdb.connect(os.environ["AML_DB"], read_only=True)
    con.execute("SET memory_limit='6GB'")
    con.execute(f"CREATE TEMP VIEW txs AS SELECT {COLUMNS} FROM tx_features WHERE {WINDOW}")
    return con


def jsonable(value):
    return value.isoformat(sep=" ") if hasattr(value, "isoformat") else value


def run(con, request):
    timer = threading.Timer(request.get("timeout", 120), con.interrupt)
    timer.start()
    started = time.time()
    try:
        cursor = con.execute(request["sql"])
        names = [d[0] for d in cursor.description]
        fetched = cursor.fetchmany(request.get("max_rows", 10000) + 1)
    except duckdb.InterruptException:
        return {"error": f"the query was stopped after {request.get('timeout', 120)} seconds"}
    except duckdb.Error as e:
        return {"error": str(e).splitlines()[0]}
    finally:
        timer.cancel()
    cap = request.get("max_rows", 10000)
    return {"columns": names, "rows": [[jsonable(v) for v in row] for row in fetched[:cap]],
            "truncated": len(fetched) > cap, "seconds": round(time.time() - started, 1)}


def score(con, request):
    ids = [int(i) for i in request["tx_ids"]]
    con.execute("CREATE TEMP TABLE flagged (tx_id BIGINT)")
    con.executemany("INSERT INTO flagged VALUES (?)", [[i] for i in ids])
    window = con.execute(
        f"SELECT count(*), sum(label), min(ts), max(ts), sum(graph_roundtrip), sum(label * graph_roundtrip) "
        f"FROM tx_features WHERE {WINDOW}").fetchone()
    hit = con.execute(
        f"SELECT count(*), sum(label), sum(graph_roundtrip), sum(label * graph_roundtrip) "
        f"FROM tx_features WHERE {WINDOW} AND tx_id IN (SELECT tx_id FROM flagged)").fetchone()
    return {
        "window": {"rows": window[0], "laundering": int(window[1]), "from": jsonable(window[2]), "to": jsonable(window[3]),
                   "in_verified_cycles": int(window[4]), "in_verified_cycles_laundering": int(window[5])},
        "flagged": {"rows": hit[0], "laundering": int(hit[1] or 0), "in_verified_cycles": int(hit[2] or 0),
                    "in_verified_cycles_laundering": int(hit[3] or 0), "outside_window": len(set(ids)) - hit[0]},
    }


def build_alerts(con):
    """Temp tables: `alerts` (one row per alerted payment, with the sources that raised it), `ends` (one row per payment and
    account it touches), `accounts` (one row per account that has an alert). A payment touches two accounts."""
    columns = "tx_id, ts, amount, from_account, to_account, label, " + ", ".join(RULES) + ", graph_roundtrip, ml_proba"
    flags = ", ".join(f"max(CAST({r} AS INTEGER)) AS {r}" for r in RULES)
    con.execute(f"""
        CREATE TEMP TABLE alerts AS
        WITH u AS (
            SELECT {columns}, 1 AS s_rule, 0 AS s_ml, 0 AS s_graph FROM alert_rule
            UNION ALL SELECT {columns}, 0, 1, 0 FROM alert_ml
            UNION ALL SELECT {columns}, 0, 0, 1 FROM alert_graph)
        SELECT tx_id, any_value(ts) AS ts, any_value(amount) AS amount, any_value(from_account) AS from_account,
               any_value(to_account) AS to_account, any_value(label) AS label, {flags},
               max(CAST(graph_roundtrip AS INTEGER)) AS graph_roundtrip, max(ml_proba) AS ml_proba,
               max(s_rule) AS s_rule, max(s_ml) AS s_ml, max(s_graph) AS s_graph
        FROM u WHERE tx_id IN (SELECT tx_id FROM tx_features WHERE {WINDOW}) GROUP BY tx_id""")
    con.execute("""
        CREATE TEMP TABLE ends AS
        SELECT from_account AS acc, 'sent' AS role, to_account AS other, * FROM alerts
        UNION ALL SELECT to_account, 'received', from_account, * FROM alerts WHERE from_account <> to_account""")
    sums = ", ".join(f"sum({r}) AS {r}" for r in RULES)
    # Which counterparties each source's alerts point at, so that the sources can be compared on the same counterparty.
    con.execute("""
        CREATE TEMP TABLE cplinks AS
        SELECT acc, count(*) AS cp_n, sum(r * m) AS cp_rm, sum(r * g) AS cp_rg, sum(m * g) AS cp_mg, sum(r * m * g) AS cp_all
        FROM (SELECT acc, other, max(s_rule) AS r, max(s_ml) AS m, max(s_graph) AS g FROM ends GROUP BY acc, other)
        GROUP BY acc""")
    con.execute(f"""
        CREATE TEMP TABLE accounts AS
        SELECT a.*,
               CASE WHEN p_all > 0 THEN 'same_payment' WHEN p_multi > 0 THEN 'pairwise' ELSE 'account_only' END AS link_class,
               c.cp_n, c.cp_rm, c.cp_rg, c.cp_mg, c.cp_all
        FROM (SELECT acc, count(*) AS n_alerts, max(s_rule) + max(s_ml) + max(s_graph) AS n_sources,
                     sum(s_rule) AS n_rule, sum(s_ml) AS n_ml, sum(s_graph) AS n_graph, {sums},
                     sum(graph_roundtrip) AS graph_roundtrip,
                     max(ml_proba) AS max_ml, sum(amount) AS total_amount, min(ts) AS first_ts, max(ts) AS last_ts,
                     max(label) AS laundering,
                     sum(s_rule * s_ml) AS p_rm, sum(s_rule * s_graph) AS p_rg, sum(s_ml * s_graph) AS p_mg,
                     sum(s_rule * s_ml * s_graph) AS p_all, sum(CAST(s_rule + s_ml + s_graph >= 2 AS INTEGER)) AS p_multi
              FROM ends GROUP BY acc) a
        JOIN cplinks c USING (acc)""")


def population(con, request):
    build_alerts(con)
    tiers = con.execute("SELECT n_sources, count(*), sum(laundering) FROM accounts GROUP BY 1 ORDER BY 1").fetchall()
    combos = con.execute("""SELECT n_rule > 0, n_ml > 0, n_graph > 0, count(*), sum(laundering)
                            FROM accounts GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").fetchall()
    per_source = con.execute("""SELECT sum(s_rule), sum(s_rule * label), sum(s_ml), sum(s_ml * label), sum(s_graph), sum(s_graph * label),
                                       count(*), sum(label) FROM alerts""").fetchone()
    names = ("rule", "ml", "graph")
    by_payment = [{"sources": r[0], "payments": r[1], "laundering": int(r[2] or 0)} for r in con.execute(
        "SELECT s_rule + s_ml + s_graph, count(*), sum(label) FROM alerts GROUP BY 1 ORDER BY 1").fetchall()]
    by_linkage = [{"sources": r[0], "link": r[1], "accounts": r[2], "laundering": int(r[3] or 0)} for r in con.execute(
        "SELECT n_sources, link_class, count(*), sum(laundering) FROM accounts WHERE n_sources >= 2 GROUP BY 1, 2 ORDER BY 1, 2").fetchall()]
    facts = []
    for column, text in LINK_FACTS:
        r = con.execute(f"""SELECT sum(CAST({column} > 0 AS INTEGER)), sum(CAST({column} > 0 AS INTEGER) * laundering),
                                   sum(CAST({column} = 0 AS INTEGER)), sum(CAST({column} = 0 AS INTEGER) * laundering)
                            FROM accounts WHERE n_sources = 3""").fetchone()
        facts.append({"fact": column, "text": text, "present": {"accounts": int(r[0]), "laundering": int(r[1] or 0)},
                      "absent": {"accounts": int(r[2]), "laundering": int(r[3] or 0)}})
    return {
        "linkage": {"by_class": by_linkage, "facts": facts}, "payments_by_sources": by_payment,
        "payments": {"alerted": per_source[6], "laundering": int(per_source[7]),
                     **{name: {"alerted": per_source[2 * i], "laundering": int(per_source[2 * i + 1])} for i, name in enumerate(names)}},
        "accounts": sum(t[1] for t in tiers),
        "laundering_accounts": int(sum(t[2] or 0 for t in tiers)),
        "by_sources": [{"sources": t[0], "accounts": t[1], "laundering": int(t[2] or 0)} for t in tiers],
        "by_combination": [{"sources": [n for n, on in zip(names, c[:3]) if on], "accounts": c[3], "laundering": int(c[4] or 0)}
                           for c in combos],
    }


def sample(con, request):
    build_alerts(con)
    seed, max_alerts = str(request.get("seed", "s4")), int(request.get("max_alerts", 12))
    picked = []
    for tier, count in sorted((int(k), int(v)) for k, v in request["per_sources"].items()):
        picked += [r[0] for r in con.execute(
            "SELECT acc FROM accounts WHERE n_sources = ? ORDER BY hash(acc || ?) LIMIT ?", [tier, seed, count]).fetchall()]
    con.execute("CREATE TEMP TABLE picked (acc VARCHAR)")
    con.executemany("INSERT INTO picked VALUES (?)", [[a] for a in picked])
    cases = {}
    rule_cols = ", ".join(RULES)
    for row in con.execute(f"""
            SELECT acc, n_alerts, n_sources, n_rule, n_ml, n_graph, {rule_cols}, graph_roundtrip, max_ml, total_amount, first_ts, last_ts,
                   link_class, p_all, p_rm, p_rg, p_mg, p_multi, cp_n, cp_rm, cp_rg, cp_mg, cp_all
            FROM accounts WHERE acc IN (SELECT acc FROM picked) ORDER BY hash(acc || ?), acc""", [seed]).fetchall():
        flags = dict(zip(RULES + ("graph_roundtrip",), (int(v) for v in row[6:13])))
        cases[row[0]] = {
            "account": row[0], "n_alerts": row[1], "n_sources": row[2],
            "sources": {"rule": int(row[3]), "ml": int(row[4]), "graph": int(row[5])},
            "flags": {k: v for k, v in flags.items() if v},
            "max_ml": None if row[13] is None else round(row[13], 3), "total_amount": round(row[14], 2),
            "first": jsonable(row[15]), "last": jsonable(row[16]),
            "links": {"class": row[17],
                      "payments": {"all": int(row[18]), "rule+ml": int(row[19]), "rule+graph": int(row[20]), "ml+graph": int(row[21]),
                                   "two_or_more": int(row[22])},
                      "counterparties": {"total": int(row[23]), "rule+ml": int(row[24]), "rule+graph": int(row[25]),
                                         "ml+graph": int(row[26]), "all": int(row[27])}},
            "alerts": []}
    shown = con.execute(f"""
        SELECT * FROM (
            SELECT acc, tx_id, ts, amount, role, other, s_rule, s_ml, s_graph, {rule_cols}, graph_roundtrip, ml_proba,
                   row_number() OVER (PARTITION BY acc ORDER BY s_rule + s_ml + s_graph DESC, ml_proba DESC NULLS LAST,
                                      amount DESC, tx_id) AS rn
            FROM ends WHERE acc IN (SELECT acc FROM picked))
        WHERE rn <= ? ORDER BY acc, rn""", [max_alerts]).fetchall()
    for r in shown:
        fired = [name for name, on in zip(RULES + ("graph_roundtrip",), r[9:16]) if on]
        cases[r[0]]["alerts"].append({
            "tx_id": r[1], "ts": jsonable(r[2]), "amount": round(r[3], 2), "role": r[4], "other": r[5],
            "sources": [n for n, on in zip(("rule", "ml", "graph"), r[6:9]) if on], "flags": fired,
            "ml_proba": None if r[16] is None else round(r[16], 3)})
    return {"cases": list(cases.values())}


def judge(con, request):
    build_alerts(con)
    con.execute("CREATE TEMP TABLE asked (acc VARCHAR)")
    con.executemany("INSERT INTO asked VALUES (?)", [[a] for a in request["accounts"]])
    rows = con.execute("""SELECT acc, laundering, (SELECT count(*) FROM ends e WHERE e.acc = a.acc AND e.label = 1)
                          FROM accounts a WHERE acc IN (SELECT acc FROM asked)""").fetchall()
    return {"accounts": {r[0]: {"laundering": bool(r[1]), "laundering_payments": int(r[2])} for r in rows}}


CURRENCIES = {"cur_yen": "Yen", "cur_brazil_real": "Brazil Real", "cur_euro": "Euro", "cur_yuan": "Yuan", "cur_ruble": "Ruble",
              "cur_shekel": "Shekel", "cur_canadian_dollar": "Canadian Dollar", "cur_us_dollar": "US Dollar",
              "cur_australian_dollar": "Australian Dollar", "cur_rupee": "Rupee", "cur_swiss_franc": "Swiss Franc",
              "cur_mexican_peso": "Mexican Peso", "cur_bitcoin": "Bitcoin", "cur_uk_pound": "UK Pound", "cur_saudi_riyal": "Saudi Riyal"}
FORMATS = {"fmt_wire": "Wire", "fmt_ach": "ACH", "fmt_cheque": "Cheque", "fmt_cash": "Cash", "fmt_credit_card": "Credit Card",
           "fmt_bitcoin": "Bitcoin", "fmt_reinvestment": "Reinvestment"}


def cycles_path():
    """The verified round trips found by the graph analysis of AML Triage Demo: <that project>/graph/_verified_roundtrip.json."""
    explicit = os.environ.get("AML_CYCLES")
    return explicit or os.path.join(os.path.dirname(os.path.dirname(os.environ["AML_DB"])), "graph", "_verified_roundtrip.json")


def cycle_of(con, tx_id):
    """The verified cycle a payment lies on: its accounts, span and legs (time, accounts, amount). None if there is none."""
    try:
        with open(cycles_path(), encoding="utf-8") as f:
            cycles = json.load(f)
    except OSError:
        return None
    found = next((c for c in cycles if tx_id in c["tx_ids"]), None)
    if found is None:
        return None
    legs = con.execute(f"SELECT tx_id, ts, from_account, to_account, amount_log FROM tx_features WHERE tx_id IN ({', '.join('?' * len(found['tx_ids']))}) ORDER BY ts",
                       found["tx_ids"]).fetchall()
    return {"accounts": found["accounts"], "span_days": round(found["span_days"], 2),
            "legs": [{"tx_id": r[0], "ts": jsonable(r[1]), "from": r[2], "to": r[3], "amount": round(math.expm1(r[4]), 2)} for r in legs]}


def payments(con, request):
    """Alerted payments raised by exactly `n_sources` systems, in a fixed random order, with everything the systems and the data say about
    each. The label is not returned."""
    build_alerts(con)
    seed, n = str(request.get("seed", "s4")), int(request["n_sources"])
    attrs = ", ".join(f"f.{c}" for c in (*CURRENCIES, *FORMATS))
    rows = con.execute(f"""
        SELECT a.tx_id, a.ts, a.amount, a.from_account, a.to_account, a.s_rule, a.s_ml, a.s_graph, a.ml_proba, {', '.join('a.' + r for r in RULES)},
               f.is_cross_currency, f.is_self_transfer, f.is_same_bank, {attrs}
        FROM alerts a JOIN tx_features f USING (tx_id)
        WHERE a.s_rule + a.s_ml + a.s_graph = ? ORDER BY hash(CAST(a.tx_id AS VARCHAR) || ?), a.tx_id LIMIT ?""",
        [n, seed, int(request.get("count", 1))]).fetchall()
    out = []
    for r in rows:
        k = 9 + len(RULES)
        flags = [name for name, on in zip(RULES, r[9:k]) if on]
        cur_on = r[k + 3:k + 3 + len(CURRENCIES)]
        fmt_on = r[k + 3 + len(CURRENCIES):]
        out.append({
            "tx_id": r[0], "ts": jsonable(r[1]), "amount": round(r[2], 2), "from": r[3], "to": r[4],
            "sources": [name for name, on in zip(("rule", "ml", "graph"), r[5:8]) if on], "rule_flags": flags,
            "ml_proba": None if r[8] is None else round(r[8], 3),
            "cross_currency": bool(r[k]), "self_transfer": bool(r[k + 1]), "same_bank": bool(r[k + 2]),
            "currency": next((v for (c, v), on in zip(CURRENCIES.items(), cur_on) if on), None),
            "format": next((v for (c, v), on in zip(FORMATS.items(), fmt_on) if on), None),
            "cycle": cycle_of(con, r[0]) if r[7] else None})
    return {"payments": out}


def judge_payments(con, request):
    build_alerts(con)
    con.execute("CREATE TEMP TABLE asked (tx_id BIGINT)")
    con.executemany("INSERT INTO asked VALUES (?)", [[int(i)] for i in request["tx_ids"]])
    rows = con.execute("SELECT tx_id, label FROM alerts WHERE tx_id IN (SELECT tx_id FROM asked)").fetchall()
    return {"payments": {str(r[0]): bool(r[1]) for r in rows}}


def main():
    request = json.load(sys.stdin)
    try:
        con = connect()
        answer = {"run": run, "score": score, "population": population, "sample": sample, "judge": judge,
               "payments": payments, "judge_payments": judge_payments}[request["action"]](con, request)
    except Exception as e:  # a request the runner cannot answer must still come back as JSON
        answer = {"error": f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"}
    json.dump(answer, sys.stdout)


if __name__ == "__main__":
    main()
