#!/usr/bin/env python3
"""
Scaffold a Zetteldev experiment folder with:
  • 16‑char secret token in .zetteldev
  • report.qmd featuring a "Copy URL" button
  • Snakefile renders <experiment>-<TOKEN>.html
  • scratchpad.ipynb Jupyter notebook pre‑wired for live exploration
  • Optional: Pre-fill design.md from GitHub issue

Usage:
  python create_experiment.py             # Interactive mode
  python create_experiment.py <issue_num> # Create from specific issue
  python create_experiment.py <exp_name>  # Create with specific name

Reads [tool.zetteldev] base_url from pyproject.toml.
"""
import json, secrets, string, sys
import re
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Dict, List

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

def get_github_repo() -> Optional[str]:
    """Extract GitHub repository from git remote origin."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        )
        url = result.stdout.strip()
        # Extract owner/repo from various URL formats
        if "github.com" in url:
            if url.startswith("git@"):
                # SSH format: git@github.com:owner/repo.git
                match = re.search(r"github\.com:([^/]+/[^.]+)", url)
            else:
                # HTTPS format: https://github.com/owner/repo.git
                match = re.search(r"github\.com/([^/]+/[^.]+)", url)
            if match:
                repo = match.group(1)
                return repo.replace(".git", "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None

def fetch_github_issues() -> List[Dict]:
    """Fetch open issues from the current GitHub repository."""
    repo = get_github_repo()
    if not repo:
        return []
    
    try:
        # Use gh CLI to fetch issues
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "open", "--json", "number,title,body", "--limit", "100"],
            capture_output=True, text=True, check=True
        )
        issues = json.loads(result.stdout)
        return issues
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        print("⚠️  Could not fetch GitHub issues. Make sure 'gh' CLI is installed and authenticated.")
        return []

def get_existing_experiment_numbers() -> set:
    """Get issue numbers from existing experiment folders."""
    base = Path("experiments")
    if not base.exists():
        return set()
    
    numbers = set()
    for folder in base.iterdir():
        if folder.is_dir():
            # Check if folder name matches pattern: number-name
            match = re.match(r"^(\d+)-", folder.name)
            if match:
                numbers.add(int(match.group(1)))
    return numbers

def slugify_title(title: str, max_length: int = 50) -> str:
    """Convert issue title to a valid folder name."""
    # Remove special characters and convert to lowercase
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    # Replace spaces with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate if too long
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug

def get_issue_by_number(issue_num: int) -> Optional[Dict]:
    """Get a specific issue by its number."""
    issues = fetch_github_issues()
    for issue in issues:
        if issue["number"] == issue_num:
            return issue
    return None

def list_available_issues() -> None:
    """List all available GitHub issues that don't have experiments yet."""
    issues = fetch_github_issues()
    if not issues:
        print("⚠️  No GitHub issues found or unable to fetch issues.")
        return
    
    existing_numbers = get_existing_experiment_numbers()
    available_issues = [i for i in issues if i["number"] not in existing_numbers]
    
    if not available_issues:
        print("ℹ️  All open issues already have corresponding experiments.")
        return
    
    print("📋 Available GitHub issues for new experiments:\n")
    for issue in available_issues:
        exp_name = f"{issue['number']}-{slugify_title(issue['title'])}"
        print(f"  #{issue['number']:3d}: {issue['title'][:60]}")
        print(f"       → pixi run create-experiment {issue['number']}")
        print()
    
    print("\n💡 To create an experiment from an issue, run:")
    print("   pixi run create-experiment <issue_number>")
    print("\n   Or run without arguments for interactive selection.")

def select_github_issue() -> Optional[Dict]:
    """Present a selector for available GitHub issues."""
    # Check if we're in an interactive terminal
    if not sys.stdin.isatty():
        return None
        
    issues = fetch_github_issues()
    if not issues:
        return None
    
    existing_numbers = get_existing_experiment_numbers()
    # Filter out issues that already have experiments
    available_issues = [i for i in issues if i["number"] not in existing_numbers]
    
    if not available_issues:
        print("ℹ️  All open issues already have corresponding experiments.")
        return None
    
    # Use simple numbered list instead of questionary to avoid compatibility issues
    print("\n📋 Select a GitHub issue to base the experiment on:\n")
    for idx, issue in enumerate(available_issues, 1):
        print(f"  {idx}. #{issue['number']}: {issue['title'][:60]}")
    print(f"  {len(available_issues) + 1}. [Skip - create experiment without issue]")
    
    try:
        choice = input("\nEnter selection number (or press Enter to skip): ").strip()
        if not choice:
            return None
        
        choice_num = int(choice)
        if choice_num == len(available_issues) + 1:
            return None
        elif 1 <= choice_num <= len(available_issues):
            return available_issues[choice_num - 1]
        else:
            print("⚠️  Invalid selection.")
            return None
    except (ValueError, KeyboardInterrupt, EOFError):
        return None

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

DESIGN_ORG_FROM_ISSUE_TEMPLATE = """\
#+TITLE: {exp} Design
#+GITHUB_ISSUE: #{issue_number}

* Issue: {issue_title}

{issue_body}

* Implementation Plan
[TODO] Add implementation details here.

* Changelog
** [YYYY-MM-DD] Initial version
Created experiment scaffolding from GitHub issue #{issue_number}.
"""

DESIGN_MD_FROM_ISSUE_TEMPLATE = """\
# {exp} Design

**GitHub Issue:** #{issue_number}

## Issue: {issue_title}

{issue_body}

## Implementation Plan

[TODO] Add implementation details here.

## Changelog

### [{date}] Initial version
Created experiment scaffolding from GitHub issue #{issue_number}.
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

def scaffold_experiment(exp: str, issue: Optional[Dict] = None) -> None:
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

    if issue:
        # Create design files from GitHub issue
        design_org_content = DESIGN_ORG_FROM_ISSUE_TEMPLATE.format(
            exp=exp,
            issue_number=issue["number"],
            issue_title=issue["title"],
            issue_body=issue.get("body", "No description provided.")
        ).replace("[YYYY-MM-DD]", today)
        (folder / "design.org").write_text(design_org_content)
        
        design_md_content = DESIGN_MD_FROM_ISSUE_TEMPLATE.format(
            exp=exp,
            issue_number=issue["number"],
            issue_title=issue["title"],
            issue_body=issue.get("body", "No description provided."),
            date=today
        )
        (folder / "design.md").write_text(design_md_content)
    else:
        # Use default templates
        design_content = DESIGN_ORG_TEMPLATE.format(exp=exp).replace("[YYYY-MM-DD]", today)
        (folder / "design.org").write_text(design_content)
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
    # Check for command-line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        # Check if it's a number (issue number)
        try:
            issue_num = int(arg)
            issue = get_issue_by_number(issue_num)
            
            if not issue:
                sys.exit(f"⚠️  Issue #{issue_num} not found or not accessible.")
            
            # Check if experiment already exists
            existing_numbers = get_existing_experiment_numbers()
            if issue_num in existing_numbers:
                sys.exit(f"⚠️  An experiment for issue #{issue_num} already exists.")
            
            name = f"{issue['number']}-{slugify_title(issue['title'])}"
            print(f"📋 Creating experiment '{name}' from issue #{issue['number']}")
            scaffold_experiment(name, issue)
            
        except ValueError:
            # It's not a number, treat it as an experiment name
            name = arg
            print(f"📋 Creating experiment '{name}'")
            scaffold_experiment(name, None)
    else:
        # No arguments - interactive mode or list issues
        if not sys.stdin.isatty():
            # Non-interactive terminal - list available issues
            list_available_issues()
        else:
            # Interactive mode - try to select a GitHub issue first
            issue = select_github_issue()
            
            if issue:
                # Generate experiment name from issue
                name = f"{issue['number']}-{slugify_title(issue['title'])}"
                print(f"\n📋 Creating experiment '{name}' from issue #{issue['number']}")
            else:
                # Fall back to manual name entry
                try:
                    name = questionary.text("New experiment name:").ask()
                    if not name:
                        sys.exit("No name provided.")
                except (KeyboardInterrupt, EOFError):
                    sys.exit("\n⚠️  Cancelled.")
                except Exception as e:
                    sys.exit(f"⚠️  Error getting experiment name: {e}")
            
            scaffold_experiment(name, issue)
