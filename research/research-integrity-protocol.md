# Research Integrity Protocol — AINM Empirical Study

> **목적**: AINM 학술 연구의 **편향·오류·확증 편향·researcher degrees of freedom**을 사전에 차단하는 규칙 집합.
> **원칙**: "원하는 값이 나오게 프로그래밍한다"는 의심을 차단하기 위해 **결과 보기 전에 모든 결정을 commit**한다.
> **작성일**: 2026-04-28
> **연구자**: Wonpyo Han (ORCID 0009-0002-7528-2228)
> **이 문서가 commit된 GitHub commit hash가 본 연구의 timestamp 증거**가 된다.

---

## 0. Conflict of Interest (COI) 선언 — 가장 먼저

본 연구의 연구자(Wonpyo Han)는 다음 이해관계를 보유한다:

- **본 발명의 단독 발명자**: 한국 특허 출원 10-2026-0071716
- **IETF Internet-Draft 등록자**: `draft-han-ai-manifest-00`
- **GitHub 리포 운영자**: `11pyo/AINavManifest` (MIT + FRAND)
- **사업화 의지 보유**: 4-Tier 수익 모델 사업계획서 작성 (`business/plan.md`)
- **현 소속 직무발명 검토 진행 중**: 동국시스템즈 (2026-04-27 자료 송부)

→ **연구자가 본 발명에 유리한 결과가 나오기를 원하는 명백한 이해관계가 있음**. 이 COI를 차단하기 위해 본 프로토콜의 모든 규칙을 강제 적용한다. 모든 출판물에 본 COI를 명시한다.

---

## 1. 연구 무결성 7대 원칙

### 1.1 Pre-registration (사전 등록)

**규칙**: 데이터 수집 전에 다음 7가지를 commit한다.
1. 가설 (H1, H2, ... — 명시적 방향성과 효과 크기 포함)
2. 종속 변수·독립 변수·통제 변수
3. 표본 크기·정지 규칙
4. 실험 절차 (시나리오·seed·환경)
5. 분석 방법 (통계 검정·다중 비교 보정·effect size)
6. 결정 기준 (가설 수용/기각 임계값)
7. 결측·이상치 처리 규칙

**구현**: `pre-registration.md` 작성 → GitHub commit. 데이터 수집 후 변경 시 *명시적 amendment 기록* + 사유.

### 1.2 No HARKing (Hypothesizing After Results Known)

**규칙**: 결과를 본 후 가설을 만들거나 수정하지 않는다.

- 사후에 발견한 흥미로운 패턴은 *exploratory* 라벨로 보고하며, **confirmatory 가설로 격상하지 않는다**.
- 사전 등록되지 않은 비교는 본문이 아닌 부록(Appendix)에 보고한다.

### 1.3 No p-hacking

**규칙**: 다중 비교 시 알파 보정.

- 4개 시나리오 × 2개 종속 변수 = 8개 비교
- **Bonferroni 보정**: α_corrected = 0.05 / 8 = **0.00625**
- **Holm-Bonferroni**(덜 보수적, 권장): 효과 크기 순으로 순차 적용
- p < α_corrected만 유의(significant)로 보고
- p < 0.05이지만 보정 후 유의 아닌 결과 = 명시적 "uncorrected significant only"로 표기

### 1.4 No Cherry-picking

**규칙**: 모든 trial 결과를 raw data로 공개.

- 실패한 trial, outlier도 빠짐없이 `metrics.csv`에 포함
- 데이터 제거가 필요한 경우 **사전 등록된 제거 규칙**에만 따름 (예: "wall_time > 60s는 timeout으로 분류")
- 사후 임의 제거 금지

### 1.5 Honest Baselines

**규칙**: Baseline은 본 발명을 돋보이게 하기 위한 약체가 아닌, 현실적 SOTA·관행 모델.

- DOM analysis baseline의 selector 추론 모델 매개변수는 **사전 등록**
- 매개변수 튜닝으로 baseline을 일부러 약화하지 않음
- 추가 baseline (ARIA-based, vision-based) 도입 시 동일 원칙
- Baseline 코드는 본 발명 코드와 **동일한 코드 리뷰·테스트 기준** 적용

### 1.6 Negative Results & Limitations 보고

**규칙**: 본 발명이 작동하지 않는 케이스도 보고한다.

- 시나리오 중 효과가 작거나 negative한 경우 그대로 보고
- 본 프로토콜의 한계 (시뮬레이션 baseline, 단일 LLM 미사용 등)를 §8에 명시
- "작동 안 한 시나리오를 빼고 작동한 것만 보고"는 fraud로 간주

### 1.7 Reproducibility

**규칙**: 외부 연구자가 동일 환경에서 동일 결과를 얻을 수 있도록 한다.

- 모든 코드: GitHub `11pyo/AINavManifest`, MIT 라이선스
- 모든 데이터: Zenodo 게시 시 `metrics.csv` 전체 포함
- 환경 명세: `requirements.txt` lock + 실행 환경 (OS·Python 버전·하드웨어) 기록
- Seed 고정: `seed=1000` 시작, trial별 `seed = base + trial_index`
- 실행 명령 한 줄로 재현 가능: `python benchmark/run_all_v3.py --seed 1000 --repeats 100`

---

## 2. Researcher Degrees of Freedom (RDF) 차단

### 2.1 정의

RDF = 연구자가 결과를 본 후 분석 결정을 바꿀 수 있는 자유. 결과를 "유의하게 만들기 위해" 다음을 사후 변경하는 것:

- 이상치 제거 기준
- 표본 분할 기준
- 측정 지표 선택
- 분석 방법 (parametric vs non-parametric)
- 표본 크기 (significant 나올 때까지 추가 수집)
- 비교군 정의

### 2.2 차단 메커니즘

| RDF | 차단 방법 |
|-----|--------|
| 표본 크기 | 사전 등록 (n=100), 정지 규칙 사전 정의 |
| 측정 지표 | Primary outcome (input_tokens, success_rate) 사전 명시. Secondary는 부록 |
| 통계 검정 | Welch's t-test (등분산 가정 X) 사전 결정 |
| 다중 비교 보정 | Bonferroni α=0.00625 사전 결정 |
| 이상치 | wall_time > 60s = timeout으로 분류, success=False, 다른 지표는 raw 그대로 보고 |
| 분석 환경 | Python 3.11, scipy 1.14.0, numpy 2.1.0 lock |

→ 위 결정은 **데이터 수집 *전에* `pre-registration.md`에 commit**된다.

---

## 3. Threats to Validity 사전 분석

### 3.1 Internal Validity (내부 타당성)

**위협**: 측정 결과가 실제 인과관계를 반영하지 못함.

| 위협 | 본 연구의 위험 | 완화 |
|-----|------------|----|
| 측정 도구 오류 | tiktoken 카운트 정확성 | OpenAI 공식 라이브러리 사용, encoding `cl100k_base` 명시 |
| 환경 변동 | wall_time 측정 시 OS 부하 영향 | 같은 머신·같은 세션에서 baseline·AINM 교차 실행 |
| Seed 의존성 | 특정 seed에서만 효과 발생 가능 | 100개 trial = 100개 다른 seed |
| 코드 버그 | baseline·AINM 중 하나에 유리한 버그 | 코드 리뷰 + 단위 테스트 + open source |

### 3.2 External Validity (외부 타당성)

**위협**: 결과가 다른 환경·도메인에 일반화되지 않음.

| 위협 | 본 연구의 위험 | 완화 |
|-----|------------|----|
| 단일 도메인 | 현재 ERP 1개 시나리오 | **4개 시나리오로 확장 (본 프로토콜의 핵심 동기)** |
| 단일 baseline | DOM analysis 1개 | 추가 baseline 향후 (Stage 5) — 본 연구는 limitation 명시 |
| 단일 LLM 환경 | 시뮬레이션 기반 | Limitation 명시, Stage C에서 실제 LLM 비교 추가 |
| 합성 시나리오 | 실제 사이트 아닌 모의 server | 시나리오 설계 근거를 *현실 사이트 패턴* 인용하여 작성 |

### 3.3 Construct Validity (구성 타당성)

**위협**: 측정 지표가 실제 의도한 개념을 반영하지 못함.

| 위협 | 본 연구의 위험 | 완화 |
|-----|------------|----|
| input_tokens가 LLM 비용 proxy인가? | 부분적. 출력 토큰·왕복 수도 비용 요소 | input_tokens가 dominant cost임을 §4-3에서 명시. 출력 토큰·HTTP 요청도 함께 보고 |
| Success rate가 신뢰성 proxy인가? | 부분적. binary success는 부분 성공 무시 | Steps_attempted / steps_succeeded 별도 보고 |
| 시뮬레이션 baseline 실패율 = 실제 LLM 실패율인가? | 부분적. 결정론적 모델 | Limitation 명시. 실제 LLM 비교는 미래 작업 |

### 3.4 Conclusion Validity (결론 타당성)

**위협**: 통계 추론의 부정확함.

| 위협 | 본 연구의 위험 | 완화 |
|-----|------------|----|
| 표본 크기 부족 | n=100은 medium effect detection 충분, small effect는 부족 | Effect size 사전 추정 (Cohen's d > 1.0 예상) → n=100 충분. Small effect 검출은 future work |
| 통계 검정 가정 위반 | t-test는 정규성 가정 | Shapiro-Wilk 정규성 검정 보고. 위배 시 Mann-Whitney U 사용 |
| 다중 비교 | 8개 비교 = false positive 위험 | Bonferroni α=0.00625 사전 적용 |

---

## 4. Open Science Practices 약속

본 연구는 다음을 약속한다:

- ✅ **Open Code** — GitHub MIT, 모든 분석 스크립트 포함
- ✅ **Open Data** — Zenodo, raw `metrics.csv` 전체
- ✅ **Open Pre-registration** — `pre-registration.md` GitHub commit, commit hash 보고
- ✅ **Open Access Publication** — Zenodo CC-BY 4.0
- ✅ **Open Standardization** — IETF draft 공개, FRAND
- ✅ **Open Conflict of Interest** — 모든 출판물 §0 또는 footer에 명시

이 6가지 모두가 충족될 때까지 본 연구는 "in progress" 상태로 표기된다.

---

## 5. Bias 식별·완화

### 5.1 Selection Bias

**위협**: 본 발명에 유리한 시나리오만 선택.

**완화**:
- 시나리오 4개 카테고리 사전 명시 (transactional, IR, multi-step, i18n)
- 각 카테고리는 reviewer가 동의할 만한 publisher-side standard 적용 영역
- 시나리오 선택 근거를 `experimental-design.md`에 명시

### 5.2 Confirmation Bias

**위협**: 가설 확인 방향으로 분석 편향.

**완화**:
- 가설 사전 등록
- Negative effect도 보고 (예: AINM이 baseline보다 wall_time 더 큰 점은 이미 보고 — §5-2 표 참조)
- HTTP requests 증가 (1.6 → 5.0)도 정직히 보고

### 5.3 Researcher Bias

**위협**: 본인이 발명자이자 분석자.

**완화**:
- COI §0 선언
- 모든 raw data 공개 → 외부 재현 가능
- 분석 코드 사전 commit
- (선택) 외부 reviewer에게 raw data 제공 후 독립 분석 (Stage E에서 권장)

### 5.4 Publication Bias

**위협**: 본 결과가 잘 나와서 발표하지만 nullified 결과는 발표 안 함.

**완화**:
- 본 연구는 *모든 시나리오 결과* 발표
- 효과가 작은 시나리오도 그대로 보고
- "실패" 시나리오 (만약 발생) 별도 섹션으로 보고

---

## 6. 코드·데이터·문서의 commit 순서 (★ 핵심)

본 프로토콜의 핵심 메커니즘. **결과 보기 전에 모든 것을 commit**한다.

### Phase 1 — 사전 등록 (Pre-registration)

순서:
1. `research-integrity-protocol.md` (본 문서) commit
2. `experimental-design.md` commit
3. `pre-registration.md` commit
4. **Phase 1 완료 GitHub release 태그**: `v0.3-prereg-2026-04-28`

이 시점 이후 가설·분석 방법 변경 = amendment로 명시 기록.

### Phase 2 — 코드 구현

순서:
5. 시나리오 server 코드 추가 (`validation/server/scenarios_v3.py`)
6. Baseline·AINM agent 코드 보강 (`validation/agent/`)
7. 분석 코드 사전 작성 (`validation/benchmark/analyze_v3.py`) — 더미 데이터로 테스트
8. **Phase 2 완료 GitHub release 태그**: `v0.4-code-2026-XX-XX`

→ **결과 데이터 수집 전에 분석 코드가 완성되어 있어야 한다.** 분석 코드는 결과 보고 짜는 게 아니다.

### Phase 3 — 실험 실행

순서:
9. 실험 1회 실행 (`python run_all_v3.py --seed 1000 --repeats 100`)
10. 결과 commit (`results_v3/`)
11. **Phase 3 완료 GitHub release 태그**: `v0.5-data-2026-XX-XX`

### Phase 4 — 분석

순서:
12. Phase 2에서 사전 작성한 분석 코드 그대로 실행
13. 결과 표·그래프 생성
14. 분석 결과 commit (`results_v3/analysis.json`)
15. **Phase 4 완료 GitHub release 태그**: `v0.6-analysis-2026-XX-XX`

→ Phase 4 단계에서 분석 코드 수정 발견 시 → amendment 기록 + 양 버전 결과 모두 보고.

### Phase 5 — 보고서 작성

순서:
16. 영문 본문 v2 갱신 (`tech-report-en.md`)
17. 한글 번역 (`tech-report-kr.md`)
18. **Phase 5 완료 GitHub release 태그**: `v1.0-report-2026-XX-XX`

### Phase 6 — 게시 (사내 검토 결과 후)

순서:
19. Zenodo 업로드, DOI 발급
20. GitHub Pages 갱신
21. (선택) IETF 메일링·학회 발표

---

## 7. 외부 검증 가능성

본 연구의 모든 결과는 외부 연구자가 다음 한 줄로 재현 가능해야 한다:

```bash
git clone https://github.com/11pyo/AINavManifest
cd AINavManifest/validation
git checkout v0.5-data-2026-XX-XX
pip install -r requirements.txt
python benchmark/run_all_v3.py --seed 1000 --repeats 100
python benchmark/analyze_v3.py
diff results_v3/analysis.json results_v3/published_analysis.json
# expected: empty (identical results)
```

차이가 발생하면 환경·라이브러리 버전 불일치 → debug. 본 연구의 결과는 환경 의존적이지 않아야 한다.

---

## 8. 본 프로토콜 위반 시 대응

만약 연구 진행 중 본 프로토콜의 규칙을 의도치 않게 위반한 사실이 발견되면:

1. 위반 사실을 본 문서에 amendment 기록 (날짜·내용·영향)
2. 영향 받은 결과를 별도 표시
3. 사전 등록 위반이 보고된 출판물에는 footer로 명시
4. 필요 시 보고서 v2 발행 또는 retraction

이는 학술 윤리상 표준 절차이며, **숨기지 않는 것이 정직성**이다.

---

## 9. 본 프로토콜 검증 체크리스트

다음 항목을 반복 점검:

- [ ] COI 선언이 모든 출판물에 명시되어 있는가?
- [ ] 가설은 데이터 수집 전 commit되었는가? (commit hash 기록)
- [ ] 분석 코드는 데이터 수집 전 작성되었는가?
- [ ] Baseline 매개변수는 결과 보기 전 고정되었는가?
- [ ] 모든 trial 결과가 raw data에 포함되어 있는가? (cherry-picking 0)
- [ ] 다중 비교 시 알파 보정 적용되었는가?
- [ ] 이상치 제거는 사전 등록된 규칙만 따랐는가?
- [ ] 효과가 작거나 부정적인 결과도 보고되었는가?
- [ ] 모든 코드·데이터가 공개되어 있는가?
- [ ] 외부 재현 가능 한 줄 명령이 README에 있는가?
- [ ] Limitations 섹션에 본 연구의 한계가 명시되어 있는가?
- [ ] Threats to Validity 4개 영역 모두 다뤄졌는가?

---

## 10. 본 문서의 본질

이 프로토콜은 본인을 **자기 편향으로부터 보호하는 안전 장치**다. 발명자 동시 분석자라는 이중 역할이 가질 수 있는 confirmation bias·researcher degrees of freedom을 사전에 규정으로 못 박는 것이다.

본인이 "원하는 값이 나오게 프로그래밍" 같은 오류를 우려한 것은 정확한 직관이며, 본 프로토콜이 그 직관을 시스템화한 결과다.

연구가 진행되며 본 프로토콜은 amendment를 통해 보강될 수 있으나, **사전 등록 시점의 가설·분석 방법은 절대 retroactively 변경되지 않는다**. 이것이 본 연구가 외부에서 신뢰받는 유일한 길이다.

---

> **다음 문서**: `experimental-design.md` (4개 시나리오 실험 설계서) → `pre-registration.md` (가설·분석 방법 사전 commit)
