# Experimental Design — AINM Multi-Scenario Empirical Study

> **목적**: 4개 시나리오 (기존 ERP + 신규 3개) 실험의 **결과 보기 전 사전 설계**.
> **본 문서가 commit된 시점 이후, 결과를 본 후 변경 시 amendment 기록 필수.**
> **상위 문서**: `research-integrity-protocol.md`
> **하위 문서**: `pre-registration.md` (가설·분석 방법 사전 commit)
> **작성일**: 2026-04-28

---

## 0. 연구 무결성 원칙 재확인 (이 문서에 강제 적용)

본 설계는 다음 원칙을 위반하지 않는다:

- ✅ Pre-registration 적용 (`pre-registration.md`)
- ✅ HARKing 금지 (가설 사전 commit)
- ✅ p-hacking 금지 (Bonferroni 보정 사전 결정)
- ✅ Cherry-picking 금지 (모든 trial raw data 공개)
- ✅ Honest baselines (DOM agent 매개변수 사전 고정)
- ✅ Negative results 보고 의무
- ✅ COI 선언 (모든 출판물 footer)

---

## 1. 시나리오 4개 — 카테고리·근거·설계

본 연구는 publisher-side standard의 **일반화 가능성(generalizability)**을 입증하기 위해 4개 카테고리를 고른다. 각 카테고리는 reviewer가 "왜 이 카테고리?"라고 물을 때 답할 수 있는 **현실 사이트 패턴 근거**가 있어야 한다.

| ID | 시나리오 | 카테고리 | 현실 사이트 근거 |
|----|--------|--------|--------------|
| **S1** | ERP 주문 입력 | Transactional UI (multi-field form, single submit) | SAP S/4HANA 주문 화면, Oracle Fusion AP, Workday 거래 입력 |
| **S2** | 검색·필터·결과 선택 | Information Retrieval UI (dynamic results) | Amazon, Naver Shopping, Indeed, Google Scholar |
| **S3** | 다단계 Wizard (5+ steps) | Multi-step Sequential UI (state-bearing) | 보험 가입, 공공 민원 (정부24), 회원 등록 |
| **S4** | 다언어 폼 (한↔영 전환) | Internationalized UI | 국제 SaaS, 정부 다언어 포털, 글로벌 e-commerce |

→ **선택 정당화**: 카테고리 4종은 publisher-side standard 적용 가능 영역의 *상호 배타적·집합적으로 모음(MECE)*에 가깝다. Transactional·IR·Sequential·i18n은 HCI 문헌에서 web UX 분류의 표준 4분면 중 핵심.

---

## 2. 시나리오 상세 설계

### S1 — ERP Order Entry (기존, 유지)

#### 1) 시나리오 정의
- 사용자 의도: "특정 vendor에 특정 item을 N개 발주"
- Steps: vendor 선택 → item 선택 → quantity 입력 → unit price 입력 → delivery date → submit
- Success criteria: HTTP 302 to `/orders/{order_id}`, order_id 매핑 정합성 검증

#### 2) Server (`validation/server/scenarios_v3.py::erp_order`)
- 기존 코드 활용 (`validation/server/__init__.py`의 erp_order_v1 라우트)
- 변경 없음

#### 3) Baseline behavior
- DOM 전체 fetch (`/orders/new`)
- Selector 추론 모델 적용 — *결정론적 시뮬레이션* (사전 고정 매개변수)
- 추론 실패율 = `1 - signal_to_noise_ratio` (DOM의 form-element 비율 함수)

#### 4) AINM behavior
- `.well-known/ai-manifest.json` fetch
- Canonical hash 검증 (registry round trip)
- `actions[id="erp_order"].steps[]` 순차 실행

#### 5) Expected metrics (사전 등록 추정치 — pre-registration.md §3 참조)
- input_tokens (baseline): 1,500~2,500 (mean ~1,887, 기존 데이터 기준)
- input_tokens (AINM): 300~400 (mean ~341, 결정론적)
- success_rate (baseline): ~20%
- success_rate (AINM): ~100%

---

### S2 — Search·Filter·Select (신규)

#### 1) 시나리오 정의
- 사용자 의도: "카테고리 X에서 조건 Y를 만족하는 결과를 필터링하고 1건 상세 보기"
- Steps: category 선택 → keyword 입력 → filter 적용 (price range·rating) → 정렬 변경 → 결과 1건 클릭 → 상세 페이지 도달
- Success criteria: 상세 페이지 도달 + 선택한 결과의 ID 일치

#### 2) Server (`validation/server/scenarios_v3.py::search_filter`)
- 새 라우트:
  - `GET /catalog` — 카테고리 트리
  - `GET /search?q=&category=&min_price=&max_price=&min_rating=&sort=` — 결과 페이지 (DOM 노이즈: 광고·추천·페이지네이션·비관련 facet)
  - `GET /item/{item_id}` — 상세 페이지
- 100개 카탈로그 시드 데이터, 결정론적 (seed 기반)
- DOM 노이즈 계수: form 요소 비율 ≈ 5~10% (전형적 commerce 페이지)

#### 3) Baseline behavior
- 카탈로그 페이지 fetch → 카테고리 추론 → 검색 페이지 fetch → 필터 셀렉터 추론
- 다중 추론점 = 다중 실패점

#### 4) AINM behavior
- Manifest의 `actions[id="search_and_select"]` 사용
- selectors{}에 `category_link`, `search_input`, `filter_price_min` 등 선언
- DOM 노이즈와 무관하게 결정론적

#### 5) Expected metrics
- input_tokens (baseline): 2,000~3,500 (DOM 노이즈 ↑)
- input_tokens (AINM): 400~500 (manifest 약간 더 큼)
- success_rate (baseline): 10~25% (다단계 → 누적 실패율)
- success_rate (AINM): ~100%

#### 6) 가설 (pre-reg)
- **H2.1**: AINM이 baseline 대비 input_tokens를 60% 이상 감소
- **H2.2**: AINM이 baseline 대비 success rate를 60 percentage points 이상 향상

---

### S3 — Multi-step Wizard (신규)

#### 1) 시나리오 정의
- 사용자 의도: "5+ step 회원가입형 wizard 완료"
- Steps:
  1. 인적사항 (이름·생년월일·이메일·휴대폰)
  2. 약관 동의 (필수 3개·선택 2개)
  3. 부가정보 (직업·관심사·소개 코드)
  4. 부가서비스 (체크박스·라디오)
  5. 검토 페이지
  6. 제출
- Success criteria: 각 step의 prerequisite 만족 + 최종 제출 응답 코드 + 제출 ID 매핑

#### 2) Server (`validation/server/scenarios_v3.py::wizard`)
- 새 라우트: `/wizard/step/{1~5}`, `/wizard/review`, `/wizard/submit`
- Session-based state (Flask session)
- 각 step마다 이전 step 검증 (state machine)
- 실패 모드: 약관 누락 시 step 2 reject, 인적사항 누락 시 step 1 reject

#### 3) Baseline behavior
- 각 step DOM fetch + 셀렉터 추론
- Step 간 state 누적 추론 부담 ↑
- 누적 실패율 = 1 - (per-step success)^N

#### 4) AINM behavior
- Manifest의 `actions[id="multi_step_signup"].steps[]` 순차 실행
- DSL의 `wait_for`·`assert` 활용으로 state 전환 결정론적

#### 5) Expected metrics
- input_tokens (baseline): 8,000~15,000 (5+ step × 페이지 DOM)
- input_tokens (AINM): 350~450 (manifest 한 번)
- success_rate (baseline): 5~15% (누적 실패)
- success_rate (AINM): ~100%

#### 6) 가설 (pre-reg)
- **H3.1**: AINM이 baseline 대비 input_tokens를 90% 이상 감소 (다단계라 격차 더 큼)
- **H3.2**: AINM이 baseline 대비 success rate를 80 percentage points 이상 향상

---

### S4 — Internationalized Form (신규)

#### 1) 시나리오 정의
- 사용자 의도: "한국어 UI에서 폼 작성 → 영어 UI로 전환 → 영어 UI에서 동일 작업 수행"
- Steps:
  1. /ko-KR/form 진입, 5개 필드 입력
  2. 언어 전환 토글 클릭 (`/en-US/form`)
  3. 같은 필드 영어 라벨에서 동일 데이터 입력
  4. 제출
- Success criteria: 양 언어에서 동일 데이터 도달

#### 2) Server (`validation/server/scenarios_v3.py::i18n_form`)
- 새 라우트: `/{locale}/form`, `/{locale}/submit`
- 한국어 라벨: "이름", "이메일", "전화번호", "주소", "관심분야"
- 영어 라벨: "Name", "Email", "Phone", "Address", "Interest"
- DOM 노이즈: 다언어 메뉴·관련 콘텐츠

#### 3) Baseline behavior
- 한국어 페이지 셀렉터 추론 + 영어 페이지 셀렉터 추론 (별도)
- i18n key 매핑 정보 없으니 매번 새로 추론

#### 4) AINM behavior
- Manifest의 `selectors{}` 에 i18n-aware locator 선언
- 라벨이 변하든 ID·name 속성 기반 셀렉터는 불변
- 한 번의 manifest로 다언어 모두 처리

#### 5) Expected metrics
- input_tokens (baseline): 3,000~5,000 (양 언어 DOM 합)
- input_tokens (AINM): 350~450 (manifest 한 번)
- success_rate (baseline): 15~30% (양 언어 모두 성공해야 함)
- success_rate (AINM): ~100%

#### 6) 가설 (pre-reg)
- **H4.1**: AINM이 baseline 대비 input_tokens를 85% 이상 감소
- **H4.2**: AINM이 baseline 대비 success rate를 70 percentage points 이상 향상

---

## 3. 측정 지표 통합 정의

### 3.1 Primary outcomes (가설 검정 대상)
- **`input_tokens`** — tiktoken cl100k_base 인코딩 기준, trial별 누적
- **`success`** — 시나리오별 success criteria 만족 여부 (boolean)

### 3.2 Secondary outcomes (보고만, 가설 X)
- `http_requests` — 시나리오별 누적 HTTP 요청 수
- `llm_calls` — LLM 결정점 수
- `wall_time_ms` — End-to-End 실행 시간
- `steps_attempted` / `steps_succeeded` — 부분 진행도

### 3.3 Derived metrics (분석 단계)
- Token reduction ratio: `(baseline_mean - ainm_mean) / baseline_mean`
- Success rate lift: `ainm_success_rate - baseline_success_rate` (percentage points)
- Cohen's d (effect size for tokens)
- 95% Confidence Interval

---

## 4. 환경·하드웨어·라이브러리 (사전 lock)

### 4.1 실행 환경
- OS: Windows 10 또는 11 (구체 버전 결과 보고 시 명시)
- Python: **3.11.x** (3.12+는 의존성 호환 미검증)
- 메모리: 8GB+ (충분)
- 네트워크: localhost only (외부 호출 0)

### 4.2 라이브러리 lock (`requirements.txt`)
```
Flask==3.0.3
requests==2.32.3
beautifulsoup4==4.12.3
tiktoken==0.7.0
matplotlib==3.9.2
numpy==2.1.0
scipy==1.14.0    # 신규 추가 (t-test, CI, Cohen's d)
```

### 4.3 Random seed
- Base seed: **1000**
- Trial seed: `base + trial_index` (즉 1000~1099)
- 시나리오 간 동일 seed 공유 → seed 효과 분리 가능

---

## 5. 실험 실행 순서 (사전 정의)

### Phase 2 — 코드 구현 (이 단계에서 결과 안 봄)
1. `validation/server/scenarios_v3.py` 작성 (4개 라우트)
2. `validation/agent/baseline_agent.py` 시나리오별 분기 추가
3. `validation/agent/manifest_agent.py` 시나리오별 분기 추가
4. `validation/benchmark/run_benchmark_v3.py` 작성
5. `validation/benchmark/analyze_v3.py` 작성 (분석 코드 *결과 보기 전*)
6. **GitHub commit + tag `v0.4-code-2026-XX-XX`**

### Phase 3 — 실험 실행
7. 1회 실행: `python benchmark/run_benchmark_v3.py --seed 1000 --repeats 100`
8. 출력: `validation/results_v3/metrics.csv` (4 시나리오 × 2 agents × 100 trials = 800 행)
9. 출력: `validation/results_v3/raw.json`
10. **GitHub commit + tag `v0.5-data-2026-XX-XX`**

### Phase 4 — 분석 (사전 작성한 코드 그대로 실행)
11. 1회 실행: `python benchmark/analyze_v3.py`
12. 출력: `validation/results_v3/analysis.json`, `summary.md`, 그래프 PNG
13. **GitHub commit + tag `v0.6-analysis-2026-XX-XX`**

### Phase 5 — 보고서 갱신
14. 영문 본문 v2 (`tech-report-en.md`) 갱신
15. 한글 번역 (`tech-report-kr.md`)
16. **GitHub commit + tag `v1.0-report-2026-XX-XX`**

---

## 6. 분석 방법 사전 정의 (확장)

### 6.1 시나리오별 검정
- **Welch's t-test** (등분산 가정 X) for input_tokens (baseline vs AINM)
- **Fisher's exact test** for success rate (baseline vs AINM, 2x2 contingency)
- **Cohen's d** (effect size for tokens)
- **95% Confidence Interval** for mean difference (tokens)

### 6.2 다중 비교 보정
- 4 시나리오 × 2 primary outcomes = 8 비교
- **Bonferroni**: α_corrected = 0.05 / 8 = **0.00625**
- 보고: corrected p-value, uncorrected p-value 둘 다

### 6.3 정규성 검정
- **Shapiro-Wilk** test for tokens distribution
- p < 0.05 (정규성 위배) → Mann-Whitney U test로 대체

### 6.4 Pooled meta-analysis
- 4 시나리오 effect size 가중 평균
- Fixed-effect model (시나리오 변동성 작을 때)
- Random-effect model (heterogeneity 있을 때)

### 6.5 Outlier handling (사전 등록)
- 사전 정의 outlier: `wall_time_ms > 60000` → timeout, success=False, 다른 지표는 raw 그대로
- z-score > 3 outlier는 **제거하지 않고** 별도 표시
- 사후 outlier 제거 금지

### 6.6 Missing data
- HTTP error → trial failure로 분류, success=False, 다른 지표 raw
- 의도적 trial 생략 금지 (전수 보고)

---

## 7. Power Analysis (표본 크기 정당화)

### 7.1 Effect size 추정
- 기존 데이터 (S1) 기준 Cohen's d ≈ 2.4 (very large effect)
- 신규 시나리오 (S2~S4) 효과 크기는 더 클 것으로 예상 (multi-step·DOM noise ↑)

### 7.2 Power calculation
- 두 그룹 t-test, α = 0.00625 (Bonferroni-corrected), power = 0.95
- d = 0.5 (medium effect 가정 — 보수적) → n = 168 per group
- d = 0.8 (large effect 가정) → n = 67 per group
- d = 1.0 (현실적) → n = 43 per group
- d = 2.0 (예상) → n = 11 per group

→ **n = 100 per group**은 d ≥ 0.5 효과를 95% power로 검출 가능. 충분.

### 7.3 Stopping rule
- 100 trial 완료 후 **추가 수집 금지** (sequential testing 금지)
- 단 코드 버그·환경 오류 발견 시 전체 재실행 (부분 추가 X)

---

## 8. 인용 권위 기준

본 연구의 모든 인용은 다음 권위 기준을 충족한다:

### 8.1 정설 (사용 가능)
- ✅ Top-tier peer-reviewed conferences (CHI, NeurIPS, ICML, ICLR, WWW, ACL 등)
- ✅ 권위 저널 (Nature, Science, CACM, ACM/IEEE Transactions)
- ✅ 표준화 문서 (IETF RFC, W3C Recommendation, ISO/IEC, NIST FIPS·SP)
- ✅ 정부·국제기구 공식 문서 (EU AI Act, OECD AI Principles)
- ✅ 학술 출판사 도서 (Springer, MIT Press, Cambridge UP, Lawrence Erlbaum 등)

### 8.2 미달 (사용 X)
- ❌ Wikipedia
- ❌ 일반 블로그 (Medium, dev.to, 회사 블로그)
- ❌ 회사 마케팅 자료
- ❌ 검증 안 된 GitHub README (도구 인용은 footnote OK)
- ❌ 단순 preprint (가능하면 published version 인용)
- ❌ 뉴스 기사·특집 기사

### 8.3 본 연구 References 권위 검증 (영문 본문 §References 갱신 시 적용)

기존 v1의 약점 인용 → 권위 인용으로 교체:

| v1 (약점) | v2 교체 (권위) |
|---------|------------|
| Anthropic Computer Use technical doc | Yang et al. (2023). "Set-of-Mark Prompting." (arXiv:2310.11441 → 가능 시 ICLR 2024 publication) |
| AutoGPT GitHub | Yao et al. (2023). "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR. |
| Anthropic Claude pricing | Brown et al. (2020). "Language Models are Few-Shot Learners." NeurIPS. (토큰 비용 구조의 학술적 출처) |
| WebVoyager (preprint only) | Zhou et al. (2024). "WebArena: A Realistic Web Environment for Building Autonomous Agents." ICLR. |

추가 권위 인용 (정설 강화):
- Schick et al. (2023). "Toolformer." NeurIPS.
- Koh et al. (2024). "VisualWebArena." ICML.
- Nosek et al. (2018). "The Preregistration Revolution." PNAS.
- Open Science Collaboration (2015). "Estimating the reproducibility of psychological science." Science.
- Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences. Lawrence Erlbaum.
- Benjamini & Hochberg (1995). "Controlling the false discovery rate." JRSS-B.

→ 이 보강은 영문 본문 v2에서 적용. 본 설계서는 *어떤 기준으로* 인용하는지를 박는다.

---

## 9. Phase 2 코드 구현 계획 (다음 단계)

### 9.1 새 파일 목록
```
validation/
├── server/
│   ├── __init__.py (기존)
│   └── scenarios_v3.py     # NEW: S2·S3·S4 라우트
├── agent/
│   ├── common.py (기존)
│   ├── baseline_agent.py   # 기존 + 시나리오별 분기 추가
│   └── manifest_agent.py   # 기존 + 시나리오별 분기 추가
├── benchmark/
│   ├── scenarios.py (기존)
│   ├── scenarios_v3.py     # NEW: S2·S3·S4 시나리오 정의
│   ├── run_benchmark_v3.py # NEW: 4 시나리오 일괄 실행
│   └── analyze_v3.py       # NEW: 통계 분석 (t-test, CI, Cohen's d)
├── manifests/
│   ├── search_filter.json  # NEW: S2 manifest
│   ├── wizard.json         # NEW: S3 manifest
│   └── i18n_form.json      # NEW: S4 manifest
└── results_v3/
    └── (Phase 3 실행 후 채워짐)
```

### 9.2 코드 작성 순서
1. Manifest JSON 3개 (선언적이라 가장 빠름)
2. Server 라우트 3개 (의존성 적음)
3. Baseline agent 시나리오 분기
4. Manifest agent 시나리오 분기
5. Benchmark runner
6. Analyzer (★ 사전 작성 — 더미 데이터로 테스트)

### 9.3 단위 테스트 의무
각 시나리오·각 agent에 대해:
- 정상 case test
- 실패 case test (예: 약관 미동의 시 wizard reject)
- Manifest 변조 case test (canonical hash 불일치)

테스트 통과 후 Phase 3 진입.

---

## 10. 본 설계서의 검증 체크리스트

다음 모두 충족 시 Phase 2 진입:

- [ ] 4개 시나리오 모두 카테고리 정당성 명시됨
- [ ] 각 시나리오 success criteria 정량 정의됨
- [ ] Primary outcomes 사전 명시 (input_tokens, success_rate)
- [ ] Secondary outcomes 별도 분류
- [ ] Outlier 처리 규칙 사전 정의
- [ ] Missing data 규칙 사전 정의
- [ ] 표본 크기 power analysis 정당화
- [ ] 통계 검정 방법 사전 명시 (Welch t / Fisher / Bonferroni)
- [ ] 정규성 위배 시 대체 검정 사전 정의 (Mann-Whitney U)
- [ ] 라이브러리 버전 lock
- [ ] Random seed 사전 고정
- [ ] 코드 작성 순서 사전 명시
- [ ] 단위 테스트 의무 명시
- [ ] 인용 권위 기준 명시

---

## 11. Amendment 기록 (이 문서의 변경 로그)

| 날짜 | 버전 | 변경 사유 | 승인자 |
|-----|-----|--------|------|
| 2026-04-28 | v0.1 | 최초 작성 | Wonpyo Han (single author) |
| (이후) | (변경 시 amendment 항목 추가, 사후 retroactive 변경 금지) | | |

---

> **다음 문서**: `pre-registration.md` (가설·통계 사전 commit)
> **이 후 단계**: Phase 2 코드 구현
