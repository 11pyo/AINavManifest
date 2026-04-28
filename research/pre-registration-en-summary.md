# Pre-Registration Summary (English)

## AI Navigation Manifest: Publisher-Side Workflow Specification for Trustworthy AI-Agent Browsing — Multi-Scenario Empirical Study

> **Author**: Wonpyo Han (Independent Researcher)
> **ORCID**: [0009-0002-7528-2228](https://orcid.org/0009-0002-7528-2228)
> **Email**: pk102h@naver.com
> **Pre-registration date**: 2026-04-28 (KST)
> **GitHub commit hash**: `764ce84ea713daa17366e4e1f1439ec99c3bf7e9`
> **GitHub tag**: `v0.3-prereg-2026-04-28` (annotated)
> **Repository**: https://github.com/11pyo/AINavManifest *(remote push deferred until corporate IP review concludes; local commit timestamp is the binding pre-registration record)*

---

## Faithful Translation Notice

This document is an English summary of the Korean originals committed at tag `v0.3-prereg-2026-04-28` (commit `764ce84`). The Korean originals are:

- `research/research-integrity-protocol.md`
- `research/experimental-design.md`
- `research/pre-registration.md`

In the event of any discrepancy between this English summary and the Korean originals, the Korean originals at the cited commit hash take precedence as the binding pre-registration record (timestamp evidence). This English summary exists to enable evaluation by non-Korean-reading reviewers and to serve as the primary content for OSF registration.

---

## 0. Conflict of Interest (COI) — Disclosed First

The author of this study holds the following interests in the technology under evaluation:

- Sole inventor on Korean Patent Application **10-2026-0071716** (filed 2026-04-21), covering the canonical-hash trust mechanism, registry API, and workflow DSL.
- Sole registered author of IETF Internet-Draft **`draft-han-ai-manifest-00`** (registered 2026-04-21).
- Sole maintainer of the GitHub reference implementation **`11pyo/AINavManifest`** (MIT + FRAND).
- Author of a companion business plan (4-Tier revenue model) for commercialization of the technology.
- Currently in active corporate IP review (employer informed 2026-04-27, formal package submitted same day).

The author has a clear interest in observing favorable outcomes for the proposed technology. **This entire pre-registration protocol exists to neutralize that bias by committing all hypotheses, statistical methods, and decision rules before observing any data.** The COI is disclosed in every publication arising from this study.

---

## 1. Research Questions

- **RQ1.** By how much does an AI Navigation Manifest (AINM)–aware agent reduce input-token consumption per task compared with a DOM-analysis baseline agent?
- **RQ2.** By how much does the AINM agent improve task success rate compared with the baseline?
- **RQ3.** Do the effects in RQ1 and RQ2 generalize across the four scenario categories: (S1) Transactional UI, (S2) Information Retrieval UI, (S3) Multi-step Sequential UI, (S4) Internationalized UI?

---

## 2. Hypotheses (Eight Confirmatory)

All hypotheses specify direction and an effect-size threshold (HARKing prevention).

### Scenario S1 — ERP Order Entry (Transactional UI)
- **H1.1** AINM mean `input_tokens` is at least **70%** lower than baseline mean.
- **H1.2** AINM `success_rate` is at least **70 percentage points (pp)** higher than baseline.

### Scenario S2 — Search-Filter-Select (Information Retrieval UI)
- **H2.1** AINM mean `input_tokens` is at least **60%** lower than baseline mean.
- **H2.2** AINM `success_rate` is at least **60 pp** higher than baseline.

### Scenario S3 — Multi-step Wizard (Sequential UI, state-bearing)
- **H3.1** AINM mean `input_tokens` is at least **90%** lower than baseline mean.
- **H3.2** AINM `success_rate` is at least **80 pp** higher than baseline.

### Scenario S4 — Internationalized Form (i18n UI)
- **H4.1** AINM mean `input_tokens` is at least **85%** lower than baseline mean.
- **H4.2** AINM `success_rate` is at least **70 pp** higher than baseline.

### Secondary (Exploratory)
- **H5** Pooled across all four scenarios, weighted Cohen's d for `input_tokens` reduction is ≥ 1.0 (large effect). Reported but **not** confirmatory.

### Threshold Justification

Thresholds derive from prior pilot data (n=30 single-scenario, 81.9% reduction observed) and conservative buffers for new scenarios. Multi-step scenarios (S3) carry the largest threshold because cumulative DOM tokens scale with step count, while information retrieval (S2) carries the smallest because dynamic-result pages are already a strong baseline weak spot.

---

## 3. Variables

### 3.1 Independent variable
- **Agent type** (categorical): `baseline_dom` | `manifest_aware`

### 3.2 Primary dependent variables (hypothesis-tested)
- **`input_tokens`** (continuous, integer ≥ 0). Measured via OpenAI's `tiktoken` library (encoding `cl100k_base`), accumulated per trial.
- **`success`** (binary). Defined per-scenario (e.g., reaching success URL, presence of confirmation marker).

### 3.3 Secondary dependent variables (reported, not tested)
- `http_requests`, `llm_calls`, `wall_time_ms`, `steps_attempted`, `steps_succeeded`.

### 3.4 Control variables
- **Scenario** (categorical, 4 levels: S1, S2, S3, S4) — analyzed per-scenario.
- **Trial seed** (deterministic): `seed = 1000 + trial_index` (trial_index ∈ [0, 99]).
- **Server configuration** — fixed per scenario.
- **Hardware** — same machine, same continuous session.
- **Library version** — pinned (see §8).

### 3.5 Variables explicitly NOT manipulated
- LLM model identity (the study uses a simulation model, not live LLM calls; see Amendment 1 below).
- User intent (single fixed scenario per condition).
- Time of day (single continuous run).

---

## 4. Sample Size

- **n = 100 trials per (agent × scenario)** → 2 × 4 × 100 = **800 trials total**.

### Power analysis
- α (Bonferroni-corrected for 8 primary comparisons) = 0.00625
- Power (1 − β) = 0.95
- Expected effect size (from pilot data): Cohen's d ≥ 1.0 (pilot d ≈ 2.4)
- At d = 1.0, n = 43 per group is sufficient
- At d = 0.5 (conservative assumption), n = 168 per group is required
- **n = 100 chosen** for medium-to-large effect detection with conservative buffer

### Stopping rule
- Data collection terminates immediately upon reaching n = 100 per condition.
- Sequential testing is **prohibited** (no adding trials until significance is reached).
- Only full re-execution is permitted, and only in the case of code or environment errors. Any re-execution requires an amendment record and joint reporting of both runs' results.

---

## 5. Analysis Plan

### 5.1 Statistical tests

| Outcome | Primary test | Fallback (assumption violation) |
|---------|--------------|---------------------------------|
| `input_tokens` | Welch's two-sample t-test (two-tailed) | Mann-Whitney U test (non-normal OR zero-variance group) |
| `success` | Fisher's exact test on 2×2 contingency | (Distribution-free; no fallback needed) |
| Effect size (tokens) | Cohen's d | Rank-biserial correlation if Mann-Whitney path |

### 5.2 Multiple comparisons correction
- 4 scenarios × 2 primary outcomes = **8 comparisons**
- **Bonferroni**: α_corrected = 0.05 / 8 = **0.00625** (binding for decisions)
- **Holm-Bonferroni**: reported in parallel as a less conservative reference.

### 5.3 Normality testing
- Shapiro-Wilk per (agent × scenario) for `input_tokens`.
- If p < 0.05, automatically switch to Mann-Whitney U.
- If a group has zero variance (e.g., the manifest agent's deterministic token count), Mann-Whitney U is used by default (parametric tests are not defined on point distributions).

### 5.4 Confidence intervals
- 95% bootstrap CI for mean difference, 10,000 resamples.
- 95% bootstrap CI for risk difference (success rate, in percentage points), 10,000 resamples.

### 5.5 Pooled meta-analysis (secondary)
- Weighted Cohen's d across the four scenarios.
- Fixed-effect if heterogeneity I² < 50%; random-effect otherwise.

---

## 6. Decision Rules (Pre-Registered, Code-Enforced)

Decisions are made automatically by code (`evaluate_hypothesis` in `validation/benchmark/scenarios_v3.py`), eliminating post-hoc judgment.

For each hypothesis H_i.j:

| Decision | All conditions met |
|----------|--------------------|
| **Accept** | Bonferroni-corrected p < 0.00625 **AND** observed effect ≥ pre-registered threshold **AND** 95% CI excludes 0 |
| **Reject** | Uncorrected p ≥ 0.05 **OR** effect < threshold **OR** 95% CI includes 0 |
| **Inconclusive** | 0.00625 ≤ uncorrected p < 0.05 (statistically significant uncorrected, but not corrected) |

This rule is committed in code at tag `v0.3-prereg-2026-04-28`. Modifying it after observing data constitutes academic misconduct.

---

## 7. Outlier and Missing-Data Handling

### Outliers (pre-registered)
- **Timeout** (`wall_time_ms` > 60,000 ms): trial reclassified as `success = False`. Other metrics retained as-is. **Trial is NOT removed from analysis.**
- **z-score |z| > 3** for `input_tokens`: marked in raw data but **NOT removed**. Analysis uses raw data.

### Missing data
- HTTP error (server 5xx): trial = failure (`success = False`).
- Network error in localhost: environment fault → full re-execution required, with amendment record and joint reporting.
- Intentional trial omission: **prohibited**.

### Post-hoc data removal — explicitly prohibited
The following constitute academic misconduct within this study:
- Removing trials because they "skew the mean."
- Removing trials because "baseline did unusually well on certain seeds."
- Reducing sample to achieve statistical significance.

---

## 8. Reproducibility Commitments

### 8.1 Library versions (pinned)
```
Python 3.11.x
Flask==3.0.3
requests==2.32.3
beautifulsoup4==4.12.3
tiktoken==0.7.0
matplotlib==3.9.2
numpy==2.1.0
scipy==1.14.0
```

### 8.2 Random seeds
- Base seed: **1000**
- Per-trial seed: `1000 + trial_index` (trial_index ∈ [0, 99])
- Seeds are scenario-independent (same seed value used across scenarios), enabling within-trial-index comparison.

### 8.3 Single-command reproduction

```bash
# Phase 3: Data collection
python validation/benchmark/run_benchmark_v3.py --seed 1000 --repeats 100 --output results_v3/

# Phase 4: Analysis
python validation/benchmark/analyze_v3.py --input results_v3/metrics.csv --output results_v3/
```

External researchers can clone the repository, check out tag `v0.4-code-2026-04-28` (post-implementation), and obtain identical results.

### 8.4 Hardware reporting
OS, CPU, RAM, and disk specifications are reported alongside results in the publication.

---

## 9. Open-Science Practices

| Asset | Distribution |
|-------|--------------|
| Source code | GitHub `11pyo/AINavManifest` (MIT) |
| Raw data (800 trials) | Zenodo (CC-BY 4.0) upon publication |
| Pre-registration | OSF (this record, embargoed; GitHub commit `764ce84` as immutable timestamp) |
| Patent license | FRAND (declared in IETF Draft and patent application) |
| Standardization | IETF Internet-Draft `draft-han-ai-manifest-00`, openly available |

All five must be in place before the study is considered fully published.

---

## 10. Amendments

| # | Date | Section affected | Change | Rationale | Effect on hypotheses/sample/methods/decisions |
|---|------|------------------|--------|-----------|-----------------------------------------------|
| 1 | 2026-04-28 | Implementation method | Switched from "Flask server routes plus simulation" to **simulation-only** measurement, reusing the validated v2 simulation model. No new HTTP server routes added for v3 scenarios. | (1) The v2 simulation model has been validated for the same invention (n=30 pilot showed 81.9% token reduction, +80 pp success). (2) External reproducibility is strengthened (zero environment dependencies; single command reproduces results). (3) Simulation-based environment models are an academic standard (e.g., WebShop, Mind2Web both use environment models). | **None.** Hypotheses (H1.1–H4.2), sample size (n=100), statistical methods, and decision rules are unchanged. |

Future amendments are appended to this table. Retroactive (i.e., undisclosed) modification of pre-registered items is prohibited.

---

## 11. Embargo and Release

- This pre-registration is filed on OSF in **embargo / private mode**.
- Embargo ends upon conclusion of corporate IP review (expected ~2026-08), or four years from filing date, whichever comes first.
- Upon embargo end, this registration becomes publicly visible at its OSF DOI, and the GitHub repository is pushed to remote with all intervening commits and tags.

---

## 12. Reporting Commitments

This study commits to publishing the following **regardless of outcome**:

1. **All 800 trials** in raw form (`metrics.csv`) on Zenodo.
2. **All eight hypothesis decisions** (Accept / Reject / Inconclusive). Partial reporting — e.g., publishing only accepted hypotheses — is prohibited.
3. **Negative or counter-intuitive results.** For example, if AINM exhibits longer wall-clock time than baseline (due to registry round-trip), this is reported in the same table as the favorable token-reduction result.
4. **Pre-registered limitations** (see §13).

---

## 13. Pre-Registered Limitations

These limitations are part of the pre-registration and cannot be retroactively softened:

1. **Single-domain workflows per category.** S1 is one ERP form, not all ERP forms; generalization across products within a category is plausible but not proven.
2. **Sample size n = 100.** Sufficient for the magnitudes observed in pilot data, but precludes detection of small effects (d < 0.5).
3. **No live-LLM comparison.** Token counts are measured via tiktoken (a standard proxy for LLM serving cost), not by sending requests to GPT-4o, Claude, etc. End-to-end behavioral fidelity on live LLMs is future work.
4. **Deterministic baseline failure model.** Selector-inference failure in the DOM agent follows a deterministic signal-to-noise heuristic. Real LLMs introduce additional failure modes (hallucination, prompt sensitivity) that this model does not capture, so the *true* baseline failure rate is at least as bad as reported.
5. **Publisher manifest authoring cost not measured.** A publisher's effort to write a manifest is excluded from this study.
6. **Centralized registry assumption.** The trust-verification flow assumes a single registry; federated or DID-based variants are not exercised.

---

## 14. Author Contributions (CRediT)

Wonpyo Han: Conceptualization, Methodology, Software, Validation, Formal Analysis, Investigation, Resources, Data Curation, Writing — Original Draft, Writing — Review & Editing, Visualization, Project Administration.

(All roles performed by the sole author.)

---

## Endnote

This pre-registration is an instrument of self-binding, not self-promotion. It commits the author to reporting whatever the data show, not what the author hopes the data will show. If the eventual analysis yields rejected or inconclusive hypotheses, that outcome is reported with the same prominence as accepted ones. The credibility of the resulting evidence depends on this commitment being taken seriously — and on independent reviewers being able, at any time, to verify it via the GitHub commit hash and OSF DOI cited above.
