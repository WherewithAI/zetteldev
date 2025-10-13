# Development

## Dev Container Quickstart

1. Install the VS Code **Dev Containers** extension and ensure Docker Desktop (or the Docker Engine) is running.
2. Clone the repository, open it in VS Code, and run `Dev Containers: Reopen in Container`.
3. The repo mounts at `/workspaces/{{ cookiecutter.project_slug }}` inside the container. Shared caches live under `/caches/*`.
4. After the container starts, run `zdev docs update` to sync organisation agent guidance files.
5. Run `pixi install` (the `postCreateCommand` does this automatically) and then `pixi run postinstall`.

### GPU Hosts

The default image is `ghcr.io/wherewithai/zdev:cuda-12.4`. If your machine has a CUDA-capable GPU, enable it by creating `.devcontainer/devcontainer.local.json` with:

```json
{
  "runArgs": ["--gpus", "all"]
}
```

For CPU-only machines, you can switch to the CPU image:

```json
{
  "image": "ghcr.io/wherewithai/zdev:cpu"
}
```

### Local (No Container) Setup

If you prefer running directly on the host, install git-lfs (e.g. `brew install git-lfs`), install [Pixi](https://pixi.sh) (`brew install pixi` or the script below), then follow the package management section.

## Package Management

We use Pixi, a modern Poetry-like package manager that supports declarative installation of conda *and* pip packages. There may be no 'one true' Python package manager, but Pixi is the 'one true' Python package manager. Behold it and weep! (As, on hearing the Good News, did one past labmate, who had previously spent up to one day a week wrestling with conda/pip incompatibilities and breaking CUDA environments.)

First install Pixi with `brew install pixi`, or

```sh
curl -fsSL https://pixi.sh/install.sh | bash
```

Then clone the repo and create the project environment by running

```sh
pixi install # downloads all python packages
pixi run postinstall # installs the '{{ cookiecutter.project_slug }}' package and creates a jupyter kernel
```

To add packages,

```sh
pixi add conda-package
pixi add --pypi pip-only-package
```

To run things in this environment, you have a few options

```sh
pixi shell # like 'conda activate'; changes Python in path to that of your project
pixi run python script.py # to run python scripts, just like Poetry
pixi run snakemake rule_name # to run with the DAG powerful *snakemake* -- see below!
```

Indeed, you can define custom pixi commands for a project in `pyproject.toml`, as we've done, e.g. with `pixi run test` (run pytest).

To use Jupyter notebooks with the Pixi kernel, either select the `{{ cookiecutter.project_slug }}-zetteldev` kernel we created with postinstall—or just launch a new Jupyter session with `pixi run notebooks`.

## zdev Helper

Inside the container, the `zdev` helper manages the runtime environment:

- `zdev shell` — start an interactive shell with caches and dotenvs loaded.
- `zdev jupyter` — launch Jupyter Lab bound to `127.0.0.1`.
- `zdev net log-on|log-off` — toggle the optional egress logging proxy.
- `zdev agents update` — update the `claude-code` and `openai` CLIs into `~/.local/zdev/npm`.
- `zdev docs update` — refresh `~/.claude/CLAUDE.md` and `~/AGENTS.md`.
- `zdev doctor` — check cache mounts, GPU visibility, and proxy state.

Before handing the session back (especially after using credentials) run `zdev auth clear` to open a shell with sensitive variables removed.

## Dotenv & Secrets

- Project-specific secrets: `./.env.local` (git ignored).
- Machine-wide overrides: `~/.config/zdev/.env.local`.
- Runtime environment variables always win over dotenv files.

Common keys include `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GH_TOKEN`, and overrides for cache locations. Never commit these files.

## Library code vs Experiment code

As academics, we understand this: the library is one place; the lab is another. Sadly, default Python projects don't understand this, and have several times made quite a mess by bringing hydrochloric acid and liquid nitrogen into Firestone. Good thing *this* project respects that division. 

1. The '/experiments' folder holds all of the code/data/analyses involved in experiments: data wrangling logic, model training scripts, metric computations, and Quarto reports and jupyter notebooks detailing the results. It gets better. Who says one repository can hold only one experiment? We divide the analyses into distinct experiment subfolders, ala '/experiments/homogenization-metrics-sanity-check'. This allows multiple people to work on different experiments independently without fearing merge conflicts. Think of an experiment as the code/computation/data that produces one set of related figures for a paper.
2. The '/{{ cookiecutter.project_slug }}' folder holds the Python library, which can by imported in any experiment with `import {{ cookiecutter.project_slug }}`. This houses the logic shared between experiments.

Thus, the repo is structured like this:

```
.
├── experiments
│   ├── example_experiment
│   │   ├── design.md
│   │   ├── report.qmd
│   │   ├── main.py
│   │   ├── Snakefile
│   │   ├── processed_data/
│   │   ├── figures/
│   │   └── tests/
│   ├── another_experiment
│   │   └── ...
├── {{ cookiecutter.project_slug }} 
│   ├── utils.py
│   ├── visualization.py
│   └── ...
├── pyproject.toml
├── .gitattributes
└── ...
```

You'll notice that each experiment folder is prepopulated with this template:
- `design.md`: Describe goals, motivation, and any to-dos as Markdown task lists
- `report.qmd`: Quarto file for generating the final output (HTML)
- `main.py`: Main Python script controlling the experiment's logic
- `Snakefile`: Defines at least two rules—(1) run main.py, (2) render report.qmd. These will be explained below!
- `processed_data/`: Holds intermediate or final data outputs. Synced via Git LFS if desired
- `figures/`: Store images, plots, or other visuals for your report
- `tests/`: Contains experiment-specific Pytest files for unit or integration testing

To make a new experiment subfolder with this structure, run `pixi run create-experiment`. 


## Become Omnipotent with Snakemake!

[Snakemake](https://snakemake.readthedocs.io/en/stable/) is a 'workflow management system for scalable and reproducible data analyses'. It was developed by a team of computational biologists who, after spending years (mis)typing intricate commands into terminals, achieved Workflow Enlightenment and realized they should write their complex commands down in a file, associate them with 'tasks' that could be invoked with simple commands, and define input-output rules to create an elegant Directed Acyclic Graph of task dependencies.

This ties very nicely with our reproducible experiment folders. Each experiment folder has a 'Snakefile' which describes at least two computations performed by the experiment. By default, something like this:

```
rule run_main:
	input:
		# Define any input files here, e.g. "../some_global_data.csv"
		script = "main.py"
		dataset = "../data/MNIST",
		annotations = "../data/annotations_path.csv"
	output:
		# If main.py produces new data files, list them here
		trained_classifier = "processed_data/MNIST_Forward_forward.pt",
		predictions = "processed_data/MNIST_forward_forward_preds.pkl"
	script:
		"pixi run {input.script} --datapath {input.dataset} --labels {input.annotations} "

rule render_report:
	input:
		report = "report.qmd",
		predictions = "processed_data/MNIST_forward_forward_preds.pkl"
	output:
		# The rendered HTML goes into ../../reports/
		"homogeneity-under-random-words.html"
	shell:
		"quarto render report.qmd --output homogeneity-under-random-words.html"
```
 
The first executes the experiment's main python script against a dataset and annotations to train a 'forward forward' model. The second produces an HTML file with the results, which can also include images and descriptive text. 

Snakemake can even write and submit slurm scripts on your behalf, letting you run computations on clusters just by invoking 'pixi run snakemake rule_name'. See the snakemake slurm executor plugin.

## Data 

Store raw artifacts to be used by many experiments in `/data`. Store anything large produced by an experiment (e.g. model checkpoints, processed datasets, classifications) in the `processed_data` folder of the experiment.

Both are auto-synced to Git LFS, so you needn't worry about ignoring or excluding them.


## This is quite an idiosyncratic repo! What is it based on?

The burgeoning `Zetteldev` framework from WherewithAI, which attempts to realize the long-held dream of *literate programming* in the most cognitively ergonomic version to-date. 

You can set up a Zetteldev repo for yourself with [Cookiecutter](https://github.com/cookiecutter/cookiecutter).

```
cookiecutter gh:WherewithAI/zetteldev
```
