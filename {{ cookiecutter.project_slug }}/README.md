# About this Repo

This repository is a research notebook, cut from the [Zetteldev](https://github.com/WherewithAI/zetteldev) template: a way of working in which an experiment is the unit of analysis, a notebook is the seat of every consequential line of code, and the machinery around them (a cluster, a notebook host, a data store, a figure bucket) is reached through one set of tools that every Zetteldev repository shares. The agents that work here read the same instructions a person would: `CLAUDE.md` imports the *packs* under `.zetteldev/agents/`, and `AGENTS.md` is the same text inlined for tools that do not follow imports.

Setting the repository up on a machine is the business of the setup guide, `.zetteldev/agents/setup.md`, and of one command that says what is still missing:

```sh
uv sync          # the environment, including the tooling package in .zetteldev
just doctor      # one line per item of the guide, with a verdict; --here skips the cluster and the notebook host
```

## Library code vs experiment code

The library is one place; the lab is another. Default Python projects do not respect that division, and this one does.

1. `experiments/` holds everything an experiment is: its design, its notebooks, the scripts that run it at scale, its data and its figures. One repository holds many experiments, each in its own numbered folder, so that several people can work on different experiments without fearing a merge conflict. Think of an experiment as the code, computation and data that produce one set of related figures for a paper.
2. `{{ cookiecutter.project_slug }}/` holds the Python library, importable from any experiment with `import {{ cookiecutter.project_slug }}`. It houses the logic shared between experiments, and most of it is exported there from notebooks by nbdev (below).

```
.
├── experiments
│   ├── 1-example-experiment
│   │   ├── design.md                 (a stub pointing at the zettel that designs the experiment)
│   │   ├── 00-example-big-picture.ipynb   (the running chronicle: every run, variation and finding)
│   │   ├── 01-foundational-notebook.ipynb (the method, developed and exported from here)
│   │   ├── demos/                    (marimo notebooks: interactive analysis of results)
│   │   ├── Snakefile                 (what runs at scale, and where its outputs go)
│   │   ├── scripts/                  (what the Snakefile orchestrates)
│   │   ├── processed_data/           (data, never in git; tracked by DVC, the cluster the store)
│   │   ├── figures/
│   │   ├── tests/
│   │   ├── .dvcpull                  (what this experiment's notebooks read)
│   │   └── .solveit-dialog           (the notebook's name on the notebook host)
│   └── 2-another-experiment
├── {{ cookiecutter.project_slug }}/          (the library)
├── nbs/                              (the library's own notebooks, if it has any)
├── .zetteldev/                       (the tooling, one editable package; its agents/ are the packs)
├── pyproject.toml                    ([tool.zetteldev] names what everyone on the repository shares)
└── justfile                          (every recipe; `just --list`)
```

A new experiment comes from `just create-experiment <name>`, which lays down every file above, numbers the folder, and names the dialog. The method itself, the conversation between a zettel, a set of notebooks and a Snakefile, is the first pack: `.zetteldev/agents/zetteldev.md`.

## Running things at scale: Snakemake and the cluster

Each experiment's `Snakefile` names what script performs what computation, where its outputs land and what parameters it is given, so that a run is a rule and a rerun is free when nothing upstream changed. CPU-sized rules run here with `uv run snakemake`; anything that wants a GPU runs on the cluster, where a rule's SLURM shape comes from a model's block in the target registry, `.zetteldev/della/targets.yaml`, and `just snake-della <experiment> <target>` drives it from this machine. Single jobs go through the submission gate, `just della-sbatch`, which checks that the checkout is clean and pushed, lints the script, runs its preflight lines and records the commit the job ran. Long-lived servers a notebook calls, a retrieval index or a chat model, are named in `.zetteldev/services.yaml` and reached with `just service up|tunnel|down`. All of this is the cluster pack, `.zetteldev/agents/della.md`, written from a season of failures that each cost compute.

## Data

Data lives on the cluster and is versioned by DVC. A result directory is tracked by the machine that made it, which hashes its contents into a cache and writes a small pointer file beside it; git commits the pointer, never the data. The cluster's cache *is* the store: it never pushes, the workstation reaches it over ssh and relays to the notebook host, and no cluster credential leaves the workstation. Each experiment's `.dvcpull` names the pointers its notebooks read, and that list is what every machine pulls; nothing pulls by size. A job through the gate names its outputs with `--dvc`, a Snakemake workflow tracks its outputs through the shared hooks, and a sweep on the cluster catches what was missed, so nobody tracks by hand.

```sh
just data pull [experiment]     # fetch the lists
just data status [experiment]   # each pointer's state, and what is untracked
just data sync                  # the hourly cycle: pull, push the cache to the cluster, commit pointers, pull on the notebook host
```

The doctrine is the data section of `.zetteldev/agents/zetteldev.md`; the cluster's share of the mechanics is in `della.md`.

## nbdev: notebooks that export the library

A notebook that develops a method is also its source. Cells marked `#|export` are written to the module the notebook names with `#|default_exp`, so `{{ cookiecutter.project_slug }}/` is built from `nbs/` and from the experiments' notebooks rather than typed beside them. `just nbdev-export <notebook>` exports one notebook and commits the module; a light edit to an exported file is carried back with `nbdev-update`. The autonomous report an agent leaves behind is written in this fashion, with its commentary in `>` blockquotes so that the author's words and the agent's are never confused; the conventions are in the method pack.

## SolveIt: where notebooks are reviewed and edited

The numbered notebooks are opened on SolveIt, a cloud instance that gives Jupyter a next-generation face and an AI of its own; each experiment names its dialog in `.solveit-dialog`. Once a dialog is open there, the instance's copy is the living one, and every edit goes through `just sicx <cmd>`: list, add, edit, run, bootstrap a fresh kernel, dump a run of cells. An hourly sync (`just solveit-sync`) commits what the server auto-saved on the instance, merges it here, pushes to GitHub and fast-forwards the instance's checkout, with guards against a dialog writing an older state over newer work. The instance reaches only this workstation, so code, pointers and data all travel through here. The pack is `.zetteldev/agents/solveit.md`.

## marimo: the living workbench

When the author sits beside the agent, the finished report gives way to a reactive notebook in the experiment's `demos/` folder: interactive visualization, exploratory interpretability, the analysis of results already produced. A marimo notebook reads what the numbered notebooks and the cluster have made and turns it over in the hand; it does not define the method, and what a demo discovers is promoted back into the numbered notebooks. Notebooks are served through Mo's Notebooks and reached with `mo pair` and `mo code`; the pack is `.zetteldev/agents/mo.md`, and the e-ink skin in `.zetteldev/eink.css` is every notebook's default.

## Keeping the tooling current

The tooling under `.zetteldev` is shared with every Zetteldev repository. A change is tried in the repository where the work is, and once it has proven itself it is lifted into the template; a repository that did not originate a change takes it with

```sh
just zdev-update        # syncs .zetteldev, the lint hook, the quiz skill and the tooling tests; never a repository's registries
```

which also rebuilds `AGENTS.md`, since a changed pack leaves the inlined copy stale. To start another repository from the template:

```sh
uvx --from cookiecutter cookiecutter gh:WherewithAI/zetteldev
```
