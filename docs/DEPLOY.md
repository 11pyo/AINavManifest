# GitHub Pages 배포 가이드

이 `docs/` 폴더는 AI Navigation Manifest 공식 Landing Page 입니다. GitHub Pages 배포만 켜면 즉시 공개됩니다.

---

## 📂 파일 구조

```
docs/
├── index.html       한국어 Landing Page (기본)
├── en.html          English version
├── style.css        공통 스타일
├── app.js           ROI 계산기 + 스무스 스크롤
├── FAQ.md           자주 묻는 질문 (기존 유지)
├── FRAND.md         FRAND 라이선스 조건 (기존 유지)
└── DEPLOY.md        본 문서
```

---

## 🚀 GitHub Pages 활성화 (최초 1회)

### 1. GitHub 웹에서 설정

1. 저장소 접속: <https://github.com/11pyo/AINavManifest>
2. 상단 탭 **`Settings`** 클릭
3. 좌측 메뉴 **`Pages`** 클릭
4. **`Build and deployment`** 섹션에서:
   - **Source**: `Deploy from a branch` 선택
   - **Branch**: `main` 선택 → 폴더 드롭다운에서 `/docs` 선택
5. **`Save`** 버튼 클릭
6. 1~2분 대기 후 상단에 초록색 알림: `Your site is live at https://11pyo.github.io/AINavManifest/`

### 2. 배포 URL 확인

배포 완료 후 접속 주소:
- **한국어**: <https://11pyo.github.io/AINavManifest/>
- **English**: <https://11pyo.github.io/AINavManifest/en.html>

---

## 🔄 이후 갱신 방법

HTML·CSS·JS 파일을 수정하고 `main` 브랜치로 푸시하면 **자동 재배포** (1~2분 소요).

```bash
# 로컬에서 수정 후
cd github_repo
git add docs/
git commit -m "docs: landing page update"
git push origin main
```

---

## 🧪 로컬 프리뷰

배포 전에 로컬에서 미리 보려면:

### 방법 1 — Python (가장 간단)
```bash
cd github_repo/docs
python -m http.server 8000
```
브라우저에서 <http://localhost:8000/> 접속.

### 방법 2 — Node.js (live reload 원할 시)
```bash
npx serve github_repo/docs
```

### 방법 3 — VS Code Live Server 확장
`index.html` 우클릭 → "Open with Live Server"

---

## 🌐 커스텀 도메인 연결 (선택, 추후)

`ainavmanifest.com` 같은 자체 도메인 연결 시:

1. 도메인 구매 (Namecheap·Gabia·Cloudflare Registrar 등)
2. `docs/CNAME` 파일 생성:
   ```
   ainavmanifest.com
   ```
3. DNS 설정:
   ```
   A   185.199.108.153
   A   185.199.109.153
   A   185.199.110.153
   A   185.199.111.153
   ```
4. GitHub Settings → Pages → Custom domain에 입력 + `Enforce HTTPS` 체크

---

## ✅ 배포 후 점검 체크리스트

배포 URL에 접속해 다음 확인:

- [ ] Hero 섹션 3개 배지 (GitHub · IETF · 특허 · 청구항) 정상 렌더링
- [ ] 실증 카드 3종 (SAP · 공공 · 벤치마크 v2) 지표 표시
- [ ] ROI 계산기 값 수정 시 월/연 절감액 실시간 반영
- [ ] Contact 섹션 "📧 이메일 문의" 버튼이 mailto 링크로 작동
- [ ] 푸터 라이선스·연락처 링크 유효
- [ ] 영문 토글 (`EN` 버튼) → `en.html` 로 이동
- [ ] 모바일 반응형 (브라우저 창 크기 조정 테스트)
- [ ] Lighthouse 점수 확인 (Performance 90+ 권장)

---

## 📊 Google Analytics 연결 (선택, 추후)

방문 추적 원할 시 `index.html` 과 `en.html` `<head>` 에 다음 추가:

```html
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXX');
</script>
```

<https://analytics.google.com/> 에서 새 속성 생성 후 측정 ID(G-XXXXXXX) 발급.

---

## 🔗 URL 활용 예시 (아웃리치용)

LinkedIn 메시지·이메일 서명·명함 등에 삽입:

```
🌐 https://11pyo.github.io/AINavManifest/
📧 pk102h@naver.com
📜 IETF draft-han-ai-manifest-00
📝 KR Patent 10-2026-0071716
```

---

*작성 2026-04-23 · Landing Page v1.0 배포 가이드*
