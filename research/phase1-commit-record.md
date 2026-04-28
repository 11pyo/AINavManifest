# Phase 1 사전 등록 — Commit Record

> **본 문서는 Phase 1 사전 등록의 immutable timestamp 증거다.**
> 본 문서를 변경할 수 없다 — 변경 시 commit history에 그 흔적이 영구히 남는다.
> 이 commit 이후 가설·분석 방법 변경은 `pre-registration.md` §11 Amendments에 기록되며 retroactive 변경은 학술 윤리 위반.

---

## Phase 1 등록 메타

| 항목 | 값 |
|-----|-----|
| **Phase** | 1 — Pre-registration |
| **등록 일시 (KST)** | 2026-04-28 09:57:56 +0900 |
| **Git commit hash** | `764ce84ea713daa17366e4e1f1439ec99c3bf7e9` |
| **Git tag** | `v0.3-prereg-2026-04-28` (annotated tag) |
| **Tagger·Author** | Won-pyo Han <pk102h@naver.com> |
| **ORCID** | 0009-0002-7528-2228 |
| **Repository (local)** | `D:/개발한 프로그램들/AINavManifest/github_repo/` |
| **Repository (remote)** | `https://github.com/11pyo/AINavManifest` (push deferred — 아래 §"Push 보류" 참조) |

---

## 등록된 문서

| 파일 | SHA-256 (참고용 외부 검증 가능) | 분량 |
|-----|----------------------------|----|
| `research/research-integrity-protocol.md` | (commit 객체 내 blob hash로 확인) | 약 10 페이지 |
| `research/experimental-design.md` | (동일) | 약 12 페이지 |
| `research/pre-registration.md` | (동일) | 약 10 페이지 |

→ 각 파일의 정확한 blob hash는 `git ls-tree v0.3-prereg-2026-04-28`로 확인 가능.

---

## 등록된 핵심 사항 요약 (재확인용)

### 가설 (8개) — `pre-registration.md` §2

- H1.1 — S1 input_tokens ≥ 70% 감소
- H1.2 — S1 success rate ≥ 70 percentage points 향상
- H2.1 — S2 input_tokens ≥ 60% 감소
- H2.2 — S2 success rate ≥ 60 pp 향상
- H3.1 — S3 input_tokens ≥ 90% 감소
- H3.2 — S3 success rate ≥ 80 pp 향상
- H4.1 — S4 input_tokens ≥ 85% 감소
- H4.2 — S4 success rate ≥ 70 pp 향상

### 표본 — `pre-registration.md` §4

- n=100 per (agent × scenario)
- 총 800 trials
- Stopping rule: n=100 즉시 종료, sequential testing 금지

### 통계 — `pre-registration.md` §5

- Welch's t-test (정규성 위배 시 Mann-Whitney U)
- Fisher's exact test (success)
- Cohen's d (effect size)
- Bootstrap 95% CI (10,000 resamples)
- Bonferroni α = 0.05/8 = 0.00625

### 결정 기준 — `pre-registration.md` §6

- 가설 수용: corrected p < 0.00625 AND 효과 크기 임계값 만족 AND 95% CI ∌ 0
- 가설 기각: uncorrected p ≥ 0.05 OR 효과 크기 미달 OR 95% CI ∋ 0
- Inconclusive: 0.00625 ≤ p < 0.05

### Outlier 처리 — `pre-registration.md` §7

- Timeout > 60s = success=False, 분석 포함
- Z-score |z| > 3 = 별도 표기, 제거 X
- 사후 임의 제거 = 학술 윤리 위반 (사전 명시)

---

## Push 보류 — 자제 약속과의 정합성

본 commit은 **로컬에만 존재**한다. 원격 push (`git push origin main`, `git push origin v0.3-prereg-2026-04-28`)는 **사내 직무발명 검토 결과 후**에 수행한다.

근거: 2026-04-27 동국시스템즈에 송부한 커버레터 §5에 본인은 다음을 자발 보류하기로 명시했다:
> "GitHub 공개 리포의 유지·관리 (신규 커밋은 자발 동결)"

Push 시점 (예정):
- 사내 검토 결과 (2026-08 경) 이후
- Phase 1·2·3·4 모두 완료된 시점에 일괄 push
- Push 시 본 commit 및 후속 commit·tag 모두 원격에 반영

이 보류는 사전 등록의 *효력*에 영향이 없다. Commit hash·tag는 이미 이 시점에 박혔고, 외부 검증 시 commit hash + OSF 등록(아래 §"OSF 등록")으로 충분하다.

---

## OSF 등록 (예정)

OSF.io (Open Science Framework)에 별도 사전 등록 권장. 이는 GitHub 외 학계 표준 플랫폼으로, DOI를 자동 발급한다.

- 등록 모드: **Private** (검토 진행 중 비공개 유지)
- 공개 전환: 사내 검토 결과 후 push와 동시에 release
- 등록 양식: AsPredicted Pre-registration Template 또는 OSF Standard Pre-Registration

OSF 등록 절차는 `osf-registration-guide.md` 참조.

---

## 외부 검증 가능성

본 사전 등록은 다음 방법으로 외부 연구자가 검증 가능하다:

### 사내 검토 결과 후 (push 완료 시점)

```bash
git clone https://github.com/11pyo/AINavManifest
cd AINavManifest
git checkout v0.3-prereg-2026-04-28
git log -1 --pretty=fuller
# Author Date: Tue Apr 28 09:57:56 2026 +0900
# Commit Date: 동일

git show v0.3-prereg-2026-04-28 --stat
# 3 files changed, 1127 insertions(+)

git ls-tree v0.3-prereg-2026-04-28 research/
# blob hash 3개로 파일 무결성 검증
```

### Phase 1 등록 시점 (현재)

- 본 문서 (`phase1-commit-record.md`)에 hash 박힘
- OSF 등록 시 OSF 자체 timestamp 발급

---

## Phase 진행 표

| Phase | 상태 | 시점 | Tag |
|-------|----|----|-----|
| 1 — Pre-registration | ✅ 완료 | 2026-04-28 09:57:56 KST | `v0.3-prereg-2026-04-28` |
| 2 — Code implementation | 진행 예정 | - | `v0.4-code-YYYY-MM-DD` |
| 3 — Data collection | 진행 예정 | - | `v0.5-data-YYYY-MM-DD` |
| 4 — Analysis | 진행 예정 | - | `v0.6-analysis-YYYY-MM-DD` |
| 5 — Report | 진행 예정 | - | `v1.0-report-YYYY-MM-DD` |
| 6 — Publication (Zenodo + GitHub push) | 사내 검토 후 | ~2026-08 이후 | `v1.0-zenodo-YYYY-MM-DD` |

---

## 본 문서의 무결성 약속

- 본 문서는 Phase 1 commit 직후 별도 commit으로 추가됨
- 본 문서의 내용은 **사실 보고**이며, 향후 사실 변경 시 (예: push 시점 변경, OSF 등록 완료) amendment 항목으로 추가만 하며 본문은 수정하지 않는다
- 모든 후속 Phase의 commit hash는 본 문서에 누적 기록된다

---

## Amendments to this record

| Date | Change | Reason |
|------|-------|------|
| 2026-04-28 | 최초 작성 | Phase 1 commit 직후 hash 기록 |
| (이후) | (Phase 2~6 진행 시 hash 추가) | |
