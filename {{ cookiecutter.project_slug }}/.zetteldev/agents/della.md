# DELLA: THE HPC CLUSTER

(For projects that run on Princeton's Della cluster: `della_host`, `della_repo` and `della_scratch` in `zetteldev.config`. Rewritten 2026-10-02 from a month's papercuts; each dated remark is a failure that has already cost compute.)

## WHAT DELLA IS, AND WHERE THINGS LIVE

Experiment-scale computation runs on Della: training, inference fleets, anything that wants an H100. Code reaches it by git, the checkout is `~/src/<repo>` (`della_repo`) under the account `henderson`, and results leave it by DVC (the data section of the method). Three places on disk matter:

- The checkout, `~/src/<repo>`: code, and every experiment's `processed_data`, which is where jobs write. Home is a 50 GB quota and is backed up by the university.
- The user's scratch (`della_user_scratch` in config): job logs (`<exp>_<name>_<JOBID>.log`), weights not in the shared cache (`models/`), merged checkpoints (`models/<exp>/<run>_step<N>`, each with a `MERGED_FROM` file), and the DVC cache that every result on the cluster lives in. Scratch is a 51 TiB group fileset at 95 percent, not backed up by the university; TigerData will back it up once access is granted, and the lists in the method put the results that matter on the other two machines.
- The weights cache (`della_weights_cache` in config, `$DELLA_CACHE` in a job): shared weights. Verify the exact directory name before using one (`Llama-3.1-8B-Instruct`, not `Meta-…`). A listed model can vanish (`Llama-3.1-8B-Instruct` left in July 2026), and an entry can be a husk whose real weights sit under the user's `models/` with their own venv (Qwen3.5).

Two GPU partitions: `pli-c` (H100, three-day limit) and `ailab` (H200, fifteen days); `cpu` for CPU work. The login node is for git, sbatch and light shell, never for a Python that works, since it reaps long processes; CPU-heavy work that is not a job belongs on a viz node.

## THE SSH MAP

All aliases in `~/.ssh/config` go through the tigress gateway and share a control master. `della` is the pli login node and the default. `della-standard` is the standard login node, used by the idle watch and for `sacct`. `della-gpu` is the GPU login node. `della-vis1` and `della-vis2` are visualisation nodes, where the retrieval service runs without a job and where OnDemand notebooks and index builds belong.

The gateway counts new port-22 connections per address and locks out a chatty one for an evening (2026-09-23: four hours of thirty-second polls from watchers whose master had died). Every wrapper in `.zetteldev` therefore calls `just della-master` first, which keeps one multiplexed connection alive and restarts it when it has died, so a hundred commands an hour are one handshake. The same master carries the port DVC rides (below).

## THE REGISTRY: ONE BLOCK, ONE MODEL

`.zetteldev/della/targets.yaml` is the only way a model is served. A target is one block inheriting `<<: *defaults` (account, cache) with `partition`, `model_path`, `tensor_parallel`, `tool_parser`, `max_model_len`, `runtime`, `vllm_extra`, `venv`, `env`, `kind` and `min_fraction`. One block drives both the SLURM allocation and the server, so the two can never disagree:

- in an sbatch: `serve_target <name> --port P --gpu G --fraction F --served-name S --log L [--max-num-seqs N …]` from `.zetteldev/della/lib/vllm_server.sh`, then `wait_for_server URL NAME TIMEOUT`;
- in a Snakefile: `resources: **gpu("<name>")`;
- from the shell: `target-info <name> <field>`, and `della-vllm-run --target <name> -- CMD` for the one-shot form that serves, runs a command against the server, and tears down.

Registering a target is the first step of any new evaluation: a merged checkpoint is a block whose `model_path` is its fold directory. Name the venv and the parsers explicitly; auto-detection is stale for new families (Qwen3.5 wants `tool_parser: qwen3_coder` and a reasoning parser, not `hermes`). The served name a config calls must be the name the server registers, or the client gets a not-found error.

## SUBMITTING: THE GATE

Never raw `sbatch`. From the workstation, in the background: `just della-sbatch <script> [args]` for one job, or a file of `label|args script` lines to `just della-sbatch-bg <file>` for many (one push, the gate run serially on the login node, ids appended to `.zetteldev/della/batches/<name>.log`, read with `just della-batch-log <name>`). Nothing that can block past a minute runs in the foreground.

The gate, `della-submit`, checks in order and refuses on the first failure:

1. The checkout is clean and at origin's tip of its branch, after a fast-forward pull. What the job runs is a pushed commit, and its hash rides on the job (`--comment=commit:<hash>`, `REPO_COMMIT` in the job's environment, a line in the sentinel). `--allow-dirty` exists for a test and for nothing else.
2. The script passes the lint (below).
3. Every `# preflight: <command>` line in the script runs locally, in the script's directory, with the `--env` values exported and a fifteen-minute cap. A launch script's dry-run mode belongs on such a line: `CFG_ONLY=1 … bash run.sh` catches an unbound variable or an override the config silently drops (verl's go at `actor.fsdp_config.*`, not `actor.engine.*`, which the dataclass clobbers) in seconds rather than after hours in the queue.
4. `sbatch` runs with a sanitised environment, so only `--env KEY=VAL` reaches the job, never the login shell's variables.
5. With `--dvc PATH …`, a one-hour CPU job queues behind the job (`afterany`, so whatever its end state) and tracks those paths with DVC; the pointer files it leaves are committed by the status tick. A job that writes results names them this way and needs no line of its own for it.

Other knobs: `--array A-B`, `--sentinel path` (written only on success, so a Snakefile can name it as the rule's output), `--no-wait`, `--time`, `--gpus N`. `batches/` is gitignored.

## WALLTIME, PARTITIONS, QUEUE EMPIRICS

Walltime past six hours is a reminder from the lint, not a rule: nothing refuses a longer job. The queue's own numbers, from September 2026 on `pli-c`, are the guidance. One-hour single-GPU jobs backfill within one to three hours. Four-hour single-GPU jobs waited a day. Seven-hour four-card training segments waited twenty minutes to three hours. So evaluations go as many one-hour jobs, and training goes in seven-hour segments chained on checkpoints.

A one-hour evaluation job times out on its last seed or two when games run long. The collectors resume over finished work, so a refill batch of the short ranges is routine, not an error: count outputs after the pull, resubmit only the short ranges once, pull again.

## SHARING A CARD AND A NODE

**Never give an embedding model a GPU of its own.** Colocate it on the chat model's rank-0 card with `launch_colocated_embedder` and request one fewer GPU. An embedder is a gnat beside an ox: on a private H100 it samples 0.0 to 0.7 percent utilisation, which caps the whole job at `tp/(tp+1)` efficiency and feeds it to the idle fuse. The audit of 2026-08-17 found 51.6 GPU-hours burnt on such cards and every long cancellation traceable to one. Two rules make sharing safe: `--gpu-memory-utilization` is a fraction of total device memory, so the fractions of all servers on a card must sum below one (0.82 chat, 0.12 embed); and the chat server comes up first and is confirmed by `wait_for_server` before the embedder starts (the 2026-08-10 hang was two servers each claiming 0.9 of one card). The one exception is a job that serves no chat model, a pure embed-the-corpus shard, where `launch_embedding_server` remains right.

**Della cancels any job whose GPU sits at 0 percent for 90 minutes.** Bursty serving jobs are the usual victims. Three defences, the first structural and the other two palliative: leave no idle card in the allocation; watch a long GPU job with `DELLA_HOST=della-standard bash .zetteldev/della/bin/gpu-idle-watch <JOBID>` in a persistent Monitor, which samples every card each tick over the master and raises one greppable alert per failure shape (`GPU_DEAD_MINUTE`, `GPU_IDLE_ALERT`, `GPU_NEVER_STARTED`, `GPU_IMBALANCE`, `GPU_UNDERUSED`, `GPU_MEM_TIGHT`, and with `WATCH_LOG` or `PROGRESS_GLOB` set, `JOB_LOG_ERROR` and `NO_PROGRESS`); and give a serving job a keepalive every two minutes that is real work, thousands of decoded tokens and a novel query, since a token-sized ping is a 0.04 percent duty cycle the sampler never sees and a repeated retrieval query is a cache hit that touches no card.

**Ports on a shared node are taken between choosing and binding.** A port picked free at job start can be claimed by another of our jobs on the same node before a late-starting server binds it (2026-09-29: a training segment's retrieval server died this way with an eval job beside it). Pick each server's port immediately before its launch; the lint flags a port chosen with another server's launch and wait in between.

## WATCHING WITHOUT OPENING SSH

`just della-status run` in a tmux window is the one poller: every five minutes (floor 120 s) it reads the queue and every registered snippet over the master and writes `~/.cache/della/status.json`. Register what an experiment needs with `just della-status add <name> '<bash on Della>'` (file counts, a log's done-lines), read it with `just della-status show [name]`, and let a Monitor watch the file (`inotifywait -m -e moved_to ~/.cache/della/`) rather than the cluster. The Bash guard denies an ssh loop that sleeps under 300 seconds.

```
just della-status add exp42_json 'cd ~/src/<repo>/experiments/<EXP_DIR> && find processed_data -name "*.json" | wc -l'
/loop 30m just della-status show
```

`just jobstats` is the author's own GPU dashboard; it reaches a job's node with `srun --jobid`, since ssh to the node sees the wrong cgroup.

## CHAINS: RESUME AND REFILL, ON THE STATUS FILE

Decided 2026-10-01: every chain goes through `della-status`, never through its own ssh loop; if papercuts accumulate the decision is revisited. Three shapes recur.

- **The resume chain** carries a training run across segments. Register a snippet that reports the job's queue state and the run's `latest_checkpointed_iteration.txt`; wait on the status file; when the job is gone, stop if the target step is reached, resubmit through the gate from the last checkpoint if the end state is `TIMEOUT` or `COMPLETED` and record the new id, and stop and report on any other state. One chain per run, in a tmux window, its log under the job's tmp.
- **The refill chain** follows an array of short jobs: wait on the batch's ids leaving the queue, pull, count outputs per range, resubmit only the short ranges once, pull again.
- **The eval chain** follows checkpoints: a snippet lists the checkpoint directory, the eval is submitted when a step appears, and the pull-and-count runs on completion.

```bash
# when the status file shows <JOBID> gone from the queue: clear stale locks, resubmit the remainder (resume by file)
ssh della 'find <output_dir> -name "*.inprogress" -delete' && just della-sbatch <sbatch_script> --time 03:00:00 --gpus 1 --env RESUME=1
```

## SERVICES AND TUNNELS

Long-lived services are named in `.zetteldev/services.yaml`: `just service status|up|tunnel|down <name>`, and `zetteldev.services.url("rag")` is the URL a notebook calls. A service runs as a SLURM job or as a tmux session on a viz node (`mode: viz`), which needs no job and survives job churn but shares its card with other users; `up` checks the viz node's free memory and falls back to the job form. Services publish the short node name; the head nodes' public addresses are firewalled.

**A tunnel lives as long as the shell that opened it.** `just service tunnel <name>` runs in a tmux window of its own, and every client checks the service's health route before work (2026-09-29: an embedding pass wrote zero vectors for an hour against a forward that had died with its shell, and the only symptom was a retry line per batch).

## DATA: WHAT THE CLUSTER PACK ADDS

The method's data section is the doctrine; this is the cluster's share of the mechanics.

- The DVC cache is the user's scratch (`della_dvc_cache` in config), set in the checkout's `.dvc/config.local` with `cache.type hardlink`, so `dvc add` moves content into the cache and leaves a hardlink in the checkout: nothing on the cluster is held twice. That cache is also the `della` remote the workstation pulls from, so the cluster never pushes.
- DVC's own ssh client cannot pass the gateway (the agent key is refused there and the passphrased key cannot be read), so the workstation's `della` remote is `ssh://localhost:2222/…`, a port forwarded to the login node's sshd over the control master. `della-master` re-arms the forward when it is down, and every `dvc` call then rides the one connection.
- A job's outputs are tracked by the gate's `--dvc` follow-up, or by the `dvc_pointers` snippet of the status tick, which sweeps the experiments listed in `.zetteldev/dvc_experiments.txt`, tracks quiet untracked entries, and commits and pushes their pointers from the login node. The login node authenticates to GitHub for this; a non-fast-forward waits for the next tick.
- rsync remains for the odd file: compress on the SolveIt link (`-az`), which runs at a few hundred kilobytes a second uncompressed; an include pattern must admit directories (`--include='*/'`) or new ones are silently skipped; a quoted brace list does not expand on the remote.

## SNAKEMAKE AND HYDRA ON DELLA

The Snakemake profile at `.zetteldev/snakemake/della/config.yaml` (`executor: slurm`) submits each GPU rule as its own SLURM job while CPU and `localrule` steps run on the login node. Work inside a tmux window on the login node and point Snakemake at the profile:

```bash
ssh della && tmux new -s smk
cd ~/src/<repo>/experiments/<exp>
export SNAKEMAKE_PROFILE=$REPO/.zetteldev/snakemake/della
uv run snakemake -j8 judge      # the controller holds up to `jobs:` concurrent SLURM jobs
```

The profile sets the concurrency cap, an NFS `latency-wait`, one auto-resubmit on transient failure, and cheap default resources for un-annotated CPU rules; it keeps going past a failed rule and never deletes partial outputs. Each rule's SLURM shape comes from `resources: **gpu("target")`, read from the registry. The executor can hang on a job that never leaves PENDING; `della-submit --sentinel` letting a rule own an array is the fallback, `#|snakerule` cells export to `rules/<nb>.smk`, and `just snake-della <exp> <target>` runs a target from the workstation. Do not define `onsuccess` in a Snakefile: `include: "../../.zetteldev/snakemake/hooks.smk"` carries figure publishing and the tracking of outputs.

```python
from zetteldev.della import gpu   # registry-driven SLURM resources (one block → allocation + server)

rule all:
    input: "processed_data/posts_judged.parquet"

rule prepare_dataset:                                  # pure CPU: the login node, no allocation
    input:  script="scripts/prepare_dataset.py", raw="../../data/posts_raw.jsonl"
    output: "processed_data/posts.parquet"
    localrule: True
    shell:  "python {input.script} --in {input.raw} --out {output}"

rule annotate:                                         # small model, pli-c, 1 GPU
    input:  script="scripts/annotate.py", stuff=rules.prepare_dataset.output
    output: "processed_data/posts_annotated.parquet"
    resources: **gpu("llama-8b")
    shell:  "della-vllm-run --target llama-8b --workers 4 -- "
            "python {input.script} --in {input.stuff} --out {output}"

rule judge:                                            # big model, ailab, 2 GPUs + embed
    input:  script="scripts/judge.py", stuff=rules.annotate.output
    output: "processed_data/posts_judged.parquet"
    resources: **gpu("qwen3-80b", runtime=300)
    shell:  "della-vllm-run --target qwen3-80b -- "
            "python {input.script} --in {input.stuff} --out {output}"
```

Hydra's launcher presets live in `.zetteldev/hydra/launcher/` and are symlinked into each experiment: `pli_c_1gpu` to `pli_c_4gpu` (H100) and `ailab_1gpu` to `ailab_4gpu` (H200). Override per job, e.g. `hydra.launcher.timeout_min=60`.

## TRAINING RUNS: WHAT IS GENERAL

Only the shape, since the method is the experiment's. A run goes in segments of a few hours chained on checkpoints, each segment a submission through the gate from the last checkpoint. The per-step cost is measured once per layout and recorded (33 minutes a step on two actor cards and a two-card updater, September 2026). Each evaluated checkpoint is merged into a servable fold under `models/`, with a `MERGED_FROM` file, and registered as a target. Held-out evaluations go as arrays with the arm list in `--env`.

Metrics travel a quieter road. The airgapped compute nodes write wandb in `WANDB_MODE=offline`. A resumed run's job log holds only its own segment's step lines, so a run of three segments keeps a third of its history there; the complete per-step record is each segment's offline file under the run's `wandb/offline-run-*/run-*.wandb`, read with wandb's `DataStore.scan_data` and the `Record` proto (keys in `HistoryItem.nested_key`), which the metrics scripts do. `wandb-osh` on the login node, started once per session in a tmux window, ferries runs to the cloud for the dashboard view:

```bash
tmux new -s wandb-osh
cd ~/src/<repo>/experiments/<your-experiment>
.venv/bin/wandb-osh
```

## THE LINT

`just preflight [paths…]` lints every tracked `*.sbatch`, and the same lint runs as a `PreToolUse` hook on every Bash call, where a fault in the command denies and a fault in a script asks. Rules live in `.zetteldev/della/sbatch_lint.py` with tests beside them; each marks a failure that has already cost compute: the lonely embedder; fractions summing past one on a card; servers started on a shared card without a `wait_for_server` between them; a missing or ping-thin keepalive; an idle card in the allocation; no `set -e`; a port chosen with another server's launch between it and its bind; `from snakemake.script import snakemake`; verl overrides at `actor.engine.*`; `report.qmd`. Walltime past six hours is a warning only.
