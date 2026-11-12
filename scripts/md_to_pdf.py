#!/usr/bin/env python3
"""Render a Markdown file to a print-quality PDF (HTML + CSS, printed by headless Google Chrome).

Used for the paper's reading copy and the project report:
    python3 scripts/md_to_pdf.py paper/writeup.md --refs paper/references.md --paper \
        --out paper/pdf/finding-is-half-the-fix_draft.pdf
    python3 scripts/md_to_pdf.py report/project-report.md --out report/project-report.pdf

Needs: Python with `markdown` (the macOS Command Line Tools python3 has 3.9) and Google Chrome >= 131
(CSS page-margin boxes for page numbers). No network access; images are embedded from local files.

Markdown conventions handled:
  * HTML comments (source notes) are removed.
  * Nested lists may use 2-space indentation (doubled to the 4 spaces python-markdown needs).
  * `![Figure N. caption](path)` on its own line becomes a numbered figure with a caption.
  * With --refs: citation keys like [key] or [key1; key2] that appear in the references file
    (lines "- **[key]** text") become numbered links [1, 2], and the list is printed in citation order.
  * With --paper: the first H1 is the title and a "**Subtitle:** ..." paragraph becomes the subtitle.
  * A line `[TOC]` becomes a table of contents (H2/H3).
"""
from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import os
import re
import subprocess
import sys
import tempfile

import markdown

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = r"""
@page { size: A4; margin: 20mm 19mm 20mm 19mm;
  @bottom-center { content: counter(page) " / " counter(pages); font: 8.5pt "Helvetica Neue", Arial, sans-serif; color: #777; }
  @top-right { content: string(runhead); font: 8pt "Helvetica Neue", Arial, sans-serif; color: #999; } }
@page :first { @top-right { content: none; } }
:root { --ink: #1d1d1f; --ink2: #4a4a4f; --rule: #d9d9de; --accent: #1f5fbf; --tint: #f4f6fa; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Charter, "Iowan Old Style", Georgia, serif; font-size: 10.4pt; line-height: 1.45; color: var(--ink);
  background: #fff; margin: 0; hyphens: auto; }
h1, h2, h3, h4 { font-family: "Helvetica Neue", Arial, sans-serif; color: var(--ink); line-height: 1.25;
  break-after: avoid; page-break-after: avoid; }
h1 { font-size: 20pt; margin: 0 0 6pt; string-set: runhead content(); }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 0.6pt solid var(--rule); }
h3 { font-size: 11.2pt; margin: 13pt 0 4pt; }
h4 { font-size: 10.4pt; margin: 10pt 0 3pt; }
p { margin: 0 0 6pt; orphans: 3; widows: 3; }
ul, ol { margin: 0 0 6pt; padding-left: 18pt; }
li { margin: 1.5pt 0; }
li > ul, li > ol { margin: 1pt 0 2pt; }
a { color: var(--accent); text-decoration: none; }
code { font-family: Menlo, "SF Mono", monospace; font-size: 8.6pt; background: var(--tint); padding: 0 2pt; border-radius: 2pt;
  overflow-wrap: anywhere; }
pre { background: var(--tint); padding: 6pt 8pt; border-radius: 3pt; font-size: 8.4pt; line-height: 1.35;
  white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-family: "Helvetica Neue", Arial, sans-serif;
  font-size: 8.4pt; line-height: 1.3; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { text-align: left; font-weight: 600; border-bottom: 0.9pt solid var(--ink2); padding: 3pt 5pt; vertical-align: bottom; }
td { border-bottom: 0.5pt solid var(--rule); padding: 3pt 5pt; vertical-align: top; }
figure { margin: 8pt 0 12pt; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 105mm; }
figure.wide img { max-height: 80mm; }
figcaption { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8.6pt; color: var(--ink2); text-align: left;
  margin-top: 4pt; line-height: 1.35; }
blockquote { margin: 6pt 0 8pt; padding: 6pt 10pt; border-left: 2.5pt solid var(--accent); background: var(--tint); }
blockquote p:last-child { margin-bottom: 0; }
hr { border: none; border-top: 0.6pt solid var(--rule); margin: 12pt 0; }
.subtitle { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 11.2pt; color: var(--ink2); margin: 0 0 8pt; line-height: 1.35; }
.meta { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8.6pt; color: #7a5a00; background: #fff6dc;
  border: 0.6pt solid #ecd9a0; border-radius: 3pt; padding: 5pt 8pt; margin: 4pt 0 12pt; }
.cite { color: var(--accent); white-space: nowrap; }
.refs ol { font-size: 8.8pt; line-height: 1.35; padding-left: 20pt; }
.refs li { margin: 2pt 0; }
.toc { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 9.4pt; background: var(--tint); padding: 8pt 12pt;
  border-radius: 3pt; margin: 8pt 0 12pt; break-inside: avoid; }
.toc ul { list-style: none; padding-left: 0; margin: 0; }
.toc ul ul { padding-left: 14pt; }
.toc li { margin: 1.5pt 0; }
.pagebreak { break-before: page; }
.status-done { color: #1a7f37; font-weight: 600; }
.status-todo { color: #b35900; font-weight: 600; }
.status-block { color: #c62828; font-weight: 600; }
"""


def strip_comments(text: str) -> str:
    # also eat preceding whitespace
    return re.sub(r"[ \t]*\n?[ \t]*<!--.*?-->", "", text, flags=re.S)


LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")


def double_list_indent(text: str) -> str:
    """Adapt lists for python-markdown."""
    out: list[str] = []
    fence = in_list = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence:
            is_item = bool(LIST_ITEM.match(line))
            if is_item and not in_list and out and out[-1].strip() and not out[-1].lstrip().startswith("|"):
                out.append("")
            if not line.strip():
                in_list = False
            elif is_item:
                in_list = True
            if line.startswith(" ") and line.strip():
                n = len(line) - len(line.lstrip(" "))
                line = " " * (2 * n) + line.lstrip(" ")
        out.append(line)
    return "\n".join(out)


def parse_refs(path: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*-\s*\*\*\[([^\]]+)\]\*\*\s*(.+)", line)
        if m:
            refs[m.group(1).strip()] = m.group(2).strip()
    return refs


def number_citations(text: str, refs: dict[str, str]) -> tuple[str, list[str]]:
    order: list[str] = []

    def repl(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(";")]
        if not all(k in refs for k in keys):
            return m.group(0)
        nums = []
        for k in keys:
            if k not in order:
                order.append(k)
            nums.append(order.index(k) + 1)
        links = ", ".join(f'<a href="#ref-{n}">{n}</a>' for n in nums)
        return f'<span class="cite">[{links}]</span>'

    text = re.sub(r"\[([a-z][a-z0-9]+(?:\s*;\s*[a-z][a-z0-9]+)*)\](?!\()", repl, text)
    order += [k for k in refs if k not in order]  # uncited entries go last
    return text, order


def embed_images(text: str, base_dir: str) -> str:
    def repl(m: re.Match) -> str:
        caption, path = m.group(1), m.group(2)
        full = os.path.normpath(os.path.join(base_dir, path))
        mime = mimetypes.guess_type(full)[0] or "image/png"
        data = base64.b64encode(open(full, "rb").read()).decode()
        cap = markdown.markdown(caption).removeprefix("<p>").removesuffix("</p>")
        cls = ' class="wide"' if "wide" in path or "fig_fix" in path else ""
        return f'\n<figure{cls}><img src="data:{mime};base64,{data}" alt=""><figcaption>{cap}</figcaption></figure>\n'

    return re.sub(r"^!\[(.+?)\]\((\S+?)\)\s*$", repl, text, flags=re.M)


def render(src: str, out: str, refs_path: str | None, paper: bool, meta: str | None, title: str | None) -> None:
    base_dir = os.path.dirname(os.path.abspath(src))
    text = open(src, encoding="utf-8").read()
    text = strip_comments(text)
    text = double_list_indent(text)
    order: list[str] = []
    refs: dict[str, str] = {}
    if refs_path:
        refs = parse_refs(refs_path)
        text, order = number_citations(text, refs)
    text = embed_images(text, base_dir)
    head = ""
    if paper:
        m = re.search(r"^# (.+)$", text, flags=re.M)
        doc_title = m.group(1).strip() if m else (title or "")
        text = text[:m.start()] + text[m.end():] if m else text
        s = re.search(r"^\*\*Subtitle:\*\*\s*(.+?)(?:\n\s*\n)", text, flags=re.M | re.S)
        sub = ""
        if s:
            sub = " ".join(s.group(1).split())
            text = text[:s.start()] + text[s.end():]
        head = f"<h1>{html.escape(doc_title)}</h1>"
        if sub:
            head += f'<p class="subtitle">{markdown.markdown(sub).removeprefix("<p>").removesuffix("</p>")}</p>'
        title = title or doc_title
    if meta:
        head += f'<div class="meta">{meta}</div>'
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "attr_list", "md_in_html"],
                           extension_configs={"toc": {"toc_depth": "2-3", "title": ""}})
    body = md.convert(text)
    body = body.replace('<div class="toc">', '<div class="toc"><b>Contents</b>')
    if refs_path:
        items = "".join(f'<li id="ref-{i + 1}">{markdown.markdown(refs[k]).removeprefix("<p>").removesuffix("</p>")}</li>'
                        for i, k in enumerate(order))
        body += f'<section class="refs"><h2>References</h2><ol>{items}</ol></section>'
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title or "")}</title>'
            f"<style>{CSS}</style></head><body>{head}{body}</body></html>")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        page_path = os.path.join(tmp, "page.html")
        open(page_path, "w", encoding="utf-8").write(page)
        if os.environ.get("KEEP_HTML"):
            open(os.path.splitext(out)[0] + ".html", "w", encoding="utf-8").write(page)
        cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
               "--disable-extensions", f"--user-data-dir={tmp}/profile", "--virtual-time-budget=10000",
               f"--print-to-pdf={os.path.abspath(out)}", f"file://{page_path}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not os.path.exists(out):
            sys.exit(f"Chrome failed ({r.returncode}): {r.stderr[-2000:]}")
    print(f"wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--refs", help="references markdown (lines '- **[key]** text') for numbered citations")
    ap.add_argument("--paper", action="store_true", help="title + subtitle block from the first H1 and **Subtitle:**")
    ap.add_argument("--meta", help="HTML for a status note under the title")
    ap.add_argument("--title", help="document title (PDF metadata)")
    a = ap.parse_args()
    render(a.src, a.out, a.refs, a.paper, a.meta, a.title)


if __name__ == "__main__":
    main()
