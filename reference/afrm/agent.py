# -*- coding: utf-8 -*-
"""Manifest-aware agent core for version "2.0" manifests.

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
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

from .discovery import fetch_manifest_bytes
from .pep import (ASK, DENY, ActionRequest, AuditLog, Decision,
                  PolicyEnforcementPoint, Provenance)
from .validator import ManifestRejected, load_for_agent, origin_of

PUBLISHER = "[publisher-written]"


# ---------------------------------------------------------------- principal side

def describe_ask(req: ActionRequest, d: Decision) -> list:
    """Lines an ask must show (Section 5.2): the action; for element actions the
    resolved element's role and accessible name; the page's origin and path;
    publisher text visibly marked as publisher-written."""
    what = req.action if req.action != "key" else f"press {req.step.get('key')}"
    lines = [f"Action: {what}"]
    if d.element is not None:
        lines.append(f"Element: role={d.element.role or d.element.tag} name={d.element.name!r}")
    if d.document_url:
        p = urlsplit(d.document_url)
        lines.append(f"Page: {origin_of(d.document_url)}{p.path or '/'}")
    if d.target_url:
        lines.append(f"Destination: {d.target_url}")
    for key in ("description", "label"):
        if req.descriptor.get(key):
            lines.append(f"{PUBLISHER} {req.descriptor[key]}")
    if d.warning:
        lines.append(f"Warning: {d.warning}")
    if d.sensitive:
        lines.append("Sensitive: this can submit or save a form changed by manifest-derived actions.")
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
    standing_approvals: frozenset = frozenset()
    manifest: Optional[dict] = None
    rejected_reason: Optional[str] = None
    pep: Optional[PolicyEnforcementPoint] = None
    task_ended: bool = False
    traps: dict = field(default_factory=dict)  # runtime integer id -> trap descriptor

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
        self.traps = {i: t for i, t in enumerate(manifest.get("knownTraps", []), 1)}
        if hasattr(self.page, "bind"):
            self.page.bind(manifest)
        self.pep = PolicyEnforcementPoint(manifest, self.audit, agent_policy=self.agent_policy,
                                          standing_approvals=self.standing_approvals,
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
        """Record step 6, update provenance, and re-check security controls."""
        if d.outcome != DENY:
            self.pep.record(req, d, principal=principal, executed=executed, alert_text=alert_text)
        if executed:
            self.pep.provenance.note(req, d.element, d.document_url)
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
        alert_text, ok = execute(d)
        sc = self._after(req, d, principal, executed=True, alert_text=alert_text)
        if sc:
            self._stop_task()
            return "stopped", sc, True
        return ("ok" if ok else "failed"), "", True

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
