# OSF 사전 등록 가이드

> **목적**: Open Science Framework (osf.io)에 본 연구를 사전 등록하는 절차.
> **상태**: 가이드만 작성. 실제 등록은 본인이 수행 (계정 인증 필요).
> **권장 시점**: 즉시 (Phase 1 GitHub commit과 동시 또는 직후)
> **공개 모드**: **Private** (검토 진행 중 비공개), 사내 검토 결과 후 공개로 release.

---

## OSF란

**Open Science Framework** (osf.io) — 학계 표준 사전 등록·데이터 공유 플랫폼. **무료, 사비 0원, 회사 자원 0**. Center for Open Science (비영리) 운영. 연 60만+ 연구자 사용.

OSF의 학술적 권위:
- 학계 표준 사전 등록 도구 (Nature, Science, PNAS 등 주요 저널 권장)
- DOI 자동 발급 (10.17605/OSF.IO/XXXXX 형식)
- Read-only frozen registration (수정 불가, timestamp 박힘)
- AsPredicted, OSF Standard 등 표준 양식 제공

---

## 왜 GitHub commit만으로는 부족한가

| 항목 | GitHub commit | OSF 등록 |
|-----|--------------|--------|
| Timestamp | ✅ commit hash | ✅ 등록 timestamp |
| 외부 검증 | △ push 후만 | ✅ 등록 즉시 |
| Frozen (수정 불가) | △ commit 위에 다른 commit 가능 | ✅ registration 후 immutable |
| DOI | ❌ Zenodo 게시 시만 | ✅ 자동 |
| 학계 인지도 | △ 코드 중심 | ✅ 학계 표준 |
| 비공개 옵션 | △ private repo | ✅ embargo |

→ 둘 다 하면 timestamp 이중 보장. **GitHub commit 위에 OSF 등록을 더하는 것**이 본 연구에 적합.

---

## 등록 절차 — 본인이 따라할 단계

### Step 1 — OSF 계정 생성 (5분, 사비 0)

1. https://osf.io/register/ 접속
2. **개인 이메일로 가입** (회사 이메일 X — 작성 당시 권리 귀속 협상 기간이라 사적 채널 권장. 2026-11-04 자유발명 확정 후에도 특허 출원 이메일과의 일관성 위해 개인 채널 유지)
   - 권장: `pk102h@naver.com` (특허 출원 시 사용한 이메일과 일관)
3. 이메일 인증
4. **ORCID 연동**: 프로필 설정 → ORCID 추가 → `0009-0002-7528-2228`
   - ORCID 연동 시 OSF 등록이 자동으로 본인 ORCID 페이지에 연결됨

### Step 2 — Project 생성 (3분)

1. 우측 상단 **"+ Create new project"** 클릭
2. 다음 정보 입력:

| 필드 | 값 |
|-----|-----|
| Title | AI Navigation Manifest: Publisher-Side Workflow Specification for Trustworthy AI-Agent Browsing |
| Description | (아래 §"Project Description" 참조) |
| Storage location | United States 또는 Frankfurt (default OK) |
| Affiliated institutions | 비워둠 (Independent Researcher) |
| Tags | `AI Agent`, `Web Automation`, `Publisher-Side Standard`, `Manifest Protocol`, `IETF Standard` |
| **Public/Private** | **Private** ⚠️ (사내 검토 진행 중 공개 X) |

#### Project Description (복사·붙여넣기용)

```
This project hosts the pre-registration, experimental design, and integrity protocol for an empirical study of AI Navigation Manifest (AINM) — a publisher-side workflow specification for AI agents browsing transactional websites.

The study evaluates AINM across four scenario categories:
- S1: ERP order entry (transactional UI)
- S2: Search-filter-select (information retrieval UI)
- S3: Multi-step wizard (sequential UI)
- S4: Internationalized form (i18n UI)

with n=100 trials per (agent × scenario), totaling 800 trials.

Hypotheses, statistical methods, and decision rules are committed in pre-registration.md before data collection.

Author: Wonpyo Han (ORCID 0009-0002-7528-2228)
Companion patent application: KR 10-2026-0071716
Companion IETF Internet-Draft: draft-han-ai-manifest-00

Conflict of Interest: The author is the inventor on the cited patent application and the registered author of the IETF Internet-Draft. All raw data and analysis code will be released openly upon publication.
```

### Step 3 — 사전 등록 파일 업로드 (10분)

1. 프로젝트 페이지 → **Files** 탭
2. **OSF Storage** 선택 → **Upload** 클릭
3. 다음 4개 파일 업로드:
   - `research/research-integrity-protocol.md`
   - `research/experimental-design.md`
   - `research/pre-registration.md`
   - `research/phase1-commit-record.md`
4. 업로드 후 각 파일의 OSF 자체 timestamp 자동 박힘

### Step 4 — Pre-registration 등록 (★ 가장 중요, 15분)

1. 프로젝트 페이지 → **Registrations** 탭 → **New Registration** 버튼
2. 양식 선택:
   - **권장: "OSF Pre-Registration"** (OSF 표준 양식, 16개 질문)
   - 대안: "AsPredicted Pre-Registration" (9개 질문, 더 간단)
3. 양식 작성 (아래 §"OSF 양식 답안 가이드" 참조)
4. 작성 완료 후:
   - **Registration mode**: **Embargo** 선택 (비공개, 자동 공개 시점 지정 가능)
   - Embargo 기간: **2027-04-28** 또는 **사내 검토 결과 후 수동 공개**
5. **Register Now** 클릭
6. OSF 자동으로 frozen — **이 시점부터 수정 불가**
7. 등록 완료 페이지에서 **DOI** 받기 (예: `10.17605/OSF.IO/XXXXX`)

### Step 5 — DOI를 phase1-commit-record.md에 기록 (5분)

1. OSF 등록 완료 페이지에서 DOI 복사
2. 본인 로컬에서 `research/phase1-commit-record.md` 열기
3. 다음 항목 추가:
   ```
   | OSF DOI | 10.17605/OSF.IO/XXXXX |
   | OSF URL | https://osf.io/XXXXX |
   | OSF 등록 일시 | YYYY-MM-DD HH:MM UTC |
   | OSF embargo 종료 | 2027-04-28 또는 수동 공개 |
   ```
4. 로컬 commit 추가:
   ```bash
   cd "C:/My-Projects/AINavManifest/github_repo"
   git add research/phase1-commit-record.md
   git commit -m "Add OSF DOI to phase1 commit record"
   ```

---

## OSF 양식 답안 가이드 (OSF Standard Pre-Registration)

OSF 표준 양식 16개 질문에 대한 답안 가이드. 본인 작성 시 참고:

### 1. Title
```
AI Navigation Manifest: Publisher-Side Workflow Specification for Trustworthy AI-Agent Browsing — Multi-Scenario Empirical Study
```

### 2. Authors
```
Wonpyo Han (Independent Researcher, ORCID: 0009-0002-7528-2228)
```

### 3. Description
(Step 2의 Project Description 재사용)

### 4. Hypotheses
```
We test 8 confirmatory hypotheses (H1.1, H1.2, H2.1, H2.2, H3.1, H3.2, H4.1, H4.2) across 4 scenario categories.

For each scenario S_i ∈ {S1: ERP order, S2: Search-filter, S3: Multi-step wizard, S4: i18n form}:
- H_i.1: AINM agent's mean input_tokens is at least X% smaller than baseline agent's mean input_tokens (X = 70/60/90/85 for S1/S2/S3/S4 respectively).
- H_i.2: AINM agent's success rate is at least Y percentage points higher than baseline agent's success rate (Y = 70/60/80/70 for S1/S2/S3/S4 respectively).

Full hypothesis statements with effect-size thresholds are in pre-registration.md §2 (uploaded as project file).

Direction: All hypotheses are one-tailed (AINM > baseline).
```

### 5. Sampling plan
```
n = 100 trials per (agent × scenario), 2 agents × 4 scenarios = 800 trials total.

Sample size justification: Power analysis with α=0.00625 (Bonferroni-corrected for 8 comparisons), power=0.95, expected Cohen's d ≥ 1.0 (large effect, based on pilot data with d≈2.4) requires n=43 per group; n=100 selected with conservative buffer for unexpectedly small effects.

Stopping rule: n=100 reached → data collection terminates immediately. Sequential testing is prohibited. Only full re-execution allowed in case of code/environment errors.
```

### 6. Variables
```
Independent variable: Agent type (categorical: baseline, ainm)
Primary dependent variables:
  - input_tokens (continuous, integer ≥ 0; tiktoken cl100k_base)
  - success (binary; scenario-specific success criteria)
Secondary outcomes (reported, not tested): http_requests, llm_calls, wall_time_ms, steps_attempted, steps_succeeded
Control variables: scenario, trial seed (deterministic 1000+i), server config, hardware, library versions
```

### 7. Analysis plan
```
Per-scenario hypothesis testing:
  - input_tokens: Welch's two-sample t-test (two-tailed); fallback to Mann-Whitney U if Shapiro-Wilk indicates non-normality (p<0.05)
  - success: Fisher's exact test on 2×2 contingency
Effect size: Cohen's d for tokens; risk difference for success
95% CI: bootstrap with 10,000 resamples for mean difference

Multiple comparisons: Bonferroni correction across 8 primary hypotheses, α_corrected = 0.05/8 = 0.00625. Holm-Bonferroni reported in parallel.

Decision rules (pre-registered):
  - Accept hypothesis: corrected p < 0.00625 AND effect size meets threshold AND 95% CI excludes 0
  - Reject: uncorrected p ≥ 0.05 OR effect size below threshold OR 95% CI includes 0
  - Inconclusive: 0.00625 ≤ p < 0.05

Outlier handling (pre-registered): timeouts (wall_time > 60s) reclassified as success=False; |z|>3 marked but NOT removed; post-hoc removal prohibited.

Missing data: HTTP errors → trial=failure; network errors in localhost → full re-run with amendment record.
```

### 8. Other
```
Conflict of Interest: The author is the sole inventor on Korean patent application 10-2026-0071716 covering core mechanisms (canonical hash trust, registry API, workflow DSL), and the registered author of IETF Internet-Draft draft-han-ai-manifest-00. The author also intends to commercialize the technology pending ongoing corporate IP review.

Open Science: All code (validation/, MIT license), all raw data (Zenodo, CC-BY 4.0), and this pre-registration (OSF, embargo until 2027-04-28 or earlier release upon corporate review conclusion) are released openly.

Reproducibility: Single command reproduces all results: `python validation/benchmark/run_benchmark_v3.py --seed 1000 --repeats 100`. Library versions locked in requirements.txt. Hardware/environment details reported in publication.
```

### 9~16. (선택 항목들)
대부분 N/A 또는 위 답안 참고하여 작성.

---

## 등록 후 — 후속 절차

### 즉시
- OSF DOI 받기
- `phase1-commit-record.md`에 DOI 기록 + 로컬 commit
- OSF embargo 설정 확인 (2027-04-28 또는 수동 공개)

### 결과 발표 단계 (사내 검토 결과 후)
- OSF 비공개 → 공개 release
- GitHub push (`v0.3-prereg-2026-04-28` tag)
- Zenodo 게시 (테크니컬 리포트)
- OSF DOI를 모든 출판물 §0 또는 footer에 명시

---

## 주의사항

### ❌ 절대 금지
- OSF 등록 후 가설·분석 방법 *내용 변경* (등록은 frozen)
- Embargo 종료 전 OSF 페이지를 외부 공유 (회사 자제 약속 위반)
- 회사 이메일·계정으로 등록 (사적 채널 사용 권장)

### ⚠️ 주의
- Embargo 기간 자동 연장은 OSF 정책상 일부 제한. 사내 검토가 길어질 가능성 대비 **최대 4년 embargo**까지 설정 가능 — 본 연구는 검토 4개월 후 release 예정이라 충분.
- OSF 양식의 "Public" 옵션 실수 클릭 주의 — 한 번 공개되면 비공개로 되돌리기 복잡

### ✅ 권장
- OSF 등록 양식 작성 시 본 가이드의 답안을 그대로 복사·붙여넣기
- 양식 작성 중 "Save Draft" 자주 활용 (자동 저장 안 됨)
- ORCID 연동으로 본인 ORCID 페이지에 자동 연결

---

## 작업 시간 추정

| 단계 | 시간 |
|-----|----|
| Step 1 — 계정 생성 | 5분 |
| Step 2 — Project 생성 | 3분 |
| Step 3 — 파일 업로드 | 10분 |
| Step 4 — Pre-registration 등록 | 15분 |
| Step 5 — DOI 기록 + 로컬 commit | 5분 |
| **총** | **약 40분** |

→ 한 번 작업으로 끝. 사적 시간(주말·야간) 활용 가능.

---

## 본 가이드의 본질

OSF 등록은 **사전 등록의 학계 표준 timestamp**다. GitHub commit hash가 본 연구의 1차 timestamp라면, OSF DOI는 학계가 공식 인정하는 2차 timestamp다.

사내 검토 결과에 따라 사업화 시나리오가 결정되더라도, 사전 등록은 **본인의 학술 자산**으로 영구 박힌다. 본인 ORCID 페이지에 OSF DOI가 연결되어 평생 인용 가능한 형태로 누적된다.

본 가이드를 따라 등록하는 데 사비 0원, 약 40분이 소요된다.
