<!-- Generated from CLAUDE.md by .zetteldev/agents/build_agents_md.py; edit that file, then `just agents-md`. -->

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
# THE HARNESS

For projects worked through the Answer.AI coding harness (clikernel, pyskills, exhash). Redrafted 2026-10-04.

### THE HARNESS, AND THE INSTRUMENTS IT PUTS IN OUR HANDS

We have taken up the Answer.AI coding harness, whose premise is that an agent should work at a persistent Python kernel rather than through one-shot shell commands.

**The instruments.** Prefer these to reading and patching files by hand.

- `lnhashview_file(path)` to read anything an edit may follow. Its `lineno|hash|text` view doubles as the address book, so the edit needs no second read.
- `file_exhash(path, (addr, "d"), (addr, "s", pat, repl))` to edit. Every addressed line's hash is checked before the command runs, so a stale address fails instead of quietly changing its neighbour.
- `lnhashview_cell` and `cell_exhash(path, cell_id, *cmds)` for one notebook cell's source.
- `aidialog.dlgskill` for notebook *content*: `summary_dlg` for one preview line per cell, `find_msgs` to search by regex, type, error, heading or structure, `view_dlg` to read, and the message editors with `dlg.save()`. This is how the chronicle is appended without loading it whole. Never edit ipynb's JSON manually. (A dialog open on SolveIt is the exception: there the live copy is edited through `sicx`, per the SolveIt pack, and the file tools are for a notebook not yet opened.)
- `fastcore.nbio`'s `validate_nb` / `validate_cell` when the question is whether the file is schema-valid and which cell is at fault.
- `rgapi`'s `fd` and `rg` for finding and searching, in place of shelling out.
- Three disciplines make them work: end the cell with the bare call, since the repr is the deliverable and must never be printed or reformatted; work **backwards**, bottom to top, because structural edits shift the lines beneath them; and re-view between calls, because hashes go stale. Two known traps: a `%%exhash` body with backticks can have them doubled on the way in, so check the view after; and an edit sequence run top to bottom leaves stale hashes beneath it.
- Discovery has two doors: the project module, and `list_pyskills()`. Read a skill's `doc()` before using it.

**Two persistent kernels, and they are not the same one.** Paired marimo work stays with the `marimo-pair` skill and marimo's own kernel, exactly as the method describes, reached through `mo pair` and `mo code` (see MO'S NOTEBOOKS). clikernel is for solo work and for everything that is not a marimo notebook. Do not drive one with the other's tooling.

### THE SHELL, WHERE IT IS STILL USED

**Three standing rules on shell commands,** enforced by a hook and not negotiable at the point of use: no `| head` or `| tail` with a count below twenty, since truncation is decided before the output exists; no `2>&1`, and where stderr must be kept, write `>meta/stdout.txt 2>meta/stderr.txt` and read the files through the kernel; and no loop that sleeps under 300 seconds beside an `ssh` to the cluster, for the gateway's reason given in the cluster pack.

Two habits that cost a shell this month. `pkill -f <pattern>` kills every process whose command line matches, and the shell issuing it matches its own command line, so it dies with exit 144 and the work after it never runs; kill a tmux session by name instead, or `pkill` by a pattern the shell does not contain. And a `cd` inside a compound command, or a working directory a backgrounded command changes, does not carry to the next call: the shell resets between calls, and a script that needs a directory names it absolutely.

Nothing that can block past a minute runs in the foreground: the long thing goes to a tmux window, a `Monitor` watches its log, and the ids and lines arrive as events (the method's no-blocking rule). One-off Python does not belong in the shell at all; where a clikernel session is available it goes there, so that state persists.

### SUBAGENTS, A CAUTION

A delegated subagent can write one sentence and go idle without a tool call. Check a delegated task at its first report, and retire a subagent that idles without acting rather than nudging it twice; the work is then done in the session.
# THE SOLVEIT PACK

(For projects whose notebooks are reviewed and edited on a SolveIt instance: `solveit_host` and `solveit_root` in `zetteldev.config`. Redrafted 2026-10-04.)

## WHAT SOLVEIT IS, AND THE THREE FACTS THAT GOVERN IT

The author reviews and edits notebooks in SolveIt, a cloud instance that gives Jupyter a next-generation face and an AI of its own. It is reached as `ssh solveit`, holds its clone of the repository at `solveit_root` (`/app/data/<repo>`), and runs each open notebook as a *dialog* with a kernel of its own. Three facts shape everything below.

- **The dialog is the living copy.** Once a notebook is open on the instance, the server's copy of it is the truth, not the file in any checkout: the server auto-commits the author's cells, re-saves its memory over the file, and a file-side edit pushed across lands as a second insertion at the same spot. So after a dialog is first opened, every edit goes through the instance's API, never through the `.ipynb`.
- **The kernel has four gigabytes.** The container is capped by a memory cgroup (`/sys/fs/cgroup/memory.max` = 4 GiB) whatever `free` reports of the host, and a kernel that crosses it is killed without a word. Nothing heavy runs in it: see the section on where computation goes.
- **The instance reaches only Athomia.** Its ssh configuration knows one host, its git clone holds no GitHub credential, its storage is paid for. Code and pointers come to it by the hourly sync from Athomia, data by the DVC lists through Athomia's cache, and everything it makes goes back the same road.

## REACHING THE INSTANCE

The server listens on `localhost:5001` *inside* the host, and localhost callers are admitted on the default token, so no cookie is wanted. A forward from the laptop, `ssh -fN -L 5001:localhost:5001 solveit`, is the whole connection, and `curl -s localhost:5001/test_route` answering `here` is the sign of a good one. The `sicx` wrapper (below) defaults to that address and needs no variable exported.

**The forward lives as long as the connection that holds it,** so it is held by the ssh control master and re-armed by `just solveit-master`, which the `sicx` recipe and the sync run first; `just solveit-master --status` reports the master and the forward. Nothing opens the forward by hand.

## THE DIALOG: A PATH, OPENED BEFORE IT IS TOUCHED

A dialog's name is its path under the instance's data root, `/`-separated, without the `.ipynb` extension: `<repo>/experiments/42-stuckness-modeling/00-big-picture`. Each experiment names its dialog once in `.solveit-dialog`, which `sicx` reads. The message routes see only dialogs open on the server, and `sicx open` (create-or-open) is therefore the first step even for a notebook that has existed for months, and again after any server restart.

A newly created dialog is born empty, and an empty dialog is broken: every route returns a 500, the server re-saves the empty file over any seed, and it cannot be deleted through the API. To make a *new* dialog, write the `.ipynb` over ssh with one seed cell, then open it, then add every real cell through the API. Cells that reach the server from the file are inert there, `exec` returns nothing and sets no run flag, while a cell added through the API runs at once. The file-side tools of the harness pack (`aidialog`, `create_dlg`) are for authoring a notebook before it is first opened; after that, put them down. Confine experiments to scratch dialogs under `tmp/`; the author's numbered notebooks are not a proving ground.

## EVERY EDIT GOES THROUGH SICX

`just sicx <cmd>` is the one control surface: the client with a memory and a wait, through which cells are read, added, edited, run and deleted. The raw `sic` client beneath it is not used directly; its `exec` is dropped by the server while the kernel is busy and gives up at thirty seconds, which is why the wrapper exists.

**Your prose goes in `note` cells inside `>` blockquotes, and nowhere else.** Code in `code` cells; bare markdown is the author's alone, so the reader never mistakes your words for theirs. This is the method's rule for every notebook, and on the instance it is the only thing that marks whose cell is whose, since the server records no author.

- `sicx list` prints every cell's id, type and first line; `sicx status` the kernel state; `sicx out <id>` one cell's output; `sicx dump [--out FILE] [--ids …]` every cell as JSON, the way to read a run of cells in one go; `sicx delete <id …>` removes your own scratch cells, never the author's.
- `sicx run <id>` waits for the kernel to be idle, queues the cell, waits for it to finish, and prints its output as text, exit 1 on a traceback. `sicx add --after <id> --type code|note --file f [--run]` and `sicx edit <id> --file f [--run]` take the cell body from a file, so there is no shell quoting.
- **List before you edit.** An edit is hash-checked against the last `sicx list`: a cell "not seen since the last list" or whose "content changed since your last view" is refused, and `--force` is for your own cells only, never the author's. `add --after` fails with "Reference message not found" when the author has reorganised, so list again before anchoring; the author moves and deletes cells while you work.
- `sicx stop`, `sicx open` and `sicx bootstrap` are the kernel cycle (next section); `sicx slim` trims outputs when the dialog has outgrown the instance AI's window; `sicx apply FILE` is the sync's own instrument, not a substitute for edits.
- A figure cell ends in `plt.show()`, or the stored output is the text repr and the figure is lost to the synced file. Figures saved under `figures/` are adopted by the sync, and `zetteldev.figpub` publishes from the kernel, whose settings hold the R2 keys.
- `exec` on a `prompt` cell summons the instance's AI and bills the author for it. Add prompt cells if asked; execute them only on request.

**Bootstrap is how a kernel remembers.** A fresh kernel knows nothing: every `sicx stop`, every server restart and every OOM leaves one, and `sicx open` alone gives an empty namespace. `sicx bootstrap` runs, in dialog order, every cell whose first line matches the export pattern (`#|default_exp` and `#|export`), waiting on each as `run` does and stopping at the first traceback with `ERR <id>` and the output, so a broken export is found rather than skipped. `--dry` lists what would run; `--also <id> <id> …` (space-separated) appends cells that are not exports but that a later cell depends on, the data-loading cell beneath a table, say. That is the gap to mind: bootstrap replays definitions, not state, and a read cell that needs a frame built by an ordinary cell above it needs that cell run again, by `--also` or by hand, before it will answer. Keep the dialog's export cells self-sufficient and cheap to replay, and keep anything heavy out of them, since the replay runs in the same four gigabytes.

**The hourly sync and a dialog you are editing.** `just solveit-sync` runs from Athomia at :23 and by hand after a handoff, and it touches an open dialog twice. At the start it commits on the instance what the server has auto-saved, your cells among the author's, after a guard has restored any notebook the server wrote back as an older state than Athomia last pushed. At the end, after the merge and the push into the instance's checkout, every notebook the push changed is applied to its live dialog through the API (`sicx apply`, which updates edited cells and adds missing ones and deletes nothing), because a loaded dialog outlives its file and would otherwise write its memory back over the push. A cell you add or edit through `sicx` while the sync runs is therefore carried, not lost: the server already holds it, and apply never deletes. What the sync will not do is merge a non-notebook file edited on both sides, or a commit on the instance that duplicates one already pushed; both are refused, and the recoveries are in the git section below.

## THE KERNEL, ITS FOUR GIGABYTES, AND WHERE COMPUTATION GOES

The kernel dies under the cap, and a dead kernel leaves every message's run flag unset, so a status check can report idle over a corpse; `sicx run` therefore probes liveness first and says "not answering (dead ipymini?)" rather than waiting out a timeout. The recovery is `sicx stop`, `sicx open`, `sicx bootstrap`, and then the non-export cells a read depends on, by `--also` or by hand (bootstrap, above). Two worse shapes: an ipymini that survives `stop` (find it with `ps` on the host, kill the pid, then open and bootstrap), and a server that stops spawning kernels after an OOM and leaves the dialog "busy" with no process (reset the dialog, then open).

Therefore nothing heavy runs in the kernel, and the rule is the method's: the computation is *written* in the notebook, as export cells, and *executed* elsewhere.

- Loops of minutes to an hour go through `zetteldev.compute` to the Dask cluster on Athomia, which the kernel reaches over the reverse tunnel that `just service tunnel` opens. Pass an explicit `exp_dir`: the kernel's working directory is not the experiment's, and a function defined in a cell ships by value, so a module-level path built from `__file__` resolves wrongly there.
- Anything larger is exported and run on Della through the gate, and its result comes back as a tracked directory on the lists.
- A notebook never loads a large frame to display a table, and never reads a statistics file synced from elsewhere merely to show it: the cell that shows a number is the cell that computes it, on the cluster.

## THE AUTHOR'S CHANNEL INTO THE DIALOG

The author writes on a Supernote E-ink tablet. A page arrives in the dialog as a `prompt` cell headed `<!-- penman:… -->` with the page's transcription, equations and diagrams included, and the instance AI's reply sits in that cell's output. Read a run of them with a `dialog.messages` dump rather than cell by cell, and answer in `note` cells after the page, never by editing the page. The dialog can exceed the instance AI's context, and its own reply says so when it does; `sicx slim` is the remedy, and the author's call.

## GIT: ATHOMIA IS THE SOURCE OF TRUTH

The instance's clone is a git remote named `solveit`, reached by ssh. `just solveit-sync`, hourly by cron at :23 and by hand after a handoff, runs the cycle: the guard on the instance restores any notebook the server has written back as an older state than Athomia last pushed; the instance commits what its server left uncommitted, notebooks, figures under `experiments/*/figures`, DVC pointer files and the ignore files beside them, and nothing else; Athomia fetches, merges, pushes to origin, and pushes into the instance's checked-out branch, which fast-forwards its tree. Modules are exported from the committed dialog with `just solveit-export <ipynb>`, never copied by hand; a bulk export can carry a stale notebook over a shared module, so export the notebook you changed.

Two refusals and their recoveries. A text file edited on both sides since the last sync, papercuts.md or a script, is REFUSED rather than merged, because a line-by-line merge drops lines without a conflict; copy the instance's lines across by hand, then resync. A commit on the instance that duplicates one already pushed from Athomia is likewise refused; reset the instance's branch to the last pushed commit and resync. Pointers travel by git alone.

## DATA ON THE INSTANCE

Storage on SolveIt is paid for, so it holds the least. The DVC remote is `athomia`, Athomia's own cache over ssh; the default pull is each experiment's `.dvcpull` and nothing more; the machine-local override only ever removes; anything beyond the lists is pulled by name for one analysis and cleared afterwards with `dvc gc -w`. `dvc` is installed at `/app/data/.local/bin`, which is not on the PATH; `just data` finds it. A result made on the instance is tracked there with `dvc add`, its pointer committed by the sync and the content pushed on to Della by Athomia's hourly cycle.

For the odd file, rsync to the instance with `-az`: uncompressed the link runs at a few hundred kilobytes a second, and an include pattern must admit directories or new ones are silently skipped.

## SECRETS, PACKAGES, AND THE INSTANCE'S OWN AI

Settings secrets reach a kernel at its next start; no server restart is needed, and until then `~/solveit_settings.json` holds them. The R2 keys there make `figpub` work from the kernel. The Gemini key in the kernel is the author's personal account: quick smokes only, bulk judging goes to Della-served models, or ask. Packages go into the container's Python with `pip install` (ripser, dvc); the kernel shares the host's network, so a forwarded service port is reachable from a cell.
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
# MO’S NOTEBOOKS

For pairing on the author's marimo notebooks, served from athomia through Mo’s Notebooks.

### WHERE THE NOTEBOOKS LIVE, AND THE DOOR AN AGENT USES

The author opens marimo notebooks through Mo’s Notebooks (the dashboard at `https://athomia.moose-walleye.ts.net/`, and the `mo` command). Each notebook runs in its repo's own environment: the experiment's `.venv` when that has marimo, else the repo root's. It runs from its experiment folder, behind a token, at `/nb/<name>/`. Such servers do not register for marimo-pair's discovery, so `discover-servers.sh` will report nothing. Use `mo` in its place.

**The two commands.**

- `mo pair NAME|PATH` finds the notebook, or starts it. A `.py` path that does not exist yet becomes a fresh notebook. It prints the notebook's name, file, working directory and interpreter, and whether a browser has it open. `--wait` blocks until one does.
- `mo code NAME|PATH [-c CODE | - | FILE]` runs code in that notebook's kernel. It is marimo-pair's own `execute-code.sh`, aimed at the right server and session, with the token passed privately. Every flag the skill documents passes through.

**The order of work.**

1. `mo ls` shows what is running. A notebook's NAME is the first column.
2. `mo pair NAME`, or `mo pair path/to/notebook.py`. If it reports no browser, ask the author to open the notebook from the dashboard, then run `mo pair NAME --wait`. Code can reach a notebook only while a browser has it open: that is marimo's rule, not ours.
3. `mo code NAME -c "import marimo._code_mode as cm; help(cm)"`. This is the skill's required first call.
4. From then on, follow the marimo-pair skill exactly, writing `mo code NAME` wherever it writes `execute-code.sh --url …`. Heredocs work as the skill shows: `mo code NAME - <<'PY'` … `PY`.

**Rules.**

- Never run bare `mo PATH`, and never read `~/.local/state/portico/`. The first prints the author's access link with its token, and the token must not enter a transcript. `pair`, `code` and `ls` never print it.
- Never start marimo by hand, and above all never with `--no-token`. marimo does not check where a connection comes from, so a token-free server lets any web page open in any of the author's browsers run code on this machine.
- Do not stop or restart a notebook the author is using. Stopping discards the kernel's state. Ask first.
- If two browser tabs have the notebook open, `mo code` stops with "Multiple active sessions". Pass the `--session ID` it lists for the tab you mean.
- When `mo pair` says marimo is not installed, it lists every environment it tried. Adding marimo to a repo is the author's decision (`uv add marimo` in the repo root), so ask.
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

# {{ cookiecutter.project_name | upper }}, THIS REPO IN PARTICULAR

- The hosts this repository uses are named in `[tool.zetteldev]` of `pyproject.toml`; what differs per person lives in `~/.config/zetteldev/config.toml`. `just doctor` says what is still missing (the setup guide above).
- Models served from the cluster are blocks of `.zetteldev/della/targets.yaml`; long-lived services are blocks of `.zetteldev/services.yaml`.
- Add here what an agent must know about this repository alone: the project module's name, where the main corpus lives, which models and services the experiments lean on.

## THE REQUEST BEGINS
