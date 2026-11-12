"""Map agent answers to gold."""

from agentloc.run import resolve, score
from spanloc.core import build_index

SRC = """\
class Session:
    def request(self, method):
        return method

def send(prep):
    return prep
"""


def _index():
    return build_index([("src/pkg/sessions.py", SRC), ("pkg/other.py", "def f():\n    pass\n")])


def test_resolve_formats():
    idx = _index()
    assert resolve(idx, "src/pkg/sessions.py::Session.request") == ("src/pkg/sessions.py", "pkg.sessions.Session.request")
    assert resolve(idx, "/workspace/src/pkg/sessions.py::send") == ("src/pkg/sessions.py", "pkg.sessions.send")
    assert resolve(idx, "pkg/sessions.py::send()") == ("src/pkg/sessions.py", "pkg.sessions.send")
    assert resolve(idx, "src/pkg/sessions.py:Session.request")[1] == "pkg.sessions.Session.request"
    assert resolve(idx, "src/pkg/sessions.py") == ("src/pkg/sessions.py", None)
    assert resolve(idx, "nope.py::x") == (None, None)


def test_score_strict_and_lenient():
    idx = _index()
    gold = {"files": ["src/pkg/sessions.py"], "functions": ["pkg.sessions.Session.request"]}
    s = score(idx, gold, ["src/pkg/sessions.py::Session"])
    assert s["file_hit"] and not s["func_hit"] and s["func_hit_lenient"] and s["func_all"]
    s = score(idx, gold, ["pkg/other.py::f", "src/pkg/sessions.py::Session.request"])
    assert s["func_hit"] and s["file_hit"] and not s["file_top1"]
