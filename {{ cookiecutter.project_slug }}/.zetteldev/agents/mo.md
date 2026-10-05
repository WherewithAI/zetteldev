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
