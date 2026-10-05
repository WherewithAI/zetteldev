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
