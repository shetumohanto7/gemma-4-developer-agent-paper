"""Minimal tool-calling localization agent."""

from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from agentloc.sandbox import Sandbox

SYSTEM_BASE = """You are a software engineer localizing a GitHub issue in the Python repository at /workspace.
Your only job is to find the code that must change to resolve the issue; do not write a fix.
Use the tools to explore. Keep reads small: read line ranges, not whole files.
When you are confident, call submit_locations with 1-5 entries formatted as
"path/to/file.py::function" or "path/to/file.py::Class.method", most likely first.
You have at most {max_turns} tool calls."""

SKILL_HINT = """
Rule: your FIRST tool call must be
run_skill_script(skill_name="spanloc", file_path="scripts/locate.py", args={"query": "<issue title and key sentences>"}).
It ranks the functions most likely to need changes, with file paths and line ranges. Then read the top
candidates at those line ranges. To list a file's functions with line numbers, call
run_skill_script(skill_name="spanloc", file_path="scripts/outline.py", args={"file": "path/to/file.py"})."""

TOOLS_BASE = [
    {"type": "function", "function": {
        "name": "run_command", "description": "Run a read-only shell command (grep, rg, find, ls, git log) in /workspace.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read lines of a file in /workspace (1-indexed, inclusive).",
        "parameters": {"type": "object", "properties": {
            "filepath": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}},
            "required": ["filepath"]}}},
    {"type": "function", "function": {
        "name": "submit_locations", "description": "Submit the code locations to change and finish.",
        "parameters": {"type": "object", "properties": {"locations": {"type": "array", "items": {"type": "string"}}},
                       "required": ["locations"]}}},
]
# mirrors the harness skill signature
TOOL_SKILL = {"type": "function", "function": {
    "name": "run_skill_script", "description": "Run a script from an installed skill.",
    "parameters": {"type": "object", "properties": {
        "skill_name": {"type": "string"}, "file_path": {"type": "string"},
        "args": {"type": "object", "description": "named arguments, passed to the script as --key value"}},
        "required": ["skill_name", "file_path"]}}}


def skill_argv(args) -> list[str]:
    """Convert skill args to argv."""
    if isinstance(args, dict):
        out: list[str] = []
        for k, v in args.items():
            out += [f"--{k}", str(v)]
        return out
    if isinstance(args, list):
        return [str(a) for a in args]
    return [str(args)] if args else []


@dataclass
class Episode:
    submitted: list[str] = field(default_factory=list)
    turns: int = 0
    prompt_tokens: int = 0          # summed over all calls
    completion_tokens: int = 0
    max_context: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    skill_calls: int = 0
    error: str = ""
    fallback_parse: bool = False    # parsed from text, no submit
    seconds: float = 0.0


MAX_NUDGES = 3
LOCATION_RE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.py(?:::[A-Za-z_][\w.]*)?)")


@dataclass
class Turn:
    """One normalized model reply."""
    content: str
    calls: list[dict]
    history: dict              # thoughts dropped
    prompt_tokens: int
    completion_tokens: int


class ContextOverflow(Exception):
    pass


def _post(url: str, body: dict, headers: dict, timeout: int = 900, attempts: int = 6) -> dict:
    """POST JSON with retries."""
    data = json.dumps(body).encode()
    for i in range(attempts):
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            if exc.code == 400 and ("context length" in detail or "maximum" in detail):
                raise ContextOverflow(detail) from exc
            if exc.code not in (429, 500, 502, 503, 504) or i == attempts - 1:
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            if i == attempts - 1:
                raise
        time.sleep(min(60, 5 * 2 ** i))
    raise RuntimeError("unreachable")


class OpenAIClient:
    """vLLM OpenAI-compatible backend."""

    def __init__(self, base_url: str, model: str, api_key: str, max_tokens: int = 4096) -> None:
        self.url = base_url.rstrip("/") + "/v1/chat/completions"
        self.model, self.max_tokens = model, max_tokens
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def chat(self, messages: list[dict], tools: list[dict], temperature: float, seed: int, think: bool) -> Turn:
        body = {"model": self.model, "messages": messages, "tools": tools, "tool_choice": "auto",
                "temperature": temperature, "seed": seed, "max_tokens": self.max_tokens,
                "chat_template_kwargs": {"enable_thinking": think}}
        if think:
            body["thinking_token_budget"] = 4096  # the harness default budget
        resp = _post(self.url, body, self.headers)
        msg = resp["choices"][0]["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            args = c.get("function", {}).get("arguments") or "{}"
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": c.get("id", ""), "name": c.get("function", {}).get("name", ""),
                          "arguments": args if isinstance(args, dict) else {}})
        history = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            history["tool_calls"] = msg["tool_calls"]
        usage = resp.get("usage") or {}
        return Turn(msg.get("content") or "", calls, history,
                    usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    @staticmethod
    def tool_message(call: dict, output: str) -> dict:
        return {"role": "tool", "tool_call_id": call["id"], "content": output}


class OllamaClient:
    """Local Ollama backend (pilot only)."""

    def __init__(self, model: str, host: str = "http://localhost:11434", num_ctx: int = 32768) -> None:
        self.model, self.url, self.num_ctx = model, f"{host}/api/chat", num_ctx

    def chat(self, messages: list[dict], tools: list[dict], temperature: float, seed: int, think: bool) -> Turn:
        resp = _post(self.url, {"model": self.model, "messages": messages, "tools": tools, "stream": False,
                                "think": think, "options": {"num_ctx": self.num_ctx, "seed": seed,
                                                            "temperature": temperature}}, {})
        msg = resp.get("message", {})
        calls = []
        for c in msg.get("tool_calls") or []:
            args = c.get("function", {}).get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({"id": "", "name": c.get("function", {}).get("name", ""), "arguments": args})
        history = {k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")}
        return Turn(msg.get("content") or "", calls, history,
                    resp.get("prompt_eval_count", 0) or 0, resp.get("eval_count", 0) or 0)

    @staticmethod
    def tool_message(call: dict, output: str) -> dict:
        return {"role": "tool", "content": output, "tool_name": call["name"]}


CONDITIONS = ("base", "skill", "inject")


def run_episode(sb: Sandbox, issue: str, client, condition: str = "base", max_turns: int = 20,
                seed: int = 0, temperature: float = 0.6, think: bool = False) -> Episode:
    """Run one episode: base/skill/inject."""
    if condition not in CONDITIONS:
        raise ValueError(condition)
    ep = Episode()
    t0 = time.time()
    use_skill = condition == "skill"
    system = SYSTEM_BASE.format(max_turns=max_turns) + (SKILL_HINT if use_skill else "")
    tools = TOOLS_BASE + ([TOOL_SKILL] if use_skill else [])
    user = f"<issue>\n{issue.strip()}\n</issue>"
    if condition == "inject":
        hints = sb.skill("locate.py", ["--query", issue])
        user += ("\n\nA localization tool ranked these candidates (score, file:lines, definition). "
                 f"They may be wrong; verify by reading.\n{hints}")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    nudges = 0
    while ep.turns < max_turns:
        try:
            turn = client.chat(messages, tools, temperature, seed, think)
        except ContextOverflow:
            ep.error = "context overflow"
            break
        except Exception as exc:  # noqa: BLE001 - record and stop this episode
            ep.error = f"model call failed: {exc}"
            break
        ep.prompt_tokens += turn.prompt_tokens
        ep.completion_tokens += turn.completion_tokens
        ep.max_context = max(ep.max_context, turn.prompt_tokens + turn.completion_tokens)
        calls = turn.calls
        messages.append(turn.history)
        if not calls:
            if nudges >= MAX_NUDGES:  # harness also stops here
                ep.error = "no tool call"
                break
            nudges += 1
            messages.append({"role": "user", "content": "Use a tool, or call submit_locations if you are done."})
            continue
        for call in calls:
            name, args = call["name"], call["arguments"]
            ep.turns += 1
            ep.tool_calls.append({"name": name, "args": {k: (v[:200] if isinstance(v, str) else v) for k, v in args.items()}})
            if name == "submit_locations":
                locs = args.get("locations") or []
                ep.submitted = [str(x) for x in (locs if isinstance(locs, list) else [locs])][:5]
                ep.seconds = time.time() - t0
                return ep
            if name == "run_command":
                out = sb.run(str(args.get("command", "")))
            elif name == "read_file":
                out = sb.read_file(str(args.get("filepath", "")), args.get("start_line"), args.get("end_line"))
            elif name == "run_skill_script" and use_skill:
                ep.skill_calls += 1
                script = str(args.get("file_path") or args.get("script") or "").rsplit("/", 1)[-1]
                out = sb.skill(script, skill_argv(args.get("args")))
            else:
                out = f"error: unknown tool {name!r}"
            messages.append(client.tool_message(call, out))
    ep.seconds = time.time() - t0
    if not ep.error:
        ep.error = "turn limit"
    # fallback: parse locations from text
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            found = list(dict.fromkeys(LOCATION_RE.findall(m["content"])))
            if found:
                ep.submitted, ep.fallback_parse = found[:5], True
                break
    return ep
