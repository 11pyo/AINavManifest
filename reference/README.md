# AFRM 2.0 reference implementation

Implements version "2.0" of the AI Friction-Recovery Manifest as specified in
`draft-han-ai-manifest-04`: the publisher-side validator and the agent-side
discovery, policy enforcement point (PEP), and audit record.

| Module | Spec | Purpose |
|---|---|---|
| `../ai-friction-manifest.schema.json` | §4 | JSON Schema (2020-12), strict publisher lint |
| `afrm/validator.py` | §3.5, §4 | I-JSON, 262144-octet limit, version, origin binding, expiry, unique ids, navigate/shortcut targets and scope, `when` references; per-descriptor fail-closed load for agents; CLI |
| `afrm/discovery.py` | §3.1, §3.2 | Fetches only `/.well-known/ai-friction-manifest.json` on the page's origin, without credentials, refusing cross-origin redirects |
| `afrm/jcs.py` | §5.5, §6.1 | RFC 8785 canonical JSON, manifest SHA-256 digest, signing payload |
| `afrm/jws.py` | §6.1 | Detached-JWS publisher signatures: ES256 and Ed25519, standard library only; verifies only against keys the agent's own configuration designates for the origin; no result of it reaches the PEP |
| `afrm/jws_sign.py` | §6.1 | Publisher-side signing helper and test kit (not used by an agent) |
| `afrm/pep.py` | §5.2–§5.5 | Non-LLM PEP: the six steps, default outcomes, "activatable element" and "value-bearing control", the Section 5.3 floor of sensitive actions, provenance, audit log |
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

## Verify publisher signatures (Section 6.1)

```python
from afrm.jws import DesignatedKey

keys = {"https://erp.example.com": [DesignatedKey("acme-2026", "ES256", {"kty": "EC", "crv": "P-256", "x": "...", "y": "..."})]}
session = ManifestSession(PlaywrightPage(page), designated_keys=keys)   # from the agent's own configuration
```

If a key is designated for the origin, a manifest without a signature that verifies under it is ignored (baseline
behaviour). With no designated key the `signatures` member is ignored. Keys named by the manifest or by a JWS header
(`jwk`, `jku`, `x5u`, `x5c`) are never used. A verified signature changes no PEP decision.

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

Default outcomes follow -04 §5.2: Enter and Escape ask on every element; click,
navigate and shortcuts ask; a wait over 5000 ms asks; focus, scroll, assert,
dismissAlert, Tab, short waits and arrow/page keys on inert elements are allowed.
There is no standing approval (withdrawn in -04): nothing turns an ask into an allow.

Each ask shows **Target** (the action with its key or wait time; the role and
accessible name of the element actually resolved; the destination's origin and
path), **Source** (a recovery step, a field-hint commit, a shortcut, or the
submission of a form the manifest modified, with the page's origin and path) and
**Effect** (first every sensitive action the PEP determined, then the conventional
effect, then a fixed statement that the page decides the actual effect; a wait has
no such statement). Values the publisher controls are shown as quoted data;
description and label text is appended last, marked `[publisher-written]`. A
warning is added when the text drawn for an activatable element is not part of its
accessible name (the name is an approximation of the accessible-name computation).

Sensitive actions the PEP determines (§5.3 floor): a click or a key step other than
Tab on a submit button; Enter on an element whose form owner could be submitted by
implicit submission; any action on a form recorded as modified by the manifest or
containing a password input. Provenance is recorded before a step runs, so the step
that modifies a form and submits it in one go is already covered.

Click target (§5.1): after any ask and immediately before the click, the adapter
works out which element would receive it at the point it will use (innermost
element, no retargeting across open shadow roots, every frame ancestor must lead to
the frame) and accepts only the resolved element, a non-activatable shadow-including
descendant, or a label of it. The check is repeated for up to 5000 ms, scrolling
only; a failure is a PEP denial (`click-target-declined`), recorded. Key steps on an
element the principal cannot see (transparent, hidden, outside the viewport) are
declined the same way. The click is then sent at the checked point.

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
submit or save it is sensitive, and
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
