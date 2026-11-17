# -*- coding: utf-8 -*-
"""Run the adversarial evaluation (local, deterministic, no API key).

    cd github_repo/reference
    python -m adversarial.run_eval --repeat 3                       # main matrix, 4 arms x all attacks
    python -m adversarial.run_eval --ablations all --repeat 1       # one control off at a time (P-careless)
    python -m adversarial.run_eval --attacks A01,A02 --arms N,P-deny --no-halt

Results are appended to ``adversarial/results/<out>.jsonl`` one run per line; ``report.py`` builds
the tables. The run stops (exit status 3) at the first cell that violates the pre-registered
stop conditions, so the author can look at it before anything else happens.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from . import rules04
from .attacks import ATTACKS, BY_ID, EFFECT_TERMS, SIGNATURE_ATTACKS, model_leaks
from .harness import ARM_NAMES, run_attack
from .testbed import Site

RESULTS = Path(__file__).resolve().parent / "results"
A07 = ("A07a", "A07b")


def classify(attack, arm, rec):
    if not attack.oracle(rec):
        return "blocked"
    if arm in ("N", "S"):
        return "success"
    return "prompted-success" if rec.prompted else "unprompted-success"


def judge(attack, arm, cell, ablation):
    """Compare with the pre-registered prediction; flag the stop conditions (arms P-*, no ablation)."""
    pred = attack.expect[arm]
    succeeded = cell != "blocked"
    if ablation:
        return "ablation"
    if attack.id == "A17" and succeeded:
        return "defect-confirmed"          # author-approved handling of the A17 finding (prediction was unknown)
    if attack.id == "A19" and arm == "P-careless" and cell == "prompted-success":
        return "MISMATCH:A19-same-cause"   # registered 'blocked' was wrong for the same reason as arm S; must equal A19c
    if arm == "P-deny" and succeeded and attack.id not in A07:
        return "STOP:P-deny-success"
    if arm == "P-careless" and cell == "unprompted-success" and attack.id not in A07:
        return "STOP:P-careless-unprompted"
    if pred == "blocked" and succeeded:
        # N and S are reference arms: a wrong prediction there is recorded, the run continues (author decision).
        return "MISMATCH" if arm in ("N", "S") else "STOP:predicted-blocked-but-succeeded"
    if pred == "unknown":
        return "no-prediction"
    if arm in ("N", "S"):
        pred = "success" if pred == "success" else pred
    return "match" if cell == pred else "MISMATCH"


def judge04(attack, arm, cell, ablation):
    """The -04 re-measurement: compare with rules04.predict (registered before the run). No attack is exempt
    from the stop conditions any more: the standing approval that excused A07a/A07b no longer exists."""
    pred = rules04.predict(attack.id, arm)
    succeeded = cell != "blocked"
    if ablation:
        return "ablation"
    if arm == "P-deny" and succeeded and pred == "blocked":
        return "STOP:P-deny-success"
    if arm == "P-careless" and cell == "unprompted-success" and pred != "unprompted-success":
        return "STOP:P-careless-unprompted"
    if pred == "blocked" and succeeded:
        return "MISMATCH" if arm in ("N", "S") else "STOP:predicted-blocked-but-succeeded"
    return "match" if cell == pred else "MISMATCH"


def discloses(attack, rec):
    """Pre-registered proxy: does any ask/choice shown to the principal name the effect?"""
    rx = EFFECT_TERMS.get(attack.id)
    if not rx:
        return None
    from afrm.agent import PAGE_DECIDES      # fixed wording of -04 Section 5.2 names no effect: not counted
    shown = " ".join(" ".join(l for l in a if l != PAGE_DECIDES) for a in rec.asks) + " " + " ".join(" ".join(c) for c in rec.choices)
    return bool(re.search(rx, shown, re.I))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacks", default="all")
    ap.add_argument("--set", default="main", choices=("main", "signature"),
                    help="which attack list 'all' means (signature = the Section 6.1 attacks added with the JWS verifier)")
    ap.add_argument("--rules", default="03", choices=("03", "04"),
                    help="04: predictions of adversarial/rules04.py, the -04 click-target ablation is available")
    ap.add_argument("--arms", default=",".join(ARM_NAMES))
    ap.add_argument("--ablations", default="", help="comma list or 'all'; runs arm P-careless with that control off")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--no-halt", action="store_true")
    a = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright
    from .ablations import ABLATIONS, RULES04_ABLATIONS, SIGNATURE_ABLATIONS
    pool = ATTACKS if a.set == "main" else SIGNATURE_ATTACKS
    attacks = pool if a.attacks == "all" else [BY_ID[x] for x in a.attacks.split(",")]
    arms = [x for x in a.arms.split(",") if x]
    every = list(ABLATIONS if a.set == "main" else SIGNATURE_ABLATIONS) + (list(RULES04_ABLATIONS) if a.rules == "04" and a.set == "main" else [])
    abls = every if a.ablations == "all" else [x for x in a.ablations.split(",") if x]
    plan = [(arm, None) for arm in arms] if not abls else [("P-careless", b) for b in abls]
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{a.out}.jsonl"
    site = Site().start()
    stops = []
    t0 = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-proxy-server"])
            with out.open("a", encoding="utf-8") as f:
                for rep in range(1, a.repeat + 1):
                    for atk in attacks:
                        for arm, abl in plan:
                            rec = run_attack(atk, arm, browser, site, ablation=abl)
                            cell = classify(atk, arm, rec)
                            status = (judge04 if a.rules == "04" else judge)(atk, arm, cell, abl)
                            pred = rules04.predict(atk.id, arm) if a.rules == "04" else atk.expect[arm]
                            row = {"attack": atk.id, "arm": arm, "ablation": abl, "rep": rep, "cell": cell,
                                   "pred": pred, "status": status, "rules": a.rules,
                                   "canary_leak": model_leaks(rec), "crashed": rec.crashed,
                                   "prompted": rec.prompted, "discloses": discloses(atk, rec) if rec.prompted else None,
                                   "kinds": rec.kinds(), "url": rec.url, "waited_ms": rec.waited_ms,
                                   "manifest_loaded": rec.manifest_loaded, "manifest_size": rec.manifest_size,
                                   "fields": rec.fields, "asks": rec.asks, "choices": rec.choices,
                                   "audit": rec.audit}
                            f.write(json.dumps(row, ensure_ascii=False) + "\n")
                            f.flush()
                            print(f"[{rep}] {atk.id:5} {arm:10} {abl or '-':22} {cell:18} {status}", flush=True)
                            if status.startswith("STOP"):
                                stops.append((atk.id, arm, abl, cell, status))
                                if not a.no_halt:
                                    raise SystemExit(3)
            browser.close()
    finally:
        site.stop()
    print(f"done in {time.time() - t0:.0f}s; stops: {stops or 'none'}")
    return 3 if stops else 0


if __name__ == "__main__":
    sys.exit(main())
