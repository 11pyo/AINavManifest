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
from afrm.agent import ManifestSession, ModelInterface, ConsolePrompt, ConsoleChooser
from afrm.playwright_page import PlaywrightPage

session = ManifestSession(PlaywrightPage(page), ask=ConsolePrompt(), choose=ConsoleChooser())
if session.discover():                     # otherwise: baseline behaviour
    model_tools = ModelInterface(session)  # the only surface the model may call
    for t in model_tools.active_traps():   # [{"trap": 1, "category": "commit-gesture", ...}]
        model_tools.run_recovery(t["trap"])
```

No string from a manifest reaches the model (§4.7). `ModelInterface` returns
only closed-vocabulary values (trap category, action name, rendering model),
integers the runtime assigns to traps, and booleans:

| Model call | Returns |
|---|---|
| `describe()` | rendering model, `[{"trap": n, "category": ...}]` |
| `active_traps()` | traps whose condition holds now, by number |
| `run_recovery(n)` | `completed`, `stopped`, per-step `{action, executed}` |
| `propose_value(v)` | `applicable`, `match`, `principalChose` (§4.5) |
| `commit_field()` | `executed` |
| `audit()` | trap number, step, action, executed, match |

PEP reasons, publisher text, allowedValues, ids, locators and targets stay on
the runtime side. When a proposed value does not match, the listed values go to
the principal (`ConsoleChooser`, marked `[publisher-written]`); a chosen value is
typed by the runtime (PEP default allow) and its form counts as modified.
Shortcuts are offered only to the principal (`session.offer_shortcuts()`).

## "ask"

Default outcomes follow the final -03 §5.2: Enter and Escape ask on every
element; click, navigate and shortcuts ask; a wait over 5000 ms asks; focus,
scroll, assert, dismissAlert, Tab, short waits and arrow/page keys on inert
elements are allowed. A standing approval, for an origin the principal names,
covers Enter only (never Escape, activatable elements, value-bearing arrows,
click, navigate, shortcuts, values, long waits, or sensitive actions).

Each ask shows the action, the role and accessible name of the element actually
resolved, the page's origin and path, and publisher text marked
`[publisher-written]`.

* `DenyAsk` + `AbandonChooser` (defaults): automated benchmark runs have no
  principal, so every ask is declined and every list choice is abandoned; the
  audit log records `outcome=ask, principal=declined`.
* `ConsolePrompt` + `ConsoleChooser`: interactive y/N and numbered choice.

A declined or denied step abandons the whole descriptor; the agent never tries
a variant of it. A detected security control stops the recovery and ends the
task (§5.4).

"Form modified by the manifest" (§2) is the form owner of an element a click or
non-Tab key step targeted, or into which a listed value was entered, or the
whole document when there is no form owner. Any later click or Enter that can
submit or save it is sensitive (no standing approval), and
`session.submission_is_sensitive(element, url)` tells the agent's own code the same.

## Redirects

* Discovery follows no redirect at all; a 3xx means no manifest. The old
  `/.well-known/ai-manifest.json` is ignored entirely.
* For navigate steps and shortcuts every hop is checked before it is followed
  (Playwright route): a different origin, a query or fragment, or a path
  outside scope aborts the navigation. Because Chromium does not re-route a
  redirect that a route fulfils, the adapter aborts each 3xx and issues the
  next hop as a new guarded navigation.

## Tests

```bash
cd github_repo/reference
python -m pytest tests -q
```

* `test_validator.py` checks the Appendix A example, an RFC 8785 test vector,
  I-JSON rejections, origin/expiry/version rejection, and fail-closed descriptors.
* `test_pep.py` exercises the PEP and runtime on a fake page: ask on click and
  on Enter (including on a gridcell), Escape and long waits, stop on HTTP
  403/429 and confirm(), standing approval limits, a no-form SPA whose save
  becomes sensitive after a manifest-derived Enter, field-hint match/choice
  flow, shortcuts offered to the principal, and that injected publisher strings
  (allowedValues, descriptions, ids, labels) never appear in model-facing output.
* `test_playwright_integration.py` runs in Chromium against a local server:
  Enter and click ask, the 403 that follows stops the recovery, confirm()
  stops, an alert is dismissed and recorded, same-origin redirects that add a
  query or leave scope (also on the second hop) are aborted, discovery refuses
  a 302, and `when` resolves within the edited row.

## Approximations

* A locator with `name` but no `role` matches by label or exact text.
* `column` compares the header cell at the same index (aria-colindex if
  present, colspan ignored).
* Security-control detection is best effort (§5.4). The default `ask` outcomes
  are the backstop for controls it misses.
* `when`: if the other field's locator matches several elements, the one in
  the same `tr`/`role=row` as the edited element is used; none or several makes
  the entry unsatisfied. Values compare as text (a select's selected option text).
* Signatures (§6.1) and reputation services (§6.2) are not implemented. No key
  is designated for any origin, so signatures are ignored, as §6.1 specifies.
