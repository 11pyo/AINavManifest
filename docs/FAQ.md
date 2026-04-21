# Frequently Asked Questions

## About the Protocol

### Q. How is this different from `robots.txt`, `llms.txt`, `agents.txt`, `ai-plugin.json`?

Those cover **declaration** (crawling permission, documentation pointer, capability metadata, API endpoint). AI Manifest covers **step-by-step UI operation** — which element to click, fill, select, in what order — for a specific task. It's the only one of these that replaces DOM analysis during execution.

### Q. Is this only for Claude / MCP?

No. MCP, Playwright, Puppeteer, Selenium WebDriver, or any browser-automation tool with CSS selector support can implement it. The reference agent uses plain HTTP + CSS selectors — no MCP-specific hooks.

### Q. What if the page changes after the manifest was published?

Two answers:
1. The publisher updates the manifest — it's their canonical declaration, so they take responsibility.
2. The agent falls back to conventional DOM inference if the trust lookup returns `unknown` or if a step fails.

### Q. What prevents a malicious site from embedding a harmful manifest?

The **Central Trust Registry** (Section 5 of the IETF draft). Manifests are pre-registered by their publishers; agents verify the SHA-256 hash before executing. Registries perform **static analysis** on submitted manifests to detect common injection patterns (cross-origin form submit, disallowed actions, etc.).

## About the Implementation

### Q. How do I add AI Manifest to my website?

Pick one of three embedding methods:

**Easiest — Well-Known URI**: Upload `/.well-known/ai-manifest.json` containing your task definitions. Add `<meta name="ai-manifest" content="/.well-known/ai-manifest.json">` to your `<head>`.

**Inline — Hidden DOM**: Add a `<div id="ai-manifest" style="display:none" data-manifest='...'></div>`.

**Header — HTTP response**: Add `X-AI-Manifest: url=/path; hash=sha256:...` to relevant response headers.

See the [examples folder](../examples/) for working manifests.

### Q. How do I write my first manifest?

Minimal skeleton:

```json
{
  "version": "1.0",
  "publisher": "your-domain.com",
  "manifestId": "task-name",
  "registry_url": "https://registry.aimanifest.io/verify",
  "task": {
    "id": "submit_form",
    "steps": [
      { "step": 1, "action": "fill", "selector": "#name", "description": "Enter user's name" },
      { "step": 2, "action": "click", "selector": "#submit" }
    ]
  }
}
```

Validate against [`ai-manifest.schema.json`](../ai-manifest.schema.json) before publishing.

### Q. Where is the trust registry deployed?

The production registry at `registry.aimanifest.io` is not yet live. For now, run the reference registry locally:

```bash
cd validation/registry && python registry.py
```

Community-operated registries are welcome — file an issue if you plan to host one.

### Q. How do I reproduce the -81.9% / 100% benchmark?

```bash
cd validation
pip install -r requirements.txt
python benchmark/run_benchmark.py --repeats 30
python benchmark/analyze.py
```

Results land in `validation/results/`. tiktoken (`cl100k_base`) is the reference encoding.

## About Licensing

### Q. Can I use this commercially?

Yes. MIT License for code and schema. Patent claims (Korean Patent Application 10-2026-0071716) are offered under FRAND terms — see [`docs/FRAND.md`](FRAND.md). In practice, good-faith implementers of the published specification will not face enforcement.

### Q. Do I need a patent license to implement the protocol?

The FRAND commitment covers implementers. If you're building an agent or a website that embeds manifests per this specification, no additional action is needed beyond complying with MIT terms for any code you reuse from this repository.

### Q. What if I want to contribute a patentable improvement?

Disclose it in the PR description. We'll discuss whether it fits under the existing FRAND umbrella or needs a separate grant.

## About Standardization

### Q. Why IETF and not W3C?

The protocol sits on top of `/.well-known/` URIs (RFC 8615, IETF), uses JSON (RFC 8259, IETF), and cares deeply about transport-level and cryptographic details. IETF is the natural home. A parallel W3C note explaining the DOM-facing aspects is plausible later.

### Q. Can I join the IETF effort?

Yes. The draft is currently an Independent Submission (`draft-han-ai-manifest-00`). Comments can be filed on GitHub Issues or by replying to any IETF mailing-list thread where this is raised. If the draft gathers momentum, a working group adoption request is the next step.

### Q. What's the roadmap from here?

1. Gather implementer feedback (Q2-Q3 2026)
2. Revise draft to `-01`, `-02` based on input
3. Register a WG BoF or request adoption in an existing WG (e.g. `httpbis`, `alto`) in Q4 2026
4. Aim for RFC status in 2028

Contributions at any stage accelerate the timeline.

## About the Project

### Q. Who is behind this?

Won-pyo Han — solo inventor and maintainer. Contact: <pk102h@naver.com>.

### Q. How can I stay updated?

- Watch this repo on GitHub
- Subscribe to the [IETF Datatracker page](https://datatracker.ietf.org/doc/draft-han-ai-manifest/)
- Follow the author for major announcements

### Q. I have a question not answered here.

Open a [GitHub Issue](https://github.com/11pyo/AINavManifest/issues) with the `question` label, or email <pk102h@naver.com>. Good questions get added to this FAQ.
