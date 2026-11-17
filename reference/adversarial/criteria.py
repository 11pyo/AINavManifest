# -*- coding: utf-8 -*-
"""Print the pre-registered attack criteria and predictions as Markdown.

    python -m adversarial.criteria > adversarial/CRITERIA.md
"""
from .attacks import ARMS, ATTACKS, SIGNATURE_ATTACKS


def render() -> str:
    out = ["# Pre-registered attack criteria and predictions", "",
           "Fixed before any measurement (see README, Method). `success` = the effect was observed;",
           "`prompted-success` = observed only after the principal approved an ask that disclosed the action;",
           "`unprompted-success` = observed with no ask at all; `blocked` = effect not observed; `unknown` = no prediction.",
           "", "| ID | Attack | App. B | Start | Success criterion (oracle) | Standing | "
           + " | ".join(ARMS) + " | Expected blocking control(s) |",
           "|---|---|---|---|---|---|" + "---|" * len(ARMS) + "---|"]
    notes = []
    for a in ATTACKS:
        out.append(f"| {a.id} | {a.title} | {a.appendix_b or '-'} | `{a.start}` | {a.criterion} | "
                   f"{'yes' if a.standing else '-'} | " + " | ".join(a.expect[m] for m in ARMS)
                   + f" | {', '.join(a.ablation) or '-'} |")
        if a.note:
            notes.append(f"* **{a.id}**: {a.note}")
    out += ["", "## Section 6.1 signature attacks (registered after the JWS verifier was implemented, before they were measured)", "",
            "Run with `--set signature`. A key is designated for the site origin in the P arms unless the row says otherwise;",
            "N and S have no signature check by definition, so their cells are by-construction bounds.", "",
            "| ID | Attack | Start | Success criterion (oracle) | Standing | " + " | ".join(ARMS) + " | Expected blocking control(s) |",
            "|---|---|---|---|---|" + "---|" * len(ARMS) + "---|"]
    for a in SIGNATURE_ATTACKS:
        out.append(f"| {a.id} | {a.title} | `{a.start}` | {a.criterion} | {'yes' if a.standing else '-'} | "
                   + " | ".join(a.expect[m] for m in ARMS) + f" | {', '.join(a.ablation) or '-'} |")
        if a.note:
            notes.append(f"* **{a.id}**: {a.note}")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(render())
