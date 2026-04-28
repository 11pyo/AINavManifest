# Pre-Registration — AINM Multi-Scenario Empirical Study

> **이 문서는 결과를 보기 *전*에 가설·분석 방법·결정 기준을 commit한다.**
> **본 문서가 GitHub에 commit된 시점 = 본 연구의 사전 등록 시점**.
> **이 시점 이후 변경은 amendment로 기록되며, 사후 변경(HARKing·p-hacking)은 학술 윤리 위반이다.**
>
> **상위 문서**: `research-integrity-protocol.md`, `experimental-design.md`
> **작성일**: 2026-04-28
> **연구자**: Wonpyo Han (ORCID 0009-0002-7528-2228)
> **사전 등록 commit hash**: (Phase 1 commit 후 채울 것: `[hash]`)
> **OSF 등록 (선택)**: 등록 시 URL 채울 것

---

## 0. Conflict of Interest

본 연구자는 본 발명의 단독 발명자(KR 10-2026-0071716)·IETF Internet-Draft 등록자(`draft-han-ai-manifest-00`)·GitHub 리포 운영자(`11pyo/AINavManifest`)이며, 사업화 의지를 보유하고 있다. 동국시스템즈 직무발명 검토가 진행 중(2026-04-27 자료 송부)이다. 이 COI는 모든 출판물에 명시된다.

---

## 1. 연구 질문 (Research Questions)

**RQ1**: Publisher-side AI Navigation Manifest를 도입한 에이전트(AINM agent)는 종래 DOM-analysis 에이전트(baseline)에 비해 입력 토큰을 얼마나 감소시키는가?

**RQ2**: AINM agent는 baseline에 비해 작업 성공률을 얼마나 향상시키는가?

**RQ3**: 위 효과는 단일 시나리오(ERP 주문 입력)뿐 아니라 다음 4개 카테고리에 일반화되는가?
- Transactional UI (S1)
- Information Retrieval UI (S2)
- Multi-step Sequential UI (S3)
- Internationalized UI (S4)

---

## 2. 가설 (Hypotheses) — 사전 등록

### 2.1 Confirmatory hypotheses

**모든 가설은 *방향성*과 *효과 크기 임계값*을 포함한다** (HARKing 차단).

#### 시나리오 S1 — ERP Order Entry
- **H1.1** AINM의 평균 input_tokens는 baseline의 평균보다 70% 이상 작다.
- **H1.2** AINM의 success rate는 baseline의 success rate보다 70 percentage points 이상 크다.

#### 시나리오 S2 — Search·Filter·Select
- **H2.1** AINM의 평균 input_tokens는 baseline의 평균보다 60% 이상 작다.
- **H2.2** AINM의 success rate는 baseline의 success rate보다 60 percentage points 이상 크다.

#### 시나리오 S3 — Multi-step Wizard
- **H3.1** AINM의 평균 input_tokens는 baseline의 평균보다 90% 이상 작다.
- **H3.2** AINM의 success rate는 baseline의 success rate보다 80 percentage points 이상 크다.

#### 시나리오 S4 — Internationalized Form
- **H4.1** AINM의 평균 input_tokens는 baseline의 평균보다 85% 이상 작다.
- **H4.2** AINM의 success rate는 baseline의 success rate보다 70 percentage points 이상 크다.

### 2.2 Pooled hypothesis (탐색적·secondary)

**H5** — 4개 시나리오 통합 시, AINM의 input_tokens 감소 효과 크기(Cohen's d)는 1.0 이상 (large effect)이다.

→ H5는 사전 등록되지만 **secondary** 분류. Confirmatory 결정은 H1~H4 시나리오별 검정에서 내림.

### 2.3 가설 임계값 정당화

| 가설 | 임계값 | 정당화 |
|-----|-----|-----|
| H1.1 ≥70% | 기존 데이터 81.9% (n=30) → 보수 추정 70% | n=100에서도 underestimate 가능성 대비 |
| H1.2 ≥70pp | 기존 80pp → 보수 추정 70pp | 동일 |
| H2.1 ≥60% | 검색 페이지 DOM 노이즈 ↑ | DOM 크기 vs manifest 비율 추정 |
| H2.2 ≥60pp | 다중 추론점 누적 실패 | per-step 실패율 × 단계 수 |
| H3.1 ≥90% | 5+ step DOM 합산 vs 단일 manifest | 단계 수 비례 |
| H3.2 ≥80pp | 누적 실패율 (1-0.8)^5 ≈ 67% (=baseline 기댓값) | per-step 80% 가정 |
| H4.1 ≥85% | 양 언어 DOM 합산 | 2× DOM 비율 |
| H4.2 ≥70pp | 한·영 양 언어 모두 성공 필요 | per-language 50% 기댓값 |

---

## 3. 변수 (Variables) — 사전 등록

### 3.1 Independent variable
- **Agent type** (categorical): {baseline, ainm}

### 3.2 Primary dependent variables
- **input_tokens** (continuous, integer ≥ 0): tiktoken cl100k_base 기준 trial별 누적
- **success** (binary): 시나리오별 success criteria 만족 여부

### 3.3 Secondary dependent variables (보고만)
- `http_requests` (continuous, integer)
- `llm_calls` (continuous, integer)
- `wall_time_ms` (continuous, float)
- `steps_attempted`, `steps_succeeded` (continuous, integer)

### 3.4 Control variables
- **Scenario** (categorical, 4 levels): {S1, S2, S3, S4} — 분리 분석
- **Trial seed** (deterministic): `1000 + trial_index` (1000~1099)
- **Server config**: 시나리오별 고정
- **Hardware**: 동일 머신 동일 세션
- **Library version**: `requirements.txt` lock

### 3.5 Variables NOT manipulated (사전 명시)
- LLM 모델 (시뮬레이션이라 LLM 실호출 X)
- 사용자 의도 (시나리오별 단일 고정)
- 시간대 (실험 1회 연속 실행)

---

## 4. 표본 크기 (Sample Size) — 사전 등록

### 4.1 결정
- **n = 100 trials per (agent × scenario)**
- 총 trial 수: 2 agents × 4 scenarios × 100 = **800 trials**

### 4.2 정당화 (Power Analysis)
- α (Bonferroni-corrected) = 0.00625
- Power (1-β) = 0.95
- Expected effect size: Cohen's d ≥ 1.0 (기존 S1 data 기준 d ≈ 2.4)
- d = 1.0에서 n = 43 per group으로 충분
- d = 0.5 (보수적 가정)에서 n = 168 per group 필요
- **n = 100 선택 근거**: medium-large effect 검출에 충분 + 보수적 여유

### 4.3 Stopping rule
- **n = 100 완료 즉시 데이터 수집 종료**
- Sequential testing 금지 (significant 나올 때까지 추가 X)
- 단, 코드 버그·환경 오류 발견 시 **전체 재실행** (부분 추가 X)
- 재실행 시 amendment 기록 + 양 결과 모두 보고

---

## 5. 통계 분석 — 사전 등록

### 5.1 검정 방법

| Outcome | Primary test | Fallback (assumption violated) |
|---------|------------|---------------------------|
| input_tokens | Welch's t-test (two-sample, two-tailed) | Mann-Whitney U test |
| success | Fisher's exact test (2×2 contingency) | (정규성 무관) |
| Effect size (tokens) | Cohen's d | (rank-based: r = Z/√N) |

### 5.2 다중 비교 보정
- 4 시나리오 × 2 primary outcomes = **8 비교**
- **Bonferroni**: α_corrected = 0.05 / 8 = **0.00625**
- 보고: corrected p-value, uncorrected p-value 둘 다
- Holm-Bonferroni 동시 보고 (덜 보수적, 권장 학계 표준)

### 5.3 정규성 검정
- Shapiro-Wilk test for input_tokens (per agent × scenario)
- p < 0.05 (정규성 위배) → Mann-Whitney U test로 자동 대체

### 5.4 95% Confidence Interval
- Mean difference for input_tokens (per scenario)
- Bootstrap 95% CI (10,000 resamples) for robust 추정

### 5.5 Pooled meta-analysis (Secondary)
- 4 시나리오 effect size 가중 평균
- Fixed-effect (heterogeneity I² < 50%) or Random-effect (I² ≥ 50%)

---

## 6. 결정 기준 (Decision Rules) — 사전 등록

### 6.1 가설 수용 기준

가설 H_i.j 수용은 다음 모두 만족해야 한다:
1. Bonferroni-corrected p < 0.00625
2. 효과 크기가 가설 임계값 (§2.1) 만족
3. 95% CI가 0을 포함하지 않음

### 6.2 가설 기각 기준

다음 중 하나라도 해당하면 기각:
- p ≥ 0.05 (uncorrected)
- 효과 크기가 임계값 미달
- 95% CI가 0을 포함

### 6.3 Inconclusive 기준

다음 경우 "inconclusive"로 보고 (수용도 기각도 아님):
- 0.00625 ≤ p < 0.05 (uncorrected significant but not corrected significant)
- 효과 크기는 임계값 만족하나 표본 분산 큼

→ 모든 결정은 **사전 등록된 임계값에 따라 자동**으로 내려진다. 사후 임의 판단 금지.

---

## 7. 결측·이상치 처리 — 사전 등록

### 7.1 Outlier 정의
- **Timeout**: `wall_time_ms > 60000` (60초)
  - 처리: success = False, 다른 지표는 raw 그대로 유지
  - 분석에서 제외하지 않음 (전수 보고)
- **Z-score outlier**: |z| > 3 for input_tokens
  - 처리: **제거하지 않음**, 별도 표기만
  - 분석에서는 raw 데이터 사용

### 7.2 Missing data 정의
- **HTTP error** (서버 5xx): trial = failure로 분류, success = False
- **Network error** (localhost인데도): 환경 오류 → 전체 재실행 (Phase 3 재실행 + amendment 기록)
- **의도적 trial 생략**: 금지

### 7.3 사후 데이터 제거 — 명시적으로 금지
다음과 같은 사후 처리는 본 연구 내에서 *학술 사기*로 간주된다:
- "튀는 trial이 평균을 왜곡한다"는 이유로 제거
- "특정 seed에서 baseline이 너무 잘했다"는 이유로 제거
- Statistical significance 안 나와서 표본 일부 제거

---

## 8. 환경·재현성 — 사전 등록

### 8.1 라이브러리 lock
```
Python 3.11.x
Flask==3.0.3
requests==2.32.3
beautifulsoup4==4.12.3
tiktoken==0.7.0
matplotlib==3.9.2
numpy==2.1.0
scipy==1.14.0
```

### 8.2 Hardware 명시 (결과 보고 시)
- OS·CPU·RAM·디스크 모두 결과 보고 시 명시
- 동일 머신·동일 세션에서 모든 baseline·AINM 실행

### 8.3 Random seed
- Base: **1000**
- Per-trial: `seed = 1000 + trial_index` (시나리오와 무관 — 시나리오 간 동일 seed 공유)
- Trial 0~99까지 1000~1099

### 8.4 실행 명령
```bash
python validation/benchmark/run_benchmark_v3.py \
  --seed 1000 \
  --repeats 100 \
  --scenarios S1 S2 S3 S4 \
  --output validation/results_v3/
```

이 명령은 사전 등록 시점에 사용 가능해야 한다 (Phase 2 코드 작성 후).

### 8.5 분석 명령
```bash
python validation/benchmark/analyze_v3.py \
  --input validation/results_v3/metrics.csv \
  --output validation/results_v3/analysis.json
```

이 분석 코드는 **결과 보기 전에 작성·테스트**되어야 한다 (사전 등록 핵심).

---

## 9. 보고 의무 (Reporting Commitments)

본 연구는 다음을 *결과와 무관하게* 보고한다:

### 9.1 모든 trial 결과 공개
- `metrics.csv` 800행 전부 Zenodo 게시
- 단 한 행도 누락 X

### 9.2 모든 가설의 결과 공개
- H1.1 ~ H4.2 (8개) 모두 보고
- 일부 가설 수용·일부 기각이라도 그대로
- 일부 가설이 inconclusive라도 그대로

### 9.3 Negative results 보고
- 본 발명이 baseline보다 *나쁜* 시나리오·지표가 발견되면 그대로 보고
- 예: wall_time_ms는 AINM이 더 클 가능성 (registry round trip) — 이미 §5-2 표에 반영됨

### 9.4 Limitations 명시
- 시뮬레이션 baseline의 한계
- 단일 LLM 미사용
- Publisher 측 manifest 작성 비용 미측정
- 단일 연구자·단일 분석자 (외부 재현 의존)

### 9.5 COI 명시
- 모든 출판물 §0 또는 footer

---

## 10. Amendment 절차

본 사전 등록 후 변경이 필요한 경우:

1. **새 amendment 항목** 본 문서 §11에 추가
2. 변경 사유·날짜·영향 명시
3. 변경된 항목은 양 결과(이전 가설·새 가설)를 모두 보고
4. 사후 retroactive 변경 절대 금지

### 변경 가능한 케이스
- ✅ 코드 버그 발견 → 코드 수정 + 재실행
- ✅ 환경 오류 → 환경 수정 + 재실행
- ✅ 분석 코드 버그 → 분석 수정 + 양 결과 보고

### 변경 금지 케이스
- ❌ "결과가 가설과 안 맞아서" 가설 변경
- ❌ "유의 안 나와서" 표본 추가
- ❌ "유리한 trial만" 선택
- ❌ "예상 못 한 패턴 발견"을 confirmatory 가설로 격상 (exploratory로만 보고)

---

## 11. Amendments

| Date | Section | Change | Reason | Author |
|------|---------|--------|--------|--------|
| 2026-04-28 | — | 최초 사전 등록 | — | Wonpyo Han |
| 2026-04-28 | experimental-design §2 (모든 시나리오), §9 (코드 파일 목록) | Implementation 측정 방법: 실제 Flask server 라우트 추가 + 시뮬레이션 → **시뮬레이션 모델 전용**으로 변경. `validation/benchmark/scenarios_v3.py`에서 v2 시뮬레이션 모델(`DOM_TIERS`, `simulate_baseline`, `simulate_manifest`)을 재사용하여 4개 시나리오(S1~S4) 정의. server 라우트는 추가하지 않음. | (1) v2 모델은 동일 발명에 대해 이미 검증됨 (n=30 토큰 -81.9%, 성공률 +80pp). (2) 외부 재현 강도 ↑ (server 환경 변수 0, 한 줄 명령으로 재현 가능). (3) 시뮬레이션 환경 모델은 학술 표준 (WebShop, Mind2Web 등도 환경 모델 기반). **가설(H1.1~H4.2)·표본 크기(n=100)·통계 검정·결정 기준 모두 변경 없음**. | Wonpyo Han |

(이후 amendment 발생 시 위 형식으로 추가)

---

## 12. 사전 등록 commit 메커니즘

### 12.1 GitHub commit
```bash
cd D:/개발한 프로그램들/AINavManifest
git add research/research-integrity-protocol.md
git add research/experimental-design.md
git add research/pre-registration.md
git commit -m "Pre-registration: AINM multi-scenario empirical study (v0.3-prereg)"
git tag v0.3-prereg-2026-04-28
git push origin main
git push origin v0.3-prereg-2026-04-28
```

### 12.2 Commit hash 기록
- 본 commit hash가 본 연구의 **사전 등록 timestamp 증거**
- 모든 출판물에 commit hash 명시
- (가능 시) 추가로 OSF.io에도 등록 — DOI 자동 발급, 학계 표준 사전 등록 플랫폼

### 12.3 사전 등록 검증
누구나 다음으로 본 사전 등록을 검증 가능:
```bash
git clone https://github.com/11pyo/AINavManifest
cd AINavManifest
git show v0.3-prereg-2026-04-28
git log --tags --pretty=format:'%h %d %s'
```

---

## 13. 본 사전 등록의 본질

이 문서는 본인을 미래의 자기 자신으로부터 보호한다.

데이터 수집 후 결과를 본 본인은, 결과에 맞춰 가설·분석을 조용히 수정하고 싶은 인지적 충동을 가진다. 이건 의도적 사기가 아니라 **인간의 자연스러운 인지 편향**이다 (motivated reasoning).

본 사전 등록은 이 편향을 **commit hash로 박아두는** 메커니즘이다. 미래의 본인이 가설을 바꾸려고 하면 amendment를 기록해야 하고, 그 amendment는 출판물에 그대로 노출된다. 즉 **숨길 수 없게 된다**.

이게 본 연구의 학술적 신뢰성의 유일한 토대다.

---

> **Phase 1 사전 등록 완료 후 Phase 2 (코드 구현)으로 진입.**
> **Phase 1 commit 후 본 문서 §0의 "사전 등록 commit hash" 항목을 채울 것.**
