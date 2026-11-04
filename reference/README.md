# AFRM 2.0 reference implementation

Implements version "2.0" of the AI Friction-Recovery Manifest as specified in
`draft-han-ai-manifest-03`: the publisher-side validator and the agent-side
discovery, policy enforcement point (PEP), and audit record.

| Module | Spec | Purpose |
|---|---|---|
| `../ai-friction-manifest.schema.json` | §4 | JSON Schema (2020-12), strict publisher lint |
| `afrm/validator.py` | §3.5, §4 | I-JSON, 262144-octet limit, version, origin binding, expiry, unique ids, navigate/shortcut targets and scope, `when` references; per-descriptor fail-closed load for agents; CLI |
| `afrm/discovery.py` | §3.1, §3.2 | Fetches only `/.well-known/ai-friction-manifest.json` on the page's origin, without credentials, refusing cross-origin redirects |
| `afrm/jcs.py` | §5.5, §6.1 | RFC 8785 canonical JSON, manifest SHA-256 digest, signing payload |
| `afrm/pep.py` | §5.2–§5.5 | Non-LLM PEP: the six steps, default outcomes, "activatable element" and "value-bearing control", standing approvals, provenance, audit log |
| `afrm/agent.py` | §5.1, §5.2 | `ManifestSession`: discover, find applicable traps, run a recovery, follow a shortcut, enter a listed value, commit a field — each through the PEP |
| `afrm/playwright_page.py` | §4.2, §5.1, §5.4 | Live-document locator resolution (same-origin, in-scope frames only), trusted input through Playwright, security-control detection |

## Validate a manifest

```bash
cd github_repo/reference
python -m afrm.validator path/to/ai-friction-manifest.json --origin https://erp.example.com
python -m afrm.validator https://erp.example.com/            # discover and validate live
```

Exit status is non-zero on any error. Plain HTTP is accepted only for loopback
origins (`localhost`, `127.0.0.1`, `[::1]`), with a warning, so that the local
demos can be validated; §3.1 requires HTTPS.

## Use the agent core

```python
from afrm.agent import ManifestSession, DenyAsk, ConsolePrompt
from afrm.playwright_page import PlaywrightPage

session = ManifestSession(PlaywrightPage(page), ask=ConsolePrompt())
if session.discover():                     # otherwise: baseline behaviour
    for trap in session.applicable_traps():
        result = session.recover(trap["trapId"])
```

`session.model_view()` is the only manifest content intended for a language
model: identifiers, categories, and allowedValues. `description` and `label`
are never included (§4.7).

## "ask"

The PEP returns `ask` for clicks, Escape, navigation, shortcuts, listed values,
Enter or arrow keys on activatable elements or value-bearing controls, and
every sensitive action. The session hands each ask to an ask handler:

* `DenyAsk` (default): answers every ask with "declined". Automated benchmark
  runs have no principal, so nothing that needs confirmation is executed, and
  the audit log shows `outcome=ask, principal=declined`.
* `ConsolePrompt`: shows the action, element, and reason on the terminal and
  waits for `y/N`.

A declined or denied step abandons the whole descriptor; the agent never tries
a variant of it (§5.2). A detected security control stops the recovery and ends
the task (§5.4).

## Tests

```bash
cd github_repo/reference
python -m pytest tests -q
```

* `test_validator.py` checks the Appendix A example, an RFC 8785 test vector,
  I-JSON rejections, origin/expiry/version rejection, and fail-closed descriptors.
* `test_pep.py` exercises the PEP on a fake page: ask on click, stop on HTTP
  403/429 and on confirm(), the Enter/arrow/Tab/Escape rules, standing approval
  limits, sensitive form submission, and audit contents.
* `test_playwright_integration.py` runs the same path in Chromium against a
  local server. A manifest-derived Enter is allowed and arrives as a trusted
  event; the click that follows is asked; the 403 it leads to stops the
  recovery; an alert is dismissed and its text recorded; confirm() stops.

## Approximations

* A locator with `name` but no `role` matches by label or exact text.
* `column` compares the header cell at the same index (aria-colindex if
  present, colspan ignored).
* Security-control detection is best effort (§5.4). The default `ask` outcomes
  are the backstop for controls it misses.
* `when` requires the referenced field hint's locator to resolve to exactly
  one element, and compares its value as text (a select's selected option text).
* Signatures (§6.1) and reputation services (§6.2) are not implemented. No key
  is designated for any origin, so signatures are ignored, as §6.1 specifies.
