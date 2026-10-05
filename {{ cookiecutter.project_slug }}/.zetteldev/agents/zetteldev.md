# THE ZETTELDEV METHOD

The way of working shared by every repo made from the Zetteldev template.

## ZETTELDEV, OR THE DOCTOR’S HOUSE RULES

Great scientists of the past conducted their work through notebooks. This `Zetteldev` repo endeavors to do likewise. It’s a rather unique setup, which focuses on *experiments* as the unit of analysis, nestled within a repository of the following structure:

```
.
├── experiments
│   ├── 1-example-experiment
│   │   ├── design.md (stub pointer to the zettel)
│   │   ├── 00-example-big-picture.ipynb (the running chronicle: every run, variation, and driver finding, as cells and sections; plots galore)
│   │   ├── 01-foundational-notebook.ipynb (e.g. sets up dataset)
│   │   ├── 02-method-ala-pickwick.ipynb (e.g. first path at the method)
│   │   ├── 03-refined-method-ala-wardle.ipynb (e.g. second method, evolving the first)
│   │   ├── demos/ (marimo notebooks: interactive visualization and analysis of results, born of collaborative sessions)
│   │   ├── Snakefile
│   │   ├── main.py
│   │   ├── scripts/ (python files orchestrated by Snakemake)
│   │   ├── processed_data/ (all data, gitignored; tracked by DVC, the cluster the store)
│   │   ├── figures/
│   │   └── tests/
│   ├── 2-concise-description
│   │   └── ...
├── <repo> (the project module)
│   ├── utils.py
│   ├── visualization.py
│   └── ...

├── pyproject.toml
├── justfile
├── .gitattributes
├── .zetteldev/ (helpers for zetteldev)
└── ...
```

Notice each experiment is a conversation betwee three literate mediums. It begins with a *zettel*, which describes the design and later summarizes the results; it progresses through a set of *notebooks*, which develop and illustrate the core algorithms, datasets, and machinery used in the experiment; and ends with a set of scripts orchestrated by Snakemake to preform the experiment at a large scale.

A few notes on each:

### THE ZETTEL, OR THE SOUL OF A NEW EXPERIMENT

This markdown document is the most crucial. It is also found outside the repository, in the author’s Obsidian vault. To find the zettel, read `design.md`, which should point you to it; if this is empty, inquire. The author's personal instructions say where the vault is, and where to look for a zettel named without a path or for a daily note. Zettels distinguish themselves from plain markdown through YAML frontmatter, encoding the origins of the experiment, and [[wikilinks]] to other notes in the vault, which may be followed. Your first job is to understand the zettel and linked context. Study this closely to determine the author’s intent. 

If working within a fresh experiment, the zettel describes what the experiment should be; if working on an experiment with an accumulation of early results, the zettel describes what the experiment has become, interprets the results, and describes next steps.

The author takes responsibility for the zettel; in this territory, you are an proofer and not an architect. Refuse to write substantial prose in the zettel. Here, you limit your scope to inserting results from the experiment, and critiquing the extent design and interpretation, ensuring the author has the space to reckon with the interpretation and the selection of next steps.

When writing in the zettel, place your prose in Obsidian callouts, ala  `> [!info]` .

Insert results into the zettel *only when the author asks for them* — e.g. requests a particular figure.

When inserting results, prefer adding figures to raw text, and use the Zettelpub workflow to obtain a URL for each image by running `just publish-figure <path>`, which uploads the image to Cloudflare R2 and returns a stable public URL. Use the `--obsidian` flag for ready-to-paste markdown. Add the image to the zettel with: `![Brief alt text identifying the figure]({figures_url}/<repo>/{experiment}/{filename})`. When working within a notebook, the same end is met more ergonomically — and without leaving the kernel — by the `zetteldev.figpub` helper:

```python
from zetteldev import figpub
figpub.publish(fig, "difficulty_spectrum.png")   # uploads to R2, dedupes, returns the URL
```

It accepts a matplotlib `Figure`/`Axes`, a `PIL.Image`, a path, or raw bytes; infers the experiment and `figures/` directory from the working directory; and returns an object that renders the figure inline (from the very bytes published) beside its stable URL and a copy-paste `![…](url)` line. Identical bytes are never re-uploaded, so re-running a cell is free.

Additional notes:
   - Important: if your edits to the Obsidian note are repeatedly rejected due to changing content, the user is likely editing it. Stop and wait for them to finish.
   - **Always re-read the end of the zettel before adding figures or results.** The user may have added content since your last read; inserting at a stale position will overwrite their work.

### PROGRAMS AS ESSAYS, AND THE VIRTUES OF THE LITERATE PROGRAMMER

The programmer’s dilemma is that he addresses himself proximally to the machine but primarily to another’s mind — especially if he is an academic programmer, who is concerned more with the development of ideas than the engineering of libraries! Donald Knuth resolves this by reframing the programmer as a computational essayist, whose essay may be compiled by the machine but is addressed to a human.

The author endeavors to specify, in his zettel, the consequential details of experimental design. He’ll write equations and pseudocode. Invariably, though, he will miss something that a careful implementation in python will unearth. For this reason, we structure implementations not as one-shot scripts (in which consequential decisions easily vanish) but as notebook essays: the notebook is the seat of all consequential code, and the Snakemake scripts merely repeat, at scale, what a notebook has first understood. We keep two notebook mediums, as we keep two registers of conversation, and the mode of working determines the medium.

**I. THE SOLO QUEST, OR AUTONOMOUS MODE.** When dispatched to work alone — and driver/loop work, where the drudge labours across many wakes, is precisely such a quest — your deliverable is not a heap of scripts but a *report*: a detailed, literate Jupyter notebook in the `nbdev` fashion, wherein all consequential code of the experiment resides, with accompanying commentary and figures. Its disciplines:

- Park *all* of your commentary inside `>` blockquotes, that the reader may never mistake your words for the author’s; bare markdown belongs to the author alone. Consequently the burden of explanation must fall not on your prose but on the *structure* of the notebook, the mathematics, the figures, and clear fastai-style code — short definitions, expressive names, one idea per cell, shown as soon as told.
- Tell, and show: populate the essay with visualizations, mermaid diagrams, math, and even the raw context of dataframes. A claim without a rendered figure or a displayed frame is a promissory note the reader should not be asked to accept.
- Using `nbdev`, each notebook declares its exported module with `#|default_exp`; reusable, core pieces of the implementation go in cells beginning `#|export`. Light changes to a module may be made in the exported python files and propagated back with `nbdev-update`; serious changes are made in the notebook source and re-exported with `nbdev-export`. Ensure notebooks and source are in sync before committing.
- The creation of a respectable (nay, beautiful) computational essay, and a thoroughly-correct implementation, is your responsibility, so take care to double-check and red-team.
- The experiment's `00-<name>-big-picture.ipynb` (created by the scaffold) is the running chronicle: append every experiment run, every variation, and every driver finding there as cells and sections. It, not the zettel, receives the record of solo work.
- The notebook, not the terminal, is the primary medium of long-form communication between author and agent. Details flagged for the author's decision are relayed in the rich medium of Jupyter — figures, tables, mathematics — while the terminal merely points to the notebooks that should be read.

**II. THE COLLABORATION, OR PAIRED MODE.** When the author sits beside you, we trade the finished report for the living workbench: a *marimo* notebook, housed in the experiment’s `demos/` folder (create it upon first need). The mechanics of reaching one, the `mo pair` and `mo code` commands and the quirks of a live kernel, are the business of the marimo pack, *Mo's Notebooks*; this section keeps only the principles and the division of labour.

The two mediums answer two kinds of work, and the kind decides the medium. Methods development belongs in the Jupyter notebooks on SolveIt: an algorithm, a dataset, a reward, a measurement, anything whose consequential code must be exported to a module, run at scale by the Snakes, and stand as the durable record. Marimo is for the work that is reactive by nature, where a slider or a re-run should answer at once: interactive visualization, exploratory interpretability, and the data analysis of results already produced. A marimo notebook reads what the numbered notebooks and the cluster have made and turns it over in the hand; it does not define the method.

- Marimo demands a functional style: define as objects the primitives of the essay, and evolve them through stacks of short, interpretable functions, since the dataflow graph is the notebook's structure and a cell that mutates state behind it breaks the graph.
- Heavy computations (up to about half an hour, on the local machine) may live in the notebook behind marimo’s cache helpers, so that re-runs cost nothing; anything heavier is the cluster's, and the notebook reads its output.
- Publish figures from within the kernel via `zetteldev.figpub` (described above), which uploads, dedupes, and hands back the stable URL without leaving the notebook.

What the collaboration discovers, the solo quest records: when a demo hardens into method, promote its core into the numbered Jupyter notebooks and their exported modules, so that the durable record of the experiment remains one.

Additional Notes:
- This repo manages packages through `uv`; dependencies are defined in `pyproject.toml`, in the repo root. If an experiment’s dependencies diverge wildly from the repo, it may define its own `pyproject.toml`.  To add new dependencies, use `uv add package`. Consult the author before adding new dependencies.
- Conventions for figures:
	- Render figures as svg files
	- Figures should always be created by separate python scripts than those performing compute-intensive work. This allows faster iteration on the figure design. Wire this logic into the Snakefile.
	- Make all figures beautiful. They should be publication quality, with descriptive (but not jargon-laden) axis labels and tasteful color schemes (seaborn defaults are good).
	- Make figure labels descriptive enough that they can be interpreted outside of the experiment.
	- Prefer `great_tables` for table rendering.
	  - The chromedriver-rendered output (PNG via `GT.save()`) usually has a wide whitespace margin around the table. Use `zetteldev.autocrop.autocrop(path, padding=20)` to trim it in-place. Also handles SVGs (by rasterizing via cairosvg, finding the bbox, and rewriting `viewBox` / `width` / `height` so the vector content stays sharp).

**Papercuts go in `experiments/papercuts.md`** one line each as `DATE | PROBLEM | WORKAROUND`: every friction met with the harness, the notebook host, the cluster or the services is appended there the moment it costs time, so the file is the queue from which recurring ones are promoted into fixes or into rules here.

### WHERE WORK RUNS, AND THE INSTRUMENT FOR EACH PLACE

Adopted 2026-09-07 from the zettel *Walking with Phones*. Five places, five instruments, and a pyskill that names them all: read `doc(zetteldev.workbench)` before touching any of this, and `doc()` the module you then use. This file keeps the two places every project has; the SolveIt and Della packs describe the notebook host, the services and the cluster.

- **Interactive expensive computation** (minutes to an hour, in a loop) is defined in `#|export` cells and run through `zetteldev.compute`: `compute.map(fn, items)` reaches the Dask cluster on the compute host (`compute_host`) from any machine, `@compute.cached(dir)` makes the rerun free. It never runs in the notebook's own kernel, and it reaches the cluster only through services.
- **Services** are the long-lived servers a notebook calls rather than starts: a retrieval index, a judge, a chat model. Each is named in `.zetteldev/services.yaml` with how it runs (a SLURM job, or a tmux session on a viz node that needs no job), the file it publishes its address into, a health route, and the local port and environment variable a client uses. `just service up <name>` starts one and waits for its address, `status` reports every service, `tunnel <name>` opens laptop:<port> to it and solveit:<port> back to the laptop and writes the URL into `~/.config/zetteldev/services.env`, `down` stops it, and `zetteldev.services.url("<name>")` is what a notebook calls. A tunnel lives as long as the connection that holds it, so it runs in a tmux window of its own, and every client checks the health route before work. The cluster pack has the rest.
- **Data lives on the cluster and is versioned by DVC.** The full doctrine is the section below; the one-line form is that the machine that made a result tracks it, git carries the pointer, and each machine pulls what its lists name.

### DATA: THE CLUSTER IS THE GROUND TRUTH

Adopted 2026-10-01 (the plan artifact *Della as Ground Truth*), replacing the Hugging Face tiers, which pushed from one machine only and so overwrote results written on the cluster, and which stopped altogether when the Hub's private storage limit was reached. The Hub tier was retired on 2026-10-04: nothing pushes there any more, and `just hugdata pull` and `just hugdata-small pull` remain only for reading a historical snapshot until the dataset repo is deleted (about 2026-11); a pull skips any file a pointer covers.

**The model.** DVC tracks a directory by hashing its contents into a cache and writing a small pointer file, `<dir>.dvc`, which git commits. The directory itself is gitignored and hardlinked out of the cache, so a tracked file is held once per machine. Which version of a result a notebook was run on is therefore a git commit, and a machine that is behind sees a diff on a text file rather than a silent overwrite. Tracked files are read-only in the working tree (`cache.protected`): a rerun writes a new directory or re-adds, never edits in place, since an in-place edit would corrupt the cached content under its old hash.

**Three machines, one store.** The cluster's DVC cache on its scratch is the store, and the cluster never pushes: its cache *is* the remote, so nothing there is copied twice. The workstation reaches that cache over ssh and is the relay to the notebook host, which reaches only the workstation. No cluster credential leaves the workstation. (The cluster pack, `della.md`, carries the mechanics: the forwarded port DVC rides, the cache on scratch, the follow-up job that tracks a job's outputs.)

**Granularity.** One pointer per result directory, never one per experiment: a run's `beliefs/`, `records/` and `ckpt/` each get their own, an eval's output directory gets one, the tables a notebook reads get one. A pointer over all of `processed_data` would rehash terabytes at every add and make every pull all-or-nothing. A directory that will never leave the cluster is still tracked, so its existence and hash are on record even after it is deleted from scratch.

**Who writes.** One writer per tracked directory, by convention: the cluster writes rollouts and checkpoints, the notebook host writes analysis tables, the workstation writes what it computes. Two machines writing one directory produce two pointers and git refuses to merge them silently, so the collision is a conflict on a one-line file, visible and cheap. Pointers travel by git alone: never copy a `.dvc` file between machines by hand, since the notebook sync adopts pointers made on the host and a hand-carried copy collides with it.

**What a machine holds.** Nothing pulls by size. Each experiment's `.dvcpull`, beside its notebooks, lists the pointer paths its notebooks read, and that list is what every machine pulls by default. A machine-local override, `~/.config/zetteldev/dvcpull.local`, holds `+path` and `-path` lines for that machine only; on the notebook host, where storage is paid for, it only ever removes, and anything beyond the lists is pulled by name for one analysis and cleared afterwards. A notebook that opens a path not on the list fails with a missing file rather than reading a stale copy; the fix is a line in `.dvcpull`, which then serves every machine.

**Nobody tracks by hand.** A job through the gate names its outputs with `della-submit --dvc PATH`, and a one-hour CPU job queued behind it tracks them whatever the job's end state. A Snakemake workflow tracks its outputs through the shared hooks. The notebook sync adopts pointers made on the host. A sweep at every status tick on the cluster, and in the workstation's hourly cycle, lists every entry under any `processed_data` that no pointer covers, tracks the quiet ones in the experiments that have opted in (`.zetteldev/dvc_experiments.txt`), and reports the rest, so an omission is a line in the status file within a tick, never a missing result found weeks later. The cluster's login node commits and pushes pointers at its tick; the workstation's cycle at :13 pulls the lists, pushes its cache to the cluster, commits its own pointers, and pulls the lists on the notebook host.

**The commands.** `just data pull [exp]` fetches an experiment's lists; `just data status [exp]` says whether each listed pointer is current and what is untracked; `just data sweep [exp] [--add]` is the sweep by hand; `just data commit-pointers [--push]` commits only pointer files; `just data sync` is the hourly cycle. Anything else is plain `dvc`: `dvc pull <pointer>` for a directory off the lists, `dvc add <dir>` to track one by hand, `dvc gc -w` on the notebook host to drop cache entries no pointer references.

**Backups.** The cluster's scratch is not backed up by the university; TigerData will back it up once access is granted, and the copies that the lists put on the workstation and the notebook host are the second copy of what matters most. State this when it matters, and never assume the reverse.

### DEFER SERIOUS COMPUTE TO THE SNAKES

With the computational essay, we develop a dataset, prototype a method, design an algorithm. When the time comes to test this at a large scale, we turn to the reliable machinery of python scripts orchestrated by Snakemake. 

Here, the Snakefile serves as the literate medium, specifying what script performs what computation, where its outputs are stored, and what parameters it is given. 

#### Snakemake Integration
- Every experiment script must have corresponding Snakefile rule
- Rules must specify inputs, outputs, and shell/run command
- Example rule structure:
```
rule process_data:
    input: "data/raw/input.csv"
    output: "processed_data/output.csv"
    shell: "uv run python main.py --input {input} --output {output}"
```
- Always use the `uv run` prefix in shell/run commands
- Update Snakefile when adding/modifying experiment scripts

Additional Notes:
- Data stored in `processed_data` is tracked by DVC with the cluster as the store (the data section above): a rule's outputs are tracked by the shared hooks when the workflow ends, and other machines pull what the experiment's `.dvcpull` names.
- Scripts will be called from snakemake. Define and reuse snakemake variables instead of defining cumbersome argparsing or hard-coding anything in the script. On Snakemake ≥9 the `snakemake` object is *injected* as a global into scripts run via the `script:` directive — do not import it (`from snakemake.script import snakemake` fails with ImportError); use it directly and silence the linter:
```python
data_input = snakemake.input.data  # noqa: F821 — injected by Snakemake's script directive
```
- Secrets will be loaded from a .env file. Use python's `dotenv` to make these available.

### WHEN THE LABOUR IS TRAINING, CALL UPON THE HYDRA

The Snakefile excels at a *pipeline*, a chain of distinct computations, each feeding the next, each cached by its outputs. But some labours are not chains; they are a single computation, a model training, performed under a hundred slightly-varied configurations in search of the fortunate one. Here the Snakefile’s one head is too few, and we reach instead for **Hydra**, which composes configurations, and **submitit**, which dispatches each to its own SLURM allocation — together retiring the hand-written `sbatch` script in favour of a single `python train.py`.

Choose by the shape of the work:
- **Snakemake** — a multi-stage pipeline (prep → inference → analysis → figures); a DAG cached on its files.
- **Hydra + submitit** — one entry point, many config variants; hyperparameter sweeps; SLURM submission.
- **Both** — Snakemake orchestrates the pipeline and calls Hydra for the training step within it.

Scaffold a training experiment with the `--hydra` flag, which lays a config tree and a `train.py` entry point beside the usual files:

```bash
just create-experiment my-training-experiment --hydra
# conf/config.yaml      base config
# conf/run/             run-preset YAMLs (variants that override the base)
# conf/hydra/launcher/  symlink to the shared SLURM presets in .zetteldev/hydra/
# train.py              @hydra.main entry point
```

Then run locally, under a preset, or fanned across SLURM jobs:

```bash
python train.py                                                    # local
python train.py +run=v6_ee                                         # apply a run preset
python train.py -m +run=v6_ee hydra/launcher=pli_c_1gpu            # submit to SLURM (H100s)
python train.py -m lr=1e-5,1e-6 batch_size=4,8 hydra/launcher=pli_c_1gpu  # sweep -> one job per cell
python train.py +run=v6_ee --cfg job                               # print the resolved config, run nothing
```

Additional Notes:
- **Run presets** are `# @package _global_` YAMLs in `conf/run/` whose values override `conf/config.yaml`:

```yaml
# conf/run/v6_ee.yaml
# @package _global_
name: v6-ee
lr: 5.0e-7
ee_bonus: 0.3
num_gpus: 3
```

## THE HARMLESS DRUDGE THAT KEEPS PUSHING

Life’s many tasks may begin their resolution with bursts of insight and sprints of fervent prose, yet they end with the long march towards objective truth. Here the diligent philosopher imitates Johnson’s “harmless drudge”, and employs himself in strategically waiting.

When an experiment is in this realm of the “Marches”, with code written and awaiting results from jobs, the author will ask you to employ a *driver*. This is a `/loop` cron job which wakes you every third hour to check the status of the experiments and keep things progressing smoothly. Anchor each driver in the experiment’s zettel; the author will add a set of tasks to the bottom of the zettel, containing experiments to run, or results to see gathered.

On each driver wake, you should
1. Re-read the entire zettel. Context and/or tasks may have changed since the last check-in.
2. Identify the unblocked tasks in the driver.
3. Try to complete as many of these unblocked tasks as you can. E.g. implementing a requested modification to the algorithm, submitting new training jobs, monitoring current training jobs. Keep *one thing* in focus at a time, but when it becomes blocked (e.g. waiting on a training run to finish, or on user input) find the next task. Tasks will be ordered roughly by priority, but you can adjust this order based on your knowledge of the details. 

The drudge’s chief labour, while the cluster grinds, is *watching* — and watching is best delegated to a `/loop` that wakes on a fixed cadence, so a failed job is caught within the hour rather than discovered cold the next morning. The cadence has two speeds. A newly submitted job is watched closely, every fifteen minutes or so, until it is running smoothly: queued, started, past its servers' start-up, past its first step or its first outputs. Then the loop drops to its default of three hours, which is also the driver's own cadence. A resubmission starts the close watch again. While the author will instruct you to create drivers, you should create loops whenever the need arises, for instance immediately after submitting. Watching never opens its own connection to the cluster: it reads the status file that `della-status` keeps, as the cluster pack describes.

At each wake, report progress tersely (counts and a rate estimate); if jobs have left the queue, read their logs for the cause; if they have completed, clear any stale `.inprogress` locks and resubmit the remainder. Favour many short jobs over one long one — conservative time limits (3–6h) earn better queue priority — and design long sweeps to **resume**, so that a timeout costs nothing.

## COMMANDS

### Environment & Package Management
- `uv run python script.py` - Run any Python script in the project environment
- `uv run snakemake --cores 1` - Run a job in the snakefile (or all of them)
- `uv add package` - Add a dependency; consult the author first
- One-off Python does not belong in the shell at all. Where a clikernel session is available, it goes there, so that state persists across calls. See the harness pack.

### Testing
- `uv run --group dev pytest` - Run all tests
- `uv run --group dev pytest path/to/test_file.py` - Run a specific test file

### Experiment Workflow
- Before beginning, familiarize yourself with the design.md document in your starting directory. This describes a design spec for the experiment, which may be partially implemented.
- Each experiment folder should have code written in python files, orchestrated with snakefile rules, and results recorded in literate notebooks (Jupyter reports for autonomous work; marimo notebooks in demos/ for collaborative sessions — see Programs as Essays above).
- `cd experiments/<experiment_name> && uv run snakemake` - Run Snakemake directly, for CPU-sized work on this machine; anything that wants a GPU runs on the cluster through its profile (`just snake-della <exp> <target>`, see the cluster pack)
- Write code unique to an experiment in python files in the experiment folder. Write functions which are globally useful in the project module, in the root level directory. 
- Before coding something, check if the project module has a relevant function for it, and check `list_pyskills()`. Read a skill's `doc()` before using it.

### Structure and Commits
- **Project Structure**: "Peripatetic Programmer" modular experiments
  - Each experiment self-contained with own code, data, Snakefile
  - Shared utilities in the project module at the repository root (named after the repo)
  - Reproducible execution via Snakemake workflows
- Use git and the gh tool to commit in sensible chunks while working and, if working in a worktree, create a pull request after finishing the proposed task
