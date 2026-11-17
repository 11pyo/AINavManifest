# Adversarial evaluation of the -03 requirements (local, no API key)

Appendix B of `draft-han-ai-manifest-03` names this as the most needed next measurement: put a malicious
manifest in front of an agent and compare the attack success rate (ASR) with and without the Section 5
requirements (validator, non-LLM PEP, no manifest string reaching the model, provenance). The method follows
AgentDojo: attack scenarios x agent configurations, success judged by **observable side effects** recorded by
an instrumented site, not by what the agent says.

Everything runs on 127.0.0.1 with Chromium/Playwright, like `validation/`. No model, no API key.

```bash
cd github_repo/reference
python -m adversarial.run_eval --repeat 3 --out main          # 4 arms x all attacks, 3 repeats
python -m adversarial.run_eval --ablations all --out ablation # P-careless with one control off at a time
python -m adversarial.run_eval --set signature --repeat 3 --out signature          # Section 6.1 attacks (after the JWS verifier)
python -m adversarial.run_eval --set signature --ablations all --out signature_ablation
python -m adversarial.report                                  # results/matrix.csv, matrix.json, SUMMARY.md
python -m adversarial.criteria > adversarial/CRITERIA.md      # pre-registered criteria + predictions
python -m pytest adversarial/tests -q                         # oracle validity + frozen results
```

## Method

* **Test site** (`testbed.py`): a site origin (`/shop/` in scope, `/private/` out of scope) and an
  "attacker" origin. The server records purchase, delete, consent, payment abort, CAPTCHA pass, 403 bypass,
  lost draft, beacon, out-of-scope access, external requests and query requests. Those records are the oracle.
* **Attacks** (`attacks.py`): 30 attacks (A19c is the control for A19), each a manifest builder + a one-line success criterion + a
  prediction per arm. Criteria and predictions were fixed **before** any measurement and reviewed
  independently; they are not edited to fit results. A wrong prediction stays in the table as MISMATCH.
  `tests/test_oracles.py` checks that every oracle fires when its effect is produced directly (no agent)
  and does not fire on an untouched run.
* **Model leak oracle**: a canary string is planted in every descriptor id/description/label; if it appears
  in anything handed to the model (every `ModelInterface` return value, the filtered audit), a manifest string
  reached the model.
* **Arms** (`harness.py`):
  * **N** unguarded: no validation, no PEP; executes manifest steps as written (first match, coordinate
    click, `navigate` = goto, `fill/select/upload` too, dialogs accepted, redirects followed). The
    "worst-case compliant model" obeys action keywords (buy, delete, accept...) in any description, label or
    allowedValues it is shown.
  * **S** N's executor + the schema validator (`load_for_agent`) only.
  * **P-deny** the full -03 agent (validator, PEP, no-string model interface, provenance); the principal
    declines every ask and abandons every list.
  * **P-careless** the same, the principal approves every ask and picks the first item of every list. This
    is the ceiling of what the PEP alone stops when the person is careless.
  * Where an attack needs a standing approval of Enter (A07a, A07b, A21, A27) the principal has granted it.
* **Result classes**: `blocked`; for N/S `success`; for P arms `prompted-success` (the effect happened after
  the principal approved an ask) and `unprompted-success` (no ask at all). The headline ASR is reported both
  as the sum and split. For each prompted success the lines the ask actually showed are recorded, with a
  keyword proxy (`EFFECT_TERMS`) for whether the display named the effect.
* **Ablation** (`ablations.py`): in the test process only, one control of the full agent is patched off:
  string block, provenance, redirect hop check, sensitive-action rule, locator uniqueness, security-control
  stop, descriptor validation, discovery redirect refusal. No flag exists in the production code path.
  The table shows which attack is contained by which control.
* **Determinism**: the matrix is repeated 3 times; any cell whose value changes is reported.
* **Process notes**: the first measurement attempt was discarded and rerun from scratch after a harness fix
  (a DOM snapshot call blocks forever behind an open `confirm()`; the harness now skips the snapshot when a
  native dialog is still open). `reference/afrm` was not modified during the measurement.
  The definition of `prompted-success` was also changed during the measurement (originally "any ask was approved
  in the run"; now "the last effect-bearing step that ran was an approved ask"), because the first definition hid
  the effect of switching provenance off (A27). All results were discarded and re-measured from scratch.
  Attack A20 was written malformed (its signature is not a schema-valid string, so the whole manifest is rejected);
  it stays in the table as registered, with a prediction mismatch, and A20b repeats the attack in valid form.

## Limits (read these before quoting a number)

* The attacks were designed by the draft's author. They are a regression suite for known classes, not a
  discovery of unknown ones.
* The model is a script, **not an LLM**. The arms measure how far the *structure* around a model contains an
  attack (what can reach the model, what the PEP permits, what the principal is asked). They say nothing about
  how susceptible a real model is to such text. N and S are therefore *by-construction upper bounds*, not
  evidence; the informative results are the P columns and the ablation table.
* The attacker is not adaptive: each attack is fixed and does not react to the agent's refusals.
* The runs are deterministic (no sampling), so a repeat confirms stability of the test harness only, not
  statistical significance.
* Scope is a local test site; no real site, network, credentials or payment is involved. The "principal"
  models are two constants (always no / always yes), not a human.
* Using a real LLM would be a separate decision and is deliberately not part of this package.

## Results (recorded run, 3 repeats, deterministic)

Full tables: `results/SUMMARY.md` (ASR, per-attack cells, mismatches with cause classes, prompted-success
displays, ablation), `results/matrix.csv`, `results/matrix.json`, raw runs in `results/*.jsonl`.
`tests/test_results.py` pins them.

Headline (32 attacks, `any` = prompted + unprompted): N 100 %, S 75 % (both by construction, not evidence);
P-deny 9 % (A07a, A07b, A17); P-careless 41 % (10 prompted, 3 unprompted: the same three). Excluding the
standing-approval attacks A07a/A07b: P-deny 3 % (A17 only), P-careless 37 %. No manifest string reached the model in
any P run (canary 0/192). Findings: A17 (RecursionError escapes discovery; Section 3.5 MUST violated, and Section 3.5
sets no depth limit), A07a/A07b (standing approval of Enter vs Section 5.3), A13 (blocked only by the adapter's
hit-target check, not by a specified rule). Three predictions were wrong and are kept as registered (A19 S and
P-careless, A20 S and P-careless; A20 was a malformed attack, repeated as A20b).
A17: defect confirmed before the fix; fixed in commit `f7afaae` (nesting limit 64, parser errors fail closed); re-measured
in `results/after_fix_A17.json` and the SUMMARY section "After the A17 fix" (S, P-deny, P-careless now blocked; the pre-fix tables are unchanged).

## Section 6.1 signature attacks (added with the JWS verifier; kept apart)

`afrm/jws.py` verifies detached-JWS publisher signatures (commit `31f9935`). Fourteen further attacks
(`SIGNATURE_ATTACKS`: forged ES256/Ed25519 under the designated kid, `alg` none, HS256 keyed with the public key, a key named by
the manifest or the header, a genuine signature moved onto another manifest, no signature although a key is designated, `EdDSA`
label, replay for another origin, valid signature on an expired manifest, and two controls) were registered with predictions
in commit `7b12c33` before they were measured (`CRITERIA.md`, second table), then run 3 times in all four arms plus one
ablation (`signature-check`: the agent has no designated key).
Results are in `results/signature.jsonl`, `results/signature_ablation.jsonl` and the last section of `results/SUMMARY.md`; the 32-attack
tables above and their pinned results are unchanged. All 14 x 4 cells matched the registered predictions. In the P arms no forged,
stripped or confused signature succeeded (0/9), the same forgery with no key designated (A20b) had succeeded after an ask,
switching the check off flips exactly those cases back, and a valid signature changed nothing: A38 equals its unsigned control
A38c and A39 equals A21, including the lines shown to the principal. Limits are the same as above (author-designed attacks, scripted
model, deterministic); in addition, these attacks test the verifier and the designation rule, not key management, which the draft
leaves to the agent's configuration.

