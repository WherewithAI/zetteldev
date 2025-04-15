#!/usr/bin/env python3
"""
Create a new experiment directory with standard files and structure.
"""
import sys
import os
from pathlib import Path
import questionary

# Template files for a new experiment
SNAKEMAKE_TEMPLATE = """rule run_main:
    input:
        # Define any input files here, e.g. "../some_global_data.csv"
    output:
        # If main.py produces new data files, list them here
    script:
        "main.py"

rule render_report:
    input:
        "report.qmd"
    output:
        # The rendered HTML goes into ../../reports/
        "{experiment_name}.html"
    shell:
        "quarto render report.qmd --output {experiment_name}.html"
"""

MAIN_PY_TEMPLATE = """#!/usr/bin/env python3
\"\"\"
Main script for {experiment_name} experiment.
\"\"\"

def main():
    print("Running {experiment_name} experiment...")

if __name__ == "__main__":
    main()
"""

REPORT_QMD_TEMPLATE = """---
title: "{experiment_name} Report"
format:
  html:
    code-fold: true
    code-tools: true
    code-summary: "Show the code"
    theme: cosmo
    toc: true
    toc-depth: 3
    toc-location: left
    fig-width: 10
---


# {experiment_name}

This is the Quarto report for the **{experiment_name}** experiment.


## Setup and Imports

```{{python}}
%load_ext autoreload # leave these to always run latest available modules
%autoreload 2

import sys # modify these as needed
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
import random
from matplotlib.lines import Line2D
from IPython.display import display, Markdown
```

```{{python}}
# You can embed Python code here, referencing local data
print("Hello from Quarto in {experiment_name}!")

main()
```
"""

TEST_BASIC_TEMPLATE = """import pytest

def test_sanity_check():
    assert True, "Basic test for {experiment_name}"
"""

DESIGN_MD_TEMPLATE = """# {experiment_name} Design

Describe your experiment's motivation, approach, and tasks here.

Tasks:
    • …
"""

def scaffold_experiment(experiment_name: str):
    """Create a new experiment folder with standard files and structure.

    Args:
        experiment_name: Name of the experiment to create
    """
    base_dir = Path("experiments")
    exp_dir = base_dir / experiment_name

    if exp_dir.exists():
        print(f"Experiment '{experiment_name}' already exists.")
        sys.exit(1)

    # Create subfolders
    exp_dir.mkdir(parents=True)
    (exp_dir / "processed_data").mkdir()
    (exp_dir / "figures").mkdir()
    (exp_dir / "tests").mkdir()

    # Write design.md
    (exp_dir / "design.md").write_text(
        DESIGN_MD_TEMPLATE.format(experiment_name=experiment_name)
    )

    # Write report.qmd
    (exp_dir / "report.qmd").write_text(
        REPORT_QMD_TEMPLATE.format(experiment_name=experiment_name)
    )

    # Write main.py
    (exp_dir / "main.py").write_text(
        MAIN_PY_TEMPLATE.format(experiment_name=experiment_name)
    )

    # Write Snakefile
    snakefile_content = SNAKEMAKE_TEMPLATE.format(experiment_name=experiment_name)
    (exp_dir / "Snakefile").write_text(snakefile_content)

    # Write a basic test
    (exp_dir / "tests" / "test_basic.py").write_text(
        TEST_BASIC_TEMPLATE.format(experiment_name=experiment_name)
    )

    print(f"Experiment '{experiment_name}' created successfully at {exp_dir}.")

def main():
    # Interactive prompt for experiment name
    experiment_name = questionary.text("Enter a name for the new experiment:").ask()
    if not experiment_name:
        print("No experiment name provided. Exiting.")
        sys.exit(0)

    scaffold_experiment(experiment_name)

if __name__ == "__main__":
    main()
