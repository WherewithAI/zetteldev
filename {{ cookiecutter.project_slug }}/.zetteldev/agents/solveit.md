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
