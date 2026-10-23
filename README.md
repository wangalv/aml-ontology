# AML ontology (middle layer)

A worked example of turning the AMLTRIX money-laundering framework into a validated RDF ontology.

| Path | What it is |
|---|---|
| `ontology/amlo.ttl` | Hand-written schema (classes and properties) |
| `scripts/build_abox.py` | Converts the AMLTRIX CSV export into `data/amltrix.ttl` |
| `data/amltrix.ttl` | Generated instance data (about 78k triples) |
| `shapes/amlo-shapes.ttl` | SHACL integrity rules |
| `scripts/validate.py` | Validates the data, then proves the rules catch broken copies |
| `scripts/run_queries.py` | SPARQL competency questions |
| `vendor/amltrix/` | Unmodified AMLTRIX 1.0-beta.4 CSV export, licence and notice |

Run in order, from this folder:

```
.venv/bin/python scripts/build_abox.py
.venv/bin/python scripts/validate.py
.venv/bin/python scripts/run_queries.py
```

## Attribution

Instance data and examples are derived from **AMLTRIX** by UAB Amlyze
(<https://framework.amltrix.com>, data: <https://github.com/Amlyze/amltrix-data>), used under the
AMLTRIX License Terms (<https://framework.amltrix.com/license>, copy in `vendor/amltrix/LICENSE.txt`).
This work is a derivative and is not endorsed by AMLTRIX. Derivative works must keep this
attribution and be distributed under the same terms.

## Known source-data issues (AMLTRIX 1.0-beta.4)

- The ID `T0098` is assigned to two different techniques (Loan Schemes, Service Contract Manipulation).
  The converter keeps them as separate nodes, disambiguated by STIX UUID.
- The website says `T0020.002` was redefined as `T0150`; the CSV still lists it as Cryptojacking and has no `T0150`.
- The references table has 1,302 rows but only 74 have a name; it is not converted.
