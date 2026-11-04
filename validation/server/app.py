# -*- coding: utf-8 -*-
"""
실증 대상 웹 서버 (AI 매니페스트 내장 방식 A/B/C 모두 구현)

- 버전 "2.0" (draft-han-ai-manifest-03): GET /.well-known/ai-friction-manifest.json
  + HTML 응답마다 Link: </.well-known/ai-friction-manifest.json>; rel="ai-friction-manifest"
- [레거시 1.0 — 부록 B 2번 벤치마크 재현 전용] 방식 A /.well-known/ai-manifest.json,
  방식 B <meta name="ai-manifest">, 방식 C X-AI-Manifest 헤더. -03 §3.1·§3.3 에 따라
  2.0 에이전트는 이 경로·방식을 사용하지 않는다. HTML 본문을 바꾸지 않아야 기준선 토큰
  수치(1887.6)가 재현되므로 그대로 둔다.
- 복잡한 다단계 ERP-style 주문 입력 폼 제공
- 폼 제출의 정답 셀렉터/값 시퀀스를 사전에 고정하여 실험의 재현성 확보
"""
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, session

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, template_folder="templates")
# [SECURE] 환경변수에서 비밀키 로드, 없으면 세션 전용 난수 생성 - Hard-coded Credentials 방지 (Category 2)
app.secret_key = os.environ.get("VALIDATION_SECRET_KEY") or secrets.token_hex(32)

# --------------------------------------------------
# 매니페스트 정의 (논문 실험용 다단계 주문 입력 시나리오)
# --------------------------------------------------
MANIFEST = {
    "schemaVersion": "1.0",
    "manifestId": "urn:ainav:demo-erp-order:v1",
    "publisher": "example-erp.local",
    "registryUrl": "http://127.0.0.1:6001/verify",
    "issuedAt": "2026-04-21T00:00:00Z",
    "task": {
        "name": "create_purchase_order",
        "description": "다단계 구매 주문 등록 태스크",
        "entryUrl": "/order/new",
        "steps": [
            {"index": 1, "action": "fill",   "selector": "#vendor",     "value": "{vendor}"},
            {"index": 2, "action": "fill",   "selector": "#item_code",  "value": "{item_code}"},
            {"index": 3, "action": "fill",   "selector": "#quantity",   "value": "{quantity}"},
            {"index": 4, "action": "select", "selector": "#currency",   "value": "{currency}"},
            {"index": 5, "action": "click",  "selector": "#btn_next",   "value": None},
            {"index": 6, "action": "fill",   "selector": "#ship_to",    "value": "{ship_to}"},
            {"index": 7, "action": "fill",   "selector": "#delivery_date", "value": "{delivery_date}"},
            {"index": 8, "action": "click",  "selector": "#btn_submit", "value": None},
        ],
        "successCriteria": {
            "type": "url_contains",
            "value": "/order/complete"
        }
    }
}

MANIFEST_BYTES = json.dumps(MANIFEST, ensure_ascii=False, sort_keys=True).encode("utf-8")
# [SECURE] SHA-256 사용 - Weak Cryptographic Algorithm 방지 (MD5/SHA1 금지, Category 2)
MANIFEST_HASH = hashlib.sha256(MANIFEST_BYTES).hexdigest()

# --------------------------------------------------
# 버전 "2.0" 매니페스트 (draft-han-ai-manifest-03 §3.1, §4)
# 이 주문 폼에는 알려진 함정이 없다(knownTraps 빈 배열). 사이트 고유 지식은
# 통화 코드 목록뿐이므로 fieldHints 로 둔다. expires 는 제공 시점 + 30 일.
# --------------------------------------------------
ORIGIN = "http://127.0.0.1:6000"


def manifest_v2():
    return {
        "version": "2.0",
        "origin": ORIGIN,
        "expires": (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": ["/order/"],
        "frameworkHints": {"name": "flask-jinja", "renderingModel": "server-rendered"},
        "knownTraps": [],
        "fieldHints": [
            {"fieldId": "currency",
             "locator": {"role": "combobox", "name": "통화"},
             "allowedValues": ["KRW", "USD", "EUR", "JPY", "CNY"],
             "description": "Currencies accepted by this order form."},
        ],
        "shortcuts": [
            {"shortcutId": "order-new", "target": "/order/new", "label": "New purchase order"},
        ],
    }


@app.route("/.well-known/ai-friction-manifest.json")
def well_known_friction_manifest():
    body = json.dumps(manifest_v2(), ensure_ascii=False).encode("utf-8")
    return Response(body, mimetype="application/json")


@app.after_request
def _link_header(resp):
    # [SECURE] 고정 문자열만 헤더에 사용 - HTTP Response Splitting 방지 (Category 1)
    if resp.mimetype == "text/html":
        resp.headers["Link"] = '</.well-known/ai-friction-manifest.json>; rel="ai-friction-manifest"'
    return resp


# --------------------------------------------------
# [레거시 1.0] 방식 A: Well-Known URI — 부록 B 2번 벤치마크 재현 전용
# --------------------------------------------------
@app.route("/.well-known/ai-manifest.json")
def well_known_manifest():
    return Response(MANIFEST_BYTES, mimetype="application/json")

# --------------------------------------------------
# [레거시 1.0] 방식 B, C 은 페이지 및 응답 헤더에서 처리 (벤치마크 재현 전용)
# --------------------------------------------------
@app.route("/")
def index():
    html = render_template(
        "form.html",
        step=1,
        manifest_meta=json.dumps({"version": "1.0", "url": "/.well-known/ai-manifest.json",
                                  "hash": MANIFEST_HASH}),
    )
    resp = Response(html, mimetype="text/html; charset=utf-8")
    # [SECURE] CR/LF 제거 - HTTP Response Splitting 방지 (Category 1)
    safe_hash = MANIFEST_HASH.replace("\r", "").replace("\n", "")
    resp.headers["X-AI-Manifest"] = f"url=/.well-known/ai-manifest.json; hash={safe_hash}"
    # [SECURE] XSS/Clickjacking 기본 방어
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp

# --------------------------------------------------
# 다단계 주문 폼 페이지 (Step 1)
# --------------------------------------------------
@app.route("/order/new", methods=["GET", "POST"])
def order_new():
    if request.method == "POST":
        # [SECURE] 화이트리스트 기반 필수 필드 검증 - Improper Input for Security Decision 방지 (Category 1)
        required = ["vendor", "item_code", "quantity", "currency"]
        form = {k: request.form.get(k, "") for k in required}
        # [SECURE] 정수 범위 검증 - Integer Overflow 방지 (Category 1)
        try:
            qty = int(form["quantity"])
            if not (1 <= qty <= 10000):
                raise ValueError("quantity out of range")
        except ValueError as e:
            logger.warning("invalid quantity: %s", e)
            return _generic_error("입력 값이 올바르지 않습니다.", 400)
        # [SECURE] 세션에 임시 저장 (서버측 상태) - 클라이언트 신뢰 금지
        session["order_step1"] = form
        return _render_step2(form)
    html = render_template("form.html", step=1,
        manifest_meta=json.dumps({"version": "1.0",
            "url": "/.well-known/ai-manifest.json", "hash": MANIFEST_HASH}))
    resp = Response(html, mimetype="text/html; charset=utf-8")
    safe_hash = MANIFEST_HASH.replace("\r", "").replace("\n", "")
    resp.headers["X-AI-Manifest"] = f"url=/.well-known/ai-manifest.json; hash={safe_hash}"
    return resp

def _render_step2(step1_data):
    html = render_template("form.html", step=2, step1=step1_data,
        manifest_meta=json.dumps({"version": "1.0",
            "url": "/.well-known/ai-manifest.json", "hash": MANIFEST_HASH}))
    resp = Response(html, mimetype="text/html; charset=utf-8")
    safe_hash = MANIFEST_HASH.replace("\r", "").replace("\n", "")
    resp.headers["X-AI-Manifest"] = f"url=/.well-known/ai-manifest.json; hash={safe_hash}"
    return resp

@app.route("/order/step2", methods=["POST"])
def order_step2():
    if "order_step1" not in session:
        return _generic_error("세션이 만료되었습니다. 처음부터 다시 시도해 주세요.", 400)
    required2 = ["ship_to", "delivery_date"]
    form2 = {k: request.form.get(k, "") for k in required2}
    # [SECURE] 간단한 길이 제한 - Memory Buffer Overflow 및 XSS 방지 (Category 1)
    for k, v in form2.items():
        if len(v) > 200:
            logger.warning("overlong field: %s", k)
            return _generic_error("입력 값이 너무 깁니다.", 400)
    session["order_step2"] = form2
    return _render_complete(session["order_step1"], form2)

def _render_complete(step1, step2):
    html = render_template("form.html", step="complete", step1=step1, step2=step2)
    return Response(html, mimetype="text/html; charset=utf-8")

@app.route("/order/complete")
def order_complete():
    s1 = session.get("order_step1")
    s2 = session.get("order_step2")
    if not s1 or not s2:
        return _generic_error("세션이 유효하지 않습니다.", 400)
    return _render_complete(s1, s2)

# --------------------------------------------------
# 공통 에러 핸들러
# --------------------------------------------------
def _generic_error(msg, code):
    # [SECURE] 내부 스택트레이스 미노출, 일반 메시지만 반환 - Error Message Information Exposure 방지 (Category 4)
    return Response(
        json.dumps({"error": msg}, ensure_ascii=False),
        mimetype="application/json",
        status=code,
    )

@app.errorhandler(404)
def _not_found(e):
    return _generic_error("요청하신 리소스를 찾을 수 없습니다.", 404)

@app.errorhandler(500)
def _server_error(e):
    # [SECURE] 내부 예외는 서버측에만 로깅 - Category 4
    logger.exception("unhandled server error")
    return _generic_error("일시적 오류가 발생했습니다.", 500)

# --------------------------------------------------
# 엔트리포인트
# --------------------------------------------------
if __name__ == "__main__":
    # [SECURE] 운영환경에서는 debug=False 필수 - Leftover Debug Code 방지 (Category 6)
    app.run(host="127.0.0.1", port=6000, debug=False)

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Weak Cryptographic Algorithm: SHA-256 사용 (MD5/SHA1 금지)
#   - Hard-coded Credentials: secret_key 환경변수 우선
#   - Improper Input for Security Decision: 서버측 화이트리스트 필드 검증
#   - Integer Overflow: quantity 범위 검증
#   - HTTP Response Splitting: 헤더 값에서 CR/LF 제거
#   - Error Message Information Exposure: 내부 예외는 로깅, 사용자에게는 일반 메시지
#   - Memory Buffer Overflow: 입력 길이 상한
#   - Leftover Debug Code: debug=False
# Not Applied:
#   - [WARN] CSRF: 실험 환경이라 토큰 미적용. 운영 배포 시 Flask-WTF CSRFProtect 필수
#   - [WARN] HTTPS: 로컬 실험용 HTTP. 운영 배포 시 TLS 필수
# --------------------------------------------------
