# AI Web Manifest 실증 프로토타입

본 발명(AI 웹 매니페스트)의 청구 효과(토큰 절감, 성공률 향상, 서버 부하 감소)를
**LLM API 키 없이 로컬에서 재현 가능**하게 검증하기 위한 최소 실증 시스템.

## 구성

```
validation/
├── server/          # 실증 대상 웹 서버 (방식 A/B/C 모두 구현)
├── registry/        # 중앙 인증 레지스트리 (도4)
├── agent/
│   ├── baseline_agent.py   # 종래 DOM 분석 방식
│   └── manifest_agent.py   # 본 발명 매니페스트 방식
├── benchmark/
│   ├── run_benchmark.py    # 서버 기동 + 에이전트 반복 실행
│   └── analyze.py          # 결과 통계/도표 생성
└── results/                # metrics.csv, metrics.json, comparison.png, summary.json
```

## 설치

```
pip install -r requirements.txt
```

## 실행

```
# 벤치마크 (20회 반복)
python benchmark/run_benchmark.py --repeats 20

# 통계 + 도표
python benchmark/analyze.py
```

## 측정 지표

| 지표 | 의미 |
|------|------|
| input_tokens | 태스크 수행에 투입된 LLM 입력 토큰 누계 (tiktoken cl100k_base) |
| http_requests | 서버에 보낸 HTTP 요청 수 (서버 부하의 직접 지표) |
| llm_calls | 태스크당 LLM 호출 횟수 |
| success | 다단계 주문 입력 태스크 최종 성공 여부 |
| wall_time_ms | End-to-End 실행 시간 |

## 왜 API 키가 필요 없는가

- LLM이 DOM을 이해·추론하는 비용은 **실제로 토큰 수에 비례**함이 알려져 있다.
  따라서 실입력 토큰 수를 tiktoken으로 직접 계측하는 것으로 충분히 정량 비교가 가능하다.
- 에이전트가 올바른 셀렉터를 추론할 확률은, DOM의 "신호 대 잡음비"(실제 form 요소
  비율)에 반비례한다는 결정론적 모델로 시뮬레이션했다.
- 실제 LLM 호출 전 단계의 비용 구조(토큰, 왕복 수, 서버 요청 수)만으로도
  본 발명의 절감 효과를 충분히 입증할 수 있다.

## 보안 적용

본 프로젝트의 모든 Python 파일은 행정안전부 소프트웨어 개발보안 가이드(2021)의
7대 분류 보안 규칙을 준수하며 각 파일 말미에 Security Checklist를 포함한다.
주요 적용 사항:

- SHA-256 해시 (Weak Cryptographic Algorithm 방지)
- 서버측 화이트리스트 입력 검증 (Improper Input for Security Decision 방지)
- subprocess shell=False 고정 (OS Command Injection 방지)
- with/try-finally 기반 리소스 해제 (Improper Resource Release 방지)
- 내부 예외는 logger.exception, 사용자에겐 일반 메시지 (Error Message Information Exposure 방지)
- HTTP 헤더 CR/LF 제거 (HTTP Response Splitting 방지)
