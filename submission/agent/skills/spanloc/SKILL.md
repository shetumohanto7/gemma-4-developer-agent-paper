---
name: spanloc
description: Find where to edit. Ranks the functions and classes most likely to need changes for the issue, with file paths and line ranges. Call it first, before reading files.
---

# spanloc: find the code to change

**First tool call of every task:**

    run_skill_script(skill_name="spanloc", file_path="scripts/locate.py",
                     args={"query": "<issue title and key sentences, error messages, names>"})

It prints up to 12 candidates, one per line: `score  path:start-end  definition`,
then the most likely files. It reads `/workspace` and never changes it.

Then:
1. `read_file` the top 2–3 candidates **at the printed line ranges**, not
   whole files.
2. If none fits, call `locate.py` again with different words: the exact error
   text, or a function name you have seen.
3. To list a file's functions with line numbers without reading it:

       run_skill_script(skill_name="spanloc", file_path="scripts/outline.py",
                        args={"file": "path/to/file.py"})
