"""Offline agent loop tests."""

import agentloc.agent as agent
from agentloc.agent import OpenAIClient, Turn, run_episode


class FakeSandbox:
    def __init__(self):
        self.calls = []

    def run(self, command, timeout=None):
        self.calls.append(("run", command))
        return "requests/utils.py:10: def stream_decode_response_unicode"

    def read_file(self, path, start=None, end=None):
        self.calls.append(("read", path, start, end))
        return "    10  def stream_decode_response_unicode(iterator, r):"

    def skill(self, script, args):
        self.calls.append(("skill", script, args))
        return "1. 1.00  requests/utils.py:10-20  def stream_decode_response_unicode(iterator, r):"


class ScriptedClient:
    """Replay one call per turn."""

    def __init__(self, script):
        self.script, self.seen = list(script), []

    def chat(self, messages, tools, temperature, seed, think):
        self.seen.append([m["role"] for m in messages])
        if not self.script:
            text = "I think it is requests/utils.py::stream_decode_response_unicode"
            return Turn(text, [], {"role": "assistant", "content": text}, 10, 5)
        name, args = self.script.pop(0)
        call = {"id": f"c{len(self.seen)}", "name": name, "arguments": args}
        return Turn("", [call], {"role": "assistant", "content": "", "tool_calls": [call]}, 100, 20)

    @staticmethod
    def tool_message(call, output):
        return {"role": "tool", "tool_call_id": call["id"], "content": output}


def test_episode_submits_and_counts():
    sb = FakeSandbox()
    client = ScriptedClient([("read_file", {"filepath": "requests/utils.py", "start_line": 1, "end_line": 30}),
                             ("submit_locations", {"locations": ["requests/utils.py::stream_decode_response_unicode"]})])
    ep = run_episode(sb, "decode_unicode is ignored", client, condition="base")
    assert ep.submitted == ["requests/utils.py::stream_decode_response_unicode"]
    assert ep.turns == 2 and ep.prompt_tokens == 200 and not ep.fallback_parse
    assert sb.calls[0][0] == "read"


def test_skill_condition_uses_dict_args_and_fallback_parse():
    sb = FakeSandbox()
    client = ScriptedClient([("run_skill_script", {"skill_name": "spanloc", "file_path": "scripts/locate.py",
                                                   "args": {"query": "decode_unicode ignored"}})])
    ep = run_episode(sb, "decode_unicode is ignored", client, condition="skill", max_turns=5)
    assert sb.calls[0] == ("skill", "locate.py", ["--query", "decode_unicode ignored"])
    # no submit: parse from text
    assert ep.fallback_parse and ep.submitted == ["requests/utils.py::stream_decode_response_unicode"]
    assert ep.error == "no tool call"


def test_inject_puts_ranking_in_first_message():
    sb = FakeSandbox()
    client = ScriptedClient([("submit_locations", {"locations": ["requests/utils.py"]})])
    run_episode(sb, "decode_unicode is ignored", client, condition="inject")
    assert sb.calls[0][:2] == ("skill", "locate.py")


def test_openai_client_parses_vllm_tool_calls(monkeypatch):
    captured = {}

    def fake_post(url, body, headers, timeout=900, attempts=6):
        captured.update(url=url, body=body, headers=headers)
        return {"choices": [{"message": {
            "role": "assistant", "content": None, "reasoning_content": "thinking...",
            "tool_calls": [{"id": "call_1", "type": "function",
                            "function": {"name": "read_file", "arguments": '{"filepath": "a.py"}'}}]}}],
            "usage": {"prompt_tokens": 1234, "completion_tokens": 56}}

    monkeypatch.setattr(agent, "_post", fake_post)
    client = OpenAIClient("https://example.modal.run/", "gemma-4-e4b-it-qat-w4a16-ct", "KEY")
    turn = client.chat([{"role": "user", "content": "hi"}], [], 0.2, 0, think=False)
    assert captured["url"] == "https://example.modal.run/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer KEY"
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "thinking_token_budget" not in captured["body"]
    assert turn.calls == [{"id": "call_1", "name": "read_file", "arguments": {"filepath": "a.py"}}]
    assert "reasoning_content" not in turn.history  # thoughts not kept
    assert (turn.prompt_tokens, turn.completion_tokens) == (1234, 56)
    assert client.tool_message(turn.calls[0], "x") == {"role": "tool", "tool_call_id": "call_1", "content": "x"}
