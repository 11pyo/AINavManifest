# -*- coding: utf-8 -*-
"""
Phase 3 — 벤치마크 실행 (사전 등록 v0.3-prereg-2026-04-28).

본 모듈은 사전 등록된 4 시나리오(S1~S4) × 2 agents × n trials 를 실행하여
raw 데이터를 CSV로 저장한다.

사전 등록 §8.4의 표준 호출:
  python -m benchmark.run_benchmark_v3 --seed 1000 --repeats 100 --output results_v3/

또는 단독 실행:
  cd validation/
  python benchmark/run_benchmark_v3.py --seed 1000 --repeats 100 --output results_v3/

사전 등록 정합성:
  - 표본 크기: --repeats 100 (사전 등록 §4.1)
  - Seed: 1000 + trial_index (사전 등록 §8.3, scenarios_v3.stable_seed_v3)
  - 실행 순서: 시나리오·agent별 인터리브 (시간 효과 분리)
  - Stopping rule: --repeats 도달 즉시 종료, 부분 추가 금지 (§4.3)
  - Outlier 처리: 분석 단계에서 결정 (본 모듈은 raw 그대로 기록)

본 모듈은 결과 보기 전 commit되어야 한다 (사전 등록 §6 핵심).
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

# v3 agent · scenario import
try:
    from .scenarios import SimRecord
    from .scenarios_v3 import SCENARIOS_V3
    from ..agent.baseline_agent_v3 import run_baseline_v3
    from ..agent.manifest_agent_v3 import run_manifest_v3
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmark.scenarios import SimRecord  # type: ignore
    from benchmark.scenarios_v3 import SCENARIOS_V3  # type: ignore
    from agent.baseline_agent_v3 import run_baseline_v3  # type: ignore
    from agent.manifest_agent_v3 import run_manifest_v3  # type: ignore


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# --------------------------------------------------
# CSV 컬럼 (사전 등록 raw 보고용 — 변경 시 amendment)
# --------------------------------------------------

CSV_COLUMNS = [
    "scenario",        # S1~S4
    "agent",           # baseline_dom | manifest_aware
    "trial_index",     # 0~n-1 (per (scenario, agent))
    "seed",            # 1000 + trial_index
    "input_tokens",    # primary outcome
    "success",         # primary outcome (True/False)
    "http_requests",
    "llm_calls",
    "steps_attempted",
    "steps_succeeded",
    "wall_time_ms",
    "failure_reason",
    "dom_tier",
    "notes",
]


# --------------------------------------------------
# Trial 실행
# --------------------------------------------------

def _run_one_trial(scenario_id: str, agent: str, trial_index: int,
                    base_seed: int) -> SimRecord:
    """단일 trial 실행. 사전 등록된 entry point를 사용."""
    if agent == "baseline_dom":
        return run_baseline_v3(scenario_id, trial_index, base_seed=base_seed)
    elif agent == "manifest_aware":
        return run_manifest_v3(scenario_id, trial_index, base_seed=base_seed)
    else:
        raise ValueError(f"unknown agent: {agent}")


def _record_to_row(rec: SimRecord, trial_index: int, base_seed: int) -> dict:
    """SimRecord → CSV row dict 변환."""
    return {
        "scenario":        rec.scenario,
        "agent":           rec.agent,
        "trial_index":     trial_index,
        "seed":             base_seed + trial_index,
        "input_tokens":    rec.input_tokens,
        "success":          rec.success,
        "http_requests":   rec.http_requests,
        "llm_calls":       rec.llm_calls,
        "steps_attempted": rec.steps_attempted,
        "steps_succeeded": rec.steps_succeeded,
        "wall_time_ms":    rec.wall_time_ms,
        "failure_reason":  rec.failure_reason,
        "dom_tier":        rec.dom_tier,
        "notes":            "|".join(rec.notes) if rec.notes else "",
    }


# --------------------------------------------------
# Main benchmark loop
# --------------------------------------------------

def run_benchmark(scenario_ids: List[str], repeats: int, base_seed: int,
                  output_dir: Path) -> dict:
    """전체 벤치마크 실행.

    실행 순서: scenario별 outer loop, trial별 inner loop, agent별 (baseline → manifest).
    Inner loop의 baseline·manifest 인터리브로 시간대 효과 분리.

    Returns:
        summary dict (counts, durations, output paths)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "metrics.csv"
    summary_path = output_dir / "run_summary.json"

    rows: List[dict] = []
    counts = {sid: {"baseline_dom": 0, "manifest_aware": 0} for sid in scenario_ids}
    failures = {sid: {"baseline_dom": [], "manifest_aware": []} for sid in scenario_ids}

    t0 = time.perf_counter()

    for sid in scenario_ids:
        logger.info("=== Scenario %s start (n=%d × 2 agents) ===", sid, repeats)
        for i in range(repeats):
            for agent in ("baseline_dom", "manifest_aware"):
                try:
                    rec = _run_one_trial(sid, agent, i, base_seed)
                    row = _record_to_row(rec, i, base_seed)
                    rows.append(row)
                    counts[sid][agent] += 1
                except Exception as e:
                    # [SECURE] 외부 입력이 아닌 코드 오류는 fail-fast — Missing Error Handling 방지
                    # 단, 1개 trial 실패가 전체 실험을 중단시키지 않도록 기록 후 계속
                    logger.exception("trial failed: scenario=%s agent=%s trial=%d", sid, agent, i)
                    failures[sid][agent].append({
                        "trial_index": i,
                        "error": str(e),
                    })
        logger.info("=== Scenario %s done (baseline=%d, manifest=%d) ===",
                     sid, counts[sid]["baseline_dom"], counts[sid]["manifest_aware"])

    elapsed = time.perf_counter() - t0

    # CSV 저장
    # [SECURE] 파일은 with-context로 자동 close — Improper Resource Release 방지
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    summary = {
        "pre_registration_tag": "v0.3-prereg-2026-04-28",
        "amendment_applied": ["Amendment 1 (2026-04-28): simulation-only measurement"],
        "scenario_ids": scenario_ids,
        "repeats": repeats,
        "base_seed": base_seed,
        "total_trials": len(rows),
        "expected_trials": len(scenario_ids) * repeats * 2,
        "counts_per_scenario": counts,
        "failures_per_scenario": failures,
        "wall_time_seconds": round(elapsed, 2),
        "csv_path": str(csv_path),
        "csv_columns": CSV_COLUMNS,
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("Total trials recorded: %d (expected %d)",
                 len(rows), summary["expected_trials"])
    logger.info("CSV saved: %s", csv_path)
    logger.info("Summary saved: %s", summary_path)
    logger.info("Total wall time: %.2fs", elapsed)

    return summary


# --------------------------------------------------
# CLI
# --------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AINM benchmark v3 (per pre-registration v0.3-prereg-2026-04-28)."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1000,
        help="Base seed (default 1000, per pre-registration §8.3).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=100,
        help="Trials per (scenario × agent). Default 100 (pre-registration §4.1).",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=[s.id for s in SCENARIOS_V3],
        choices=[s.id for s in SCENARIOS_V3],
        help="Scenario IDs to run. Default: all 4 (S1 S2 S3 S4).",
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
    if args.repeats < 1:
        logger.error("--repeats must be >= 1")
        return 1
    if args.seed < 0:
        logger.error("--seed must be >= 0")
        return 1

    summary = run_benchmark(
        scenario_ids=list(args.scenarios),
        repeats=args.repeats,
        base_seed=args.seed,
        output_dir=args.output,
    )

    # Sanity check: 예상 trial 수와 실제 일치하는지
    if summary["total_trials"] != summary["expected_trials"]:
        logger.warning(
            "Trial count mismatch: actual=%d expected=%d (failures: %s)",
            summary["total_trials"], summary["expected_trials"],
            summary["failures_per_scenario"],
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Input for Security Decision: scenario IDs / agent 화이트리스트 검증
#   - Improper Resource Release: with-context로 CSV·JSON 파일 자동 close
#   - Missing Error Handling: trial 단위 try/except로 부분 실패 격리
#   - Path Traversal: argparse Path 객체 + mkdir parents 사용
#   - Integer Overflow: --repeats / --seed 음수 검증
# Not Applied:
#   - [WARN] 외부 호출 X (시뮬레이션 모델). 향후 real-LLM 모드 활성화 시 보안 재검토 필수.
# --------------------------------------------------
