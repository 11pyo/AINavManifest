# -*- coding: utf-8 -*-
"""
벤치마크 v3 — 사전 등록 (Pre-registration v0.3-prereg-2026-04-28) 4 시나리오.

본 모듈은 `pre-registration.md` 및 `experimental-design.md`의 정의를 그대로 코드로 옮긴
implementation이며, 결과 보기 전 commit된다. 사후 변경은 amendment로 기록되어야 한다.

시뮬레이션 모델은 v2 (`scenarios.py`)의 검증된 모델을 그대로 재사용한다 (Amendment 1, 2026-04-28).
시나리오 정의·DOM tier 매핑·manifest_tokens는 본 모듈에 결과 보기 전 박힌다.

사전 등록 요약:
  - 4 시나리오 (S1 ERP / S2 Search-filter / S3 Multi-step Wizard / S4 i18n form)
  - 2 agents (baseline_dom, manifest_aware)
  - n=100 trials per (agent × scenario)
  - 총 800 trials
  - Random seed: 1000 + trial_index (per scenario)

Hypotheses (사전 등록):
  - H_i.1: AINM input_tokens가 baseline 대비 X% 이상 작다 (X=70/60/90/85 for S1/S2/S3/S4)
  - H_i.2: AINM success rate가 baseline 대비 Y pp 이상 크다 (Y=70/60/80/70)

DOM tier 매핑 근거 (실제 사이트 패턴 인용):
  - S1 ERP order entry → mid: 전형적 SAP/Oracle/Workday 거래 폼, 노이즈 비율 ~55%
  - S2 Search-filter-select → mid: 이커머스/잡사이트 검색 결과, 광고·추천·페이지네이션 노이즈
  - S3 Multi-step Wizard → legacy: 5+ step 누적 DOM, hidden field·세션 state 누적
  - S4 i18n form → mid: 다언어 메뉴·번역 콘텐츠 노이즈

Manifest tokens 추정 근거:
  - 시나리오의 step 수·selector 수·requirement 복잡도에 따라 결정론적으로 추정
  - 실제 manifest JSON을 tiktoken으로 카운트한 값 + 메타 오버헤드
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import List

# v2 시뮬레이션 모델 재사용 (Amendment 1)
from .scenarios import (
    DOM_TIERS,
    SimRecord,
    _baseline_success_prob,
    simulate_baseline,
    simulate_manifest,
)


# --------------------------------------------------
# 사전 등록 4 시나리오 정의 (v0.3-prereg-2026-04-28)
# --------------------------------------------------
# 본 정의는 결과 보기 전 commit된다. 변경은 amendment 기록 필수.
# --------------------------------------------------

@dataclass(frozen=True)
class ScenarioConfigV3:
    """사전 등록 v3 시나리오 정의.

    Attributes:
        id: 사전 등록 ID (S1~S4)
        name_en: 영문 명 (논문 표기용)
        name_ko: 한국어 명
        category: HCI 분류 (Transactional/IR/Sequential/i18n)
        steps: manifest steps 수
        manifest_tokens: 매니페스트 JSON 토큰 길이 (사전 등록값)
        dom_tier: 시뮬레이션 DOM 복잡도 (light/mid/legacy)
        h_token_pct: 가설 H_i.1 임계값 (토큰 감소율 %)
        h_success_pp: 가설 H_i.2 임계값 (성공률 향상 percentage points)
        description: 카테고리 정당화
    """
    id: str
    name_en: str
    name_ko: str
    category: str
    steps: int
    manifest_tokens: int
    dom_tier: str
    h_token_pct: float
    h_success_pp: float
    description: str


SCENARIOS_V3: List[ScenarioConfigV3] = [
    ScenarioConfigV3(
        id="S1",
        name_en="ERP Order Entry",
        name_ko="ERP 주문 입력",
        category="Transactional UI",
        steps=8,
        manifest_tokens=520,
        dom_tier="mid",
        h_token_pct=70.0,
        h_success_pp=70.0,
        description=(
            "다단계 폼 입력·single submit. 현실 사이트 근거: "
            "SAP S/4HANA 주문 화면, Oracle Fusion AP, Workday 거래 입력."
        ),
    ),
    ScenarioConfigV3(
        id="S2",
        name_en="Search-Filter-Select",
        name_ko="검색·필터·선택",
        category="Information Retrieval UI",
        steps=6,
        manifest_tokens=320,
        dom_tier="mid",
        h_token_pct=60.0,
        h_success_pp=60.0,
        description=(
            "동적 결과 페이지·필터 조합·정렬·결과 1건 선택. 현실 사이트 근거: "
            "Amazon, Naver Shopping, Indeed, Google Scholar."
        ),
    ),
    ScenarioConfigV3(
        id="S3",
        name_en="Multi-step Wizard",
        name_ko="다단계 위저드",
        category="Sequential UI (state-bearing)",
        steps=12,
        manifest_tokens=640,
        dom_tier="legacy",
        h_token_pct=90.0,
        h_success_pp=80.0,
        description=(
            "5+ step 누적 state·약관·검토·제출. 현실 사이트 근거: "
            "보험 가입, 공공 민원 (정부24), 회원 등록 wizard."
        ),
    ),
    ScenarioConfigV3(
        id="S4",
        name_en="Internationalized Form",
        name_ko="다언어 폼",
        category="Internationalized UI",
        steps=10,
        manifest_tokens=480,
        dom_tier="mid",
        h_token_pct=85.0,
        h_success_pp=70.0,
        description=(
            "한국어 UI ↔ 영어 UI 전환·동일 데이터 입력. 현실 사이트 근거: "
            "국제 SaaS, 정부 다언어 포털, 글로벌 e-commerce."
        ),
    ),
]


def get_scenario_v3(sid: str) -> ScenarioConfigV3:
    """ID로 시나리오 조회. 없으면 ValueError."""
    # [SECURE] 화이트리스트 검증 - Improper Input for Security Decision 방지 (Category 1)
    valid_ids = {s.id for s in SCENARIOS_V3}
    if sid not in valid_ids:
        raise ValueError(f"unknown scenario id: {sid} (valid: {sorted(valid_ids)})")
    return next(s for s in SCENARIOS_V3 if s.id == sid)


# --------------------------------------------------
# v3 시뮬레이션 어댑터
# --------------------------------------------------
# v3 시나리오를 v2 simulate_baseline / simulate_manifest 함수 입력으로 변환.
# v2 함수는 ScenarioConfig를 받으므로 어댑터 데이터클래스 사용.
# --------------------------------------------------

@dataclass(frozen=True)
class _V2ScenarioAdapter:
    """v2 simulate_* 함수 호환을 위한 어댑터 (v2 ScenarioConfig 인터페이스)."""
    id: str
    name_ko: str
    steps: int
    manifest_tokens: int
    description: str


def _to_v2_adapter(scn: ScenarioConfigV3) -> _V2ScenarioAdapter:
    return _V2ScenarioAdapter(
        id=scn.id,
        name_ko=scn.name_ko,
        steps=scn.steps,
        manifest_tokens=scn.manifest_tokens,
        description=scn.description,
    )


def simulate_baseline_v3(scn: ScenarioConfigV3, rng: random.Random) -> SimRecord:
    """v2 simulate_baseline에 v3 시나리오의 dom_tier를 결합."""
    return simulate_baseline(_to_v2_adapter(scn), scn.dom_tier, rng)


def simulate_manifest_v3(scn: ScenarioConfigV3, rng: random.Random,
                          trust_noise: float = 0.0) -> SimRecord:
    """v2 simulate_manifest에 v3 시나리오의 dom_tier를 결합.

    trust_noise=0.0 (기본): 본 사전 등록 가설은 manifest agent의 success_rate=100%
    가정. registry 신뢰 검증 실패 모델은 별도 ablation 시나리오로 분리 (future work).
    """
    return simulate_manifest(_to_v2_adapter(scn), scn.dom_tier, rng,
                              trust_noise=trust_noise)


# --------------------------------------------------
# 결정론적 시드 (v2 stable_seed 재사용 + v3 prefix)
# --------------------------------------------------

def stable_seed_v3(scenario_id: str, repeat_index: int, base: int = 1000) -> int:
    """시나리오 + repeat_index로 결정론적 seed 생성.

    사전 등록 §8.3: base=1000, per-trial seed = 1000 + trial_index.
    시나리오 간 동일 seed 공유 (시나리오 효과 분리 가능).
    """
    if not isinstance(repeat_index, int) or repeat_index < 0:
        raise ValueError(f"repeat_index must be non-negative integer: {repeat_index}")
    if base < 0:
        raise ValueError(f"base must be non-negative: {base}")
    # 사전 등록 §8.3 정의: 시나리오 무관 동일 seed
    return base + repeat_index


# --------------------------------------------------
# 가설 평가 헬퍼 (사전 등록 §6 결정 기준)
# --------------------------------------------------

@dataclass(frozen=True)
class HypothesisDecision:
    """사전 등록된 결정 기준에 따른 가설 평가 결과."""
    hypothesis_id: str       # 예: "H1.1"
    accepted: bool           # 수용 여부
    rejected: bool           # 기각 여부
    inconclusive: bool       # 결정 불가
    threshold_met: bool      # 효과 크기 임계값 만족
    p_corrected: float       # Bonferroni-corrected p
    p_uncorrected: float     # 원 p
    effect_size: float       # 절감률(%) 또는 percentage points
    ci_excludes_zero: bool   # 95% CI가 0 제외하는가
    reason: str              # 결정 사유


def evaluate_hypothesis(
    hypothesis_id: str,
    p_uncorrected: float,
    effect_size: float,
    threshold: float,
    ci_low: float,
    ci_high: float,
    n_comparisons: int = 8,
) -> HypothesisDecision:
    """사전 등록 §6 결정 기준에 따라 가설 자동 평가.

    수용: p_corrected < 0.00625 AND effect_size >= threshold AND CI excludes 0
    기각: p_uncorrected >= 0.05 OR effect_size < threshold OR CI includes 0
    Inconclusive: 0.00625 <= p_uncorrected < 0.05 (otherwise above)
    """
    if not (0.0 <= p_uncorrected <= 1.0):
        raise ValueError(f"p_uncorrected out of range: {p_uncorrected}")
    if n_comparisons < 1:
        raise ValueError(f"n_comparisons must be >= 1: {n_comparisons}")

    p_corrected = min(1.0, p_uncorrected * n_comparisons)  # Bonferroni
    threshold_met = effect_size >= threshold
    ci_excludes_zero = (ci_low > 0.0) or (ci_high < 0.0)

    accepted = (p_corrected < 0.00625) and threshold_met and ci_excludes_zero
    rejected = (p_uncorrected >= 0.05) or (not threshold_met) or (not ci_excludes_zero)
    inconclusive = (0.00625 <= p_uncorrected < 0.05) and (not rejected) and (not accepted)

    if accepted:
        reason = "All criteria met"
    elif rejected:
        reasons = []
        if p_uncorrected >= 0.05:
            reasons.append(f"p_uncorrected={p_uncorrected:.4f} >= 0.05")
        if not threshold_met:
            reasons.append(f"effect={effect_size:.2f} < threshold={threshold:.2f}")
        if not ci_excludes_zero:
            reasons.append(f"CI=[{ci_low:.2f},{ci_high:.2f}] includes 0")
        reason = "; ".join(reasons)
    else:
        reason = f"Inconclusive (0.00625 <= p={p_uncorrected:.4f} < 0.05)"

    return HypothesisDecision(
        hypothesis_id=hypothesis_id,
        accepted=accepted,
        rejected=rejected,
        inconclusive=inconclusive,
        threshold_met=threshold_met,
        p_corrected=p_corrected,
        p_uncorrected=p_uncorrected,
        effect_size=effect_size,
        ci_excludes_zero=ci_excludes_zero,
        reason=reason,
    )


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Input for Security Decision: scenario id 화이트리스트 검증 (get_scenario_v3)
#   - Integer/Float Overflow: p_uncorrected, repeat_index, n_comparisons 범위 사전 검증
#   - Improper Resource Release: 본 모듈은 외부 리소스(파일·소켓) 미사용
# Not Applied:
#   - [WARN] 본 모듈은 결정론 시뮬레이션·통계 헬퍼만 제공. 외부 입력은 호출자가 검증.
#   - [WARN] HypothesisDecision 결과는 frozen dataclass로 immutable. 결과 변경 불가.
# --------------------------------------------------
