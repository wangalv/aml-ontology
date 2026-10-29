"""Calls sqlrun.py, the only code that opens the transaction database.

The database is the one AML Triage Demo already holds; it is referenced, never copied. Set AML_DB to its path. If that file was
written by a newer DuckDB than the one installed here, set AML_DB_PYTHON to a Python that can read it (for AML Triage Demo that
is its own .venv/bin/python); the default is the Python running this code.
"""
import json
import os
import subprocess
import sys

from . import config

RUNNER = config.DEMO_DIR / "amldemo" / "sqlrun.py"


class DatabaseError(RuntimeError):
    """The database could not be reached or the request could not be answered."""


def call(request, timeout=300):
    if config.AML_DB is None or not config.AML_DB.exists():
        raise DatabaseError("AML_DB is not set to an existing database file (the .duckdb of AML Triage Demo)")
    python = config.AML_DB_PYTHON or sys.executable
    try:
        done = subprocess.run([python, str(RUNNER)], input=json.dumps(request), capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "AML_DB": str(config.AML_DB)})
    except subprocess.TimeoutExpired as e:
        raise DatabaseError(f"the database call took longer than {timeout} seconds") from e
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as e:
        raise DatabaseError(f"the runner did not answer with JSON: {(done.stderr or done.stdout)[:300]}") from e


def run_query(sql, max_rows=10000, timeout=120):
    return call({"action": "run", "sql": sql, "max_rows": max_rows, "timeout": timeout}, timeout=timeout + 60)


def score(tx_ids):
    return call({"action": "score", "tx_ids": list(tx_ids)})


def population():
    return call({"action": "population"})


def sample_cases(seed, per_sources, max_alerts=12):
    return call({"action": "sample", "seed": seed, "per_sources": per_sources, "max_alerts": max_alerts})


def judge_accounts(accounts):
    return call({"action": "judge", "accounts": list(accounts)})


def sample_payments(seed, n_sources, count=1):
    return call({"action": "payments", "seed": seed, "n_sources": n_sources, "count": count})


def judge_payments(tx_ids):
    return call({"action": "judge_payments", "tx_ids": list(tx_ids)})
