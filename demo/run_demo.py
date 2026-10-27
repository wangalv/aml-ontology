"""Entry point for the demo. For now only the "build" step exists:

    ../.venv/bin/python run_demo.py build [--only s1|s2]

It maps each sample source to JSON-LD, validates it, and writes generated/*.jsonld and generated/*.ttl.
"""
import argparse
import json
import sys

from amldemo import adapters, config, jsonld_build, validate

SCENARIOS = {
    "s1": ("alert", "alert_source.json", adapters.alert_doc, "context_alert.jsonld"),
    "s2": ("case", "case_source.json", adapters.case_doc, "context_case.jsonld"),
}


def build(only=None):
    failed = False
    for key, (name, source_file, adapt, context_file) in SCENARIOS.items():
        if only and key != only:
            continue
        source = json.loads((config.SAMPLES_DIR / source_file).read_text(encoding="utf-8"))
        doc = jsonld_build.attach_context(adapt(source), jsonld_build.load_context(context_file))
        report = validate.validate_doc(doc)
        print(f"[{key}] {source_file} -> generated/{name}.jsonld : {'valid' if report.ok else 'INVALID'}")
        print(report.summary())
        if report.ok:
            jsonld_build.write_json(doc, config.GENERATED_DIR / f"{name}.jsonld")
            jsonld_build.to_graph(doc).serialize(destination=str(config.GENERATED_DIR / f"{name}.ttl"), format="turtle")
        failed = failed or not report.ok
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--only", choices=list(SCENARIOS))
    args = parser.parse_args()
    sys.exit(build(args.only))
