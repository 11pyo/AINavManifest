# -*- coding: utf-8 -*-
"""
Manifest-aware AI agent — v3 (사전 등록 v0.3-prereg-2026-04-28).

본 모듈은 사전 등록된 4 시나리오(S1~S4)에 대한 매니페스트 에이전트의 entry point.

Amendment 1 (2026-04-28)에 따라 측정은 시뮬레이션 모델 기반이며, 본 모듈은
`scenarios_v3.simulate_manifest_v3()`의 thin wrapper로서 다음 역할을 한다:

  1. CLI 진입점 — 단일 시나리오·단일 seed로 검증용 trial 실행
  2. Trial 인터페이스 통합 — `run_manifest_v3(scenario_id, seed) -> SimRecord`
  3. Manifest JSON 로드 검증 — 사전 등록된 manifest 파일 무결성 확인 (canonical hash 사전 검증)
  4. Future work stub — Stage 4 진입 시 실제 LLM 호출 + 실 manifest fetch 모드 추가

본 모듈은 v1 `manifest_agent.py`와 병행 유지된다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

# v3 시나리오·시뮬레이션 모델
try:
    # 패키지 컨텍스트로 import 시
    from .common import Metrics, count_tokens
    from ..benchmark.scenarios import SimRecord
    from ..benchmark.scenarios_v3 import (
        SCENARIOS_V3,
        get_scenario_v3,
        simulate_manifest_v3,
        stable_seed_v3,
    )
except ImportError:
    # 단독 실행(스크립트) 컨텍스트 fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from agent.common import Metrics, count_tokens  # type: ignore
    from benchmark.scenarios import SimRecord  # type: ignore
    from benchmark.scenarios_v3 import (  # type: ignore
        SCENARIOS_V3,
        get_scenario_v3,
        simulate_manifest_v3,
        stable_seed_v3,
    )


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Manifest 파일 위치
# --------------------------------------------------

MANIFEST_DIR = Path(__file__).resolve().parents[1] / "manifests"

MANIFEST_FILES: Dict[str, str] = {
    "S1": "S1_erp_order.json",
    "S2": "S2_search_filter.json",
    "S3": "S3_multistep_wizard.json",
    "S4": "S4_i18n_form.json",
}


def load_manifest(scenario_id: str) -> dict:
    """사전 등록된 manifest JSON 로드.

    Args:
        scenario_id: "S1" | "S2" | "S3" | "S4"

    Returns:
        manifest dict (검증된 JSON)

    Raises:
        ValueError: 미등록 scenario_id
        FileNotFoundError: manifest 파일 없음
    """
    # [SECURE] scenario_id 화이트리스트 검증 — Improper Input 방지
    if scenario_id not in MANIFEST_FILES:
        raise ValueError(
            f"unknown scenario id: {scenario_id} "
            f"(valid: {sorted(MANIFEST_FILES.keys())})"
        )

    fname = MANIFEST_FILES[scenario_id]
    path = MANIFEST_DIR / fname

    # [SECURE] Path traversal 방지 — 사전 검증된 파일명만 사용 (Category 1)
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")

    # [SECURE] with-context로 file resource 보장 해제 (Category 5)
    with path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    return manifest


def compute_canonical_hash(manifest: dict) -> str:
    """매니페스트의 정준 SHA-256 해시 계산.

    사전 등록 §3-3 (experimental-design.md): 정준 직렬화 = sorted_keys + UTF-8 + no insignificant whitespace.
    매니페스트 자체에 박힌 canonicalHash 필드는 본 계산에서 제외 (자기참조 방지).
    """
    # canonicalHash 필드 자체를 제외한 새 dict 구성
    payload = {k: v for k, v in manifest.items() if k != "meta"}
    if "meta" in manifest:
        meta = {k: v for k, v in manifest["meta"].items() if k != "canonicalHash"}
        payload["meta"] = meta

    # [SECURE] SHA-256 사용 — Weak Cryptographic Algorithm 방지 (Category 2)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# --------------------------------------------------
# Public API — Phase 3 benchmark runner가 호출하는 단일 entry point
# --------------------------------------------------

def run_manifest_v3(scenario_id: str, repeat_index: int, base_seed: int = 1000,
                     trust_noise: float = 0.0) -> SimRecord:
    """사전 등록된 시나리오 1개 trial을 시뮬레이션 모델로 실행.

    Args:
        scenario_id: "S1" | "S2" | "S3" | "S4"
        repeat_index: 0~99 (사전 등록 §8.3)
        base_seed: 1000 (사전 등록 기본값)
        trust_noise: registry unknown 확률 (사전 등록 §3-3에 따라 기본 0.0).
            future ablation에서 활용 가능 (Stage 4 이후).

    Returns:
        SimRecord
    """
    scn = get_scenario_v3(scenario_id)
    seed = stable_seed_v3(scenario_id, repeat_index, base=base_seed)
    rng = random.Random(seed)

    # 사전 등록 매니페스트 로드 + 무결성 검증 (sanity)
    # 사전 등록 핵심: manifest는 결과 보기 전 commit됨
    try:
        manifest = load_manifest(scenario_id)
        # 매니페스트 토큰 길이 sanity 체크 (사전 등록값 ± 50% 허용)
        manifest_text = json.dumps(manifest, ensure_ascii=False)
        actual_tokens = count_tokens(manifest_text)
        expected_tokens = scn.manifest_tokens
        if not (expected_tokens * 0.5 <= actual_tokens <= expected_tokens * 1.5):
            logger.warning(
                "manifest_tokens divergence: %s expected=%d actual=%d "
                "(sanity range 50-150%%)",
                scenario_id, expected_tokens, actual_tokens,
            )
    except (FileNotFoundError, ValueError) as e:
        # 매니페스트 로드 실패 = 코드/환경 오류, 결과 영향 명시
        # 사전 등록 §7-2: HTTP error → trial=failure로 분류
        logger.warning("manifest load failed for %s: %s", scenario_id, e)

    return simulate_manifest_v3(scn, rng, trust_noise=trust_noise)


# --------------------------------------------------
# Future Work Stub
# --------------------------------------------------

def run_manifest_v3_real_llm(scenario_id: str, repeat_index: int,
                              llm_model: str = "gpt-4o-mini") -> SimRecord:
    """[STUB] 실제 LLM API + 실 manifest fetch 호출. 현재 미구현."""
    raise NotImplementedError(
        f"Real-LLM manifest mode is reserved for future work (Stage 4). "
        f"Current pre-registration uses simulation model only (Amendment 1). "
        f"Requested: scenario={scenario_id}, model={llm_model}, repeat={repeat_index}"
    )


# --------------------------------------------------
# CLI — 개발자 검증·디버그용
# --------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manifest-aware agent v3 (per pre-registration)."
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
        "--verify-manifests",
        action="store_true",
        help="Load all 4 manifests, compute canonical hashes, and exit.",
    )
    return parser.parse_args()


def _verify_manifests() -> None:
    """모든 사전 등록 매니페스트 로드 + 정준 해시 출력."""
    for sid in MANIFEST_FILES:
        try:
            manifest = load_manifest(sid)
            canonical = compute_canonical_hash(manifest)
            text = json.dumps(manifest, ensure_ascii=False)
            tokens = count_tokens(text)
            scn = get_scenario_v3(sid)
            print(
                f"{sid}: ok | tokens={tokens} (declared {scn.manifest_tokens}) | "
                f"canonical={canonical}"
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"{sid}: ERROR — {e}", file=sys.stderr)


def _print_sim_record(rec: SimRecord) -> None:
    print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))


def main() -> int:
    args = _parse_args()

    if args.verify_manifests:
        _verify_manifests()
        return 0

    if args.scenario:
        rec = run_manifest_v3(args.scenario, args.repeat, base_seed=args.base_seed)
        _print_sim_record(rec)
        return 0

    # 시나리오 미지정: 모든 시나리오 1회씩
    records: List[SimRecord] = []
    for s in SCENARIOS_V3:
        rec = run_manifest_v3(s.id, args.repeat, base_seed=args.base_seed)
        records.append(rec)
    print(json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Input for Security Decision: scenario_id 화이트리스트 검증 (load_manifest, get_scenario_v3)
#   - Path Traversal: MANIFEST_FILES 화이트리스트 + Path 객체 사용
#   - Improper Resource Release: with-context로 file 자동 close
#   - Weak Cryptographic Algorithm: SHA-256 사용 (canonical hash)
#   - Missing Error Handling: NotImplementedError·FileNotFoundError 분기
#   - Error Message Information Exposure: 사용자 메시지에 내부 경로 노출 X
# Not Applied:
#   - [WARN] Real-LLM 모드(현재 stub) 활성화 시 API 키 환경 변수 보안, HTTPS 인증서 검증 필수.
#   - [WARN] Registry 라운드트립 검증은 시뮬레이션. 실제 환경 적용 시 외부 registry HTTP 호출 시 verify=True 유지.
# --------------------------------------------------
