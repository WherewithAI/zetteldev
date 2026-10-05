"""Static hygiene checks for the repository: no project install, no notebook execution.

The dependency tree here (torch, vllm, verl, flash-attn) cannot be installed on a
GitHub runner in any reasonable time, so CI cannot run the test suites; and the
notebooks are computational essays whose outputs are the deliverable, so it must not
strip them either. What is left is worth having anyway -- these are the failures that
have actually reached this repository:

1. Notebooks that are not valid JSON. A conflicted merge leaves markers inside the
   .ipynb, and the file stops being a notebook; nothing notices until someone opens it.
2. Python that does not compile.
3. Conflict markers left in any tracked text file.

Run it locally exactly as CI does:  python .zetteldev/ci_static_checks.py
"""

from __future__ import annotations

import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

#: Anchored to line starts, and 7 characters exactly, so prose about conflicts is safe
#: and a markdown '====' rule underneath a heading is not mistaken for a merge marker.
CONFLICT_MARKERS = ("<<<<<<< ", ">>>>>>> ", "=======\n")

TEXT_SUFFIXES = {".py", ".ipynb", ".md", ".yaml", ".yml", ".toml", ".cfg", ".txt",
                 ".qmd", ".sbatch", ".sh", ".json"}


def tracked(*patterns: str) -> list[Path]:
    """Files git tracks, so untracked scratch and ignored data never fail the build."""
    out = subprocess.run(["git", "ls-files", "-z", *patterns],
                         capture_output=True, text=True, check=True).stdout
    return [Path(p) for p in out.split("\0") if p]


def check_notebooks() -> list[str]:
    """Every tracked notebook parses and carries the keys that make it a notebook."""
    failures = []
    for path in tracked("*.ipynb"):
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            failures.append(f"{path}: not valid JSON -- {exc}")
            continue
        if not isinstance(notebook, dict) or "cells" not in notebook:
            failures.append(f"{path}: parses, but has no 'cells' -- not a notebook")
        elif not isinstance(notebook["cells"], list):
            failures.append(f"{path}: 'cells' is {type(notebook['cells']).__name__}, not a list")
    return failures


def check_python_compiles() -> list[str]:
    """Every tracked .py byte-compiles. Catches syntax errors and stray conflict markers."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in tracked("*.py"):
            try:
                py_compile.compile(str(path), cfile=str(Path(tmp) / "out.pyc"),
                                   doraise=True, quiet=1)
            except py_compile.PyCompileError as exc:
                failures.append(f"{path}: {str(exc).splitlines()[-1]}")
    return failures


def check_no_conflict_markers() -> list[str]:
    """No tracked text file carries an unresolved merge marker."""
    failures = []
    for path in tracked():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue        # binary or unreadable: not our business
        for number, line in enumerate(text.splitlines(keepends=True), start=1):
            if any(line.startswith(marker) for marker in CONFLICT_MARKERS):
                failures.append(f"{path}:{number}: unresolved conflict marker {line.strip()[:20]!r}")
                break
    return failures


CHECKS = {
    "notebooks are valid JSON": check_notebooks,
    "python compiles": check_python_compiles,
    "no unresolved conflict markers": check_no_conflict_markers,
}


def main() -> int:
    total = 0
    for name, check in CHECKS.items():
        failures = check()
        total += len(failures)
        print(f"{'FAIL' if failures else 'ok  '}  {name}"
              f"{f' ({len(failures)} problem(s))' if failures else ''}")
        for failure in failures:
            print(f"        {failure}")
    print()
    print(f"{total} problem(s)" if total else "all checks passed")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
