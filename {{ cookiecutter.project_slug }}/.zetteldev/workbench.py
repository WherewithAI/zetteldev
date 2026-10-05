"""Where work runs in this repo, and the one call for each place: notebook on SolveIt, Dask on Athomia, services and Snakemake on Della, git and data synced from here.

The doctrine (the author's zettel "Walking with Phones", 2026-09-07) and the tools that make it the default:

1. **Code begins in a notebook on SolveIt.** Drive it from here with `just sicx …` or, in Python,
   `zetteldev.sicx` (`run(id)` is queue-safe and waits; `add`, `edit`, `bootstrap`, `out`, `slim`). Athomia is
   the source of truth for git: `git_sync()` (hourly by cron) merges SolveIt's auto-commits here, pushes origin,
   and fast-forwards SolveIt; modules are exported HERE from the committed dialog (`just solveit-export <ipynb>`).
2. **Interactive expensive computations** (minutes to an hour, tight loops) are defined in `#|export` cells and
   run through `zetteldev.compute`: `compute.map(fn, items)` on Athomia's Dask from any machine,
   `@compute.cached(dir)` so a rerun reads the earlier result. Della's GPUs are reached only as services.
3. **Services** (news RAG, Qwen chat, pooled embeddings) live in `.zetteldev/services.yaml`:
   `service_status()`, `just service up|tunnel|down <name>`, `zetteldev.services.url("rag")` for the URL a
   notebook should call. The RAG runs on della-vis2 without a job; the Qwen servers are SLURM jobs.
4. **Experiment-scale computations** (training, inference fleets) are Snakemake rules on Della:
   `snake_della(exp, target)`; a rule may own an sbatch array through `della-submit --sentinel`; rules can be
   written in the notebook in `#|snakerule` cells (exported to `rules/<nb>.smk`). Completion tracks what the
   workflow wrote with DVC (`.zetteldev/snakemake/hooks.smk`).
5. **Data** lives on Della and is versioned by DVC: the machine that made a result tracks it, git carries the pointer,
   and each machine pulls what its experiments' `.dvcpull` lists name (`data_sync()` is the hourly cycle,
   `data_status()` the report; `just data` has the rest). The Hub tiers were retired 2026-10-04.

Each function here is a thin wrapper over the same script the `just` recipe calls, so the notebook, the terminal
and the cron agree.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

__all__ = ["git_sync", "git_status", "data_sync", "data_status", "service_status", "snake_della", "export_notebook", "REPO"]

REPO = Path(__file__).resolve().parents[1]


def _run(*cmd, timeout=3600) -> str:
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return (r.stdout + r.stderr).strip()


def git_sync() -> str:
    "Commit SolveIt's dialog state, merge its branch here, push origin, fast-forward SolveIt (what the hourly cron does)."
    return _run("bash", ".zetteldev/solveit_sync.sh", "sync")


def git_status() -> str:
    "Ahead/behind counts against SolveIt and origin, dirty paths on both sides, last sync."
    return _run("bash", ".zetteldev/solveit_sync.sh", "status")


def data_sync() -> str:
    "The hourly DVC cycle: pull every experiment's lists, push this machine's cache to Della, commit pointers, pull the lists on SolveIt."
    return _run(".venv/bin/python", ".zetteldev/dvc_data.py", "sync")


def data_status(*experiments: str) -> str:
    "Each listed pointer's state against the workspace, then what under processed_data no pointer covers."
    return _run(".venv/bin/python", ".zetteldev/dvc_data.py", "status", *(experiments or ["--all"]))


def service_status() -> str:
    "Every registered service: where it runs, its health, its address."
    return _run(".venv/bin/python", ".zetteldev/services.py", "status", timeout=300)


def snake_della(experiment: str, target: str, *args: str) -> str:
    "Push code, pull it on Della, run a Snakemake target there under the Della profile, and return the log (blocks until the run ends)."
    return _run("bash", ".zetteldev/della/bin/snake-della", experiment, target, *args, timeout=6 * 3600)


def export_notebook(notebook: str) -> str:
    "Export a dialog's #|export cells to the project module and its #|snakerule cells to rules/<nb>.smk, then commit (run here, on the committed dialog)."
    return _run("just", "solveit-export", notebook, timeout=600)
