# -*- coding: utf-8 -*-
"""Manifest-aware agent core for version "2.0" manifests (draft-han-ai-manifest-04).

Two surfaces, kept apart as Section 4.7 requires:

* ``ManifestSession`` is the agent's runtime, on the principal's side. It
  retrieves and validates the manifest, evaluates trap conditions against the
  live document, runs recoveries through the PEP, asks the principal, shows
  publisher text (marked as publisher-written) and lists allowedValues and
  shortcuts to the principal only.
* ``ModelInterface`` is the only thing a language model may call. Everything
  it returns is built from closed-vocabulary values (trap categories, action
  names, rendering models), integers the runtime assigns, and booleans. No
  manifest string - description, label, allowedValues, ids, locators, targets
  - and no PEP reason or audit text passes through it.

Principal-facing handlers:
* ask handlers decide one PEP "ask": ``ConsolePrompt`` (terminal y/N) or
  ``DenyAsk`` (default; automated runs have no principal, so every ask is
  declined and recorded as such).
* choosers let the principal pick from a publisher-written list (allowedValues,
  shortcut labels): ``ConsoleChooser`` or ``AbandonChooser`` (default; automated
  runs abandon the entry).
"""
import json
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

from .discovery import fetch_manifest_bytes
from .pep import (ASK, DENY, ActionRequest, AuditLog, Decision,
                  PolicyEnforcementPoint, Provenance)
from .jws import verify_manifest
from .validator import ManifestRejected, load_for_agent, origin_of, parse_i_json

PUBLISHER = "[publisher-written]"


# ---------------------------------------------------------------- principal side

PAGE_DECIDES = ("Effect: the page decides the actual effect, which the agent cannot determine; "
                "it can include a purchase, a deletion, or another sensitive action.")
"""Fixed wording of Section 5.2: it discloses that the effect is unknown and identifies no effect, so a
check of whether an ask 'names the effect' must not count it (adversarial.run_eval.discloses drops it)."""

_SOURCE = {"step": "a recovery step of a known trap", "commit": "the commit of a field hint",
           "shortcut": "a shortcut", "value": "a value the principal chose from a field hint"}
_CONVENTIONAL = {"click": "activating the element", "focus": "moving focus to the element",
                 "scroll": "scrolling", "assert": "checking that the element exists",
                 "navigate": "loading the destination with GET", "dismissAlert": "dismissing an alert",
                 "wait": "letting time pass"}


def q(value) -> str:
    """Publisher-controlled values are shown as quoted data, apart from the agent's own wording."""
    return json.dumps(value, ensure_ascii=False)


def describe_ask(req: ActionRequest, d: Decision) -> list:
    """The lines an ask shows (Section 5.2): Target, Source, Effect. Built from the live page, the structural
    values of the validated descriptor and the PEP's own classification; never from description or label text
    (those are appended afterwards, marked as publisher-written)."""
    action = req.action
    key = (req.step or {}).get("key") if req.step else None
    el = d.element
    if action == "wait":
        target = f"Target: wait {req.step.get('timeoutMs')} ms"
    elif action in ("navigate",) or req.kind == "shortcut":
        url = d.target_url or ""
        target = f"Target: navigate to origin {q(origin_of(url) if url else '')} path {q(urlsplit(url).path if url else '')}"
    elif req.kind == "value":
        target = "Target: enter the value the principal chose into the focused element"
        if el is not None:
            target += f" (role {q(el.role or el.tag)}, accessible name {q(el.name)})"
    else:
        what = f"press {key}" if action == "key" else action
        target = f"Target: {what}"
        if el is not None:
            target += f" on the element with role {q(el.role or el.tag)} and accessible name {q(el.name)}"
    lines = [target]

    src = f"Source: {_SOURCE.get(req.kind, req.kind)} from the manifest of the page's origin"
    if d.document_url:
        p = urlsplit(d.document_url)
        src += f"; page origin {q(origin_of(d.document_url))} path {q(p.path or '/')}"
    if d.form_modified:
        src += "; the submission of a form the manifest modified"
    lines.append(src)

    if d.sensitive:                                     # the sensitive actions the PEP determined come first
        lines += [f"Effect: sensitive action determined by the agent: {e}" for e in d.effects]
    conv = _CONVENTIONAL.get(action)
    if req.kind == "shortcut":
        conv = _CONVENTIONAL["navigate"]
    if action == "key":
        conv = {"Enter": "committing with Enter", "Escape": "dismissing with Escape"}.get(key, f"pressing {key}")
        if el is not None and key not in ("Enter", "Escape"):
            conv += " (this can change the value of a control)"
    if conv:
        lines.append(f"Effect: conventional effect: {conv}")
    if req.kind == "value":
        lines.append("Effect: conventional effect: changing the value of a control")
    if action != "wait":
        lines.append(PAGE_DECIDES)
    if d.warning == "mislabel" and el is not None:
        lines.append(f"Warning: the text drawn for this element ({q(el.rendered_text)}) is not part of its "
                     f"accessible name ({q(el.name)})")
    elif d.warning:
        lines.append(f"Warning: {d.warning}")
    for k in ("description", "label"):
        if req.descriptor.get(k):
            lines.append(f"{PUBLISHER} {req.descriptor[k]}")
    return lines


class DenyAsk:
    """Automated runs: no principal is present, so every ask is declined."""
    def __call__(self, req: ActionRequest, d: Decision) -> bool:
        return False


class ApproveAsk:
    """Tests only: stands in for a principal who approves."""
    def __call__(self, req: ActionRequest, d: Decision) -> bool:
        return True


class ConsolePrompt:
    def __init__(self, input_fn=input, print_fn=print):
        self.input, self.print = input_fn, print_fn

    def __call__(self, req: ActionRequest, d: Decision) -> bool:
        self.print("[AFRM] The agent wants to perform a manifest-derived action:")
        for line in describe_ask(req, d):
            self.print("  " + line)
        return self.input("Allow this action? [y/N] ").strip().lower() in ("y", "yes")


class AbandonChooser:
    """Automated runs: nobody can choose, so the entry is abandoned."""
    def __call__(self, options: list, context: list) -> Optional[int]:
        return None


class ConsoleChooser:
    def __init__(self, input_fn=input, print_fn=print):
        self.input, self.print = input_fn, print_fn

    def __call__(self, options: list, context: list) -> Optional[int]:
        for line in context:
            self.print("  " + line)
        for i, o in enumerate(options, 1):
            self.print(f"  {i}. {PUBLISHER} {o}")
        ans = self.input("Choose a number, or press Enter to abandon: ").strip()
        return int(ans) - 1 if ans.isdigit() and 1 <= int(ans) <= len(options) else None


# ---------------------------------------------------------------- runtime

@dataclass
class RecoveryResult:
    trap_no: int
    status: str                    # completed | abandoned | stopped | assert-failed
    reason: str = ""               # principal/log only
    steps: list = field(default_factory=list)      # [(action, executed)]
    security_control: Optional[str] = None


@dataclass
class ManifestSession:
    """The agent runtime for one task on one origin."""
    page: object                               # page adapter (PlaywrightPage or a fake)
    ask: object = field(default_factory=DenyAsk)
    choose: object = field(default_factory=AbandonChooser)
    audit: AuditLog = field(default_factory=AuditLog)
    agent_policy: object = None
    manifest: Optional[dict] = None
    rejected_reason: Optional[str] = None
    pep: Optional[PolicyEnforcementPoint] = None
    task_ended: bool = False
    traps: dict = field(default_factory=dict)  # runtime integer id -> trap descriptor
    # Section 6.1: public keys the agent's own configuration designates, {origin: [DesignatedKey, ...]}.
    # Never filled from a manifest. Verification only decides whether the manifest is used at all; it
    # grants nothing and the PEP does not see it.
    designated_keys: dict = field(default_factory=dict)
    signed_by: Optional[str] = None            # kid that verified (audit/log only)

    def discover(self, fetch=fetch_manifest_bytes, now=None) -> bool:
        """At most once per origin per task (Section 3.5)."""
        try:
            raw, url = fetch(self.page.url())
            manifest, _ = load_for_agent(raw, url, now=now)
            self.signed_by = None
            keys = self.designated_keys.get(origin_of(url))
            if keys:                       # Section 6.1: a key is designated, so a verifying signature is required
                try:
                    outcome = verify_manifest(parse_i_json(raw), keys)
                except Exception as e:     # fail closed whatever goes wrong
                    raise ManifestRejected(f"signature check failed: {type(e).__name__}")
                if not outcome.verified:
                    raise ManifestRejected("no signature verifies under a key designated for this origin (Section 6.1): "
                                           + "; ".join(outcome.reasons)[:300])
                self.signed_by = outcome.kid
        except ManifestRejected as e:
            self.manifest, self.rejected_reason, self.signed_by = None, str(e), None
            return False
        self.use(manifest)
        return True

    def use(self, manifest: dict):
        self.manifest = manifest
        self.traps = {i: t for i, t in enumerate(manifest.get("knownTraps", []), 1)}
        if hasattr(self.page, "bind"):
            self.page.bind(manifest)
        self.pep = PolicyEnforcementPoint(manifest, self.audit, agent_policy=self.agent_policy,
                                          provenance=Provenance())

    # -- reactive consultation (Section 5.1)
    def active_trap_numbers(self) -> list:
        if not self.manifest or self.task_ended:
            return []
        out = []
        for n, trap in self.traps.items():
            if trap["category"] == "native-alert":
                if self.page.condition_holds(trap.get("condition")):
                    out.append(n)
                continue
            if len(self.page.resolve(trap["locator"])) != 1:
                continue
            if trap.get("condition") is None or self.page.condition_holds(trap["condition"]):
                out.append(n)
        return out

    def _authorize(self, req: ActionRequest):
        """Returns (decision, principal) where principal is approved/declined/None."""
        d = self.pep.decide(req, self.page)
        if d.outcome == ASK:
            return d, ("approved" if self.ask(req, d) else "declined")
        return d, None

    def _after(self, req, d, principal, executed, alert_text=None) -> Optional[str]:
        """Record step 6 and re-check security controls (provenance was noted before execution)."""
        if d.outcome != DENY:
            self.pep.record(req, d, principal=principal, executed=executed, alert_text=alert_text)
        if executed:
            controls = self.page.detect_security_controls()
            if controls:
                stop = Decision(DENY, "security-control:" + ",".join(sorted(controls)), stop=True)
                self.pep.record(req, stop)
                return stop.reason
        return None

    def _stop_task(self):
        # Section 5.4: hand control to the principal or end the task. Without a
        # principal at hand, this agent ends the task; it never retries.
        self.task_ended = True

    def _run(self, req: ActionRequest, execute):
        """One manifest-derived action: authorize, execute, record.
        Returns (status, reason, executed) with status ok|abandoned|stopped|failed."""
        d, principal = self._authorize(req)
        if d.stop:
            self._stop_task()
            return "stopped", d.reason, False
        if d.outcome == DENY or principal == "declined":
            if principal == "declined":
                self._after(req, d, principal, executed=False)
            # Section 5.2: abandon the descriptor, never try a variant of it.
            return "abandoned", d.reason if d.outcome == DENY else "principal declined", False
        # Section 2: the form this step modifies is recorded BEFORE the step runs.
        self.pep.provenance.note(req, d.element, d.document_url)
        bad = self._target_check(req, d)
        if bad:                                          # Section 5.1: treated as denied by the PEP, recorded (5.5)
            self.pep.record(req, Decision(DENY, bad, element=d.element, document_url=d.document_url),
                            principal=principal, executed=False)
            return "abandoned", bad, False
        alert_text, ok = execute(d)
        sc = self._after(req, d, principal, executed=True, alert_text=alert_text)
        if sc:
            self._stop_task()
            return "stopped", sc, True
        return ("ok" if ok else "failed"), "", True

    def _target_check(self, req: ActionRequest, d: Decision) -> Optional[str]:
        """Section 5.1, immediately before the input and after any ask: a click must reach the resolved element
        (or an allowed descendant or label); a click or key step on an element the principal cannot see is
        declined. The adapter repeats the check for up to 5000 ms, scrolling only. None = proceed."""
        if d.handle is None or req.action not in ("click", "key"):
            return None
        check = getattr(self.page, "verify_click_target" if req.action == "click" else "verify_key_target", None)
        if check is None:
            return None
        ok, why = check(d.handle)
        return None if ok else f"{'click' if req.action == 'click' else 'key'}-target-declined: {why}"

    def recover(self, trap_no: int) -> RecoveryResult:
        trap = self.traps.get(trap_no)
        if trap is None or self.pep is None or self.task_ended:
            return RecoveryResult(trap_no, "abandoned", "no such trap or no manifest")
        res = RecoveryResult(trap_no, "completed")
        for pos, step in enumerate(trap["recovery"]):
            req = ActionRequest("step", trap["trapId"], pos, trap, step=step)
            status, reason, executed = self._run(req, lambda d, s=step: self._execute(s, d, trap))
            res.steps.append((step["action"], executed))
            if status == "ok":
                continue
            res.reason = reason
            if status == "stopped":
                res.status, res.security_control = "stopped", reason
            elif status == "failed":
                res.status = "assert-failed" if step["action"] == "assert" else "abandoned"
                res.reason = f"{step['action']} did not succeed"
            else:
                res.status = "abandoned"
            return res
        return res

    def _execute(self, step, d: Decision, trap):
        a = step["action"]
        if a == "wait":
            return None, self.page.wait_until_clear(trap.get("condition"), step["timeoutMs"])
        if a == "assert":
            return None, True                    # resolution to exactly one element succeeded
        if a == "dismissAlert":
            text = self.page.dismiss_alert()
            return text, text is not None
        if a == "navigate":
            return None, self.page.navigate_same_origin(d.target_url, self.manifest["origin"], self.manifest.get("scope"))
        return None, self.page.perform(a, d.handle, step.get("key"))

    # -- field hints (Section 4.5)
    def _applicable_hints(self) -> list:
        out = []
        for h in (self.manifest or {}).get("fieldHints", []):
            m = self.page.resolve_focused_field(h["locator"])
            if len(m) == 1 and self.page.when_holds(h.get("when"), self.manifest, m[0][1]):
                out.append(h)
        return out

    def propose_value(self, value: str) -> dict:
        """The model proposes a value for the focused field. Returns booleans only."""
        if not self.manifest or self.task_ended:
            return {"applicable": False, "match": False, "principalChose": False}
        hints = [h for h in self._applicable_hints() if "allowedValues" in h]
        if not hints:
            return {"applicable": False, "match": False, "principalChose": False}
        if any([self.pep.check_value(h, value) for h in hints]):
            # The model enters its own value from the task; that is not manifest-derived.
            return {"applicable": True, "match": True, "principalChose": False}
        hint = hints[0]
        context = ["The value proposed for this field is not one the site lists."]
        if hint.get("description"):
            context.append(f"{PUBLISHER} {hint['description']}")
        idx = self.choose(list(hint["allowedValues"]), context)
        if idx is None:
            return {"applicable": True, "match": False, "principalChose": False}
        chosen = hint["allowedValues"][idx]
        req = ActionRequest("value", hint["fieldId"], None, hint, value=chosen)
        status, _, _ = self._run(req, lambda d: (None, self.page.type_into(d.handle, chosen)))
        return {"applicable": True, "match": False, "principalChose": status == "ok"}

    def commit_focused_field(self) -> bool:
        hint = next((h for h in self._applicable_hints() if "commit" in h), None) if self.manifest else None
        if hint is None or self.task_ended:
            return False
        req = ActionRequest("commit", hint["fieldId"], 0, hint, step=hint["commit"])
        status, _, _ = self._run(req, lambda d: (None, self.page.perform("key", d.handle, hint["commit"]["key"])))
        return status == "ok"

    # -- shortcuts (Section 4.6): offered to the principal only
    def offer_shortcuts(self) -> bool:
        shortcuts = (self.manifest or {}).get("shortcuts", [])
        if not shortcuts or self.task_ended:
            return False
        idx = self.choose([s["label"] for s in shortcuts], ["Pages this site lists for direct navigation:"])
        if idx is None:
            return False
        sc = shortcuts[idx]
        req = ActionRequest("shortcut", sc["shortcutId"], None, sc)
        status, _, _ = self._run(req, lambda d: (None, self.page.navigate_same_origin(
            d.target_url, self.manifest["origin"], self.manifest.get("scope"))))
        return status == "ok"

    def submission_is_sensitive(self, element, document_url) -> bool:
        """For the agent's own submit/save: True if the manifest modified that form."""
        return self.pep is not None and self.pep.submission_is_sensitive(element, document_url)


# ---------------------------------------------------------------- model side

class ModelInterface:
    """The only manifest-related surface a language model may use (Section 4.7)."""

    def __init__(self, session: ManifestSession):
        self._s = session

    def describe(self) -> dict:
        m = self._s.manifest
        if not m:
            return {"manifest": False}
        rm = (m.get("frameworkHints") or {}).get("renderingModel")
        return {"manifest": True,
                "renderingModel": rm if rm in ("server-rendered", "client-rendered", "hybrid", "canvas") else None,
                "traps": [{"trap": n, "category": t["category"]} for n, t in self._s.traps.items()]}

    def active_traps(self) -> list:
        return [{"trap": n, "category": self._s.traps[n]["category"], "recoveryAvailable": True}
                for n in self._s.active_trap_numbers()]

    def run_recovery(self, trap: int) -> dict:
        if not isinstance(trap, int) or isinstance(trap, bool):
            return {"trap": None, "completed": False, "stopped": False, "steps": []}
        r = self._s.recover(trap)
        return {"trap": trap, "completed": r.status == "completed", "stopped": r.status == "stopped",
                "steps": [{"action": a, "executed": bool(e)} for a, e in r.steps]}

    def propose_value(self, value: str) -> dict:
        return self._s.propose_value(value)

    def commit_field(self) -> dict:
        return {"executed": self._s.commit_focused_field()}

    def audit(self) -> list:
        """Audit records reduced to permitted items: runtime trap number, step
        position, action name, executed flag, match result."""
        by_id = {t["trapId"]: n for n, t in self._s.traps.items()}
        vocab = {"click", "focus", "key", "scroll", "wait", "assert", "navigate", "dismissAlert"}
        out = []
        for r in self._s.audit.records:
            kind, _, did = r.descriptor.partition(":")
            action = r.action.split(":")[0]
            out.append({"trap": by_id.get(did) if kind == "step" else None,
                        "step": r.position if isinstance(r.position, int) else None,
                        "action": action if action in vocab else None,
                        "executed": bool(r.executed),
                        "match": r.match if isinstance(r.match, bool) else None})
        return out
