# AMLTRIX ontology + JSON-LD demo

Status: milestones M0 to M2, M4 and M7 are done: dictionary lookup, JSON-LD building and validation for scenarios 1 and 2,
scenario 1 end to end (a model suggests where to look, and only suggestions that validate are kept), and scenario 2 end
to end (a model drafts the findings section of a report, and only paragraphs that cite real findings are kept).
Neither scenario queries transaction data (the sample data is synthetic, so a data check would prove little).
Scenario 3 (text-to-SQL) and scenario 4 (why monitoring systems alerted on a payment) read the AML Triage
Demo database. On the pages, scenarios 1 to 3 are the Investigation agent and scenario 4 is the Identification agent.

## Run

```
cd demo
../.venv/bin/python run_demo.py build                          # sample sources -> validated JSON-LD and Turtle in generated/
../.venv/bin/python run_demo.py advise --compare --llm mock    # scenario 1 with canned answers, with and without the dictionary
../.venv/bin/python run_demo.py advise --compare --llm ollama  # the same with a model on this machine (default qwen3.5:9b)
../.venv/bin/python run_demo.py report --compare --llm mock     # scenario 2 with canned answers, with and without the dictionary
../.venv/bin/python run_demo.py report --llm ollama             # scenario 2 with a model on this machine
AML_DB=... AML_DB_PYTHON=... ../.venv/bin/python run_demo.py hunt --llm ollama   # scenario 3; needs the transaction database (see below)
AML_DB=... AML_DB_PYTHON=... ../.venv/bin/python run_demo.py reason --llm ollama   # scenario 4; needs the database
../.venv/bin/python -m unittest discover -s tests              # tests; none of them calls a real model or opens the database
```

Model settings go in `demo/.env` (git-ignored; copy `.env.example`). `mock` replays hand-written canned answers and is not a
model. `zai` (GLM) is written but has not been tried against the real API.

## What scenario 1 shows, and what it does not

Shown: given the dictionary, a model's suggestions can be checked by code (real ids, indicator belongs to the suspected
technique, data source is one AMLTRIX lists for it); without it, the same check rejects them.
Not shown: that the advice is good. Validation checks membership in the dictionary, not whether the reasoning fits the alert,
and a model given no dictionary could still give sensible advice in words that simply cannot be checked. One alert, one model
and one run is an illustration, not a measurement.

## What scenario 2 shows, and what it does not

Shown: the model gets the case's findings and what the dictionary says about the technique and indicators, and writes
the findings section of a report. Each paragraph must name the findings it rests on. Code keeps a paragraph only if it
cites at least one finding, every cited finding is a finding of this case, and every technique or indicator id it
mentions belongs to the findings it cites. A reviewer can trace each paragraph to a finding, and each finding to its
evidence and to the dictionary. The draft is always marked as needing investigator review.
Not shown: that the wording is faithful. Code does not check that "5.2 days" in a paragraph matches the finding, or
that a "not assessed" finding is not written up as established. The sample run on a local model (qwen3.5:9b, one case,
one run) had no rejected paragraphs with or without the dictionary, so the checks did not matter for that model; the
difference was that with the dictionary the text used the indicator's own definition. One paragraph also added
"lacks a legitimate business rationale", which comes from the dictionary's definition, not from the finding.
The canned baseline shows what the checks catch if a model does make those mistakes; it is not evidence about any model.

## What scenario 4 shows, and what it does not

A payment that several monitoring systems alerted on (a rule engine, an ML model, a graph check) carries a reason from each, in its own
terms. `scenarios/s4_reason.py` builds each system's evidence from the data (`sqlrun.py` action `payments`): the fired rule flags with the
rule's own definition, the ML score (it names no reason), the verified cycle with its legs and amounts, and the payment itself. The model
is given the AMLTRIX techniques that the payment's flags point to (`mapping/alert_sources.json`, the draft typology mapping) with their risk
indicators, and is asked, **for each system's evidence on its own** (`explain_lanes`), which indicators that evidence supports, citing it.
The ML model is not asked: a score with no reason is nothing to judge. `lamps()` then reads off, for each technique and each system,
whether that system's evidence supports one of its indicators, and whether the system's own flag points to that technique. A technique lit
by more than one system is one that independent systems agree on. Code checks each note: every indicator was listed, every match cites
evidence that exists, the numbers and dollar amounts in a reason (digits, and number words such as "four payments") appear in the evidence
it cites, technique ids were listed; a failed note is sent back once. The label is used only afterwards.
Run: `run_demo.py reason --llm ollama`; result: `generated/reason.json`. The pages show it as one diagram (systems on the left, LLM + AMLTRIX
in the middle, a matrix of lamps on the right; `ontology/s4_diagram.py` in AML Triage Demo draws it from the saved result; resting on a lamp shows
the model's reason, and clicking a technique shows it in the AML typology, with the same detail and relationship graph as the AML typology box).

- **Shown:** the figures by number of systems are computed by code with no model: of the payments alerted on by all three systems (64 in the
  test period), 50% are laundering, against 0.14% of those only one system alerted on.
- **One payment, one run (qwen3.5:9b):** T0011 (Money Mule Exploitation) is lit by the rule engine and by the graph check, T0039 by the
  graph, T0141 partly by the rule engine, T0083 by none. Only the rule engine's own flag points to T0011; the graph's lamp is the model's
  reading of the cycle's evidence, and its reason ("rapidly moving funds") does not hold up against the dates in the evidence (a 6.92-day
  cycle), and another graph reason speaks of cross-border transfers where the evidence says cross-currency no. The checks cannot catch
  that (they check ids, citations and numbers, not what a reason claims); the pages say so in the line on what is not checked, and carry no
  reviewer's notes. The example payment is not laundering.
- **Not shown:** that a lamp lit by two systems means more than a lamp lit by one (one payment; the 50% figure above is about the number of
  systems that alerted, not about the lamps), that the indicators are the true reason for the alert (the rules are code and their reason is
  known; this restates it in AMLTRIX terms), that it works across payments, or that the ontology improves anything (no run without the
  indicators: without them there is nothing to judge).
- Earlier versions of scenario 4 are kept but not shown: one request with all the evidence (`explain`), and an account-level version
  (`scenarios/s4_cases.py`, `run_demo.py consolidate`, the account actions in `sqlrun.py`) with link facts computed by code. A version that
  asked the model for a route (priority, standard, defer) gave priority to 73 of 100 accounts and found no more laundering than a ranking
  by number of systems, and was dropped.
- The model window is set to 16,384 tokens (`num_ctx`) because the prompt lists many indicators; the default would cut it off.

## What scenario 3 shows, and what it does not

Shown on the Investigation agent page (third scenario): an investigator working a case picks a technique to test, a hunting task rather
than monitoring, which is why it is not under the Identification agent.

The model is given a technique (default T0039 Circular Transactions), its indicators, and a data dictionary of one table of payments,
and does two things: says which indicators that table can show at all, and writes a query for the ones it says it can.
Code does the rest: `sqlguard.py` refuses anything that is not one read-only SELECT over the listed columns, with a LIMIT, a `tx_id`
column and the time column; a refused or failing query goes back to the model with the reason, up to three attempts; an accepted query
runs read-only and is judged with the labels, which the model never sees. Result: `generated/hunt.json`.

- **The database is not copied.** `AML_DB` points at AML Triage Demo's `data/features.duckdb`. Only `amldemo/sqlrun.py` opens it, as
  a subprocess; if the file was written by a newer DuckDB than this environment has (it was: file format 999 vs this venv's duckdb 1.4.5,
  Python 3.9), `AML_DB_PYTHON` names a Python that can read it. The queries run on a view `txs` of the test period (not the tail) that
  holds only the columns in `mapping/data_dictionary.json`: no label, no round-trip flag, no rule flags, no whole-dataset degrees.
- **One example query is in the dictionary**, for a different and simpler pattern (money passed on within an hour). Without it the first run
  of qwen3.5:9b returned account ids under the name `tx_id` and ignored the refusals. With it, it writes queries that run.
- **The saved real run (qwen3.5:9b, one run) is a failure, shown as such.** It correctly says only IND02191 can really be seen in a table of
  payments (it also says yes to IND02195, which a payments table can only approximate). Its query for IND02191 follows chains of three or more
  payments but never checks that the money returns to where it started, so it flags 10,000 payments (the LIMIT) of which 0.11% are laundering,
  the same as any payment, and finds none of the 107 payments in verified round trips. Its query for IND02195 never gets past the guard: it
  resubmits the same query three times. The guard says a query is safe, not that it is right; the judging step is what shows the difference.
- **What the pages show:** one thread, from the investigator's intent to SQL: the technique and the indicator (AML typology), the data
  dictionary as the link between the indicator's words and the table's columns (`data_dictionary.json`, including a `data_source` field that
  names the AMLTRIX data source the table stands for, a draft by people), and the query that passed the guard and ran (IND02191), each part
  of it with the words of the indicator it is said to come from and the columns it uses. The refused attempts, the query that never passed
  the guard (IND02195), the coverage table and the rest are not displayed or exported; the full run stays in `generated/hunt.json`.
- **Not shown:** that a stronger model would do better (only qwen3.5:9b is installed; the GLM key is not set), that the typology helps (no
  with/without comparison), or anything about real data (the dataset is synthetic and the period is about two and a half days).
- The quotes a model gives for each part of its SQL are checked against the indicator text: a quote that is not in the indicator is flagged.

## Idea

AMLTRIX / AMLO is the single, read-only dictionary of AML techniques and indicators, pinned to one release.
Each business scenario maps its own JSON fields to the dictionary's IRIs with a JSON-LD `@context`;
an LLM then receives only the parts of the dictionary it needs, with identifiers that code can check.

## Planned scenarios

1. **Investigation advice**: alert and suspected technique, then a prioritised list of indicators to look into and where to look. No data is queried.
2. **Report narrative**: findings (technique, indicator, status), then a draft in which every paragraph cites a finding. Draft only; the investigator reviews it.
3. **Typology-driven text-to-SQL**: technique, then generated SQL, then execution, then evaluation against labels.

## Layout

| Path | Purpose |
|---|---|
| `amldemo/` | Python package: `config`, `ontology`, `lookup`, `adapters`, `jsonld_build`, `validate` |
| `mapping/` | JSON-LD contexts and mapping tables |
| `vocab/`, `shapes/` | Investigation Ontology (Demo) and its SHACL shapes. An extension, not part of AMLO |
| `samples/` | Synthetic source data |
| `queries/` | SPARQL queries |
| `generated/` | Output, not committed |
| `docs/`, `tests/` | Documentation and tests |

The dictionary under `ontology/` and `data/` is read-only for the demo.

## Configuration

Environment variables: `AML_DB` (path to a read-only transaction database), `AML_DB_PYTHON` (a Python whose duckdb can read it), `LLM_PROVIDER` (default `mock`),
`LLM_MODEL`, `LLM_API_KEY`. Nothing machine-specific is stored in the repository.

## Attribution

AMLTRIX content is used under the AMLTRIX License Terms (see the repository README and `vendor/amltrix/LICENSE.txt`).
