# -*- coding: utf-8 -*-
"""
Baseline DOM-analysis agent — v3 (사전 등록 v0.3-prereg-2026-04-28).

본 모듈은 사전 등록된 4 시나리오(S1~S4)에 대한 베이스라인 에이전트의 entry point.

Amendment 1 (2026-04-28)에 따라 측정은 시뮬레이션 모델 기반이며, 본 모듈은
`scenarios_v3.simulate_baseline_v3()`의 thin wrapper로서 다음 역할을 한다:

  1. CLI 진입점 — 단일 시나리오·단일 seed로 검증용 trial 실행
  2. Trial 인터페이스 통합 — `run_baseline_v3(scenario_id, seed) -> SimRecord`
  3. Future work stub — Stage 4(실제 LLM 호출 비교) 진입 시 본 함수에
     real-LLM 모드 추가 (현재는 시뮬레이션만)

본 모듈은 v1 `baseline_agent.py`(실제 HTTP + 휴리스틱)와 병행 유지된다.
v1은 ERP 시나리오 단독 검증용으로 보존되며, v3는 사전 등록 4 시나리오를 대상으로 한다.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from typing import List

# v3 시나리오·시뮬레이션 모델
try:
    # 패키지 컨텍스트로 import 시
    from .common import Metrics
    from ..benchmark.scenarios import SimRecord
    from ..benchmark.scenarios_v3 import (
        SCENARIOS_V3,
        get_scenario_v3,
        simulate_baseline_v3,
        stable_seed_v3,
    )
except ImportError:
    # 단독 실행(스크립트) 컨텍스트 fallback
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    from agent.common import Metrics  # type: ignore
    from benchmark.scenarios import SimRecord  # type: ignore
    from benchmark.scenarios_v3 import (  # type: ignore
        SCENARIOS_V3,
        get_scenario_v3,
        simulate_baseline_v3,
        stable_seed_v3,
    )


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Public API — Phase 3 benchmark runner가 호출하는 단일 entry point
# --------------------------------------------------

def run_baseline_v3(scenario_id: str, repeat_index: int, base_seed: int = 1000) -> SimRecord:
    """사전 등록된 시나리오 1개 trial을 시뮬레이션 모델로 실행.

    Args:
        scenario_id: "S1" | "S2" | "S3" | "S4"
        repeat_index: 0~99 (사전 등록 §8.3: per-trial seed = base + index)
        base_seed: 1000 (사전 등록 기본값)

    Returns:
        SimRecord: scenario·agent·input_tokens·success·etc 포함

    Raises:
        ValueError: scenario_id가 사전 등록 화이트리스트 외부일 경우
    """
    # [SECURE] 입력 화이트리스트 검증 — Improper Input for Security Decision 방지
    scn = get_scenario_v3(scenario_id)
    seed = stable_seed_v3(scenario_id, repeat_index, base=base_seed)
    rng = random.Random(seed)
    return simulate_baseline_v3(scn, rng)


# --------------------------------------------------
# Future Work Stub — Stage 4 실제 LLM 호출 비교 (Phase 5 이후)
# --------------------------------------------------

def run_baseline_v3_real_llm(scenario_id: str, repeat_index: int,
                              llm_model: str = "gpt-4o-mini") -> SimRecord:
    """[STUB] 실제 LLM API를 호출하는 베이스라인. 현재 미구현.

    사전 등록 §8 Limitations에 명시된 future work. Stage 4 진입 시 본 함수에
    실제 OpenAI/Anthropic API 호출 + 토큰·성공률 측정 로직을 추가할 예정.
    그 시점에 별도 amendment 기록 + 가설 검증 재실행이 필요하다.

    현재 호출 시 NotImplementedError를 발생시켜 우발적 실 LLM 호출을 차단.
    """
    raise NotImplementedError(
        f"Real-LLM baseline mode is reserved for future work (Stage 4). "
        f"Current pre-registration uses simulation model only (Amendment 1). "
        f"Requested: scenario={scenario_id}, model={llm_model}, repeat={repeat_index}"
    )


# --------------------------------------------------
# CLI — 개발자 검증·디버그용
# --------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baseline agent v3 (DOM-analysis simulation, per pre-registration)."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        required=False,
        choices=[s.id for s in SCENARIOS_V3],
        help="Scenario ID (S1~S4). If omitted, all 4 scenarios are run once each.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=0,
        help="Repeat index (0..n-1). Determines seed = base_seed + repeat.",
    )
    parser.add_argument(
        "--base-seed",
        type=int,
        default=1000,
        help="Base seed (default 1000, per pre-registration §8.3).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered scenarios and exit.",
    )
    return parser.parse_args()


def _list_scenarios() -> None:
    rows = [
        f"  {s.id}: {s.name_en} ({s.category}) | "
        f"steps={s.steps} tier={s.dom_tier} manifest_tokens={s.manifest_tokens} | "
        f"H_{s.id[1]}.1 ≥{s.h_token_pct}%, H_{s.id[1]}.2 ≥{s.h_success_pp}pp"
        for s in SCENARIOS_V3
    ]
    print("Registered scenarios (pre-registration v0.3-prereg-2026-04-28):")
    print("\n".join(rows))


def _print_sim_record(rec: SimRecord) -> None:
    """SimRecord를 사람·스크립트가 모두 읽기 쉽게 JSON으로 출력."""
    payload = rec.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    args = _parse_args()
    if args.list:
        _list_scenarios()
        return 0

    if args.scenario:
        rec = run_baseline_v3(args.scenario, args.repeat, base_seed=args.base_seed)
        _print_sim_record(rec)
        return 0

    # 시나리오 미지정: 모든 시나리오 1회씩 실행 (sanity check)
    records: List[SimRecord] = []
    for s in SCENARIOS_V3:
        rec = run_baseline_v3(s.id, args.repeat, base_seed=args.base_seed)
        records.append(rec)
    print(json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Input for Security Decision: scenario_id 화이트리스트 검증 (get_scenario_v3 위임)
#   - Missing Error Handling: NotImplementedError로 미구현 경로 차단
#   - Error Message Information Exposure: 사용자 가시 메시지에 내부 경로·세션 정보 미노출
# Not Applied:
#   - [WARN] 본 모듈은 시뮬레이션 모델 wrapper로서 외부 네트워크·파일·DB 미사용.
#           Real-LLM 모드 활성화 시 별도 보안 검토 필요 (API 키 환경 변수, 인증서 검증 등).
# --------------------------------------------------
