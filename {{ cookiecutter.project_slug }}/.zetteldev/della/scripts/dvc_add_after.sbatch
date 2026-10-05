#!/bin/bash
#SBATCH --job-name=dvc-add
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
# The follow-up job `della-submit --dvc PATH …` queues with --dependency=afterany:<job>: when the job has ended, whatever its
# state, track its declared output paths with `dvc add` (local work on GPFS, no network, so an airgapped node will do), and
# leave the pointer files in the checkout for the login node's status tick to commit (`just data commit-pointers --push`).
# DVC_PATHS holds the paths, space-separated, relative to the repository root. A path that does not exist is reported and
# skipped: a job that produced nothing has nothing to track.
set -euo pipefail
REPO="${REPO_DIR:?REPO_DIR must name the checkout; the gate exports it}"
cd "$REPO"
[[ -n "${DVC_PATHS:-}" ]] || { echo "dvc-add: DVC_PATHS is empty; nothing to do"; exit 0; }
present=()
for p in $DVC_PATHS; do
    if [[ -e "$p" ]]; then present+=("$p"); else echo "dvc-add: $p does not exist; skipped"; fi
done
[[ ${#present[@]} -gt 0 ]] || exit 0
echo "dvc-add: tracking ${present[*]}"
# the add stages its pointer (core.autostage) and so takes git's index lock, which the login node's status tick holds for a
# moment every five minutes; a collision is retried rather than failed
for attempt in 1 2 3 4 5; do
    if .venv/bin/dvc add "${present[@]}"; then break; fi
    [[ $attempt -lt 5 ]] || { echo "dvc-add: giving up after $attempt attempts"; exit 1; }
    echo "dvc-add: attempt $attempt failed (index lock?); retrying in 30 s"; sleep 30
done
for p in "${present[@]}"; do cat "$p.dvc"; done
echo "DVC_ADD_DONE"
