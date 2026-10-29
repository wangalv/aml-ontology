"""Entry point for the demo.

    ../.venv/bin/python run_demo.py build [--only s1|s2]
    ../.venv/bin/python run_demo.py advise [--llm mock|ollama|zai] [--baseline | --compare]
    ../.venv/bin/python run_demo.py report [--llm mock|ollama|zai] [--baseline | --compare]
    ../.venv/bin/python run_demo.py hunt [--llm mock|ollama|zai] [--technique T0039]
    ../.venv/bin/python run_demo.py reason [--llm ollama|zai] [--seed s4] [--examples 1] [--resume]
    ../.venv/bin/python run_demo.py consolidate [--llm ollama|zai] [--sample 3:40] [--seed s4] [--examples N] [--compare] [--resume]

build   maps each sample source to JSON-LD, validates it, and writes generated/*.jsonld and generated/*.ttl.
advise  scenario 1: asks a model where an investigator should look first for the sample alert, using the
        AMLTRIX dictionary, and keeps only the suggestions that pass validation. --baseline withholds the
        dictionary; --compare runs both and counts what each gets wrong.
report  scenario 2: asks a model to draft the findings section of a report for the sample case, one paragraph per
        group of findings, and keeps only the paragraphs that cite real findings and mention only ids that belong
        to them. The draft is always marked as needing investigator review.
hunt    scenario 3: asks a model which indicators of a technique the payments table can show and to write a query for
        them; a guard checks the SQL, it runs read-only on the test period of the AML Triage Demo database (AML_DB, and
        AML_DB_PYTHON if that file needs a newer duckdb), and the labels judge it afterwards. Writes generated/hunt.json.
reason  scenario 4: takes payments that three monitoring systems all alerted on (the first one(s) in a fixed random order), builds the
        evidence each system gives (rule definition, ML score, verified cycle, the payment), and asks a model which AMLTRIX risk
        indicators that evidence supports, citing it. Code checks the citations, numbers and ids; the label judges afterwards. Needs
        a real model and the database. Writes generated/reason.json.
consolidate  the earlier, account-level version of scenario 4 (not shown on the pages): groups the alerts of the rule engine, the ML model and the graph check by account, asks a model for a
        note on each of a sample of those candidate cases (what each source says, how their alerts are linked), and
        judges the sample with the labels: link facts computed by code on the one hand, the model's agreement on the other. It needs a real model: there is no canned answer
        for it. Progress is saved in generated/cases.partial.json; --resume continues an interrupted run. Writes generated/cases.json.
"""
import argparse
import json
import sys

from amldemo import adapters, config, jsonld_build, validate
from amldemo.llm import LLMError, make_llm
from amldemo import dbrun
from amldemo.scenarios import s1_advisor, s2_report, s3_hunting, s4_cases, s4_reason

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


def _show_hunt(result):
    t = result["technique"]
    print(f"\n[s3] {t['id']} {t['name']}; model: {result['provider']}/{result['model']}")
    print("  coverage (can the payments table show this indicator?)")
    for c in result["coverage"]:
        flag = f"  [{'; '.join(c['problems'])}]" if c["problems"] else ""
        print(f"    {c['indicator']}  {c['queryable']:<12} {', '.join(c['columns'])}{flag}")
        print(f"        {c['reason']}")
    for q in result["queries"]:
        print(f"\n  query for {q['indicator']} ({q['queryable']}): {len(q['attempts'])} attempt(s), {'accepted' if q['accepted'] else 'NOT accepted'}")
        for n, a in enumerate(q["attempts"], start=1):
            print(f"    attempt {n}:\n      " + a["sql"].replace("\n", "\n      "))
            for problem in a["guard"]:
                print(f"      refused: {problem}")
            if a["run"]:
                print("      error: " + a["run"]["error"] if "error" in a["run"] else f"      ran: {a['run']['n_rows']} rows in {a['run']['seconds']} s")
        if q["evaluation"]:
            e, w = q["evaluation"], result["window"]
            print(f"    judged: {e['rows']} flagged payments, {e['laundering']} laundering; {e['in_verified_cycles']} lie in the verified round trips "
                  f"({w['in_verified_cycles']} exist in this period, {w['in_verified_cycles_laundering']} of them laundering)")


def hunt(provider, technique):
    try:
        llm = make_llm(provider)
        result = s3_hunting.hunt(technique, llm)
    except (LLMError, dbrun.DatabaseError) as e:
        print(f"[s3] problem: {e}")
        return 1
    _show_hunt(result)
    jsonld_build.write_json(result, config.GENERATED_DIR / "hunt.json")
    print("\n[s3] wrote generated/hunt.json")
    return 0


def reason(provider, seed, examples, resume):
    partial_path = config.GENERATED_DIR / "reason.partial.json"
    done = json.loads(partial_path.read_text(encoding="utf-8")) if resume and partial_path.exists() else {}

    def save(payment, result):
        done[str(payment["tx_id"])] = result
        jsonld_build.write_json(done, partial_path)
        print(f"  payment {payment['tx_id']} ({len(payment['sources'])} systems): judged", flush=True)

    try:
        result = s4_reason.run(make_llm(provider), seed, examples, done=done, on_payment=save)
    except (LLMError, dbrun.DatabaseError) as e:
        print(f"[s4] problem: {e}")
        return 1
    print(f"\n[s4] model: {result['provider']}/{result['model']}")
    for t in result["population"]["payments_by_sources"]:
        print(f"  payments alerted by {t['sources']} system(s): {t['payments']:>8,}, {t['laundering']:>5,} laundering ({_pct(t['laundering'], t['payments'])})")
    for payment, r in zip(result["payments"], result["results"]):
        print(f"\n  payment {payment['tx_id']}: laundering={result['labels'].get(str(payment['tx_id']))}")
        for e in r["evidence"]:
            print(f"    {e['id']} [{e['kind']}] {e['text'][:120]}")
        print("    technique        " + "  ".join(f"{k:<8}" for k in s4_reason.LANES))
        for row in s4_reason.lamps(r):
            print(f"    {row['id']} {row['name'][:22]:<22} " + "  ".join(f"{row['cells'][k]['state']:<8}" for k in s4_reason.LANES)
                  + ("   <- more than one system" if len(row["systems"]) > 1 else ""))
        for kind in s4_reason.LANES:
            lane = r["lanes"][kind]
            for m in (lane["note"] or {"matches": []})["matches"]:
                print(f"    {kind}: {m['indicator']} ({m['support']}, {m['technique']['id'] if m['technique'] else '?'}): {m['reason']}")
            if lane["skipped"]:
                print(f"    {kind}: not judged: {lane['skipped']}")
            elif not lane["note"]:
                print(f"    {kind}: no accepted note: " + "; ".join(p for a in lane["attempts"] for p in a["problems"]))
    jsonld_build.write_json(result, config.GENERATED_DIR / "reason.json")
    print("\n[s4] wrote generated/reason.json")
    return 0


def _pct(part, whole):
    return f"{100 * part / whole:.2f}%" if whole else "-"


def _show_cases(r):
    pop, ev = r["population"], r["evaluation"]
    print(f"\n[s4] {pop['payments']['alerted']:,} alerted payments touch {pop['accounts']:,} accounts "
          f"({pop['laundering_accounts']:,} hold a laundering payment); model: {r['provider']}/{r['model']}")
    print("  all accounts, by how many sources alerted")
    for t in pop["by_sources"]:
        print(f"    {t['sources']} source(s): {t['accounts']:>7,} accounts, {t['laundering']:>5,} laundering ({_pct(t['laundering'], t['accounts'])})")
    print("  link facts of the 3-source accounts (computed by code, no model)")
    for f in pop["linkage"]["facts"]:
        yes, no = f["present"], f["absent"]
        print(f"    {f['text']:<62} yes: {yes['accounts']:>3} accounts, {_pct(yes['laundering'], yes['accounts']):>7} laundering;"
              f" no: {no['accounts']:>3}, {_pct(no['laundering'], no['accounts']):>7}")
    if ev is None:
        for c, consulted in zip(r["cases"], r["consults"]):
            print(f"  example {c['account']} ({c['links']['class']}): laundering={r['labels'][c['account']]}; "
                  f"note {'accepted' if consulted['note'] else 'not accepted'}")
        return
    print(f"  sample of {ev['cases']} accounts ({ev['laundering']} laundering); notes accepted {ev['notes']['accepted']}, "
          f"not accepted {ev['notes']['not_accepted']}")
    for title, key in (("by link class (code)", "by_class"), ("by agreement (model)", "by_agreement")):
        print(f"  {title}")
        for name, tally in ev[key].items():
            print(f"    {name:<14} {tally['cases']:>3} accounts, {tally['laundering']:>2} laundering")


def consolidate(provider, sample, seed, resume, examples, compare):
    per_sources = {k: int(v) for k, v in (part.split(":") for part in sample.split(","))}
    partial_path = config.GENERATED_DIR / "cases.partial.json"
    done = {}
    if resume and partial_path.exists():
        done = json.loads(partial_path.read_text(encoding="utf-8"))
        print(f"[s4] resuming with {len(done)} notes already written")

    def save(key, case, result):
        done[key] = result
        jsonld_build.write_json(done, partial_path)
        note = result["note"]
        print(f"  {len(done):>3}. {key} ({case['n_sources']} source(s), {case['links']['class']}): "
              + (f"agreement {note['agreement']}" if note else "no usable note"), flush=True)

    try:
        llm = make_llm(provider)
        result = s4_cases.run(llm, per_sources, seed, done=done, on_case=save, examples_per_class=examples, compare=compare)
    except (LLMError, dbrun.DatabaseError) as e:
        print(f"[s4] problem: {e}")
        return 1
    _show_cases(result)
    jsonld_build.write_json(result, config.GENERATED_DIR / "cases.json")
    print("\n[s4] wrote generated/cases.json")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "advise", "report", "hunt", "consolidate", "reason"])
    parser.add_argument("--only", choices=list(SCENARIOS))
    parser.add_argument("--llm", choices=["mock", "ollama", "zai"], help="default: LLM_PROVIDER, else mock")
    parser.add_argument("--technique", default="T0039", help="hunt: the AMLTRIX technique to turn into queries")
    parser.add_argument("--sample", default="3:40", help="consolidate: accounts to sample, as sources:count pairs")
    parser.add_argument("--examples", type=int, default=0, help="consolidate: write notes only for the first N cases of each link class")
    parser.add_argument("--seed", default="s4", help="consolidate: seed of the sample")
    parser.add_argument("--resume", action="store_true", help="consolidate: reuse the notes saved by an interrupted run")
    parser.add_argument("--baseline", action="store_true", help="advise or report without giving the model the dictionary")
    parser.add_argument("--compare", action="store_true", help="advise or report with and without the dictionary; consolidate: each example also without the AMLTRIX techniques")
    args = parser.parse_args()
    if args.command == "build":
        sys.exit(build(args.only))
    if args.command == "hunt":
        sys.exit(hunt(args.llm, args.technique))
    if args.command == "reason":
        sys.exit(reason(args.llm, args.seed, args.examples or 1, args.resume))
    if args.command == "consolidate":
        sys.exit(consolidate(args.llm, args.sample, args.seed, args.resume, args.examples, args.compare))
    sys.exit((advise if args.command == "advise" else report)(args.llm, args.baseline, args.compare))
