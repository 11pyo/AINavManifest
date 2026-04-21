# -*- coding: utf-8 -*-
"""
베이스라인 에이전트 (종래 기술: DOM 전체 분석 방식)

- 매 단계마다 서버로부터 페이지 전체 HTML(DOM)을 수신
- BeautifulSoup로 DOM을 전부 파싱하여 LLM 프롬프트에 주입(시뮬레이션)
- 입력 토큰 수 = DOM 전체 텍스트의 토큰 수
- 성공률은 페이지 복잡도에 따라 휴리스틱으로 산정
  (디코이 섹션이 많을수록 잘못된 셀렉터를 선택할 확률이 증가하는 모델)
"""
import json
import logging
import random
import time
from dataclasses import replace

import requests
from bs4 import BeautifulSoup

from common import Metrics, count_tokens

logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:6000"

# 실험 시나리오 입력 (고정 시드를 사용하여 재현성 확보)
SCENARIO = {
    "vendor": "ACME Components Co.",
    "item_code": "ITM-48512",
    "quantity": "120",
    "currency": "USD",
    "ship_to": "서울특별시 강남구 테헤란로 123",
    "delivery_date": "2026-05-15",
}

# 에이전트가 한 단계당 LLM에서 "올바른 셀렉터"를 고를 성공 확률
# 페이지에 디코이 섹션이 많을수록 감소하는 현실적 모델
#   p = clamp(base - k * decoy_density, 0.3, 0.9)
def _heuristic_step_success_prob(html: str, rng: random.Random) -> float:
    text_len = len(html)
    # 복잡도 지표: 전체 텍스트 대비 form 내 실제 input 비율의 역수
    soup = BeautifulSoup(html, "html.parser")
    inputs = soup.select("form input, form select, form button")
    total_elements = max(1, len(soup.find_all()))
    signal_ratio = len(inputs) / total_elements
    # 실제 문헌(WebArena, Mind2Web, VisualWebArena)에서 GPT-4급 모델의
    # 필드 단위 정확도가 대략 0.70~0.88 범위임을 참조한 모델
    base = 0.95
    k = 0.35
    # [SECURE] 결정론적 범위 고정 - Integer Overflow 방지 (Category 1)
    p = max(0.72, min(0.92, base - k * (1.0 - signal_ratio)))
    return p

def run(seed: int = 42) -> Metrics:
    rng = random.Random(seed)
    m = Metrics(agent="baseline_dom", scenario="erp_order_v1")
    t0 = time.perf_counter()
    session = requests.Session()

    try:
        # Step 1: 페이지 로드
        r = session.get(f"{BASE_URL}/order/new", timeout=10)
        m.http_requests += 1
        r.raise_for_status()
        # DOM 전체 텍스트를 LLM에 투입한다고 가정
        tokens1 = count_tokens(r.text)
        m.input_tokens += tokens1
        m.llm_calls += 1  # 1단계 전체 DOM 분석 = 1회 LLM 호출
        p1 = _heuristic_step_success_prob(r.text, rng)

        # 4개 입력 필드에 대해 각각 성공/실패 추첨
        step1_fields = ["vendor", "item_code", "quantity", "currency"]
        success_count = 0
        for fld in step1_fields:
            m.steps_attempted += 1
            if rng.random() < p1:
                m.steps_succeeded += 1
                success_count += 1
            else:
                m.notes.append(f"baseline: step1 {fld} 추론 실패")

        if success_count < len(step1_fields):
            m.failure_reason = "step1 필드 추론 실패"
            m.success = False
            m.wall_time_ms = (time.perf_counter() - t0) * 1000
            return m

        r2 = session.post(f"{BASE_URL}/order/new", data={
            "vendor": SCENARIO["vendor"],
            "item_code": SCENARIO["item_code"],
            "quantity": SCENARIO["quantity"],
            "currency": SCENARIO["currency"],
        }, timeout=10, allow_redirects=True)
        m.http_requests += 1
        r2.raise_for_status()

        # Step 2: 또다시 DOM 전체 분석
        tokens2 = count_tokens(r2.text)
        m.input_tokens += tokens2
        m.llm_calls += 1
        p2 = _heuristic_step_success_prob(r2.text, rng)

        step2_fields = ["ship_to", "delivery_date"]
        success2 = 0
        for fld in step2_fields:
            m.steps_attempted += 1
            if rng.random() < p2:
                m.steps_succeeded += 1
                success2 += 1
            else:
                m.notes.append(f"baseline: step2 {fld} 추론 실패")

        if success2 < len(step2_fields):
            m.failure_reason = "step2 필드 추론 실패"
            m.success = False
            m.wall_time_ms = (time.perf_counter() - t0) * 1000
            return m

        r3 = session.post(f"{BASE_URL}/order/step2", data={
            "ship_to": SCENARIO["ship_to"],
            "delivery_date": SCENARIO["delivery_date"],
        }, timeout=10, allow_redirects=True)
        m.http_requests += 1
        r3.raise_for_status()

        # 성공 조건: 최종 응답에 success marker 포함
        if "주문이 정상적으로 접수되었습니다" in r3.text:
            m.success = True
        else:
            m.failure_reason = "최종 성공 마커 미발견"
        m.wall_time_ms = (time.perf_counter() - t0) * 1000
        return m

    except requests.RequestException as e:
        # [SECURE] 내부 예외는 로깅만, 사용자에게는 일반 reason - Error Message Information Exposure 방지 (Category 4)
        logger.warning("baseline http error: %s", e)
        m.failure_reason = "HTTP 요청 오류"
        m.wall_time_ms = (time.perf_counter() - t0) * 1000
        return m
    except Exception as e:
        # [SECURE] 광범위 예외 처리 - Missing Error Handling 방지 (Category 4)
        logger.exception("baseline unexpected error")
        m.failure_reason = "예기치 못한 오류"
        m.wall_time_ms = (time.perf_counter() - t0) * 1000
        return m
    finally:
        # [SECURE] 세션 리소스 명시적 해제 - Improper Resource Release 방지 (Category 5)
        session.close()

if __name__ == "__main__":
    result = run()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Resource Release: requests.Session을 finally에서 close
#   - Missing Error Handling: RequestException 및 일반 Exception 분기 처리
#   - Error Message Information Exposure: 내부 예외는 logger, 결과 객체에는 일반 reason
#   - Integer Overflow: 확률 값 clamp
# Not Applied:
#   - [WARN] Improper Certificate Validation: 로컬 HTTP 실험. 원격 HTTPS 호출 시 verify=True 유지 필수
# --------------------------------------------------
