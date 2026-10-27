# AMLTRIX ontology + JSON-LD demo

Status: milestones M0 to M2 are done: dictionary lookup, and JSON-LD building and validation for scenarios 1 and 2.
The checks that run SQL, the scenario logic and the text-to-SQL scenario are not built yet.

## Run

```
cd demo
../.venv/bin/python run_demo.py build                 # sample sources -> validated JSON-LD and Turtle in generated/
../.venv/bin/python -m unittest discover -s tests     # 37 tests
```

## Idea

AMLTRIX / AMLO is the single, read-only dictionary of AML techniques and indicators, pinned to one release.
Each business scenario maps its own JSON fields to the dictionary's IRIs with a JSON-LD `@context`;
an LLM then receives only the parts of the dictionary it needs, with identifiers that code can check.

## Planned scenarios

1. **Investigation advice**: alert and suspected technique, then an indicator checklist, then checks run on the data.
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
