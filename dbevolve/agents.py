"""Agent backends. Each call is a fresh context: state travels through files, never through a chat.

`ClaudeCLI` runs Claude Code headless (`claude -p`) inside one worktree slot. The agent can read
and (if `writable`) edit files in that worktree, and run exactly one shell command: the
agent-facing tool `bin/dbe-tool`. `Mock` makes no model calls and exists to exercise the pipeline.
"""
from __future__ import annotations

import json
import re
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT, Config
from .util import log, write_json

TOOL = ROOT / "bin" / "dbe-tool"


@dataclass
class AgentResult:
    ok: bool
    output: dict = field(default_factory=dict)   # structured output matching the role's schema
    text: str = ""
    cost_usd: float = 0.0
    seconds: float = 0.0
    error: str = ""
    billing: str = "plan"                         # "plan" (subscription) or "api" (fallback key)


class ClaudeCLI:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.a = cfg["agents"]

    def run(self, role: str, prompt: str, cwd: Path, schema: dict, budget_usd: float,
            log_dir: Path, writable: bool = False) -> AgentResult:
        # Belt and braces: the hidden workload is never written to disk, but keep agents away
        # from the framework's own source, config (seed) and stored results anyway.
        deny = [f"Read(//{str(ROOT / d).lstrip('/')}/**)" for d in ("dbevolve", "config", "runs", "results", "tests")]
        deny += [f"Read(//{str(self.cfg.refs).lstrip('/')}/**)", "WebFetch", "WebSearch"]
        cmd = ["claude", "-p", "--model", self.a["model"], "--output-format", "json",
               "--json-schema", json.dumps(schema), "--max-budget-usd", str(budget_usd),
               "--tools", "Read,Glob,Grep,Bash" + (",Edit,Write" if writable else ""),
               "--allowedTools", f"Bash({TOOL} *)",
               # dbe-tool calls (bench, a polled build) can exceed the default 2-minute shell limit
               "--settings", json.dumps({"permissions": {"deny": deny},
                                         "env": {"BASH_DEFAULT_TIMEOUT_MS": "600000",
                                                 "BASH_MAX_TIMEOUT_MS": "900000"}}),
               "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]
        if writable:
            cmd += ["--permission-mode", "acceptEdits"]
        env = dict(os.environ, DBE_SLOT=str(cwd), DBE_CONFIG=str(self.cfg.path))
        env.pop("ANTHROPIC_API_KEY", None)   # plan login by default; the key is only a fallback
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{role}.prompt.md").write_text(prompt)
        start = time.time()
        waited = 0.0
        while True:
            api = _on_api()
            run_env = dict(env, ANTHROPIC_API_KEY=fallback_api_key()) if api else env
            try:
                p = subprocess.run(cmd, input=prompt, cwd=cwd, env=run_env, text=True, capture_output=True,
                                   timeout=self.a["timeout_s"])
                stdout, stderr = p.stdout, p.stderr
            except subprocess.TimeoutExpired as e:
                return AgentResult(False, error=f"agent timed out after {self.a['timeout_s']}s",
                                   seconds=time.time() - start, text=str(e.stdout or "")[-2000:])
            pause = None if api else usage_limit_pause(f"{stdout}\n{stderr}")
            if pause is None or waited > 48 * 3600:
                break
            if fallback_api_key():
                global _api_until
                _api_until = time.time() + pause
                log(f"{role}: plan usage limit hit; using the API key for {pause / 60:.0f} min "
                    f"until the reset, then back to the plan")
            else:
                log(f"{role}: plan usage limit hit; waiting {pause / 60:.0f} min for the reset, then retrying")
                sleep_wall(pause)
                waited += pause
            start = time.time()
        (log_dir / f"{role}.raw.json").write_text(stdout or "")
        res = parse_cli_output(stdout, stderr)
        res.seconds = time.time() - start
        if api:
            res.billing = "api"
            log(f"{role}: billed to the API key: ${res.cost_usd:.2f}")
        write_json(log_dir / f"{role}.result.json", res.__dict__)
        return res


_api_until = 0.0   # wall-clock time until which agent calls go to the fallback API key
KEY_FILE = Path.home() / ".config" / "db_evolve" / "anthropic_api_key"


def fallback_api_key() -> str | None:
    """The Anthropic API key used only while the plan is rate-limited: $DBE_FALLBACK_API_KEY, or
    the file ~/.config/db_evolve/anthropic_api_key (keep it chmod 600). Never written to logs."""
    key = os.environ.get("DBE_FALLBACK_API_KEY", "").strip()
    if not key and KEY_FILE.is_file():
        key = KEY_FILE.read_text().strip()
    return key or None


def _on_api() -> bool:
    return bool(fallback_api_key()) and time.time() < _api_until


_LIMIT = re.compile(r"hit your [^\n]*?limit", re.I)
_RESET = re.compile(r"resets\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)", re.I)


def sleep_wall(seconds: float) -> None:
    """Sleep until a wall-clock deadline. time.sleep alone stalls while the machine is suspended
    (WSL's monotonic clock stops), so a wait for a usage reset could run hours past the reset."""
    deadline = time.time() + seconds
    while (left := deadline - time.time()) > 0:
        time.sleep(min(left, 60))


def usage_limit_pause(text: str, now: "datetime.datetime | None" = None) -> float | None:
    """Seconds to wait when the CLI reports a plan usage limit (None if it did not).

    The message looks like "You've hit your 5-hour limit · resets 3:40pm (America/New_York)".
    Waits until the stated reset plus 3 minutes; 30 minutes if no reset time can be read.
    """
    if not _LIMIT.search(text or ""):
        return None
    m = _RESET.search(text)
    if not m:
        return 1800.0
    import datetime
    from zoneinfo import ZoneInfo
    tz = re.search(r"resets[^(\n]*\(([A-Za-z_/]+)\)", text)
    zone = ZoneInfo(tz.group(1)) if tz else None
    now = now or datetime.datetime.now(zone)
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    reset = now.replace(hour=h, minute=int(m.group(2) or 0), second=0, microsecond=0)
    if reset <= now:
        reset += datetime.timedelta(days=1)
    return (reset - now).total_seconds() + 180


def parse_cli_output(stdout: str, stderr: str = "") -> AgentResult:
    """Parse `claude -p --output-format json` output, tolerating either result shape."""
    try:
        doc = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return AgentResult(False, error=f"unparseable agent output: {(stdout or stderr or '')[-800:]}")
    if isinstance(doc, list):  # a message array: the result record is the last element
        doc = next((d for d in reversed(doc) if isinstance(d, dict) and d.get("type") == "result"), {})
    text = doc.get("result") or ""
    cost = float(doc.get("total_cost_usd") or 0.0)
    out = doc.get("structured_output")
    if not isinstance(out, dict):
        out = _json_from_text(text)
    if doc.get("is_error") or out is None:
        return AgentResult(False, text=text, cost_usd=cost,
                           error=f"{doc.get('subtype', 'no structured output')}: {text[-600:]}")
    return AgentResult(True, output=out, text=text, cost_usd=cost)


def _json_from_text(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


class Mock:
    """Scripted stand-in. DBE_MOCK_SCENARIO: noop (default) | audit | forbidden | abandon."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.scenario = os.environ.get("DBE_MOCK_SCENARIO", "noop")

    def run(self, role: str, prompt: str, cwd: Path, schema: dict, budget_usd: float,
            log_dir: Path, writable: bool = False) -> AgentResult:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{role}.prompt.md").write_text(prompt)
        if role == "planner":
            out = {"issues": [{"title": f"mock change ({self.scenario})",
                               "hypothesis": "No-op change used to exercise the pipeline.",
                               "plan": "Add a comment to one source file.", "target_files": ["src/common"],
                               "expected_gain": "none", "generality": "Not workload specific.", "risk": "none"}],
                   "dispatch": [f"mock change ({self.scenario})"],
                   "memory": "# Memory\n\nMock run: nothing learned.\n"}
        elif role == "implementer":
            if self.scenario == "abandon":
                out = {"status": "abandon", "summary": "mock abandon", "generality": "", "notes": ""}
            else:
                target = sorted((cwd / "src" / "common").glob("*.cpp"))[0]
                note = {"noop": "// db_evolve mock change\n",
                        "audit": "// fast path for lineitem scans\n",
                        "forbidden": "// db_evolve mock change\n"}[self.scenario]
                if self.scenario == "forbidden":
                    target = sorted((cwd / "test").rglob("*.cpp"))[0]
                with open(target, "a") as f:
                    f.write(note)
                out = {"status": "ready", "summary": f"appended a comment to {target.name}",
                       "generality": "comment only", "notes": ""}
        elif role == "grouper":
            ts = json.loads((cwd / "templates.json").read_text())
            k = int((cwd / "k.txt").read_text())
            out = {"groups": [ts[i::k] for i in range(k)], "rationale": "mock: round robin"}
        else:
            out = {"verdict": "approve", "benchmark_specific": False, "findings": [], "required_changes": []}
        res = AgentResult(True, output=out, text=json.dumps(out))
        write_json(log_dir / f"{role}.result.json", res.__dict__)
        return res


def make(cfg: Config):
    return {"claude-cli": ClaudeCLI, "mock": Mock}[os.environ.get("DBE_AGENT_BACKEND") or cfg["agents"]["backend"]](cfg)


# --- structured-output schemas, one per role -----------------------------------

_STR = {"type": "string"}
ISSUE = {"type": "object", "additionalProperties": False,
         "required": ["title", "hypothesis", "plan", "target_files", "expected_gain", "generality", "risk"],
         "properties": {"title": _STR, "hypothesis": _STR, "plan": _STR,
                        "target_files": {"type": "array", "items": _STR},
                        "expected_gain": _STR, "generality": _STR, "risk": _STR}}
PLANNER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["issues", "dispatch", "memory"],
                  "properties": {"issues": {"type": "array", "items": ISSUE},
                                 "dispatch": {"type": "array", "items": _STR},
                                 "memory": _STR}}
IMPLEMENTER_SCHEMA = {"type": "object", "additionalProperties": False,
                      "required": ["status", "summary", "generality", "notes"],
                      "properties": {"status": {"type": "string", "enum": ["ready", "abandon"]},
                                     "summary": _STR, "generality": _STR, "notes": _STR}}
REVIEWER_SCHEMA = {"type": "object", "additionalProperties": False,
                   "required": ["verdict", "benchmark_specific", "findings", "required_changes"],
                   "properties": {"verdict": {"type": "string", "enum": ["approve", "reject"]},
                                  "benchmark_specific": {"type": "boolean"},
                                  "findings": {"type": "array", "items": _STR},
                                  "required_changes": {"type": "array", "items": _STR}}}
GROUPER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["groups", "rationale"],
                  "properties": {"groups": {"type": "array", "items": {"type": "array", "items": _STR}},
                                 "rationale": _STR}}
