# THE SETUP GUIDE

(For a repository cut from the Zetteldev template: what the template cannot set up, and the one command that says what is still missing. Written 2026-10-04.)

## WHAT THE TEMPLATE GIVES YOU, AND WHAT IT CANNOT

A repository cut from the template holds the method, the packs, the tooling, the registries with their example blocks, and the scaffolder. It does not hold your hosts, your keys, your clones on the other machines, or the processes that have to be running for the tools to answer. Those live in four places, the four sections below, and `just doctor` reports each of them as one line with a verdict: `ok`, `WARN` (the tools work, but a pack leans on something that is missing, or a value sits in the wrong layer), or `FAIL` (a tool will not work until this is fixed). A red line names the section here that fixes it. `just doctor --here` skips the cluster and the instance. An agent in a fresh repository reads this file and runs that command, rather than finding each gap by failure.

## PER PERSON, ONCE, OUTSIDE ANY REPOSITORY

- **`~/.config/zetteldev/config.toml`**, a `[zetteldev]` table, holds what differs per person: the ssh aliases of the cluster's login node and of the notebook instance (`della_host`, `solveit_host`), your directory on the cluster's scratch (`della_user_scratch`, from which the models, the serving venvs and the DVC cache are derived), and the compute host. A `[zetteldev.<repo>]` table applies to one repository. Everything shared by everyone on a repository lives in its `pyproject.toml` instead (the next section), and `python3 .zetteldev/config.py` prints every resolved value, `config.layers()` which layer it came from.
- **`~/.ssh/config`** carries one alias per host with `ControlMaster auto`, `ControlPersist yes` and a `ControlPath`; the cluster aliases reach their login nodes through the gateway with `ProxyJump`, and the instance alias has its own key. The masters are not optional: the gateway counts new connections per address and locks out a chatty one for an evening, and every wrapper in `.zetteldev` rides one multiplexed connection.
- **`~/.ssh/agent.sock`** is a symlink the login shell keeps pointing at the live agent, so cron jobs and resumed sessions find it. The notebook sync, the data cycle and the pointer push all set `SSH_AUTH_SOCK` to it.
- **Claude Code skills** are installed at user level, in `~/.claude/skills`, never in a repository. The packs lean on these, and a user who leaves one uninstalled drops the matching pack's import line from `CLAUDE.md` or ignores that section: `persistent-python` and `pyskills` (the harness pack; from the Answer.AI coding harness checkout, symlinked); `marimo-pair` (the marimo pack; from marimo-team/marimo-pair); `solveit-client` (the reference behind `sicx` in the SolveIt pack; `uv tool install solveit_client`); `vllm-model-setup` and `della-gpu` (the cluster pack's helpers for a new model and a GPU watch); `fastanki` (the flashcards workflow; needs the `fastanki` package). The doctor reports a missing one as a warning naming the pack, never as a failure.

## PER REPOSITORY, IN PYPROJECT.TOML AND THE REGISTRIES

- **`[tool.zetteldev]`** in `pyproject.toml`: the hosts everyone on the repository shares, the SLURM account (`della_account`), the group's scratch fileset (`della_group_scratch`), the figures URL, the compute host. **`[tool.uv.sources]`** declares `zetteldev = { path = ".zetteldev", editable = true }` and the dependency list names `zetteldev`; without those two lines nothing in the packs imports.
- **`.env`**, never committed, with the keys the tools read by name: the Cloudflare trio for figures (`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_R2_ACCESS_KEY_ID`, `CLOUDFLARE_R2_SECRET_ACCESS_KEY`), `WANDB_API_KEY`, `DATALAB_KEY` for `mdify-paper`, `ANKI_USER` and `ANKI_PASS` if the flashcards skill is used, and whatever the experiments' providers need.
- **The registries**: `.zetteldev/della/targets.yaml`, one block per model you will serve, whose group values are `${setting}` placeholders the loader resolves from config (so a new repository serves the same targets on its first day, and another group changes one file); `.zetteldev/services.yaml` for anything long-lived; `.zetteldev/dvc_experiments.txt` naming the experiments the sweep may track.
- **Data**: `dvc init`, a `.dvc/config` with the cluster as the default remote and the workstation as the second, a `.dvc/config.local` per machine (below), and the three-line `.gitignore` rule that ignores `processed_data` yet admits its directories, its `*.dvc` pointers and the ignore files DVC writes. `.dvc/config.local` is per machine and is never committed; `.dvc/config` is per repository and carries no machine's forwarded port.
- **Papers**: `just new-paper <slug>` scaffolds `papers/<slug>/` with its `paper.yaml` naming the Workshop source and the Overleaf repository; the manuscripts stay in the repository, the machinery is the template's.

## THE WORKSTATION

The repository checkout and `uv sync`. Two cron lines with `SSH_AUTH_SOCK` set on them: the notebook sync (`solveit_sync.sh`) and the data cycle (`just data sync`). `just della-status run` in a tmux window, the one poller every watch reads. The DVC remote to the cluster rides a port forwarded over the control master (`della-master` re-arms it), and the `.dvc/config.local` here names that forwarded URL for the cluster remote and a local path for the workstation's own. The Dask cluster, if `compute_host` is this machine.

## THE CLUSTER

A clone at `della_repo` on the login node with a GitHub key, since pointer commits leave from there. The venv (`uv sync`, or `uv pip install` of what the sync refuses). The scratch directories the config names: the DVC cache (`della_dvc_cache`), the models (`della_models`), the serving venvs (`della_envs`, with `della_vllm_venv` the default). A `.dvc/config.local` that points the cache at scratch with hardlinks and names the self-remote as a local path. The gate charges `della_account` to any script that names no account of its own.

## THE INSTANCE

A clone at `solveit_root` with `receive.denyCurrentBranch=updateInstead` and the workstation's key authorised, since the sync pushes into it and fast-forwards its tree. `dvc` installed into the container's Python, off the PATH (`just data` finds it). A `.dvc/config.local` with the workstation as the default remote and hardlinks. The figure keys and any provider keys in the instance's settings, which reach a kernel at its next start.

## PER EXPERIMENT, LAID DOWN BY THE SCAFFOLDER

`design.md` pointing at the zettel; the chronicle notebook; a `Snakefile` that includes the shared hooks; `.solveit-dialog` naming the dialog; `.dvcpull` naming what the notebooks read; `rules/` for exported snakerules; a `conf/` tree when `--hydra` is given. An experiment that predates the scaffolder's stubs is reported by the doctor as one summarised warning per stub.

## WHAT JUST DOCTOR CHECKS

Each item above, as a probe with a one-line verdict: the config keys the tools read, resolved, and which layer each came from (a per-person value in the shared layer is a warning); each ssh alias has a Host entry with a master; the agent socket resolves; the user-level skills, as warnings naming the pack; the editable dependency; the `.env` names; the registries parse and `zetteldev` imports from the venv; `.dvc/config` has a remote and `.gitignore` admits pointers; the experiments' stubs, summarised; the cron lines, the poller and the age of its status file, the two masters and their forwards; on the cluster, the clone's branch against origin as known here, its venv's `dvc`, the cache, weights and venv directories, its `.dvc/config.local`; on the instance, the push setting, `dvc`, its `.dvc/config.local`, and the server answering on the forwarded port. It starts nothing, opens no connection the masters do not hold, and walks no data, so it finishes in seconds; `HOME=$(mktemp -d) just doctor --here` shows what red looks like without removing anything.
