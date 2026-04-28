# OSF Wiki Content (for direct copy-paste)

> This file contains the content to paste into the OSF project's Wiki section.
> Click "Edit" on the OSF project Wiki, paste the content below the horizontal rule, click "Save".
> After receiving OSF DOI, edit the Wiki again to fill the DOI placeholder near the bottom.

---

# AI Navigation Manifest — Multi-Scenario Empirical Study

## Status: Embargoed Pre-Registration

This OSF project hosts the pre-registration of an empirical study of **AI Navigation Manifest (AINM)**, a publisher-side workflow specification for AI agents browsing transactional websites.

The registration is currently **embargoed**. Public release is scheduled upon conclusion of an ongoing corporate IP review (expected ~2026-08, or upon four-year auto-release, whichever comes first).

---

## Project Identifiers

| Item | Value |
|------|-------|
| Author | Wonpyo Han (Independent Researcher) |
| ORCID | [0009-0002-7528-2228](https://orcid.org/0009-0002-7528-2228) |
| Email | pk102h@naver.com |
| GitHub repository | https://github.com/11pyo/AINavManifest *(remote push deferred — currently local-only)* |
| GitHub commit hash | `764ce84ea713daa17366e4e1f1439ec99c3bf7e9` |
| GitHub annotated tag | `v0.3-prereg-2026-04-28` |
| Korean Patent Application | 10-2026-0071716 (filed 2026-04-21) |
| IETF Internet-Draft | `draft-han-ai-manifest-00` (registered 2026-04-21) |
| Reference implementation license | MIT + FRAND |

---

## Abstract

AI agents that operate websites today rediscover each site's structure on every visit, paying a compounding cost in input tokens and selector-inference failure. This study evaluates **AI Navigation Manifest (AINM)** — a publisher-side specification through which a website declares to AI agents the workflows, selectors, trust signals, and execution constraints needed to operate it reliably — across four scenario categories: transactional UI, information retrieval UI, multi-step sequential UI, and internationalized UI.

The hypotheses, sample size, statistical methods, and decision rules are committed prior to data collection (this pre-registration). The reference implementation, simulation harness, and full raw data will be openly released upon embargo conclusion.

---

## Conflict of Interest (Disclosed)

The author of this study holds the following interests in the technology under evaluation:

- **Sole inventor** on Korean Patent Application 10-2026-0071716.
- **Sole registered author** of IETF Internet-Draft `draft-han-ai-manifest-00`.
- **Sole maintainer** of the GitHub reference implementation.
- **Author of a companion business plan** for commercialization.
- **Currently in active corporate IP review.**

The author has a clear interest in observing favorable outcomes for the proposed technology. The entire pre-registration protocol attached to this project exists to neutralize that bias by binding the author to decisions made prior to data observation.

---

## Pre-Registered Hypotheses (Eight Confirmatory)

| ID | Scenario | Outcome | Direction & Threshold |
|----|----------|---------|------------------------|
| H1.1 | S1 — ERP Order Entry (Transactional) | input_tokens | AINM ≤ baseline by ≥70% |
| H1.2 | S1 | success_rate | AINM ≥ baseline by ≥70 pp |
| H2.1 | S2 — Search-Filter-Select (IR) | input_tokens | AINM ≤ baseline by ≥60% |
| H2.2 | S2 | success_rate | AINM ≥ baseline by ≥60 pp |
| H3.1 | S3 — Multi-step Wizard (Sequential) | input_tokens | AINM ≤ baseline by ≥90% |
| H3.2 | S3 | success_rate | AINM ≥ baseline by ≥80 pp |
| H4.1 | S4 — Internationalized Form (i18n) | input_tokens | AINM ≤ baseline by ≥85% |
| H4.2 | S4 | success_rate | AINM ≥ baseline by ≥70 pp |

Sample size: n = 100 per (agent × scenario), 800 trials total.
Statistics: Welch's t-test (Mann-Whitney U fallback), Fisher's exact test, Cohen's d, bootstrap 95% CI (10,000 resamples), Bonferroni α=0.00625.

---

## Files in this Project

| File | Language | Role |
|------|----------|------|
| `pre-registration-en-summary.md` | English | OSF-facing pre-registration content (faithful summary) |
| `research-integrity-protocol-en.md` | English | Integrity principles, RDF mitigations, threats to validity |
| `pre-registration.md` | Korean | Original pre-registration (binding timestamp record) |
| `experimental-design.md` | Korean | 4-scenario experimental design |
| `research-integrity-protocol.md` | Korean | Integrity protocol (Korean original) |
| `phase1-commit-record.md` | Korean | Phase 1 commit metadata (hash, tag, timestamp) |

In the event of any discrepancy between English summaries and Korean originals, the Korean originals at GitHub commit `764ce84` (tag `v0.3-prereg-2026-04-28`) take precedence as the binding record.

---

## Reproducibility

All code is open source under MIT (with patent license declared FRAND). Single-command reproduction:

```
git clone https://github.com/11pyo/AINavManifest
cd AINavManifest/validation
git checkout v0.4-code-2026-04-28
pip install -r requirements.txt
python benchmark/run_benchmark_v3.py --seed 1000 --repeats 100
python benchmark/analyze_v3.py --input results_v3/metrics.csv --output results_v3/
```

Library versions are pinned in `requirements.txt`. Random seed: `1000 + trial_index`. Hardware/environment details will be reported in the final publication.

---

## Open Science Commitments

| Asset | Distribution |
|-------|--------------|
| Source code | GitHub `11pyo/AINavManifest` (MIT license) |
| Raw data (800 trials) | Zenodo (CC-BY 4.0) — upon embargo conclusion |
| Pre-registration | This OSF project (private/embargo) + GitHub commit `764ce84` (immutable) |
| Patent license | FRAND, declared in IETF Draft and patent application |
| Standardization | IETF Internet-Draft `draft-han-ai-manifest-00`, openly available |

---

## Citation (After Embargo End)

```
Han, W. (2026). AI Navigation Manifest: Publisher-Side Workflow Specification for
Trustworthy AI-Agent Browsing — Multi-Scenario Empirical Study. OSF.
https://doi.org/10.17605/OSF.IO/[ID-WILL-BE-ASSIGNED]
```

ORCID-linked. Citation activates upon embargo end.

---

## Contact

For questions about this pre-registration, contact the author at pk102h@naver.com or via the GitHub repository's issue tracker.
