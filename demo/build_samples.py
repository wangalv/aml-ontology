# -*- coding: utf-8 -*-
"""Write samples/alert_source.json and samples/case_source.json from the payment of scenario 4.

Scenarios 1 and 2 used to run on a hand-written alert of five fields. They now run on the same payment as scenario 4, so
that the alert carries what a monitoring system really attaches: the rule flags, the model score, the cycle with the amount
of every payment, and the payment itself. The facts are copied from generated/reason.json (written by `run_demo.py reason`);
nothing is invented here except the wording of the sample checklist, the findings and the report draft, which stand in for
what a source system or an investigator would have written. The payment is in the synthetic IBM AML data.

    python3 build_samples.py
"""
import json
from pathlib import Path

DEMO = Path(__file__).resolve().parent
REASON = DEMO / "generated" / "reason.json"


def build(reason):
    payment = reason["payments"][0]
    evidence = next(r for r in reason["results"] if r["tx_id"] == payment["tx_id"])["evidence"]
    cycle = payment["cycle"]
    tx = payment["tx_id"]
    first, last = cycle["legs"][0], cycle["legs"][-1]
    when = payment["ts"].replace(" ", "T") + "Z"

    alert = {
        "alert_id": f"ALT-{tx}",
        "raised_at": when,
        "trigger_reason": (f"Graph analysis: payment {tx} closes a verified time-ordered cycle of {len(cycle['legs'])} payments "
                           f"that returns to the originating account within {cycle['span_days']} days"),
        "suspected_technique": "T0039",
        "facts": [e["text"] for e in evidence],
        "evidence": [{"evidence_id": f"EV-TXLOG-{tx}", "record_type": "DS0019"}],
        "checklist": [
            {"item_id": f"CHK-{tx}-1", "indicator": "IND02191", "priority": 1,
             "reason": "The graph found a verified cycle that returns to the originating account, which is the core of this indicator.",
             "suggested_data_source": "DS0019"},
            {"item_id": f"CHK-{tx}-2", "indicator": "IND02194", "priority": 2,
             "reason": "Three accounts form the ring, which raises the question of who owns them and when they were opened.",
             "suggested_data_source": "DS0039"},
            {"item_id": f"CHK-{tx}-3", "indicator": "IND02195", "priority": 3,
             "reason": "The payment currency is Ruble, which the rule engine treats as a high-risk jurisdiction proxy; the routing of the ring is worth checking.",
             "suggested_data_source": "DS0047"},
        ],
    }

    legs = "; ".join(f"{leg['from']} to {leg['to']} {leg['amount']:,.2f}" for leg in cycle["legs"])
    case = {
        "case_id": f"CASE-{tx}",
        "opened_at": when.replace(when[11:], "23:59:00Z"),
        "hypothesis": ["T0039"],
        "evidence": [{"evidence_id": f"EV-TXLOG-{tx}", "record_type": "DS0019"}],
        "findings": [
            {"finding_id": "F-1", "technique": "T0039", "indicator": "IND02191", "status": "supported",
             "observation": (f"In the transaction log, {len(cycle['legs'])} payments take funds from {first['from']} through "
                             f"{len(cycle['accounts']) - 2} other accounts and back to it within {cycle['span_days']} days: {legs}."),
             "supported_by": [f"EV-TXLOG-{tx}"]},
            {"finding_id": "F-2", "technique": "T0039", "indicator": "IND02194", "status": "not-assessable",
             "observation": "Ownership and onboarding records were not part of this case's evidence, so this indicator was not assessed."},
            {"finding_id": "F-3", "technique": "T0039", "indicator": "IND02195", "status": "not-assessable",
             "observation": (f"The payment currency is {payment['currency']}, which the rule engine treats as a proxy for a high-risk country, "
                             "but the data has no country field, so cross-border routing could not be assessed.")},
        ],
        "report_draft": {
            "draft_id": f"RD-{tx}",
            "review_status": "draft, requires investigator review",
            "paragraphs": [
                {"text": (f"Transaction records show funds leaving account {first['from']} and returning to it within {cycle['span_days']} days, "
                          f"consistent with Circular Transactions (T0039) and indicator IND02191; the last payment is {last['amount']:,.2f} {payment['currency']}."),
                 "based_on": ["F-1"]},
                {"text": "Indicators IND02194 and IND02195 could not be assessed, because ownership records and country data were not available.",
                 "based_on": ["F-2", "F-3"]},
            ],
        },
    }
    return alert, case


def main():
    reason = json.loads(REASON.read_text(encoding="utf-8"))
    alert, case = build(reason)
    for name, doc in (("alert_source.json", alert), ("case_source.json", case)):
        (DEMO / "samples" / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", DEMO / "samples" / name)


if __name__ == "__main__":
    main()
