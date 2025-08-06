#!/usr/bin/env python3
"""
Scaffold a Zetteldev experiment folder with:
  • 16‑char secret token in .zetteldev
  • report.qmd featuring a “Copy URL” button
  • Snakefile renders <experiment>-<TOKEN>.html
  • scratchpad.ipynb Jupyter notebook pre‑wired for live exploration
Reads [tool.zetteldev] base_url from pyproject.toml.
"""
import json, secrets, string, sys
from pathlib import Path

try:
    import tomllib            # Python ≥3.11
except ModuleNotFoundError:   # pragma: no cover – for ≤3.10
    import tomli as tomllib

import questionary            # interactive prompt

# ---------------------------------------------------------------------------- #
# helper functions
# ---------------------------------------------------------------------------- #
TOKEN_ALPHABET = string.ascii_lowercase + string.digits

def make_token(n: int = 16) -> str:
    """Return an n‑char random slug suitable for URLs."""
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(n))

def get_base_url() -> str:
    """Read project‑wide base_url from pyproject.toml or fall back."""
    try:
        data = tomllib.loads(Path("pyproject.toml").read_text())
        return data["tool"]["zetteldev"]["base_url"].rstrip("/")
    except Exception:
        return "http://localhost:8000"

# ---------------------------------------------------------------------------- #
# templates – double braces → single brace in output
# ---------------------------------------------------------------------------- #

SNAKEMAKE_TEMPLATE = """\
rule run_main:
    input:
        data = "../../data/foo.arrow" # placeholder
    output:
        # main.py outputs
    script:
        "main.py"

rule render_report:
    input:
        "report.qmd"
    output:
        "{exp}-{token}.html"
    shell:
        "quarto render report.qmd --output {exp}-{token}.html"
"""

REPORT_QMD_TEMPLATE = """\
---
title: "{exp} Report"
format:
  html:
    code-fold: true
    code-tools: true
    theme: cosmo
    toc: true
    toc-depth: 3
---

```{{=html}}
<button id=\"copy-url\" style=\"margin:1rem 0;\" class=\"btn btn-primary\">
  Copy experiment URL
</button>
<script>
  const EXP_URL = \"{url}\";
  document.getElementById(\"copy-url\").addEventListener("click",
    () => navigator.clipboard.writeText(EXP_URL)
         .then(()=>alert('Copied to clipboard')));
</script>
```

# {exp}

> *Dataset*: Describe what data you used and how?
> *Metrics*: Which metrics did you use and how?
> *Hypothesis*: ...

Welcome to **{exp}**!  The canonical link for collaborators is:

`{url}`

## Setup

```{{python}}
print("Hello from {exp}")
```
"""

DESIGN_ORG_TEMPLATE = """\
#+TITLE: {exp} Design

* Motivation & Goals
Describe the purpose and objectives of this experiment.

* Step 1
Outline the first step in the experimental process.

* Changelog
** [YYYY-MM-DD] Initial version
Created experiment scaffolding.
"""



MAIN_PY_TEMPLATE     = """\"\"\"
Main module for the {exp} experiment.

This module contains the core functionality for the experiment.
\"\"\"
from snakemake.script import snakemake # direct access to Snakefile variables
data_input = snakemake.input.data

"""


print("Running {exp} …")
TEST_BASIC_TEMPLATE  = """import os
import sys
import pytest

# Add the parent directory to the path so we can import the main module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import from the current experiment's main.py
from main import *

def test_{exp_underscore}_sanity():
    \"\"\"Basic sanity check for the {exp} experiment.\"\"\"
    assert True, "Basic test for {exp}"
"""

# ---------------------------------------------------------------------------- #
# notebook creation helpers
# ---------------------------------------------------------------------------- #

NOTEBOOK_PREAMBLE = """%load_ext autoreload
%autoreload 2

import sys
import importlib
"""

def create_scratchpad(exp: str, exp_underscore: str, path: Path) -> None:
    """Write a minimal Jupyter notebook with autoreload and imports."""
    # Format the preamble with the experiment name and underscored version
    formatted_preamble = NOTEBOOK_PREAMBLE.format(exp=exp, exp_underscore=exp_underscore)

    nb = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": [f"# Scratchpad for **{exp}** Experiment"]},
            {"cell_type": "code", "metadata": {}, "source": formatted_preamble.splitlines(True), "outputs": [], "execution_count": None},
            {"cell_type": "code", "metadata": {}, "source": "", "outputs": [], "execution_count": None},
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython", "version": sys.version.split()[0]},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(nb, indent=2))

# ---------------------------------------------------------------------------- #

def scaffold_experiment(exp: str) -> None:
    base = Path("experiments")
    folder = base / exp
    if folder.exists():
        sys.exit(f"⚠️  Experiment {exp!r} already exists.")

    # create folders
    folder.mkdir(parents=True)
    for sub in ("processed_data", "figures", "tests"):
        (folder / sub).mkdir()

    token = make_token()
    url   = f"{get_base_url()}/experiments/{exp}-{token}"

    # metadata
    (folder / ".zetteldev").write_text(f"token={token}\nurl={url}\n", encoding="utf-8")

    # write core files
    exp_underscore = exp.replace("-", "_")

    # Get today's date for the changelog
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")

    # Replace the placeholder with today's date
    design_content = DESIGN_ORG_TEMPLATE.format(exp=exp).replace("[YYYY-MM-DD]", today)
    (folder / "design.org").write_text(design_content)

    # Create a simple design.md that points to the org file for non-org users
    (folder / "design.md").write_text(f"# {exp} Design\n\nSee design.org for full details.\n")

    (folder / "main.py").write_text(MAIN_PY_TEMPLATE.format(exp=exp))
    (folder / "report.qmd").write_text(REPORT_QMD_TEMPLATE.format(exp=exp, url=url))
    (folder / "Snakefile").write_text(SNAKEMAKE_TEMPLATE.format(exp=exp, token=token))
    (folder / "tests" / f"test_{exp_underscore}.py").write_text(TEST_BASIC_TEMPLATE.format(exp=exp, exp_underscore=exp_underscore))

    # scratchpad notebook with experiment name in filename
    create_scratchpad(exp, exp_underscore, folder / f"scratchpad_{exp_underscore}.ipynb")

    print(f"✅  Experiment {exp!r} scaffolded at {folder}")
    print(f"🔗  Canonical URL: {url}")

# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    name = questionary.text("New experiment name:").ask()
    if not name:
        sys.exit("No name provided.")
    scaffold_experiment(name)
