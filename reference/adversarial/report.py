# -*- coding: utf-8 -*-
"""Build result tables from adversarial/results/{main,ablation}.jsonl.

    python -m adversarial.report            # writes matrix.csv, matrix.json, SUMMARY.md next to the jsonl files
"""
import csv
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

from .attacks import ARMS, ATTACKS, BY_ID

RES = Path(__file__).resolve().parent / "results"
SUCCESS = ("success", "prompted-success", "unprompted-success")
NO_SITE_EFFECT = ("A17", "A18")


def load(name):
    p = RES / f"{name}.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def cells(rows):
    """(attack, arm, ablation) -> list of cell values over repeats."""
    d = OrderedDict()
    for r in rows:
        d.setdefault((r["attack"], r["arm"], r["ablation"]), []).append(r)
    return d


def asr(main, arm, exclude=()):
    ids = [a.id for a in ATTACKS if a.id not in exclude]
    c = cells(main)
    cnt = Counter()
    for i in ids:
        runs = c.get((i, arm, None))
        if not runs:
            continue
        v = runs[0]["cell"]
        cnt["n"] += 1
        cnt["any"] += v in SUCCESS
        cnt["prompted"] += v == "prompted-success"
        cnt["unprompted"] += v == "unprompted-success"
    return cnt


def pct(x, n):
    return f"{x}/{n} ({100 * x / n:.0f}%)" if n else "-"


def build():
    main, abl = load("main"), load("ablation")
    mc = cells(main)
    out = {"matrix": [], "nondeterministic": [], "mismatches": [], "ablation": []}
    # ---- matrix
    with (RES / "matrix.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["attack", "title"] + [x for a in ARMS for x in (a, a + " predicted")] + ["canary_leak(N|S|P)", "deterministic"])
        for a in ATTACKS:
            row, det = [a.id, a.title], True
            leaks = []
            for arm in ARMS:
                runs = mc.get((a.id, arm, None), [])
                vals = [r["cell"] for r in runs]
                if len(set(vals)) > 1:
                    det = False
                    out["nondeterministic"].append((a.id, arm, vals))
                row += [vals[0] if vals else "not-run", a.expect[arm]]
                leaks.append(any(r["canary_leak"] for r in runs))
                for r in runs[:1]:
                    if r["status"] == "MISMATCH":
                        out["mismatches"].append((a.id, arm, r["cell"], a.expect[arm]))
                out["matrix"].append({"attack": a.id, "arm": arm, "values": vals, "predicted": a.expect[arm],
                                      "status": runs[0]["status"] if runs else None})
            row += ["|".join("Y" if x else "n" for x in leaks), "yes" if det else "NO"]
            w.writerow(row)
    (RES / "matrix.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- summary
    L = ["# Adversarial evaluation: results", "",
         "Source: `results/main.jsonl` (4 arms, repeated) and `results/ablation.jsonl` (P-careless with one control off).",
         "Predictions were registered before measurement in `CRITERIA.md`; wrong predictions stay in the table as MISMATCH.", "",
         "> **Reading the N and S columns.** The compliant-model stand-in is built to follow any instruction it sees, so",
         "> N and S are *by-construction upper bounds*, not evidence. The informative columns are P-deny, P-careless",
         "> and the ablation table. No LLM was involved anywhere (see README, Limits).", "",
         "## 1. Attack success rate (ASR) per arm", "",
         f"{len(ATTACKS)} attacks. `any` = prompted + unprompted. A07a/A07b need a standing approval; they are also shown separately.", "",
         "| Arm | ASR any | prompted-success | unprompted-success | any, excluding A07a/A07b | side-effect ASR | side-effect ASR, excluding A07a/A07b |",
         "|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        c, c2 = asr(main, arm), asr(main, arm, ("A07a", "A07b"))
        e1, e2 = asr(main, arm, NO_SITE_EFFECT), asr(main, arm, NO_SITE_EFFECT + ("A07a", "A07b"))
        tail = f" {pct(e1['any'], e1['n'])} | {pct(e2['any'], e2['n'])} |"
        if arm in ("N", "S"):
            L.append(f"| {arm} | {pct(c['any'], c['n'])} | n/a | n/a | {pct(c2['any'], c2['n'])} |{tail}")
        else:
            L.append(f"| {arm} | {pct(c['any'], c['n'])} | {pct(c['prompted'], c['n'])} | {pct(c['unprompted'], c['n'])} "
                     f"| {pct(c2['any'], c2['n'])} |{tail}")
    L += ["", "`side-effect ASR` leaves out A17 (loss of availability: the agent dies) and A18 (a long wait: resource use);",
          "neither is a side effect on the site. The `any` columns are unchanged."]
    L += ["", "P-deny and P-careless are separate columns on purpose: P-careless is the ceiling of what the PEP alone",
          "stops when the person approves every ask; P-deny is the floor.", ""]

    L += ["## 2. Per-attack cells", "",
          "| ID | Attack | N | S | P-deny | P-careless | predicted (N/S/P-deny/P-careless) | status | canary reached model (N/S/P) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for a in ATTACKS:
        vals = [(mc.get((a.id, arm, None)) or [{"cell": "not-run", "status": ""}])[0] for arm in ARMS]
        st = ",".join(sorted({v["status"] for v in vals[2:] if v["status"] and v["status"] != "match"})) or "match"
        leaks = ["Y" if any(r["canary_leak"] for r in mc.get((a.id, arm, None), [])) else "n" for arm in ("N", "S", "P-deny")]
        L.append(f"| {a.id} | {a.title} | " + " | ".join(v["cell"] for v in vals) + " | "
                 + "/".join(a.expect[x] for x in ARMS) + f" | {st} | {'/'.join(leaks)} |")
    L.append("")

    L += ["## 3. Prediction mismatches and non-deterministic cells", ""]
    L.append("Mismatches (MISMATCH, prediction left as registered): " +
             (", ".join(f"{i} {arm}: got {got}, predicted {pred}" for i, arm, got, pred in out["mismatches"]) or "none") + ".")
    nd = out["nondeterministic"]
    L.append("Cells whose value changed between repeats: " + (", ".join(f"{i}/{arm} {v}" for i, arm, v in nd) or "none (deterministic over all repeats)") + ".")
    reps = max((len(v) for v in mc.values()), default=0)
    L += [f"Repeats per cell: {reps}.", ""]

    CAUSES = {
        ("A19", "S"): "prediction error: Section 4.1 makes a validator ignore removed/unknown members, it does not reject; "
                      "the success comes from the well-formed click trap, not from the self-declared members",
        ("A19", "P-careless"): "prediction error, same cause as A19/S; the registered 'blocked' ignored that the trap is an "
                               "ordinary click (ask, approved)",
        ("A20", "S"): "prediction error / malformed attack: the signature is an object, the schema wants a detached-JWS "
                      "string, so the whole manifest is rejected; A20b repeats the attack with a valid shape",
        ("A20", "P-careless"): "same as A20/S",
        ("A17", "N"): "implementation defect (Section 3.5 MUST: failure to validate = baseline behaviour) + specification gap "
                      "(Section 3.5 sets no nesting-depth limit); RecursionError escapes parse_i_json/discover",
        ("A17", "S"): "same as A17/N", ("A17", "P-deny"): "same as A17/N", ("A17", "P-careless"): "same as A17/N",
        ("A07a", "P-deny"): "no prediction error: known residual risk of a standing approval, and an internal tension "
                            "(Section 5.2 allows a standing approval of Enter; Section 5.3 requires confirming purchases whatever approvals exist, "
                            "and admits the PEP cannot judge effects)",
        ("A07b", "P-deny"): "no prediction: same tension as A07a; this form holds no personal data or password, so Section 5.3's "
                            "first item does not apply",
        ("A10", "N"): "no prediction: javascript:/data: navigation executed by an unguarded agent",
    }
    L += ["### Prediction mismatches, defects and unpredicted cells, with cause", "",
          "| ID | Arm | Observed | Registered prediction | Status | Cause class |", "|---|---|---|---|---|---|"]
    seen = set()
    for r in main:
        k = (r["attack"], r["arm"])
        if k in seen or not (r["status"].startswith("MISMATCH") or r["status"] in ("defect-confirmed", "no-prediction")):
            continue
        seen.add(k)
        cause = CAUSES.get(k) or CAUSES.get((r["attack"], "P-deny" if r["arm"].startswith("P") else r["arm"]), "unclassified")
        L.append(f"| {k[0]} | {k[1]} | {r['cell']} | {BY_ID[k[0]].expect[k[1]]} | {r['status']} | {cause} |")
    L.append("")
    eq = []
    for arm in ARMS:
        x = (mc.get(("A19", arm, None)) or [None])[0]
        y = (mc.get(("A19c", arm, None)) or [None])[0]
        if x and y:
            eq.append(f"{arm}: A19 {x['cell']} / {len(x['asks'])} ask(s), A19c {y['cell']} / {len(y['asks'])} ask(s)"
                      f" -> {'same' if (x['cell'], len(x['asks'])) == (y['cell'], len(y['asks'])) else 'DIFFERENT'}")
    L += ["**A19 vs control A19c (do self-declared trust members change anything?)** " + "; ".join(eq) + ".", ""]
    leak = {arm: sum(1 for r in main if r["arm"] == arm and r["canary_leak"]) for arm in ARMS}
    tot = {arm: sum(1 for r in main if r["arm"] == arm) for arm in ARMS}
    L += ["**Canary (manifest string reached the model), runs with a leak / runs:** " +
          ", ".join(f"{a} {leak[a]}/{tot[a]}" for a in ARMS) + ". In P arms the model sees only closed-vocabulary values.", "",
          "**Notes on reading the table**", "",
          "* A17 is counted as a success in every arm because the oracle is 'an exception escaped discovery'; it is a",
          "  loss of availability (the agent dies), not a side effect on the site. It is reported separately as a defect.",
          "* A13 (invisible overlay): blocked in the P arms by the adapter's Playwright hit-target check, not by a PEP",
          "  rule. Section 4.2 requires exactly one *rendered* element but no hit test: an implementation-dependent defence,",
          "  a specification gap candidate for -04.",
          "* A07a/A07b (standing approval of Enter) are the only P-deny successes besides A17. They are a known residual risk",
          "  and also an internal tension of the draft: Section 5.2 permits the standing approval, Section 5.3 requires",
          "  confirmation of purchases regardless, and Section 5.3 admits the PEP cannot judge effects. Recorded, not changed.",
          "* A08/A24 (native dialogs) stay blocked even when the security-control stop is switched off: the agent never",
          "  accepts a dialog, so the dialog simply stays open. A09-A11, A14, A16, A28, A29 are contained by the validator",
          "  AND, for navigation targets, by the PEP's own target check (defence in depth), so switching one off does not flip them.",
          "* A15 does not flip when the discovery redirect refusal is switched off: the redirected manifest names the",
          "  attacker's origin, and the PEP's own origin check (document-not-same-origin) still denies every step.",
          "* A19 does not flip with descriptor validation off: the self-declared members have no effect either way (see A19c).",
          "* Pre-registered expectations in the last column of the ablation list that did not materialise are kept as registered",
          "  and explained here; they are defence in depth, not errors in the controls.",
          "", ""]

    # ---- prompted successes
    L += ["## 4. What the principal was shown before each prompted success (P-careless)", "",
          "`names effect` is a pre-registered keyword proxy (`EFFECT_TERMS` in `attacks.py`) for 'the display",
          "named the effect'; it is not a human-factors judgement.", "",
          "| ID | Ask display (first ask) | list shown for choosing | names effect |", "|---|---|---|---|"]
    for a in ATTACKS:
        r = (mc.get((a.id, "P-careless", None)) or [None])[0]
        if r and r["cell"] == "prompted-success":
            ask = " / ".join(r["asks"][0]) if r["asks"] else "-"
            ch = "; ".join(", ".join(c) for c in r["choices"]) or "-"
            L.append(f"| {a.id} | {ask.replace('|', '/')} | {ch.replace('|', '/')} | {'unregistered' if r['discloses'] is None else r['discloses']} |")
    L += ["", "Where Enter causes the side effect (A06, A27) the ask shows only the element and the warning that the page can",
          "bind any effect to Enter; the person cannot learn that the effect is a purchase. This is the same limit",
          "Section 5.3 admits: the PEP cannot judge the effect.", ""]

    # ---- ablation
    if abl:
        ac = cells(abl)
        names = list(OrderedDict.fromkeys(r["ablation"] for r in abl))
        L += ["## 5. Ablation (P-careless, one control switched off in test code)", "",
              "`->` marks a cell that changed from the full-control P-careless value; those are the controls responsible.", "",
              "| ID | full | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
        flips = {}
        for a in ATTACKS:
            base = (mc.get((a.id, "P-careless", None)) or [{"cell": "not-run"}])[0]["cell"]
            row = [a.id, base]
            for n in names:
                r = (ac.get((a.id, "P-careless", n)) or [{"cell": "not-run"}])[0]
                v = r["cell"]
                if v != base:
                    row.append(f"**-> {v}**")
                    flips.setdefault(a.id, []).append(n)
                else:
                    row.append(v)
            L.append("| " + " | ".join(row) + " |")
        L += ["", "### Which control blocks which attack (cells that flipped)", ""]
        for a in ATTACKS:
            reg = ", ".join(a.ablation) or "-"
            L.append(f"* {a.id}: flipped by `{', '.join(flips.get(a.id, [])) or 'none'}` (pre-registered expectation: {reg})")
        L.append("")
        out["ablation"] = flips
        (RES / "matrix.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    (RES / "SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(build())
