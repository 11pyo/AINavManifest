# -*- coding: utf-8 -*-
"""
매니페스트 인지 에이전트 (본 발명 방식)

- 방식 A(Well-Known URI) 우선, 실패 시 방식 C(HTTP 헤더), 마지막으로 방식 B(meta 태그) 폴백
- 매니페스트 JSON만 LLM 입력으로 사용 → 토큰 소모 극적 감소
- SHA-256 해시를 중앙 레지스트리와 대조하여 신뢰 상태 판정
- 신뢰 확인된 경우 steps 배열을 명시된 순서로 직접 실행 (LLM 추론 불필요)
"""
import hashlib
import json
import logging
import time

import requests
from bs4 import BeautifulSoup

from common import Metrics, count_tokens

logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:6000"
REGISTRY_URL = "http://127.0.0.1:6001/verify"

SCENARIO = {
    "vendor": "ACME Components Co.",
    "item_code": "ITM-48512",
    "quantity": "120",
    "currency": "USD",
    "ship_to": "서울특별시 강남구 테헤란로 123",
    "delivery_date": "2026-05-15",
}

# --------------------------------------------------
# 매니페스트 탐지 (방식 A → C → B 폴백)
# --------------------------------------------------
def _fetch_manifest_well_known(session, m: Metrics):
    # [SECURE] HTTPS/타임아웃 지정 - Use of Vulnerable API 방지 (Category 7)
    r = session.get(f"{BASE_URL}/.well-known/ai-manifest.json", timeout=10)
    m.http_requests += 1
    if r.status_code == 200:
        return r.content, "A_well_known"
    return None, None

def _fetch_manifest_from_header(session, m: Metrics, html_resp):
    header = html_resp.headers.get("X-AI-Manifest", "")
    if "url=" not in header:
        return None, None
    # 헤더 형식: url=/path; hash=xxxx
    try:
        parts = dict(p.strip().split("=", 1) for p in header.split(";") if "=" in p)
        url_path = parts.get("url")
        if not url_path or not url_path.startswith("/"):
            return None, None
        r = session.get(f"{BASE_URL}{url_path}", timeout=10)
        m.http_requests += 1
        if r.status_code == 200:
            return r.content, "C_header"
    except Exception as e:
        logger.warning("header parse failed: %s", e)
    return None, None

def _fetch_manifest_from_meta(m: Metrics, html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    tag = soup.find("meta", attrs={"name": "ai-manifest"})
    if not tag or not tag.get("content"):
        return None, None
    try:
        meta_info = json.loads(tag["content"])
        return meta_info, "B_meta"
    except json.JSONDecodeError as e:
        logger.warning("meta manifest JSON decode failed: %s", e)
        return None, None

def _verify_with_registry(session, m: Metrics, manifest_obj, supplied_hash):
    payload = {
        "publisher": manifest_obj.get("publisher"),
        "manifestId": manifest_obj.get("manifestId"),
        "hash": supplied_hash,
    }
    try:
        r = session.post(REGISTRY_URL, json=payload, timeout=10)
        m.http_requests += 1
        if r.status_code != 200:
            return "unknown"
        return r.json().get("status", "unknown")
    except requests.RequestException as e:
        logger.warning("registry unreachable: %s", e)
        return "unknown"

def run(seed: int = 42) -> Metrics:
    m = Metrics(agent="manifest_aware", scenario="erp_order_v1")
    t0 = time.perf_counter()
    session = requests.Session()
    try:
        # 1) 진입 페이지 로드 (헤더/meta 확보 목적)
        entry = session.get(f"{BASE_URL}/order/new", timeout=10)
        m.http_requests += 1
        entry.raise_for_status()

        # 2) 매니페스트 탐지: A → C → B
        manifest_bytes = None
        method_used = None

        data, method = _fetch_manifest_well_known(session, m)
        if data is not None:
            manifest_bytes = data
            method_used = method
        else:
            data, method = _fetch_manifest_from_header(session, m, entry)
            if data is not None:
                manifest_bytes = data
                method_used = method
            else:
                meta_info, method = _fetch_manifest_from_meta(m, entry.text)
                if meta_info and "url" in meta_info:
                    r = session.get(f"{BASE_URL}{meta_info['url']}", timeout=10)
                    m.http_requests += 1
                    if r.status_code == 200:
                        manifest_bytes = r.content
                        method_used = "B_meta_via_url"

        if manifest_bytes is None:
            m.failure_reason = "매니페스트 미발견"
            m.wall_time_ms = (time.perf_counter() - t0) * 1000
            return m

        m.notes.append(f"detection_method={method_used}")

        # 3) 매니페스트 파싱 (LLM 입력은 매니페스트 JSON에 한정)
        manifest_text = manifest_bytes.decode("utf-8")
        m.input_tokens += count_tokens(manifest_text)
        m.llm_calls += 1  # 매니페스트 이해용 1회 호출 (실제 실행 단계엔 LLM 불필요)

        try:
            manifest = json.loads(manifest_text)
        except json.JSONDecodeError:
            m.failure_reason = "매니페스트 파싱 실패"
            m.wall_time_ms = (time.perf_counter() - t0) * 1000
            return m

        # 4) 중앙 레지스트리 해시 검증 (도4 흐름)
        # [SECURE] SHA-256 해시 산출 - Weak Cryptographic Algorithm 방지 (Category 2)
        manifest_canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        manifest_hash = hashlib.sha256(manifest_canonical).hexdigest()
        trust = _verify_with_registry(session, m, manifest, manifest_hash)
        m.notes.append(f"trust={trust}")
        if trust == "black":
            m.failure_reason = "레지스트리 블랙리스트 - 작업 거부"
            m.wall_time_ms = (time.perf_counter() - t0) * 1000
            return m
        # unknown의 경우: 특허 청구항에 따라 사용자 경고 후 DOM 분석 전환 가능
        # 데모에서는 white 만 진행
        if trust != "white":
            m.failure_reason = f"신뢰 상태 미확인({trust})"
            m.wall_time_ms = (time.perf_counter() - t0) * 1000
            return m

        # 5) steps 배열을 순서대로 실행
        values = dict(SCENARIO)
        step1_payload = {}
        for step in manifest["task"]["steps"]:
            m.steps_attempted += 1
            selector = step["selector"]
            raw_value = step["value"]
            if raw_value and raw_value.startswith("{") and raw_value.endswith("}"):
                key = raw_value[1:-1]
                resolved = values.get(key, "")
            else:
                resolved = raw_value

            # 셀렉터로부터 필드 ID 추출 (#field_name)
            if selector.startswith("#"):
                field_name = selector[1:]
            else:
                field_name = selector

            # click 단계는 단계 전환 트리거
            if step["action"] == "click" and field_name == "btn_next":
                r1 = session.post(f"{BASE_URL}/order/new", data=step1_payload,
                                  timeout=10, allow_redirects=True)
                m.http_requests += 1
                if r1.status_code >= 400:
                    m.failure_reason = "step1 제출 실패"
                    m.wall_time_ms = (time.perf_counter() - t0) * 1000
                    return m
                m.steps_succeeded += 1
                step2_payload = {}
            elif step["action"] == "click" and field_name == "btn_submit":
                r2 = session.post(f"{BASE_URL}/order/step2", data=step2_payload,
                                  timeout=10, allow_redirects=True)
                m.http_requests += 1
                if r2.status_code >= 400:
                    m.failure_reason = "step2 제출 실패"
                    m.wall_time_ms = (time.perf_counter() - t0) * 1000
                    return m
                m.steps_succeeded += 1
                # 성공 판정
                if "주문이 정상적으로 접수되었습니다" in r2.text:
                    m.success = True
                else:
                    m.failure_reason = "최종 성공 마커 미발견"
            elif step["action"] in ("fill", "select"):
                # step1 또는 step2 중 어느 payload에 담을지는 click 전환 시점으로 결정
                if "step2_payload" in locals():
                    step2_payload[field_name] = resolved
                else:
                    step1_payload[field_name] = resolved
                m.steps_succeeded += 1
            else:
                m.notes.append(f"unsupported action: {step['action']}")

        m.wall_time_ms = (time.perf_counter() - t0) * 1000
        return m

    except requests.RequestException as e:
        logger.warning("manifest agent http error: %s", e)
        m.failure_reason = "HTTP 요청 오류"
        m.wall_time_ms = (time.perf_counter() - t0) * 1000
        return m
    except Exception:
        logger.exception("manifest agent unexpected error")
        m.failure_reason = "예기치 못한 오류"
        m.wall_time_ms = (time.perf_counter() - t0) * 1000
        return m
    finally:
        session.close()

if __name__ == "__main__":
    result = run()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Weak Cryptographic Algorithm: SHA-256 사용
#   - Improper Resource Release: session.close() in finally
#   - Missing Error Handling: RequestException / Exception 분리 처리
#   - Error Message Information Exposure: 내부 예외 logger, 결과 객체엔 일반 reason
#   - Use of Vulnerable API: requests 호출 시 timeout 명시
# Not Applied:
#   - [WARN] Improper Certificate Validation: 로컬 HTTP 실험. 운영 시 verify=True 유지
#   - [WARN] Integrity Check for Deserialization: json.loads 전 HMAC 미수행.
#           레지스트리 해시 검증이 이 역할을 대체하나, 매니페스트 서명(JWS) 도입 권장
# --------------------------------------------------
