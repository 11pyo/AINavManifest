# -*- coding: utf-8 -*-
"""Print the pre-registered attack criteria and predictions as Markdown.

    python -m adversarial.criteria > adversarial/CRITERIA.md
"""
from .attacks import ARMS, ATTACKS


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
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(render())
