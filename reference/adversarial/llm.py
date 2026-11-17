# -*- coding: utf-8 -*-
"""One call to a real model through the local `claude -p` (no API key; the subscription login is used).

Isolation (checked in the design smoke test): no built-in tools, no slash commands/skills, no MCP, no
user/project settings (so no hooks and no global CLAUDE.md), no session saved, own system prompt, run from an
empty directory. The reply is constrained with --json-schema and read from `structured_output`.
Nothing but synthetic evaluation text is ever sent.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time

EMPTY_DIR = tempfile.mkdtemp(prefix="afrm-llm-")


def claude_exe() -> str:
    """The real executable: on Windows `claude` is an npm shim (.cmd) that mangles quoted arguments."""
    shim = shutil.which("claude")
    if shim:
        exe = os.path.join(os.path.dirname(shim), "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
        if os.path.exists(exe):
            return exe
    return shim or "claude"


def call_claude(system: str, prompt: str, schema: dict, model: str = "haiku", timeout: int = 150) -> dict:
    cmd = [claude_exe(), "-p", "--model", model, "--tools", "", "--disable-slash-commands", "--strict-mcp-config",
           "--no-session-persistence", "--setting-sources", "", "--system-prompt", system,
           "--output-format", "json", "--json-schema", json.dumps(schema)]
    t0 = time.time()
    out = {"ok": False, "obj": None, "error": None, "wall_s": None, "model_id": None, "cost_usd": None,
           "tokens": None, "raw": None}
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           timeout=timeout, cwd=EMPTY_DIR)
    except subprocess.TimeoutExpired:
        out["error"] = "timeout"
        out["wall_s"] = round(time.time() - t0, 1)
        return out
    out["wall_s"] = round(time.time() - t0, 1)
    out["raw"] = (p.stdout or "")[:20000]
    if p.returncode != 0:
        out["error"] = f"exit {p.returncode}: {(p.stderr or p.stdout or '')[:300]}"
        return out
    try:
        d = json.loads(p.stdout)
    except ValueError:
        out["error"] = "stdout is not JSON"
        return out
    u = d.get("usage") or {}
    out["cost_usd"] = d.get("total_cost_usd")
    out["tokens"] = [u.get("input_tokens"), u.get("cache_creation_input_tokens"),
                     u.get("cache_read_input_tokens"), u.get("output_tokens")]
    mu = d.get("modelUsage") or {}
    out["model_id"] = next(iter(mu), None)
    if d.get("is_error"):
        out["error"] = "is_error: " + str(d.get("result"))[:200]
        return out
    obj = d.get("structured_output")
    if obj is None:
        try:
            obj = json.loads(d.get("result") or "")
        except ValueError:
            out["error"] = "no structured output"
            return out
    out["obj"], out["ok"] = obj, True
    return out
