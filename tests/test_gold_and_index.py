"""Gold extraction and index tests."""

from spanloc.core import (Localizer, Weights, build_index, code_snippets, extract_mentions, member_expand,
                          mention_scores, module_name, snippet_scores, tokenize)
from locbench.gold import gold_locations, parse_patch

SRC = '''\
import os


class Session:
    """A session."""

    def request(self, method, url):
        prep = self.prepare(method, url)
        return send(prep)

    @property
    def prepare(self, method, url):
        return (method, url)


def send(prep):
    return prep
'''

FILES = [("pkg/sessions.py", SRC), ("tests/test_sessions.py", "def test_request():\n    pass\n")]


def _index():
    return build_index(FILES)


def test_module_name_layouts():
    assert module_name("src/pkg/a.py") == "pkg.a"
    assert module_name("pkg/__init__.py") == "pkg"
    assert module_name("a.py") == "a"


def test_tokenize_splits_identifiers():
    toks = set(tokenize("getHTTPResponse_code jsonable_encoder status_code"))
    assert {"http", "response", "jsonable", "encoder", "jsonable_encoder", "status_code"} <= toks
    # stopword sub-words dropped
    assert "get" not in toks and "code" not in toks


def test_index_entities_and_edges():
    idx = _index()
    assert {"pkg.sessions", "pkg.sessions.Session", "pkg.sessions.Session.request",
            "pkg.sessions.Session.prepare", "pkg.sessions.send"} <= set(idx.entities)
    prep = idx.entities["pkg.sessions.Session.prepare"]
    assert prep.start == 11 and prep.end == 13  # decorator line included
    edges = {(s, d, t) for s, d, t in idx.edges}
    assert ("pkg.sessions.Session.request", "pkg.sessions.Session.prepare", "calls") in edges
    assert ("pkg.sessions.Session.request", "pkg.sessions.send", "calls") in edges


def test_modification_maps_to_method():
    patch = """\
diff --git a/pkg/sessions.py b/pkg/sessions.py
--- a/pkg/sessions.py
+++ b/pkg/sessions.py
@@ -7,3 +7,3 @@ class Session:
     def request(self, method, url):
-        prep = self.prepare(method, url)
+        prep = self.prepare(method.upper(), url)
         return send(prep)
"""
    g = gold_locations(_index(), patch)
    assert g["files"] == ["pkg/sessions.py"]
    assert g["functions"] == ["pkg.sessions.Session.request"]
    assert g["modules"] == []


def test_appended_method_maps_to_class_and_import_to_module():
    patch = """\
diff --git a/pkg/sessions.py b/pkg/sessions.py
--- a/pkg/sessions.py
+++ b/pkg/sessions.py
@@ -1,2 +1,3 @@
 import os
+import sys

@@ -13,2 +14,5 @@ class Session:
         return (method, url)
+
+    def close(self):
+        pass

"""
    g = gold_locations(_index(), patch)
    assert g["functions"] == ["pkg.sessions.Session"]
    assert g["modules"] == ["pkg.sessions"]


def test_new_file_is_not_gold_but_recorded():
    patch = """\
diff --git a/pkg/new.py b/pkg/new.py
new file mode 100644
--- /dev/null
+++ b/pkg/new.py
@@ -0,0 +1,2 @@
+def f():
+    return 1
"""
    g = gold_locations(_index(), patch)
    assert g["files"] == [] and g["added_files"] == ["pkg/new.py"]


def test_parse_patch_ignores_blank_removals():
    edits = parse_patch("""\
--- a/x.py
+++ b/x.py
@@ -1,3 +1,2 @@
 a = 1
-
 b = 2
""")
    assert edits["x.py"].removed == []


def test_quoted_code_line_signal():
    idx = _index()
    issue = "Wrong method sent. In sessions.py:\n\n    prep = self.prepare(method, url)\n\nkeeps the original case."
    assert "prep = self.prepare(method, url)" in code_snippets(issue)
    assert dict(snippet_scores(idx, issue)) == {"pkg.sessions.Session.request": 1.0}
    # common boilerplate lines ignored
    many = build_index([(f"m{i}.py", "x = compute(value)\n") for i in range(5)])
    assert not snippet_scores(many, "`x = compute(value)` fails")


def test_member_expansion_lends_class_mention_to_methods():
    idx = _index()
    mention = {"pkg.sessions.Session": 1.0}
    bm25 = {"pkg.sessions.Session.prepare": 0.6, "pkg.sessions.Session.request": 0.2}
    out = member_expand(idx, mention, bm25, weight=1.0)
    assert out["pkg.sessions.Session"] == 1.0
    assert abs(out["pkg.sessions.Session.prepare"] - 0.75) < 1e-9
    assert abs(out["pkg.sessions.Session.request"] - 0.25) < 1e-9
    assert member_expand(idx, mention, bm25, weight=0.0) == mention


def test_v01_is_recovered_by_zeroing_v02_weights():
    idx = _index()
    issue = "Session.request ignores `send` when prep = self.prepare(method, url) is called"
    v01 = Localizer(idx, Weights(snippet=0.0, member=0.0)).signals(issue)
    assert v01["snippet"] == {}
    assert v01["mention"] == {k: v / max(mention_scores(idx, issue, Weights()).values())
                              for k, v in mention_scores(idx, issue, Weights()).items()}


def test_mentions_and_ranking():
    idx = _index()
    issue = ("Session.request crashes.\n"
             'Traceback:\n  File "/site-packages/pkg/sessions.py", line 9, in request\n'
             "Calling `send(prep)` fails")
    m = extract_mentions(issue)
    assert m["trace"] and any(d == "Session.request" for d, _ in m["dotted"])
    ranked = Localizer(idx, Weights()).rank(issue, kinds=("function", "class"))
    assert ranked[0].entity.id == "pkg.sessions.Session.request"
    # test files down-weighted
    ids = [r.entity.id for r in ranked]
    assert "tests.test_sessions.test_request" not in ids[:3]
