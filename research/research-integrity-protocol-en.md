# Research Integrity Protocol — AINM Empirical Study (English)

> **Purpose**: A self-imposed rule set that blocks bias, statistical error, confirmation bias, and researcher degrees of freedom in the AINM empirical study.
> **Principle**: To neutralize the suspicion that "the author programmed the result they wanted," **all decisions are committed before observing any data**.
> **Author**: Wonpyo Han (ORCID [0009-0002-7528-2228](https://orcid.org/0009-0002-7528-2228))
> **Companion document**: `research-integrity-protocol.md` (Korean original — binding timestamp record)
> **Pre-registration tag**: `v0.3-prereg-2026-04-28`
> **GitHub commit**: `764ce84ea713daa17366e4e1f1439ec99c3bf7e9`

---

## Faithful Translation Notice

This English document is a faithful translation of the Korean original `research-integrity-protocol.md` committed at tag `v0.3-prereg-2026-04-28`. In the event of any discrepancy, the Korean original at the cited commit hash takes precedence as the binding record. This translation exists to enable evaluation by non-Korean-reading reviewers.

---

## 0. Conflict of Interest (COI) — Declared First

The author of this study holds the following interests in the technology under evaluation:

- **Sole inventor** on Korean Patent Application **10-2026-0071716** (filed 2026-04-21).
- **Sole registered author** of IETF Internet-Draft **`draft-han-ai-manifest-00`** (registered 2026-04-21).
- **Sole maintainer** of the GitHub reference implementation **`11pyo/AINavManifest`** (MIT + FRAND).
- **Author of a companion business plan** (4-Tier revenue model) for commercialization of the technology.
- **Currently in active corporate IP review**: employer (Dongkuk Systems) was informed and the formal package was submitted on 2026-04-27.

→ **The author has a clear personal interest in observing favorable outcomes for the proposed technology.** Every rule in this protocol exists to neutralize that bias by binding the author to decisions made prior to data observation. The COI is disclosed in every publication arising from this study.

---

## 1. Seven Principles of Research Integrity

### 1.1 Pre-registration

**Rule**: Before any data is collected, the following seven items are committed to a public timestamped record:

1. Hypotheses (H1, H2, ... — with explicit direction and effect-size threshold)
2. Dependent, independent, and control variables
3. Sample size and stopping rule
4. Experimental procedure (scenarios, seeds, environment)
5. Analysis plan (statistical tests, multiple-comparisons correction, effect-size estimator)
6. Decision rules (acceptance/rejection thresholds)
7. Outlier and missing-data handling

**Implementation**: `pre-registration.md` is committed to GitHub with the tag `v0.3-prereg-2026-04-28`. Any post-commit modification is recorded in §11 Amendments with explicit rationale and impact disclosure.

### 1.2 No HARKing (Hypothesizing After Results Known)

**Rule**: The author does not formulate or modify hypotheses after observing results.

- Patterns discovered post-hoc are reported under an *exploratory* label and **never elevated to confirmatory hypotheses**.
- Comparisons not pre-registered appear in the appendix, not in the main report.

### 1.3 No p-hacking

**Rule**: Multiple-comparison alpha correction is applied to all primary tests.

- 4 scenarios × 2 dependent variables = 8 comparisons.
- **Bonferroni**: α_corrected = 0.05 / 8 = **0.00625**.
- **Holm-Bonferroni** (less conservative; recommended academic standard): applied in step-down order.
- Significance reported with both corrected and uncorrected p-values.
- Results that are uncorrected-significant but not corrected-significant are explicitly labeled "uncorrected significant only."

### 1.4 No Cherry-picking

**Rule**: All trial outcomes are released as raw data.

- Failed trials and outliers are retained in `metrics.csv` without modification.
- Data exclusion follows only the pre-registered exclusion rule (e.g., "wall_time > 60 s is classified as a timeout").
- Post-hoc exclusion is prohibited.

### 1.5 Honest Baselines

**Rule**: Baselines reflect realistic state-of-the-art behavior, not weakened straw-man variants.

- The DOM-analysis baseline's selector-inference parameters are **pre-registered**.
- Parameter tuning to weaken the baseline is prohibited.
- Additional baselines (ARIA-based, vision-based) introduced in future work follow the same rule.
- Baseline code is held to the same code-review and unit-test standards as the proposed method.

### 1.6 Negative Results and Limitations Reporting

**Rule**: Outcomes unfavorable to the proposed method are reported.

- Scenarios where the effect is small or negative are reported as-is.
- The protocol's limitations (simulation-based baseline, no live LLM comparison, etc.) are explicitly stated in §8 of the main report.
- "Reporting only successful scenarios while suppressing unsuccessful ones" constitutes academic fraud.

### 1.7 Reproducibility

**Rule**: An external researcher must be able to obtain identical results in an identical environment.

- All code: GitHub `11pyo/AINavManifest`, MIT-licensed.
- All data: `metrics.csv` (full 800 trials) released on Zenodo upon publication.
- Environment specification: `requirements.txt` lock + execution environment (OS, Python version, hardware) reported.
- Random seeds fixed: `seed = 1000 + trial_index`.
- Single-command reproduction: `python validation/benchmark/run_benchmark_v3.py --seed 1000 --repeats 100`.

---

## 2. Researcher Degrees of Freedom (RDF) Mitigation

### 2.1 Definition

RDF refers to the post-hoc decision freedom of a researcher to modify analysis choices after observing results, in order to "make the result significant." Common RDF moves include:

- Changing outlier-removal thresholds.
- Altering subgroup partitioning.
- Selecting which dependent variable to report.
- Switching between parametric and non-parametric tests.
- Increasing sample size until significance is reached.
- Redefining comparison groups.

### 2.2 Mitigation Mechanisms

| RDF | Mitigation |
|-----|-----------|
| Sample size | Pre-registered (n=100); sequential testing prohibited. |
| Choice of dependent variable | Primary outcomes (`input_tokens`, `success_rate`) pre-registered; secondaries kept in appendix. |
| Statistical test | Welch's t-test pre-decided (Mann-Whitney U as fallback for non-normal or zero-variance groups). |
| Multiple-comparisons correction | Bonferroni α=0.00625 pre-decided. |
| Outliers | Timeout > 60 s reclassified to `success=False`; `|z|>3` flagged but not removed; raw data analyzed. |
| Analysis environment | Python 3.11, scipy 1.14.0, numpy 2.1.0 locked. |

→ All decisions are committed in `pre-registration.md` before data collection.

---

## 3. Threats to Validity — Pre-emptive Analysis

### 3.1 Internal Validity

**Threat**: Measurements fail to reflect the true causal relationship.

| Threat | Risk in this study | Mitigation |
|--------|---------------------|-----------|
| Measurement instrument error | tiktoken counter accuracy | OpenAI's official library used; encoding `cl100k_base` declared. |
| Environment variability | Wall-time affected by OS load | Baseline and AINM trials interleaved in the same machine session. |
| Seed dependence | Effects appear only on specific seeds | 100 distinct seeds (one per trial). |
| Code bugs | A bug favors one agent | Code review, unit tests, full open source. |

### 3.2 External Validity

**Threat**: Results do not generalize to other environments or domains.

| Threat | Risk | Mitigation |
|--------|------|-----------|
| Single domain | One ERP scenario | **Extended to four scenario categories — central design choice of this protocol.** |
| Single baseline | Only DOM-analysis | Future work (Stage 5) adds additional baselines; current limitation explicitly stated. |
| Single LLM environment | Simulation-based, no live LLM | Stated as a limitation; live-LLM comparison added in Stage C (§8 Limitations). |
| Synthetic scenarios | Mock servers, not real sites | Scenario design is justified by citing real-world site patterns (per-scenario references in `experimental-design.md`). |

### 3.3 Construct Validity

**Threat**: Measured variables fail to capture the intended construct.

| Threat | Risk | Mitigation |
|--------|------|-----------|
| Is `input_tokens` a valid LLM-cost proxy? | Partial; output tokens and round-trips also matter | `input_tokens` dominates per-token cost; output tokens and HTTP requests reported alongside. |
| Is `success` a valid reliability proxy? | Partial; binary success ignores partial completion | `steps_attempted` and `steps_succeeded` reported. |
| Does the simulated baseline-failure rate match a real LLM's failure rate? | Partial; the deterministic model omits hallucination and prompt sensitivity | Stated as a limitation; live-LLM comparison is future work; the simulation is conservative (real LLMs likely fail at least as often as modeled). |

### 3.4 Conclusion Validity

**Threat**: Statistical inference is incorrect.

| Threat | Risk | Mitigation |
|--------|------|-----------|
| Insufficient sample size | n=100 detects medium-large effects but not small ones | Effect size pre-estimated (d > 1); n=100 has 95% power; small-effect detection is future work. |
| Test-assumption violations | t-test assumes normality | Shapiro-Wilk reported; Mann-Whitney U automatic fallback. |
| Multiple comparisons inflate false positives | 8 tests at α=0.05 → ~33% family-wise error | Bonferroni α=0.00625 pre-applied. |

---

## 4. Open Science Practices — Commitments

This study commits to:

- ✅ **Open Code** — GitHub MIT license, full analysis scripts.
- ✅ **Open Data** — Zenodo CC-BY 4.0, raw `metrics.csv` (all 800 trials).
- ✅ **Open Pre-registration** — `pre-registration.md` GitHub commit; commit hash and tag reported.
- ✅ **Open Access Publication** — Zenodo CC-BY 4.0.
- ✅ **Open Standardization** — IETF Internet-Draft openly available; FRAND patent license declared.
- ✅ **Open Conflict of Interest** — disclosed in every publication's §0 or footer.

The study is "in progress" until all six are in place.

---

## 5. Bias Identification and Mitigation

### 5.1 Selection Bias

**Threat**: Choosing only scenarios that favor the proposed method.

**Mitigation**:
- Four scenario categories pre-stated (transactional, IR, multi-step, i18n).
- Each category is a publisher-side standard target that a reviewer would recognize as legitimate.
- Scenario selection rationale recorded in `experimental-design.md`.

### 5.2 Confirmation Bias

**Threat**: Bias toward analyses that confirm the hypothesis.

**Mitigation**:
- Hypotheses pre-registered.
- Negative effects reported (e.g., AINM has higher wall_time than baseline due to registry round-trip — already disclosed in pilot table).
- HTTP request count increase (1.6 → 5.0) also reported transparently.

### 5.3 Researcher Bias

**Threat**: The author is both inventor and analyst.

**Mitigation**:
- COI declared in §0.
- All raw data published, enabling independent analysis.
- Analysis code committed before data collection.
- (Optional, future) Independent third-party reviewer performing analysis on the released raw data.

### 5.4 Publication Bias

**Threat**: Favorable results are published while null results are suppressed.

**Mitigation**:
- This study commits to publishing **all** scenario results.
- Scenarios with small effects are reported as-is.
- Failed scenarios (if any) are reported in a separate section.

---

## 6. Commit Sequence — Mechanism Core

This is the core protective mechanism: **everything is committed before observing results.**

### Phase 1 — Pre-registration

1. Commit `research-integrity-protocol.md` (this file).
2. Commit `experimental-design.md`.
3. Commit `pre-registration.md`.
4. **Tag**: `v0.3-prereg-2026-04-28`.

After this point, hypothesis and analysis-method changes require explicit amendment records.

### Phase 2 — Code Implementation

5. Add scenario server code (`validation/server/scenarios_v3.py` if applicable).
6. Reinforce baseline and AINM agent code (`validation/agent/`).
7. **Pre-author analysis code** (`validation/benchmark/analyze_v3.py`) — tested with dummy data.
8. **Tag**: `v0.4-code-2026-XX-XX`.

→ **Analysis code must exist before result data exists.** Analysis code is not authored from results.

### Phase 3 — Experiment Execution

9. Execute experiment once: `python run_all_v3.py --seed 1000 --repeats 100`.
10. Commit results (`results_v3/`).
11. **Tag**: `v0.5-data-2026-XX-XX`.

### Phase 4 — Analysis

12. Execute the analysis code authored in Phase 2 unchanged.
13. Generate result tables and figures.
14. Commit analysis output (`results_v3/analysis.json`).
15. **Tag**: `v0.6-analysis-2026-XX-XX`.

→ Phase 4 modifications to analysis code, if discovered, are amendment-recorded; results from both versions are reported.

### Phase 5 — Reporting

16. Update English main report (`tech-report-en.md`).
17. Translate to Korean (`tech-report-kr.md`).
18. **Tag**: `v1.0-report-2026-XX-XX`.

### Phase 6 — Publication (after corporate IP review concludes)

19. Upload to Zenodo, obtain DOI.
20. Update GitHub Pages.
21. (Optional) IETF mailing-list activity, conference submission.

---

## 7. External Verification

All results in this study must be reproducible by an external researcher with a single command:

```bash
git clone https://github.com/11pyo/AINavManifest
cd AINavManifest/validation
git checkout v0.5-data-2026-XX-XX
pip install -r requirements.txt
python benchmark/run_benchmark_v3.py --seed 1000 --repeats 100
python benchmark/analyze_v3.py
diff results_v3/analysis.json results_v3/published_analysis.json
# expected: empty (identical results)
```

If the diff is non-empty, the cause is environment/library version mismatch and is debugged. **The results must not be environment-dependent.**

---

## 8. Protocol Violation — Response

If a protocol violation is discovered during the course of the study (intentionally or otherwise):

1. **Record** the violation as an amendment in this document, with date, content, and impact.
2. **Mark** affected results separately in published outputs.
3. **Disclose** the violation as a footer note in publications affected by the cited commit hash.
4. If necessary, **publish a v2 report** or **retract** the original.

This is the academic-ethics standard procedure. **Concealment, not disclosure, constitutes the breach of integrity.**

---

## 9. Protocol Verification Checklist

The following items are inspected repeatedly throughout the study:

- [ ] Is COI disclosed in every publication?
- [ ] Were hypotheses committed before data collection? (commit hash recorded)
- [ ] Was analysis code authored before data collection?
- [ ] Were baseline parameters fixed before observing results?
- [ ] Are all trial results included in raw data? (zero cherry-picking)
- [ ] Was alpha correction applied to multiple comparisons?
- [ ] Were outliers handled per pre-registered rules only?
- [ ] Are small or negative effects reported?
- [ ] Are all code and data publicly available?
- [ ] Is single-command external reproduction documented in README?
- [ ] Are limitations of this study explicitly stated?
- [ ] Are all four threats-to-validity domains addressed?

---

## 10. The Nature of This Protocol

This protocol is a safeguard for the author against the author's own bias. The dual role — inventor and analyst — carries inherent confirmation bias and researcher-degrees-of-freedom risks. This protocol locks those down with rules committed in advance.

The author's stated concern that results might be "programmed to come out a certain way" is a precise diagnosis. This protocol systematizes that diagnosis into an enforcement mechanism.

The protocol may be reinforced over time through amendments, but **hypotheses and analysis methods at the moment of pre-registration are never retroactively modified**. This is the only path through which this study can earn external trust.

---

> **Subsequent documents**: `experimental-design.md` (4-scenario design), `pre-registration.md` (hypothesis and analysis-method commit).
