"""Entry point for the demo.

    ../.venv/bin/python run_demo.py build [--only s1|s2]
    ../.venv/bin/python run_demo.py advise [--llm mock|ollama|zai] [--baseline | --compare]
    ../.venv/bin/python run_demo.py report [--llm mock|ollama|zai] [--baseline | --compare]

build   maps each sample source to JSON-LD, validates it, and writes generated/*.jsonld and generated/*.ttl.
advise  scenario 1: asks a model where an investigator should look first for the sample alert, using the
        AMLTRIX dictionary, and keeps only the suggestions that pass validation. --baseline withholds the
        dictionary; --compare runs both and counts what each gets wrong.
report  scenario 2: asks a model to draft the findings section of a report for the sample case, one paragraph per
        group of findings, and keeps only the paragraphs that cite real findings and mention only ids that belong
        to them. The draft is always marked as needing investigator review.
"""
import argparse
import json
import sys

from amldemo import adapters, config, jsonld_build, validate
from amldemo.llm import LLMError, make_llm
from amldemo.scenarios import s1_advisor, s2_report

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


def _show(result):
    label = "with the AMLTRIX dictionary" if result["with_dictionary"] else "WITHOUT the dictionary (baseline)"
    print(f"\n[s1] alert {result['alert_id']} ({result['technique']}), {label}; model: {result['provider']}/{result['model']}")
    print(f"  accepted {len(result['accepted'])}, rejected {len(result['rejected'])}")
    for a in result["accepted"]:
        print(f"  {a['priority']}. {a['indicator']}  look at {a['data_source']} {a['data_source_name']}")
        print(f"       {a['indicator_text'][:110]}")
        print(f"       why: {a['reason']}")
    for r in result["rejected"]:
        s = r["suggestion"] if isinstance(r["suggestion"], dict) else {}
        print(f"  REJECTED {s.get('indicator', '?')} / {s.get('data_source', '?')}")
        for problem in r["problems"]:
            print(f"       - {problem}")


def advise(provider, baseline, compare):
    alert = json.loads((config.SAMPLES_DIR / "alert_source.json").read_text(encoding="utf-8"))
    alert = {k: v for k, v in alert.items() if k != "checklist"}  # the model gets the alert, not the sample answer
    try:
        llm = make_llm(provider)
        modes = [True, False] if compare else [not baseline]
        results = [s1_advisor.advise(alert, llm, with_dictionary=m) for m in modes]
    except LLMError as e:
        print(f"[s1] LLM problem: {e}")
        return 1
    for result in results:
        _show(result)
    if compare:
        withd, without = results
        print(f"\n[s1] compare: rejected with dictionary = {len(withd['rejected'])} of {len(withd['accepted']) + len(withd['rejected'])}, "
              f"without = {len(without['rejected'])} of {len(without['accepted']) + len(without['rejected'])}")
    main = results[0]
    if main["with_dictionary"] and main["doc"] is not None:
        jsonld_build.write_json(main["doc"], config.GENERATED_DIR / "advice.jsonld")
        print("\n[s1] wrote generated/advice.jsonld (validated)")
    return 0


def _show_report(result):
    label = "with the AMLTRIX dictionary" if result["with_dictionary"] else "WITHOUT the dictionary (baseline)"
    print(f"\n[s2] case {result['case_id']}, {label}; model: {result['provider']}/{result['model']}")
    print(f"  accepted {len(result['accepted'])}, rejected {len(result['rejected'])}  ({result['review_status']})")
    for p in result["accepted"]:
        print(f"  {p['number']}. {p['text']}")
        print(f"       based on: {', '.join(p['based_on'])}")
    for r in result["rejected"]:
        text = r["paragraph"].get("text") if isinstance(r["paragraph"], dict) else None
        print(f"  REJECTED {(text or '(no text)')[:90]}")
        for problem in r["problems"]:
            print(f"       - {problem}")


def report(provider, baseline, compare):
    case = json.loads((config.SAMPLES_DIR / "case_source.json").read_text(encoding="utf-8"))
    case = {k: v for k, v in case.items() if k != "report_draft"}  # the model gets the findings, not the sample draft
    try:
        llm = make_llm(provider)
        modes = [True, False] if compare else [not baseline]
        results = [s2_report.draft_report(case, llm, with_dictionary=m) for m in modes]
    except LLMError as e:
        print(f"[s2] LLM problem: {e}")
        return 1
    for result in results:
        _show_report(result)
    if compare:
        withd, without = results
        print(f"\n[s2] compare: rejected with dictionary = {len(withd['rejected'])} of {len(withd['accepted']) + len(withd['rejected'])}, "
              f"without = {len(without['rejected'])} of {len(without['accepted']) + len(without['rejected'])}")
    main = results[0]
    if main["with_dictionary"] and main["doc"] is not None:
        jsonld_build.write_json(main["doc"], config.GENERATED_DIR / "report.jsonld")
        print("\n[s2] wrote generated/report.jsonld (validated)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "advise", "report"])
    parser.add_argument("--only", choices=list(SCENARIOS))
    parser.add_argument("--llm", choices=["mock", "ollama", "zai"], help="default: LLM_PROVIDER, else mock")
    parser.add_argument("--baseline", action="store_true", help="advise or report without giving the model the dictionary")
    parser.add_argument("--compare", action="store_true", help="advise or report with and without the dictionary")
    args = parser.parse_args()
    if args.command == "build":
        sys.exit(build(args.only))
    sys.exit((advise if args.command == "advise" else report)(args.llm, args.baseline, args.compare))
