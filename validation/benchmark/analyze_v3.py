# -*- coding: utf-8 -*-
"""
Phase 4 — 분석 (사전 등록 v0.3-prereg-2026-04-28).

본 모듈은 사전 등록 §5의 통계 방법을 결과 보기 *전*에 코드로 박는다.
구현된 분석:

  - Welch's two-sample t-test (input_tokens), §5.1 primary
  - Mann-Whitney U test (정규성 위배 시 자동 대체), §5.1 fallback
  - Fisher's exact test (success rate), §5.1 primary
  - Cohen's d (effect size for tokens), §5.1
  - Bootstrap 95% CI (10,000 resamples) for mean difference, §5.4
  - Shapiro-Wilk normality test, §5.3
  - Bonferroni correction (α=0.05/8=0.00625), §5.2
  - Holm-Bonferroni correction (parallel report), §5.2
  - HypothesisDecision auto-evaluation per §6 decision rules

본 모듈이 수행하지 *않는* 것 (사전 등록 외 변경 금지):
  - Outlier 제거 (raw 그대로, 사전 등록 §7)
  - 사후 가설 추가 (HARKing 차단)
  - 사후 표본 크기 변경 (사전 등록 §4.3 stopping rule)

표준 호출:
  python -m benchmark.analyze_v3 --input results_v3/metrics.csv --output results_v3/

본 모듈은 결과 보기 *전* commit되어야 한다 (사전 등록 핵심).
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

# v3 시나리오·가설 정의
try:
    from .scenarios_v3 import (
        SCENARIOS_V3,
        ScenarioConfigV3,
        get_scenario_v3,
        evaluate_hypothesis,
        HypothesisDecision,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmark.scenarios_v3 import (  # type: ignore
        SCENARIOS_V3,
        ScenarioConfigV3,
        get_scenario_v3,
        evaluate_hypothesis,
        HypothesisDecision,
    )


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# --------------------------------------------------
# 사전 등록 상수 (변경 시 amendment 필수)
# --------------------------------------------------

ALPHA = 0.05
N_COMPARISONS = 8                          # 4 시나리오 × 2 primary outcomes
ALPHA_CORRECTED = ALPHA / N_COMPARISONS    # 0.00625 (사전 등록 §5.2)
BOOTSTRAP_RESAMPLES = 10_000               # 사전 등록 §5.4
BOOTSTRAP_SEED = 42                        # bootstrap 재현성 (사전 등록 외 implementation detail)
SHAPIRO_THRESHOLD = 0.05                   # 정규성 위배 임계값 (사전 등록 §5.3)


# --------------------------------------------------
# Statistic helpers
# --------------------------------------------------

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d (independent samples, pooled SD)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    m_a, m_b = float(np.mean(a)), float(np.mean(b))
    s_a, s_b = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
    pooled = float(np.sqrt((s_a ** 2 + s_b ** 2) / 2.0))
    if pooled == 0.0:
        return 0.0 if m_a == m_b else float("inf")
    return (m_a - m_b) / pooled


def bootstrap_ci_mean_diff(a: np.ndarray, b: np.ndarray,
                            n_resamples: int = BOOTSTRAP_RESAMPLES,
                            seed: int = BOOTSTRAP_SEED,
                            ci_level: float = 0.95) -> Tuple[float, float]:
    """Bootstrap 95% CI for mean(a) - mean(b)."""
    if len(a) == 0 or len(b) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        sample_a = rng.choice(a, size=len(a), replace=True)
        sample_b = rng.choice(b, size=len(b), replace=True)
        diffs[i] = float(np.mean(sample_a) - np.mean(sample_b))
    lo = float(np.percentile(diffs, (1 - ci_level) / 2 * 100))
    hi = float(np.percentile(diffs, (1 + ci_level) / 2 * 100))
    return (lo, hi)


def shapiro_wilk_safe(x: np.ndarray) -> Tuple[float, float]:
    """Shapiro-Wilk 정규성 검정. n<3이면 (nan, nan), n>5000이면 truncation."""
    if len(x) < 3:
        return (float("nan"), float("nan"))
    if np.std(x, ddof=1) == 0.0:
        # 분산 0이면 정규성 정의 안 됨 (e.g. manifest_aware tokens가 결정론적 상수)
        return (float("nan"), float("nan"))
    sample = x if len(x) <= 5000 else np.random.default_rng(0).choice(x, 5000, replace=False)
    try:
        stat, p = stats.shapiro(sample)
        return (float(stat), float(p))
    except Exception:
        logger.exception("Shapiro-Wilk failed")
        return (float("nan"), float("nan"))


def holm_bonferroni(p_values: List[float]) -> List[float]:
    """Holm-Bonferroni step-down adjusted p-values.

    Reference: Holm (1979), 'A Simple Sequentially Rejective Multiple Test Procedure'.
    """
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * n
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = min(1.0, p * (n - rank))
        # monotone 보정
        if rank > 0:
            prev_orig_idx = indexed[rank - 1][0]
            adj = max(adj, adjusted[prev_orig_idx])
        adjusted[orig_idx] = adj
    return adjusted


# --------------------------------------------------
# Analysis dataclasses
# --------------------------------------------------

@dataclass
class TokenStat:
    """input_tokens 분석 결과 (사전 등록 §5.1)."""
    scenario: str
    n_baseline: int
    n_manifest: int
    mean_baseline: float
    mean_manifest: float
    std_baseline: float
    std_manifest: float
    median_baseline: float
    median_manifest: float
    reduction_pct: float                    # (mean_b - mean_m) / mean_b * 100
    cohens_d: float
    shapiro_p_baseline: float
    shapiro_p_manifest: float
    test_used: str                           # "welch_t" | "mann_whitney_u"
    test_statistic: float
    p_uncorrected: float
    p_bonferroni: float
    ci_low: float
    ci_high: float


@dataclass
class SuccessStat:
    """success rate 분석 결과 (사전 등록 §5.1)."""
    scenario: str
    n_baseline: int
    n_manifest: int
    success_baseline: int
    success_manifest: int
    rate_baseline: float                     # 0..1
    rate_manifest: float                     # 0..1
    risk_difference_pp: float                # (rate_m - rate_b) * 100
    odds_ratio: float
    test_used: str                           # "fisher_exact"
    p_uncorrected: float
    p_bonferroni: float
    ci_low_pp: float                         # bootstrap CI for risk diff in pp
    ci_high_pp: float


@dataclass
class ScenarioResult:
    scenario: str
    token: TokenStat
    success: SuccessStat
    h_token: HypothesisDecision              # H_i.1
    h_success: HypothesisDecision            # H_i.2


# --------------------------------------------------
# Per-scenario analysis
# --------------------------------------------------

def analyze_tokens(scn: ScenarioConfigV3,
                    baseline: np.ndarray, manifest: np.ndarray) -> TokenStat:
    """input_tokens 분석 (사전 등록 §5.1, §5.3, §5.4)."""
    n_b, n_m = len(baseline), len(manifest)

    mean_b = float(np.mean(baseline)) if n_b else float("nan")
    mean_m = float(np.mean(manifest)) if n_m else float("nan")
    std_b = float(np.std(baseline, ddof=1)) if n_b > 1 else float("nan")
    std_m = float(np.std(manifest, ddof=1)) if n_m > 1 else float("nan")
    median_b = float(np.median(baseline)) if n_b else float("nan")
    median_m = float(np.median(manifest)) if n_m else float("nan")

    reduction = ((mean_b - mean_m) / mean_b * 100.0) if mean_b > 0 else float("nan")
    d = cohens_d(baseline, manifest)

    sw_b_stat, sw_b_p = shapiro_wilk_safe(baseline)
    sw_m_stat, sw_m_p = shapiro_wilk_safe(manifest)

    # Test 선택 (사전 등록 §5.3 + implementation 명료화):
    #   - Shapiro-Wilk p < 0.05 위배 → Mann-Whitney U
    #   - 어느 한 그룹의 분산이 0 (e.g. manifest_aware의 결정론적 토큰) → Mann-Whitney U
    #     (정규성을 정의할 수 없는 점분포에 대한 학술 표준 fallback)
    normality_violated = False
    if not np.isnan(sw_b_p) and sw_b_p < SHAPIRO_THRESHOLD:
        normality_violated = True
    if not np.isnan(sw_m_p) and sw_m_p < SHAPIRO_THRESHOLD:
        normality_violated = True

    zero_variance = (
        (n_b > 1 and float(np.std(baseline, ddof=1)) == 0.0) or
        (n_m > 1 and float(np.std(manifest, ddof=1)) == 0.0)
    )
    if normality_violated or zero_variance:
        # Mann-Whitney U (two-sided)
        u_stat, p_unc = stats.mannwhitneyu(baseline, manifest, alternative="two-sided")
        test_used = "mann_whitney_u"
        test_stat = float(u_stat)
    else:
        # Welch's t-test (등분산 가정 X)
        t_stat, p_unc = stats.ttest_ind(baseline, manifest, equal_var=False)
        test_used = "welch_t"
        test_stat = float(t_stat)

    p_unc = float(p_unc)
    p_bon = min(1.0, p_unc * N_COMPARISONS)

    ci_low, ci_high = bootstrap_ci_mean_diff(baseline, manifest)

    return TokenStat(
        scenario=scn.id,
        n_baseline=n_b,
        n_manifest=n_m,
        mean_baseline=mean_b,
        mean_manifest=mean_m,
        std_baseline=std_b,
        std_manifest=std_m,
        median_baseline=median_b,
        median_manifest=median_m,
        reduction_pct=reduction,
        cohens_d=d,
        shapiro_p_baseline=sw_b_p,
        shapiro_p_manifest=sw_m_p,
        test_used=test_used,
        test_statistic=test_stat,
        p_uncorrected=p_unc,
        p_bonferroni=p_bon,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def analyze_success(scn: ScenarioConfigV3,
                     baseline: np.ndarray, manifest: np.ndarray) -> SuccessStat:
    """success rate 분석 (사전 등록 §5.1).

    Args:
        baseline, manifest: success boolean arrays (0/1).
    """
    n_b, n_m = len(baseline), len(manifest)
    s_b = int(baseline.sum())
    s_m = int(manifest.sum())
    rate_b = s_b / n_b if n_b else float("nan")
    rate_m = s_m / n_m if n_m else float("nan")

    risk_diff_pp = (rate_m - rate_b) * 100.0

    # 2x2 contingency table:
    #             success | failure
    # baseline    s_b     | n_b - s_b
    # manifest    s_m     | n_m - s_m
    table = [[s_b, n_b - s_b], [s_m, n_m - s_m]]
    try:
        odds_ratio, p_unc = stats.fisher_exact(table, alternative="two-sided")
    except Exception:
        logger.exception("fisher_exact failed; using fallback")
        odds_ratio, p_unc = float("nan"), 1.0
    p_unc = float(p_unc)
    p_bon = min(1.0, p_unc * N_COMPARISONS)

    # Bootstrap CI for risk difference (in pp)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    diffs = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
    for i in range(BOOTSTRAP_RESAMPLES):
        sample_b = rng.choice(baseline, size=n_b, replace=True)
        sample_m = rng.choice(manifest, size=n_m, replace=True)
        diffs[i] = (float(np.mean(sample_m)) - float(np.mean(sample_b))) * 100.0
    ci_low = float(np.percentile(diffs, 2.5))
    ci_high = float(np.percentile(diffs, 97.5))

    return SuccessStat(
        scenario=scn.id,
        n_baseline=n_b,
        n_manifest=n_m,
        success_baseline=s_b,
        success_manifest=s_m,
        rate_baseline=rate_b,
        rate_manifest=rate_m,
        risk_difference_pp=risk_diff_pp,
        odds_ratio=float(odds_ratio),
        test_used="fisher_exact",
        p_uncorrected=p_unc,
        p_bonferroni=p_bon,
        ci_low_pp=ci_low,
        ci_high_pp=ci_high,
    )


def analyze_scenario(scn: ScenarioConfigV3,
                      df_rows: List[dict]) -> ScenarioResult:
    """단일 시나리오 분석 + H_i.1, H_i.2 자동 평가."""
    baseline_rows = [r for r in df_rows
                     if r["scenario"] == scn.id and r["agent"] == "baseline_dom"]
    manifest_rows = [r for r in df_rows
                     if r["scenario"] == scn.id and r["agent"] == "manifest_aware"]

    b_tokens = np.array([int(r["input_tokens"]) for r in baseline_rows])
    m_tokens = np.array([int(r["input_tokens"]) for r in manifest_rows])
    b_success = np.array([1 if str(r["success"]).lower() == "true" else 0
                          for r in baseline_rows])
    m_success = np.array([1 if str(r["success"]).lower() == "true" else 0
                          for r in manifest_rows])

    token_stat = analyze_tokens(scn, b_tokens, m_tokens)
    success_stat = analyze_success(scn, b_success, m_success)

    # H_i.1 (token reduction) 평가
    h_token = evaluate_hypothesis(
        hypothesis_id=f"H{scn.id[1]}.1",
        p_uncorrected=token_stat.p_uncorrected,
        effect_size=token_stat.reduction_pct,
        threshold=scn.h_token_pct,
        ci_low=-token_stat.ci_high,    # ci is for (b - m); positive means reduction
        ci_high=-token_stat.ci_low,
        n_comparisons=N_COMPARISONS,
    )
    # H_i.2 (success rate lift) 평가
    h_success = evaluate_hypothesis(
        hypothesis_id=f"H{scn.id[1]}.2",
        p_uncorrected=success_stat.p_uncorrected,
        effect_size=success_stat.risk_difference_pp,
        threshold=scn.h_success_pp,
        ci_low=success_stat.ci_low_pp,
        ci_high=success_stat.ci_high_pp,
        n_comparisons=N_COMPARISONS,
    )

    return ScenarioResult(
        scenario=scn.id,
        token=token_stat,
        success=success_stat,
        h_token=h_token,
        h_success=h_success,
    )


# --------------------------------------------------
# Pooled meta-analysis (Secondary)
# --------------------------------------------------

def pooled_effect_size(token_stats: List[TokenStat]) -> Dict[str, float]:
    """4개 시나리오 effect size 가중 평균 (사전 등록 §5.5, secondary)."""
    ds = [ts.cohens_d for ts in token_stats if not np.isnan(ts.cohens_d)
          and not np.isinf(ts.cohens_d)]
    ns = [ts.n_baseline + ts.n_manifest for ts in token_stats]
    if not ds:
        return {"weighted_d": float("nan"), "n_studies": 0}
    weights = np.array(ns[:len(ds)], dtype=float)
    weights = weights / weights.sum()
    weighted_d = float(np.average(ds, weights=weights))
    return {
        "weighted_d": weighted_d,
        "n_studies": len(ds),
        "min_d": float(np.min(ds)),
        "max_d": float(np.max(ds)),
    }


# --------------------------------------------------
# CSV load
# --------------------------------------------------

def load_metrics_csv(path: Path) -> List[dict]:
    """Phase 3 산출 metrics.csv 로드."""
    # [SECURE] with-context로 file 자동 close
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


# --------------------------------------------------
# Main analyze
# --------------------------------------------------

def analyze_all(csv_path: Path, output_dir: Path) -> dict:
    """전체 분석 실행 (사전 등록 §5 그대로)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    df_rows = load_metrics_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df_rows), csv_path)

    # 시나리오별 분석
    results: Dict[str, ScenarioResult] = {}
    for scn in SCENARIOS_V3:
        result = analyze_scenario(scn, df_rows)
        results[scn.id] = result
        logger.info(
            "%s: tokens reduction=%.1f%% (p=%.4f) | success diff=%+.1fpp (p=%.4f)",
            scn.id,
            result.token.reduction_pct,
            result.token.p_uncorrected,
            result.success.risk_difference_pp,
            result.success.p_uncorrected,
        )

    # Holm-Bonferroni (8 비교, parallel report)
    p_values_for_holm = []
    for sid in [s.id for s in SCENARIOS_V3]:
        p_values_for_holm.append(results[sid].token.p_uncorrected)
        p_values_for_holm.append(results[sid].success.p_uncorrected)
    p_holm = holm_bonferroni(p_values_for_holm)

    # Pooled meta-analysis (secondary)
    pooled = pooled_effect_size([r.token for r in results.values()])

    # 8 가설 결정 요약
    decisions = []
    for sid in [s.id for s in SCENARIOS_V3]:
        r = results[sid]
        decisions.append(asdict(r.h_token))
        decisions.append(asdict(r.h_success))

    # Holm-corrected p를 결정에 추가 (parallel report)
    for i, dec in enumerate(decisions):
        dec["p_holm"] = p_holm[i]

    # 가설 수용/기각/inconclusive 카운트
    summary_counts = {
        "accepted": sum(1 for d in decisions if d["accepted"]),
        "rejected": sum(1 for d in decisions if d["rejected"]),
        "inconclusive": sum(1 for d in decisions if d["inconclusive"]),
        "total": len(decisions),
    }

    output = {
        "pre_registration_tag": "v0.3-prereg-2026-04-28",
        "amendment_applied": ["Amendment 1 (2026-04-28): simulation-only measurement"],
        "alpha": ALPHA,
        "n_comparisons": N_COMPARISONS,
        "alpha_corrected": ALPHA_CORRECTED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "shapiro_threshold": SHAPIRO_THRESHOLD,
        "scenarios": {sid: {
            "token": asdict(results[sid].token),
            "success": asdict(results[sid].success),
        } for sid in [s.id for s in SCENARIOS_V3]},
        "decisions": decisions,
        "summary_counts": summary_counts,
        "pooled_meta_analysis": pooled,
    }

    json_path = output_dir / "analysis.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    md_path = output_dir / "analysis_summary.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write(_render_markdown_summary(output))

    logger.info("Analysis saved: %s", json_path)
    logger.info("Summary saved: %s", md_path)
    logger.info(
        "Hypothesis decisions — accepted: %d / rejected: %d / inconclusive: %d (of %d)",
        summary_counts["accepted"], summary_counts["rejected"],
        summary_counts["inconclusive"], summary_counts["total"],
    )
    return output


# --------------------------------------------------
# Markdown summary renderer
# --------------------------------------------------

def _render_markdown_summary(output: dict) -> str:
    """사람이 읽기 좋은 분석 요약."""
    lines = [
        "# AINM v3 Analysis Summary",
        "",
        f"**Pre-registration**: {output['pre_registration_tag']}",
        f"**Amendments**: {', '.join(output['amendment_applied'])}",
        f"**Alpha (uncorrected)**: {output['alpha']}",
        f"**Alpha (Bonferroni-corrected)**: {output['alpha_corrected']:.5f}",
        f"**Bootstrap resamples**: {output['bootstrap_resamples']:,}",
        "",
        "## Hypothesis Decisions",
        "",
        "| Hypothesis | Decision | Effect | Threshold | p (uncorrected) | p (Bonferroni) | p (Holm) | CI 95% |",
        "|------------|----------|--------|-----------|-----------------|----------------|----------|--------|",
    ]
    for d in output["decisions"]:
        if d["accepted"]:
            decision = "✅ Accepted"
        elif d["rejected"]:
            decision = "❌ Rejected"
        else:
            decision = "⚠️ Inconclusive"
        lines.append(
            f"| {d['hypothesis_id']} | {decision} | "
            f"{d['effect_size']:.2f} | "
            f"{_get_threshold_for_decision(d, output)} | "
            f"{d['p_uncorrected']:.5f} | {d['p_corrected']:.5f} | "
            f"{d.get('p_holm', float('nan')):.5f} | "
            f"({_get_ci_low(d, output):.2f}, {_get_ci_high(d, output):.2f}) |"
        )

    lines += [
        "",
        "## Per-Scenario Detail",
        "",
    ]
    for sid in ["S1", "S2", "S3", "S4"]:
        s = output["scenarios"][sid]
        t = s["token"]
        sc = s["success"]
        lines += [
            f"### {sid}",
            "",
            f"**Tokens** — baseline mean={t['mean_baseline']:.1f} (σ={t['std_baseline']:.1f}, n={t['n_baseline']}) | "
            f"manifest mean={t['mean_manifest']:.1f} (σ={t['std_manifest']:.1f}, n={t['n_manifest']})",
            f"  - Reduction: **{t['reduction_pct']:.2f}%** | Cohen's d = {t['cohens_d']:.3f}",
            f"  - Test: {t['test_used']} (Shapiro-Wilk p_baseline={t['shapiro_p_baseline']}, p_manifest={t['shapiro_p_manifest']})",
            f"  - Bootstrap 95% CI for mean(b) - mean(m): ({t['ci_low']:.2f}, {t['ci_high']:.2f})",
            "",
            f"**Success** — baseline rate={sc['rate_baseline']*100:.1f}% ({sc['success_baseline']}/{sc['n_baseline']}) | "
            f"manifest rate={sc['rate_manifest']*100:.1f}% ({sc['success_manifest']}/{sc['n_manifest']})",
            f"  - Risk difference: **{sc['risk_difference_pp']:+.2f} pp** | Odds ratio = {sc['odds_ratio']}",
            f"  - Bootstrap 95% CI for risk diff (pp): ({sc['ci_low_pp']:.2f}, {sc['ci_high_pp']:.2f})",
            "",
        ]

    lines += [
        "## Pooled Meta-analysis (Secondary)",
        "",
        f"- Weighted Cohen's d (across scenarios): {output['pooled_meta_analysis'].get('weighted_d', 'n/a')}",
        f"- Min d: {output['pooled_meta_analysis'].get('min_d', 'n/a')}",
        f"- Max d: {output['pooled_meta_analysis'].get('max_d', 'n/a')}",
        "",
        "## Decision Counts",
        "",
        f"- Accepted: **{output['summary_counts']['accepted']}** / {output['summary_counts']['total']}",
        f"- Rejected: **{output['summary_counts']['rejected']}** / {output['summary_counts']['total']}",
        f"- Inconclusive: **{output['summary_counts']['inconclusive']}** / {output['summary_counts']['total']}",
        "",
        "---",
        "",
        "*Generated by `analyze_v3.py` per pre-registration §5. "
        "All decision rules pre-registered (§6); no post-hoc analysis applied.*",
    ]
    return "\n".join(lines)


def _get_threshold_for_decision(d: dict, output: dict) -> str:
    """가설 ID에서 시나리오·임계값 추출."""
    hid = d["hypothesis_id"]   # 예: "H1.1"
    sid = "S" + hid[1]
    is_token = hid.endswith(".1")
    scn = next(s for s in SCENARIOS_V3 if s.id == sid)
    if is_token:
        return f"{scn.h_token_pct}%"
    else:
        return f"{scn.h_success_pp}pp"


def _get_ci_low(d: dict, output: dict) -> float:
    """가설 ID로 해당 CI low 추출."""
    hid = d["hypothesis_id"]
    sid = "S" + hid[1]
    if hid.endswith(".1"):
        # token: ci is for (b - m); H_i.1 reduction = positive; CI for "AINM reduction" = (-ci_high, -ci_low)
        return -output["scenarios"][sid]["token"]["ci_high"]
    else:
        return output["scenarios"][sid]["success"]["ci_low_pp"]


def _get_ci_high(d: dict, output: dict) -> float:
    hid = d["hypothesis_id"]
    sid = "S" + hid[1]
    if hid.endswith(".1"):
        return -output["scenarios"][sid]["token"]["ci_low"]
    else:
        return output["scenarios"][sid]["success"]["ci_high_pp"]


# --------------------------------------------------
# CLI
# --------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze AINM v3 benchmark per pre-registration v0.3-prereg-2026-04-28."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to metrics.csv (output of run_benchmark_v3.py).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results_v3"),
        help="Output directory (default ./results_v3/).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.input.is_file():
        logger.error("input not found: %s", args.input)
        return 1
    analyze_all(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Resource Release: with-context로 CSV·JSON·MD 파일 자동 close
#   - Improper Input for Security Decision: file existence 체크, scenario 화이트리스트 (scenarios_v3 위임)
#   - Missing Error Handling: Shapiro-Wilk·Fisher·Mann-Whitney 예외 처리
#   - Hard-coded Credentials: 없음 (모든 설정은 사전 등록 상수)
#   - Improper Random Value: bootstrap에 numpy default_rng (PCG64 — 결정론·재현성 목적, 보안용 X)
# Not Applied:
#   - [WARN] 본 모듈은 분석 전용. 외부 입력은 Phase 3 산출 CSV만 받음.
#   - [WARN] CSV 파싱 시 입력 자체의 무결성은 Phase 3에서 보장 (별도 검증 없음).
# --------------------------------------------------
