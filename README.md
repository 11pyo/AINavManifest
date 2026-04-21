# AI Manifest

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Patent: FRAND](https://img.shields.io/badge/Patent-FRAND-green.svg)](docs/FRAND.md)
[![IETF Draft](https://img.shields.io/badge/IETF-draft--han--ai--manifest--00-blue)](https://datatracker.ietf.org/doc/draft-han-ai-manifest/)
[![Korean Patent](https://img.shields.io/badge/KIPO-10--2026--0071716-red)](https://github.com/11pyo/AINavManifest/blob/main/docs/FRAND.md)
[![Tokens](https://img.shields.io/badge/Input_tokens-−81.9%25-brightgreen)](validation/results/summary.json)
[![Success](https://img.shields.io/badge/Task_success-20%25→100%25-brightgreen)](validation/results/summary.json)

> **Embedded workflow instructions for AI agents — enabling efficient web UI automation without repeated DOM analysis.**

Korean Patent Application No. **10-2026-0071716** (filed 2026-04-21) · IETF Internet-Draft **`draft-han-ai-manifest-00`** · MIT License · FRAND terms for patent claims

---

## Why

LLM-based AI agents (Claude Code, MCP clients, Puppeteer/Playwright-driven tools) currently parse entire DOMs or screenshots on every page, wasting tokens and failing on complex multi-step transactions. Website operators have no standardized way to declare "AI-Ready" workflows.

**AI Manifest** is a JSON specification that websites embed to tell AI agents exactly how to operate their UIs — step by step, with CSS selectors and actions.

```
Without manifest:  AI analyzes full DOM/screenshots repeatedly → high token cost, frequent failures
With manifest:     AI reads instructions → executes directly via CSS selectors → done
```

---

## Empirical Results

Benchmark: ERP-style 2-step order entry transaction, n=30 iterations, tiktoken(cl100k_base).

| Metric | Baseline (DOM analysis) | AI Manifest | Improvement |
|---|:---:|:---:|:---:|
| Mean input tokens | 1887.6 | **341.0** | **−81.9%** |
| Task success rate | 20.0% (6/30) | **100.0%** (30/30) | **+80.0 %p** |
| Mean LLM calls | 1.4 | 1.0 | −0.4 |

Reproducible benchmark code lives in [`validation/`](validation/).

---

## Protocol Overview

Three embedding methods (sites can combine):

### Method A — Well-Known URI
```html
<meta name="ai-manifest" content="/.well-known/ai-manifest.json">
```
Serve the JSON at `/.well-known/ai-manifest.json` per IETF RFC 8615.

### Method B — Hidden DOM Element
```html
<div id="ai-manifest" style="display:none" aria-hidden="true"
     data-manifest='{"version":"1.0", ...}'></div>
```

### Method C — HTTP Response Header
```
X-AI-Manifest: url=/.well-known/ai-manifest.json; hash=sha256:...
```

Agents fetch the manifest, compute its SHA-256 hash over a canonical (key-sorted, UTF-8) byte sequence, and verify against a central trust registry before executing `steps[]` sequentially.

---

## Trust & Security

A **Central Trust Registry** prevents malicious sites from injecting harmful instructions into AI agents (prompt injection defense):

```
AI Agent → detects manifest → queries registry.aimanifest.io/verify
                                      ↓
                          Trusted  ✅ → Execute steps
                          Unknown  ⚠️ → Warn user, fall back to DOM analysis
                          Blacklist ❌ → Refuse and alert user
```

The registry also performs **static analysis** of submitted manifests — detecting suspicious selector patterns (iframe injection, external form submissions), disallowed actions, and untrusted value sources — automatically blacklisting risky manifests.

---

## Schema

See [`ai-manifest.schema.json`](./ai-manifest.schema.json) for the full JSON Schema (Draft-07).

### Supported Actions

| Action | Description |
|--------|-------------|
| `click` | Click a button or link |
| `fill` | Type text into an input field |
| `select` | Choose an option from a dropdown |
| `upload` | Upload a file to a file input |
| `wait` | Wait for a condition or timeout |
| `scroll` | Scroll to an element |
| `navigate` | Go to a URL |
| `assert` | Verify a condition before proceeding |
| `hover` | Hover over an element |

---

## Examples

| Example | File |
|---------|------|
| Academic manuscript submission (ScholarOne-like) | [`examples/academic-submission.json`](./examples/academic-submission.json) |
| SAP Material Master creation (MM01) | [`examples/sap-material-create.json`](./examples/sap-material-create.json) |

---

## How This Differs from Related Standards

| Standard | Purpose | Covers step-by-step UI? |
|----------|---------|:-----------------------:|
| `robots.txt` | Crawling permissions | ❌ |
| `llms.txt` | LLM-friendly documentation | ❌ |
| `agents.txt` / `agent-permissions.json` | Agent capability & permission declarations | ❌ |
| OpenAI `ai-plugin.json` | API integration manifest | ❌ |
| **`ai-manifest`** | **Step-by-step UI workflow instructions with trust verification** | **✅** |

---

## Patent Notice

This protocol is subject to:

**Korean Patent Application No. 10-2026-0071716** · Filed 2026-04-21 · Applicant: Won-pyo Han

- **Code** in this repository (including the JSON Schema, validation harness, and examples) is licensed under the **MIT License**.
- **Patent claims** are offered under **FRAND (Fair, Reasonable, and Non-Discriminatory) terms** to promote adoption as an open standard. See [`docs/FRAND.md`](docs/FRAND.md) for the full declaration.
- Early publication of the Korean application has been requested (public publication expected within ~2–3 months of filing).

International counterparts (PCT, direct national filings) may be pursued within 12 months of the Korean priority date (until 2027-04-21).

---

## Roadmap

- [x] v0.1 schema and reference implementation
- [ ] IETF Internet-Draft: `draft-han-ai-manifest-00`
- [ ] SDK: auto-generate manifests from existing web UIs (Python, Node.js)
- [ ] Central Trust Registry deployment: `registry.aimanifest.io`
- [ ] AI-Certified badge program for compliant websites
- [ ] Collaboration with W3C / IETF standardization tracks

---

## Contributing

Issues, schema proposals, and implementation PRs welcome. Please read [`docs/FRAND.md`](docs/FRAND.md) before contributing patentable improvements.

---

## License

- Code & schema: **MIT License** (see [`LICENSE`](LICENSE))
- Patent claims: **FRAND terms** (see [`docs/FRAND.md`](docs/FRAND.md))

---

## Author

**Won-pyo Han** · <pk102h@naver.com>
