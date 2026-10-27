# AMLTRIX ontology + JSON-LD demo

Status: milestones M0 to M2 and M4 are done: dictionary lookup, JSON-LD building and validation for scenarios 1 and 2,
and scenario 1 end to end (a model suggests where to look, and only suggestions that validate are kept).
Scenario 1 does not query transaction data (the sample data is synthetic, so a data check would prove little).
Report narrative (scenario 2 with a model) and text-to-SQL (scenario 3) are not built yet.

## Run

```
cd demo
../.venv/bin/python run_demo.py build                          # sample sources -> validated JSON-LD and Turtle in generated/
../.venv/bin/python run_demo.py advise --compare --llm mock    # scenario 1 with canned answers, with and without the dictionary
../.venv/bin/python run_demo.py advise --compare --llm ollama  # the same with a model on this machine (default qwen3.5:9b)
../.venv/bin/python -m unittest discover -s tests              # tests; none of them calls a real model
```

Model settings go in `demo/.env` (git-ignored; copy `.env.example`). `mock` replays hand-written canned answers and is not a
model. `zai` (GLM) is written but has not been tried against the real API.

## What scenario 1 shows, and what it does not

Shown: given the dictionary, a model's suggestions can be checked by code (real ids, indicator belongs to the suspected
technique, data source is one AMLTRIX lists for it); without it, the same check rejects them.
Not shown: that the advice is good. Validation checks membership in the dictionary, not whether the reasoning fits the alert,
and a model given no dictionary could still give sensible advice in words that simply cannot be checked. One alert, one model
and one run is an illustration, not a measurement.

## Idea

AMLTRIX / AMLO is the single, read-only dictionary of AML techniques and indicators, pinned to one release.
Each business scenario maps its own JSON fields to the dictionary's IRIs with a JSON-LD `@context`;
an LLM then receives only the parts of the dictionary it needs, with identifiers that code can check.

## Planned scenarios

1. **Investigation advice**: alert and suspected technique, then a prioritised list of indicators to look into and where to look. No data is queried.
2. **Report narrative**: findings (technique, indicator, status), then a draft in which every paragraph cites a finding.
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

Environment variables: `AML_DB` (path to a read-only transaction database), `LLM_PROVIDER` (default `mock`),
`LLM_MODEL`, `LLM_API_KEY`. Nothing machine-specific is stored in the repository.

## Attribution

AMLTRIX content is used under the AMLTRIX License Terms (see the repository README and `vendor/amltrix/LICENSE.txt`).
