# -*- coding: utf-8 -*-
"""
벤치마크 오케스트레이터

- 서버 2종(메인/레지스트리)을 자식 프로세스로 기동
- baseline / manifest 에이전트를 각 N회 반복 실행
- 결과를 CSV + JSON으로 저장
"""
import csv
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT / "agent"
RESULT_DIR = ROOT / "results"
RESULT_DIR.mkdir(exist_ok=True)

# 에이전트 모듈을 찾기 위한 sys.path 주입
sys.path.insert(0, str(AGENT_DIR))

import baseline_agent  # noqa: E402
import manifest_agent  # noqa: E402

SERVER_CMD = [sys.executable, str(ROOT / "server" / "app.py")]
REGISTRY_CMD = [sys.executable, str(ROOT / "registry" / "registry.py")]

def _wait_ready(url: str, timeout: float = 10.0) -> bool:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code < 500:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.3)
    return False

def _start_child(cmd, name):
    # [SECURE] shell=False 고정 - OS Command Injection 방지 (Category 1)
    logger.info("starting %s: %s", name, " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=str(ROOT), shell=False)
    return p

def _stop_child(p, name):
    if p and p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            logger.warning("force-killing %s", name)
            try:
                p.kill()
            except Exception:
                pass

def run_benchmark(repeats: int = 20, seed_base: int = 1000):
    server = None
    registry = None
    results = []
    try:
        server = _start_child(SERVER_CMD, "server")
        registry = _start_child(REGISTRY_CMD, "registry")

        if not _wait_ready("http://127.0.0.1:6000/order/new"):
            raise RuntimeError("메인 서버 기동 실패")
        if not _wait_ready("http://127.0.0.1:6001/verify", timeout=5):
            # /verify는 GET에 대해 405를 반환할 수 있음 → 연결만 확인
            pass
        logger.info("servers are ready")

        for i in range(repeats):
            seed = seed_base + i
            bm = baseline_agent.run(seed=seed)
            mm = manifest_agent.run(seed=seed)
            bm.notes.append(f"seed={seed}")
            mm.notes.append(f"seed={seed}")
            results.append(bm.to_dict())
            results.append(mm.to_dict())
            logger.info("[%d/%d] baseline success=%s tokens=%d ms=%.1f | manifest success=%s tokens=%d ms=%.1f",
                        i + 1, repeats,
                        bm.success, bm.input_tokens, bm.wall_time_ms,
                        mm.success, mm.input_tokens, mm.wall_time_ms)

        # CSV 저장
        csv_path = RESULT_DIR / "metrics.csv"
        # [SECURE] 컨텍스트 매니저 사용 - Improper Resource Release 방지 (Category 5)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "agent", "scenario", "input_tokens", "http_requests", "llm_calls",
                "steps_attempted", "steps_succeeded", "wall_time_ms",
                "success", "failure_reason", "notes",
            ])
            writer.writeheader()
            for row in results:
                row = dict(row)
                row["notes"] = "|".join(row.get("notes", []))
                writer.writerow(row)

        json_path = RESULT_DIR / "metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info("results saved: %s, %s", csv_path, json_path)

    finally:
        _stop_child(server, "server")
        _stop_child(registry, "registry")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--seed-base", type=int, default=1000)
    args = ap.parse_args()
    run_benchmark(repeats=args.repeats, seed_base=args.seed_base)

# --------------------------------------------------
# Security Checklist
# Applied:
#   - OS Command Injection: subprocess.Popen shell=False 고정
#   - Improper Resource Release: 파일 open은 with, 자식 프로세스는 finally에서 terminate
#   - Missing Error Handling: 서버 기동 실패 시 RuntimeError, 자식 종료 실패 시 kill 폴백
# Not Applied:
#   - [WARN] Race Condition: 서버 준비 대기가 sleep 폴링. 실제 운영은 health-check 엔드포인트 권장
# --------------------------------------------------
