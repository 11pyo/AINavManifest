# -*- coding: utf-8 -*-
"""
에이전트 공통 유틸리티
- 토큰 카운트 (tiktoken 사용, 실패 시 휴리스틱 폴백)
- 지표 기록용 Metrics 데이터클래스
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        if text is None:
            return 0
        return len(_enc.encode(text))
except Exception:  # pragma: no cover
    # [SECURE] tiktoken 미설치 시 휴리스틱 폴백 (1 token ≈ 4 chars) - Missing Error Handling 방지 (Category 4)
    def count_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

@dataclass
class Metrics:
    agent: str
    scenario: str
    input_tokens: int = 0          # LLM에 들어간 입력 토큰 누계
    http_requests: int = 0         # 서버에 보낸 HTTP 요청 수
    llm_calls: int = 0             # LLM 호출 횟수
    steps_attempted: int = 0
    steps_succeeded: int = 0
    wall_time_ms: float = 0.0
    success: bool = False
    failure_reason: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Missing Error Handling: tiktoken import 실패 경로 대비 폴백 구현
# Not Applied:
#   - [WARN] 해당 모듈은 입력 검증/암호화/권한 로직 없음 (순수 계측 유틸)
# --------------------------------------------------
