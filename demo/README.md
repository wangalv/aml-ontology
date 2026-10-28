# AMLTRIX ontology + JSON-LD demo

Status: milestones M0 to M2, M4 and M7 are done: dictionary lookup, JSON-LD building and validation for scenarios 1 and 2,
scenario 1 end to end (a model suggests where to look, and only suggestions that validate are kept), and scenario 2 end
to end (a model drafts the findings section of a report, and only paragraphs that cite real findings are kept).
Neither scenario queries transaction data (the sample data is synthetic, so a data check would prove little).
Text-to-SQL (scenario 3) is not built yet.

## Run

```
cd demo
../.venv/bin/python run_demo.py build                          # sample sources -> validated JSON-LD and Turtle in generated/
../.venv/bin/python run_demo.py advise --compare --llm mock    # scenario 1 with canned answers, with and without the dictionary
../.venv/bin/python run_demo.py advise --compare --llm ollama  # the same with a model on this machine (default qwen3.5:9b)
../.venv/bin/python run_demo.py report --compare --llm mock     # scenario 2 with canned answers, with and without the dictionary
../.venv/bin/python run_demo.py report --llm ollama             # scenario 2 with a model on this machine
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

Environment variables: `AML_DB` (path to a read-only transaction database), `LLM_PROVIDER` (default `mock`),
`LLM_MODEL`, `LLM_API_KEY`. Nothing machine-specific is stored in the repository.

## Attribution

AMLTRIX content is used under the AMLTRIX License Terms (see the repository README and `vendor/amltrix/LICENSE.txt`).
