# Shared Snakemake hooks. Include from an experiment's Snakefile with
#     include: "../../.zetteldev/snakemake/hooks.smk"
# and do not define onsuccess/onerror in the Snakefile itself: Snakemake keeps one handler of each kind.
# On success: publish the experiment's figures (the old per-Snakefile onsuccess) and track what the workflow wrote
# under processed_data with DVC (the sweep of .zetteldev/dvc_data.py: every entry no pointer covers is added, in an
# experiment listed in .zetteldev/dvc_experiments.txt; elsewhere it is only reported). The pointer files are committed
# by the machine's hourly cycle, and the other machines pull what their lists name. On failure: track anyway, since
# partial results are still results. (The Hub's small tier was retired 2026-10-04; nothing is pushed there any more.)
import os as _os, subprocess as _sp
_EXP = _os.path.basename(_os.path.abspath(workflow.basedir))
_REPO = _os.path.abspath(_os.path.join(workflow.basedir, "..", ".."))
_PY = _os.path.join(_REPO, ".venv", "bin", "python")

def _run(label, *cmd, timeout=900):
    print(f"[hooks.smk] {label}", flush=True)
    try: _sp.run(cmd, cwd=_REPO, check=False, timeout=timeout)
    except Exception as e: print(f"[hooks.smk] {label} failed: {e}", flush=True)

def track_outputs(why):
    _run(f"{why}: tracking {_EXP}'s processed_data with DVC", _PY, _os.path.join(_REPO, ".zetteldev", "dvc_data.py"), "sweep", _EXP, "--add", "--quiet-min", "0", timeout=3600)

def publish_figures():
    _run(f"publishing figures of {_EXP}", _PY, _os.path.join(_REPO, ".zetteldev", "publish_figure.py", ), "--sync", _EXP, timeout=600)

onsuccess:
    publish_figures()
    track_outputs("workflow finished")

onerror:
    track_outputs("workflow failed; tracking what it produced")
