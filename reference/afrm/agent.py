# -*- coding: utf-8 -*-
"""Minimal manifest-aware agent core for version "2.0" manifests.

The agent's own model (not included) drives the task. This module is the part
that touches the manifest:

* ``ManifestSession.discover``   retrieve + validate (Sections 3, 4); on any
  failure the session has no manifest and the agent keeps its baseline.
* ``applicable_traps``           reactive consultation (Section 5.1).
* ``recover``                    runs a trap's recovery, every step through the
  PEP (Section 5.2) and the principal's answer to "ask".
* ``follow_shortcut`` / ``enter_listed_value`` / ``commit_field``
                                 the other manifest-derived actions.

Free-text members are never returned to a caller that feeds a model; the
``model_view`` helper exposes ids, categories and allowedValues only (4.7).

"ask" handling: ``ConsolePrompt`` asks a human on the terminal;
``DenyAsk`` answers every ask with "declined" and is the default, for
automated benchmark runs where no principal is present.
"""
import time
from dataclasses import dataclass, field
from typing import Optional

from .discovery import fetch_manifest_bytes
from .pep import (ALLOW, ASK, DENY, NAV_KEYS, ActionRequest, AuditLog, Decision,
                  PolicyEnforcementPoint, Provenance, is_value_bearing)
from .validator import ManifestRejected, load_for_agent


# ---------------------------------------------------------------- ask handlers

class DenyAsk:
    """Automated runs: no principal is present, so every ask is declined."""
    def __call__(self, req: ActionRequest, d: Decision) -> bool:
        return False


class ApproveAsk:
    """Tests only: stands in for a principal who approves."""
    def __call__(self, req: ActionRequest, d: Decision) -> bool:
        return True


class ConsolePrompt:
    """Interactive runs: shows the principal what would happen and waits for y/N."""
    def __init__(self, input_fn=input, print_fn=print):
        self.input, self.print = input_fn, print_fn

    def __call__(self, req: ActionRequest, d: Decision) -> bool:
        what = req.action if req.action != "key" else f"press {req.step.get('key')}"
        on = f" on {d.element.role or d.element.tag} '{d.element.name}'" if d.element else ""
        to = f" -> {d.target_url}" if d.target_url else ""
        val = f" value {req.value!r}" if req.value is not None else ""
        self.print(f"[AFRM] manifest-derived action from {req.kind} '{req.descriptor_id}'"
                   f" step {req.position}: {what}{val}{on}{to}  ({d.reason})")
        if d.warning:
            self.print(f"[AFRM] warning: {d.warning}")
        return self.input("Allow this action? [y/N] ").strip().lower() in ("y", "yes")


# ---------------------------------------------------------------- session

@dataclass
class RecoveryResult:
    trap_id: str
    status: str                    # completed | abandoned | stopped | assert-failed
    reason: str = ""
    steps_executed: int = 0
    security_control: Optional[str] = None


@dataclass
class ManifestSession:
    """One task on one origin."""
    page: object                               # page adapter (PlaywrightPage or a fake)
    ask: object = field(default_factory=DenyAsk)
    audit: AuditLog = field(default_factory=AuditLog)
    agent_policy: object = None
    standing_approvals: frozenset = frozenset()
    manifest: Optional[dict] = None
    rejected_reason: Optional[str] = None
    pep: Optional[PolicyEnforcementPoint] = None
    task_ended: bool = False

    def discover(self, fetch=fetch_manifest_bytes, now=None) -> bool:
        """At most once per origin per task (Section 3.5)."""
        try:
            raw, url = fetch(self.page.url())
            manifest, _ = load_for_agent(raw, url, now=now)
        except ManifestRejected as e:
            self.manifest, self.rejected_reason = None, str(e)
            return False
        self.use(manifest)
        return True

    def use(self, manifest: dict):
        self.manifest = manifest
        if hasattr(self.page, "bind"):
            self.page.bind(manifest)
        self.pep = PolicyEnforcementPoint(manifest, self.audit, agent_policy=self.agent_policy,
                                          standing_approvals=self.standing_approvals,
                                          provenance=Provenance())

    # -- what the model may see (Section 4.7): no description / label prose
    def model_view(self) -> dict:
        if not self.manifest:
            return {}
        return {
            "traps": [{"trapId": t["trapId"], "category": t["category"]}
                      for t in self.manifest.get("knownTraps", [])],
            "fieldHints": [{"fieldId": h["fieldId"], "allowedValues": h.get("allowedValues", []),
                            "publisherQuoted": True}
                           for h in self.manifest.get("fieldHints", [])],
            "shortcuts": [{"shortcutId": s["shortcutId"]} for s in self.manifest.get("shortcuts", [])],
        }

    # -- reactive consultation
    def applicable_traps(self) -> list:
        if not self.manifest or self.task_ended:
            return []
        out = []
        for trap in self.manifest.get("knownTraps", []):
            if trap["category"] == "native-alert":
                if self.page.condition_holds(trap.get("condition")):
                    out.append(trap)
                continue
            if len(self.page.resolve(trap["locator"])) != 1:
                continue
            if trap.get("condition") is None or self.page.condition_holds(trap["condition"]):
                out.append(trap)
        return out

    def _trap(self, trap_id):
        for t in (self.manifest or {}).get("knownTraps", []):
            if t["trapId"] == trap_id:
                return t
        return None

    def _authorize(self, req: ActionRequest):
        """Returns (decision, principal) where principal is approved/declined/None."""
        d = self.pep.decide(req, self.page)
        if d.outcome == ASK:
            approved = bool(self.ask(req, d))
            return d, "approved" if approved else "declined"
        return d, None

    def _after(self, req, d, principal, executed, alert_text=None) -> Optional[str]:
        """Record step 6, update provenance, and re-check security controls."""
        if d.outcome != DENY:
            self.pep.record(req, d, principal=principal, executed=executed, alert_text=alert_text)
        if executed:
            modifies = req.kind == "value" or (
                req.action == "key" and req.step.get("key") in NAV_KEYS
                and d.element is not None and is_value_bearing(d.element))
            self.pep.provenance.note(req, d.element, modifies)
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

    def recover(self, trap_id: str) -> RecoveryResult:
        trap = self._trap(trap_id)
        if trap is None or self.pep is None or self.task_ended:
            return RecoveryResult(trap_id, "abandoned", "no such trap or no manifest")
        done = 0
        for pos, step in enumerate(trap["recovery"]):
            req = ActionRequest("step", trap_id, pos, trap, step=step)
            d, principal = self._authorize(req)
            if d.stop:
                self._stop_task()
                return RecoveryResult(trap_id, "stopped", d.reason, done, d.reason)
            if d.outcome == DENY or principal == "declined":
                if principal == "declined":
                    self._after(req, d, principal, executed=False)
                # Section 5.2: abandon the descriptor, never try a variant of it.
                return RecoveryResult(trap_id, "abandoned", d.reason if d.outcome == DENY else "principal declined", done)
            alert_text, ok = self._execute(step, d, trap)
            done += 1
            sc = self._after(req, d, principal, executed=True, alert_text=alert_text)
            if sc:
                self._stop_task()
                return RecoveryResult(trap_id, "stopped", sc, done, sc)
            if not ok:
                return RecoveryResult(trap_id, "assert-failed" if step["action"] == "assert" else "abandoned",
                                      f"{step['action']} did not succeed", done)
        return RecoveryResult(trap_id, "completed", "", done)

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
            return None, self.page.navigate_same_origin(d.target_url, self.manifest["origin"])
        return None, self.page.perform(a, d.handle, step.get("key"))

    # -- other manifest-derived actions
    def follow_shortcut(self, shortcut_id: str) -> bool:
        sc = next((s for s in (self.manifest or {}).get("shortcuts", []) if s["shortcutId"] == shortcut_id), None)
        if sc is None or self.task_ended:
            return False
        req = ActionRequest("shortcut", shortcut_id, None, sc)
        d, principal = self._authorize(req)
        if d.stop:
            self._stop_task()
        if d.outcome == DENY or principal == "declined":
            if principal == "declined":
                self._after(req, d, principal, executed=False)
            return False
        ok = self.page.navigate_same_origin(d.target_url, self.manifest["origin"])
        if self._after(req, d, principal, executed=True):
            self._stop_task()
            return False
        return ok

    def enter_listed_value(self, field_id: str, value: str) -> bool:
        """The model proposes a listed value for the field being edited (4.5)."""
        hint = next((h for h in (self.manifest or {}).get("fieldHints", []) if h["fieldId"] == field_id), None)
        if hint is None or self.task_ended:
            return False
        req = ActionRequest("value", field_id, None, hint, value=value)
        d, principal = self._authorize(req)
        if d.stop:
            self._stop_task()
        if d.outcome == DENY or principal == "declined":
            if principal == "declined":
                self._after(req, d, principal, executed=False)
            return False
        ok = self.page.type_into(d.handle, value)
        if self._after(req, d, principal, executed=True):
            self._stop_task()
            return False
        return ok

    def commit_field(self, field_id: str) -> bool:
        hint = next((h for h in (self.manifest or {}).get("fieldHints", []) if h["fieldId"] == field_id), None)
        if hint is None or "commit" not in hint or self.task_ended:
            return False
        req = ActionRequest("commit", field_id, 0, hint, step=hint["commit"])
        d, principal = self._authorize(req)
        if d.stop:
            self._stop_task()
        if d.outcome == DENY or principal == "declined":
            if principal == "declined":
                self._after(req, d, principal, executed=False)
            return False
        ok = self.page.perform("key", d.handle, hint["commit"]["key"])
        if self._after(req, d, principal, executed=True):
            self._stop_task()
            return False
        return ok
