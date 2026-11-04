# -*- coding: utf-8 -*-
"""Policy Enforcement Point (draft-han-ai-manifest-03 Sections 5.2-5.5).

Deterministic code only: no language model takes part in a decision, and no
decision reads a free-text member (description, label).

Every manifest-derived action is described by an ``ActionRequest``. The PEP
runs the six steps of Section 5.2 in order:
  1. validate the descriptor            -> deny  "invalid-descriptor"
  2. re-resolve the locator / target    -> deny  "locator-*" / "target-*"
  3. detected security control          -> deny + stop  "security-control:*"
  4. default outcome (table below)
  5. agent policy (stricter only) and standing approval (key steps only)
  6. audit record
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import urlsplit

from .jcs import manifest_digest
from .validator import _DESC_VALIDATORS, in_scope, origin_of, resolve_target

ALLOW, ASK, DENY = "allow", "ask", "deny"
_RANK = {ALLOW: 0, ASK: 1, DENY: 2}

# Section 5.2 definitions -------------------------------------------------------
ACTIVATABLE_INPUT_TYPES = {"submit", "image", "reset", "button", "checkbox", "radio"}
ACTIVATABLE_ROLES = {"button", "link", "menuitem", "menuitemcheckbox", "menuitemradio",
                     "option", "tab", "switch", "checkbox", "radio"}
VALUE_BEARING_TAGS = {"select", "input", "textarea"}
VALUE_BEARING_ROLES = {"combobox", "listbox", "radiogroup", "slider", "spinbutton",
                       "textbox", "tablist"}
ALWAYS_ALLOWED_ACTIONS = {"focus", "scroll", "wait", "assert", "dismissAlert"}
NAV_KEYS = {"ArrowUp", "ArrowDown", "PageUp", "PageDown"}
LOCATOR_ACTIONS = {"click", "focus", "key", "scroll", "assert"}


@dataclass(frozen=True)
class Ancestor:
    tag: str
    role: Optional[str] = None
    editing_host: bool = False


@dataclass(frozen=True)
class ElementInfo:
    """Facts about one live element, gathered by the page adapter."""
    tag: str                                  # lower-case tag name
    role: Optional[str] = None                # explicit role, else implicit role
    input_type: Optional[str] = None
    has_href: bool = False
    form_id: Optional[str] = None             # identity of the form owner, if any
    form_has_credentials: bool = False        # form contains a password field
    editing_host: bool = False
    ancestors: tuple = ()                     # tuple[Ancestor], nearest first
    name: str = ""                            # accessible name (for the principal only)
    rendered: bool = True


def is_activatable(el: ElementInfo) -> bool:
    return (el.tag == "button"
            or (el.tag in ("a", "area") and el.has_href)
            or el.tag == "summary"
            or (el.tag == "input" and (el.input_type or "text") in ACTIVATABLE_INPUT_TYPES)
            or el.role in ACTIVATABLE_ROLES)


def _value_bearing_self(tag, role, editing_host) -> bool:
    return tag in VALUE_BEARING_TAGS or editing_host or role in VALUE_BEARING_ROLES


def is_value_bearing(el: ElementInfo) -> bool:
    if _value_bearing_self(el.tag, el.role, el.editing_host):
        return True
    return any(_value_bearing_self(a.tag, a.role, a.editing_host) for a in el.ancestors)


def is_form_input(el: ElementInfo) -> bool:
    """'an input element with a form owner' (Enter rule)."""
    return el.tag == "input" and el.form_id is not None


# Requests, decisions, records --------------------------------------------------

@dataclass
class ActionRequest:
    kind: str                       # "step" | "commit" | "shortcut" | "value"
    descriptor_id: str              # trapId / fieldId / shortcutId
    position: Optional[int]         # zero-based step position (Section 4.3); 0 for commit
    descriptor: dict                # the trap / field hint / shortcut as published
    step: Optional[dict] = None     # the step object (kind step/commit)
    value: Optional[str] = None     # kind value: the listed value to enter

    @property
    def action(self) -> str:
        if self.kind in ("step", "commit"):
            return (self.step or {}).get("action", "?")
        return self.kind


@dataclass
class Decision:
    outcome: str                    # allow | ask | deny
    reason: str
    stop: bool = False              # security control: stop the recovery (Section 5.4)
    standing_eligible: bool = False
    sensitive: bool = False
    warning: Optional[str] = None   # must be shown to the principal (form-submitting Enter)
    element: Optional[ElementInfo] = None
    handle: object = None           # adapter handle of the resolved element
    target_url: Optional[str] = None


@dataclass
class AuditRecord:
    time: str
    origin: str
    manifest_digest: str
    descriptor: str                 # "<kind>:<id>"
    position: Optional[int]
    action: str
    outcome: str
    reason: str
    principal: Optional[str] = None     # "approved" | "declined" | None
    executed: bool = False
    alert_text: Optional[str] = None
    stop: bool = False


class AuditLog:
    """Section 5.5. Kept in memory and, if a path is given, appended as JSON Lines
    so that the principal can read it."""

    def __init__(self, path: Optional[str] = None):
        self.records = []
        self.path = path

    def append(self, rec: AuditRecord):
        self.records.append(rec)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")


class Provenance:
    """Tracks what manifest-derived actions changed (Section 2, 'Manifest-Derived
    Action'), so that a later submission of such a form is itself treated as
    manifest-derived and sensitive (Section 5.3)."""

    def __init__(self):
        self.modified_forms = set()
        self.actions = []           # (descriptor, position, action)

    def note(self, req: ActionRequest, el: Optional[ElementInfo], modifies: bool):
        self.actions.append((f"{req.kind}:{req.descriptor_id}", req.position, req.action))
        if modifies and el is not None and el.form_id is not None:
            self.modified_forms.add(el.form_id)

    def form_modified(self, form_id: Optional[str]) -> bool:
        return form_id is not None and form_id in self.modified_forms


# The PEP -----------------------------------------------------------------------

AgentPolicy = Callable[[ActionRequest, Decision], str]


class PolicyEnforcementPoint:
    def __init__(self, manifest: dict, audit: AuditLog, *,
                 agent_policy: Optional[AgentPolicy] = None,
                 standing_approvals: frozenset = frozenset(),
                 provenance: Optional[Provenance] = None,
                 clock=lambda: datetime.now(timezone.utc)):
        self.manifest = manifest
        self.origin = manifest["origin"]
        self.scope = manifest.get("scope")
        self.digest = manifest_digest(manifest)
        self.audit = audit
        self.agent_policy = agent_policy
        # Origins the principal named for a standing approval of key steps.
        self.standing_approvals = frozenset(standing_approvals)
        self.provenance = provenance or Provenance()
        self.clock = clock

    # -- step 1
    def _validate(self, req: ActionRequest) -> Optional[str]:
        kind = {"step": "trap", "commit": "fieldHint", "shortcut": "shortcut", "value": "fieldHint"}.get(req.kind)
        if kind is None:
            return "unknown request kind"
        if any(True for _ in _DESC_VALIDATORS[kind].iter_errors(req.descriptor)):
            return "descriptor fails Section 4"
        if req.kind == "step":
            rec = req.descriptor.get("recovery") or []
            if req.position is None or not (0 <= req.position < len(rec)) or rec[req.position] != req.step:
                return "step is not part of the descriptor"
        if req.kind == "commit" and req.descriptor.get("commit") != req.step:
            return "commit step is not part of the descriptor"
        if req.kind == "value" and req.value not in (req.descriptor.get("allowedValues") or []):
            return "value is not in allowedValues"
        return None

    def decide(self, req: ActionRequest, page) -> Decision:
        """Steps 1-5. A denial is recorded here; for allow/ask the caller reports
        the principal's answer and execution through ``record`` (step 6)."""
        d = self._decide(req, page)
        if d.outcome == DENY:
            self.record(req, d)
        return d

    def _decide(self, req: ActionRequest, page) -> Decision:
        problem = self._validate(req)
        if problem:
            return Decision(DENY, f"invalid-descriptor: {problem}")

        # Documents of the manifest's origin whose path is in scope only (Section 4.2).
        cur = page.url()
        if origin_of(cur) != self.origin:
            return Decision(DENY, "document-not-same-origin")
        if not in_scope(urlsplit(cur).path or "/", self.scope):
            return Decision(DENY, "document-out-of-scope")

        # -- step 2: re-resolve against the live document
        el, handle, target_url, unresolved = None, None, None, None
        action = req.action
        if req.kind == "value":
            matches = page.resolve_focused_field(req.descriptor["locator"])
            if len(matches) != 1:
                unresolved = "field-hint-not-applicable-to-focused-element"
            else:
                el, handle = matches[0]
                if not page.when_holds(req.descriptor.get("when"), self.manifest):
                    unresolved = "field-hint-when-not-satisfied"
        elif action in LOCATOR_ACTIONS:
            matches = page.resolve(req.step["locator"])
            if len(matches) != 1:
                unresolved = f"locator-matches-{len(matches)}-elements"
            else:
                el, handle = matches[0]
                if not el.rendered:
                    unresolved = "locator-element-not-rendered"
        elif action == "navigate" or req.kind == "shortcut":
            target = req.step["target"] if req.kind == "step" else req.descriptor["target"]
            target_url = resolve_target(self.origin, target, self.scope)
            if target_url is None:
                unresolved = "target-cross-origin-or-out-of-scope"

        # -- step 3: security controls (Section 5.4). Checked even when resolution
        # failed: a pending confirm() blocks the DOM, and must stop, not just deny.
        controls = page.detect_security_controls()
        if controls:
            return Decision(DENY, "security-control:" + ",".join(sorted(controls)), stop=True,
                            element=el, handle=handle)
        if unresolved:
            return Decision(DENY, unresolved)

        # -- step 4: default outcome
        d = self._default(req, el)
        d.element, d.handle, d.target_url = el, handle, target_url

        # -- step 5: agent policy (stricter only), then standing approval
        if self.agent_policy is not None:
            stricter = self.agent_policy(req, d)
            if _RANK.get(stricter, 2) > _RANK[d.outcome]:
                d.outcome, d.reason = stricter, f"agent-policy ({d.reason})"
        if (d.outcome == ASK and d.standing_eligible and not d.sensitive
                and self.origin in self.standing_approvals):
            d.outcome, d.reason = ALLOW, f"standing-approval ({d.reason})"
        return d

    def _default(self, req: ActionRequest, el: Optional[ElementInfo]) -> Decision:
        action = req.action
        if req.kind == "shortcut":
            return Decision(ASK, "shortcut")
        if req.kind == "value":
            return Decision(ASK, "value-from-allowedValues")
        if action in ALWAYS_ALLOWED_ACTIONS:
            return Decision(ALLOW, f"{action}-default-allow")
        if action in ("click", "navigate"):
            return Decision(ASK, f"{action}-default-ask")
        if action == "key":
            key = req.step.get("key")
            activatable = is_activatable(el)
            value_bearing = is_value_bearing(el)
            if key == "Tab":
                return Decision(ALLOW, "key-Tab-default-allow")
            if key in NAV_KEYS:
                if not activatable and not value_bearing:
                    return Decision(ALLOW, f"key-{key}-on-inert-element")
                return Decision(ASK, f"key-{key}-on-{'activatable' if activatable else 'value-bearing'}-element")
            if key == "Enter":
                if not activatable and not is_form_input(el):
                    return Decision(ALLOW, "key-Enter-cannot-activate-or-submit")
                if activatable:
                    return Decision(ASK, "key-Enter-on-activatable-element")
                sensitive = self.provenance.form_modified(el.form_id) or el.form_has_credentials
                return Decision(ASK, "key-Enter-may-submit-form" + ("-sensitive" if sensitive else ""),
                                standing_eligible=True, sensitive=sensitive,
                                warning="This key press can submit the form.")
            if key == "Escape":
                return Decision(ASK, "key-Escape-default-ask", standing_eligible=not activatable)
        return Decision(DENY, "unclassifiable")

    # Agent-originated submission of a form a manifest-derived action modified.
    def submission_is_sensitive(self, form_id: Optional[str]) -> bool:
        return self.provenance.form_modified(form_id)

    def record(self, req: ActionRequest, d: Decision, *, principal=None, executed=False, alert_text=None):
        self.audit.append(AuditRecord(
            time=self.clock().isoformat().replace("+00:00", "Z"),
            origin=self.origin, manifest_digest=self.digest,
            descriptor=f"{req.kind}:{req.descriptor_id}", position=req.position,
            action=req.action if req.action != "key" else f"key:{req.step.get('key')}",
            outcome=d.outcome, reason=d.reason, principal=principal,
            executed=executed, alert_text=alert_text, stop=d.stop))
