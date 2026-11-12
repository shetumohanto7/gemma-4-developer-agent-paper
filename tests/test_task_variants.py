"""Variants only append a hint."""

from locbench.make_task_variants import CONDITIONS, variants_for

SRC = """\
class Session:
    def request(self, method):
        return method.lower()
"""
PATCH = """\
diff --git a/pkg/sessions.py b/pkg/sessions.py
--- a/pkg/sessions.py
+++ b/pkg/sessions.py
@@ -2,2 +2,2 @@ class Session:
     def request(self, method):
-        return method.lower()
+        return method.upper()
"""


def test_variants_append_hints_only():
    task = {"instance_id": "x", "problem_statement": "Session.request lowercases the method", "patch": PATCH}
    texts, gold = variants_for(task, [("pkg/sessions.py", SRC)])
    assert set(texts) == set(CONDITIONS)
    for c in CONDITIONS:
        assert texts[c].startswith(task["problem_statement"])
    assert texts["base"] == task["problem_statement"]
    assert "`pkg/sessions.py`" in texts["oracle_file"]
    assert "`pkg/sessions.py::Session.request` (lines 2-3)" in texts["oracle_func"]
    assert "pkg/sessions.py:2-3" in texts["spanloc"]
    assert gold["functions"] == ["pkg.sessions.Session.request"]
