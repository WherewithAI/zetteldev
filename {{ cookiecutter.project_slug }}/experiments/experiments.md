

# Experiments

There are two guiding principles:

1. Most work happens within `experiment` subfolders, which have a structure described below. Think of an experiment as the code/computation/data that produces one set of related figures for a paper.
2. Everything performed in an experiment is specified by a `design.md` file in the experiment root: a design specification which describes exactly how the experiment should be run in precise language.

As a coding agent, you will usually be asked to perform some task in an experiment folder. BEFORE DOING ANYTHING ELSE, read the `design.md` file to understand what the experiment should do. You may be asked to implement this design from scratch, or to update the existing code to match the design.

design.md might mirror a github issue. If so, then use the `gh` command to comment on the issue with minimal descriptions of completed implementations.

If you notice discrepancies between the existing code and the design spec, please bring this to my attention.

## Experiment Structure

The repo is structured like this:

```
.
├── experiments
│   ├── 1-example-experiment
│   │   ├── design.md
│   │   ├── report.qmd
│   │   ├── main.py
│   │   ├── Snakefile
│   │   ├── processed_data/
│   │   ├── figures/
│   │   └── tests/
│   ├── 2-concise-description
│   │   └── ...
├── {library_name}
│   ├── utils.py
│   ├── visualization.py
│   └── ...
├── infra
├── gambols

├── pixi.toml
├── .gitattributes
└── ...
```

You'll notice that each experiment folder is prepopulated with this template:
- `design.md`: The design spec described above. The source of truth for the experiment.
- `Snakefile`: Defines at least two rules—(1) run main.py, (2) render report.qmd. These will be explained below!
- `main.py`: Main Python script controlling the experiment's logic.
- `report.qmd`: Quarto file for generating the final output (HTML) and rendering figures.
- `processed_data/`: Holds intermediate or final data outputs. Synced via Git LFS if desired
- `figures/`: Store images, plots, or other visuals for your report
- `tests/`: Contains experiment-specific Pytest files for unit or integration testing

Here's how each of these works.

### Snakemake & Snakefiles
The snakefile specifies a DAG of computations associated to each experiment.
- Every experiment script must have corresponding Snakefile rule.
- Rules must specify inputs, outputs, and shell/run commands. Prefer Snakemake's 'script' option, so it automatically tracks changes to the files and makes snakemake metadata accessible to the files.
- Example rule structure:
```
rule run_main:
    input:
        data = "../../data/foo.arrow" # placeholder
    output:
        # main.py outputs
    params:
        # miscellaneous arguments to script - hardcoded CONSTANTS, and other parameters set by researchers
    script:
        "main.py"
```
- Update Snakefile when adding/modifying experiment scripts.
- Always define an `all` rule so the entire experiment can be run with `pixi run snakemake`.

### Python Scripts
- Anything that requires substantial computation should get its own python script. The results of computations should always be saved in the `./processed_data` folder in the experiment directory.
- If an experiment's design spec calls for multiple stages of computation, put these in separate python files.
- Scripts will be called from snakemake. Define and reuse snakemake variables instead of defining cumbersome argparsing or hard-coding anything in the script.
```python
from snakemake.script import snakemake # direct access to Snakefile variables
data_input = snakemake.input.data
```
- Secrets will be loaded from a .env file. Use python's `dotenv` to make these available.

### Quarto Reports
We use Quarto for visualizations and analysis. The design spec will specify figures; these should be coded in the `report.qmd` file, which loads the results of heavy computation performed in the python scripts and analyzes them. A snakemake rule then renders the report into HTML, for analysis by the principal investigator.

- Make all figures beautiful. They should be publication quality, with descriptive (but not jargon-laden) axis labels and tasteful color schemes (e.g. seaborn).
- In addition to rendering figures inline in report.qmd, save them as .svg files in the ./figures folder.
- Prefer `great_tables` for table rendering. Save any rendered table to a .tex file in ./figures.

### Testing
Always write and perform two types of tests.

1. *Is it doing what the design.md spec wants?* While writing scripts, write corresponding tests in the `./tests` folder, using Pytest. Execute these with `pixi run test` (which executes `pytest --cov=src --cov=experiments --cov-report=term-missing`) or `pixi run pytest file`. Because there are multiple experiment directories, include the current experiment name in any tests you write to prevent collisions.
2. *Does it run without errors?* In all scripts, respect a `test_run` parameter (set globally in the Snakefile) which performs only the bare minimum computation to use all bits of the code. For example, process a tiny subset of the input data; do only 2 epochs of training; use only 2 rounds of monte-carlo sampling. After implementing an experiment, set the `test_run` to true and run `pixi run snakemake all`. Ensure the full pipeline works.


## GitHub Issue Integration

After completing a task, always stage the relevant files and commit them to git with a short, descriptive commit name.

If the experiment is associated with a GitHub issue (check `**GitHub Issue:**` in design.md):
- When making changes that ARE described in the design.md: Comment on the issue with minimal descriptions of completed implementations
- When making changes that are NOT described in the design.md: Leave a comment explaining what was changed and why (e.g., bug fixes, optimizations, additional features discovered during implementation)

Use the `gh` command to interact with issues, for example:
```bash
gh issue comment <issue_number> -b "Implemented the data preprocessing pipeline as specified in the design doc."
```
