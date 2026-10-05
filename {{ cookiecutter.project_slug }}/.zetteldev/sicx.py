"""sicx: the SolveIt client with a memory and a wait.

`sic` (solveit_client) needs the server URL, the dialog name and a message id on every call, and its
`exec` returns before a long cell finishes and is dropped by the server when the kernel is busy. This
wrapper fixes the ergonomics from outside the package:

- the dialog comes from `--name`, `$SOLVEIT_DIALOG`, or the nearest `.solveit-dialog` file above the cwd
  (`sicx use <dialog>` writes one);
- `run` waits until no cell is queued or running, queues the cell, waits for it to finish, and prints its
  output as text (tables as rows, html stripped), exiting 1 on a traceback;
- `add` and `edit` take the cell body from a file, so no shell quoting;
- `bootstrap` re-runs every export cell in order after a kernel restart;
- `apply FILE` brings the live dialog into line with a notebook file through the API (edited cells updated, missing
  cells added after their predecessors, live-only cells reported, nothing deleted, the file untouched): the server keeps
  a loaded dialog in memory for the life of its process and writes that memory over the file, so a git push cannot
  reach an open dialog and this is the route that can; `--if-open` skips dialogs the server has not loaded;
- `out`, `status`, `slim`, `stop`, `open`, `list` do what they say.

Usage:  just sicx <command> [args]      (see `just sicx --help`)
"""
import argparse, html, json, os, re, sys, time
import httpx
from pathlib import Path
from solveit_client.core import SolveItClient, Dialog, Message

__all__ = ["dialog", "run", "state", "queued", "wait_idle", "as_text", "export_cells", "find_dialog", "client", "DIALOG_FILE"]

DIALOG_FILE = ".solveit-dialog"


def find_dialog(name=None):
    "The dialog name from the flag, the environment, or the nearest `.solveit-dialog` file above the cwd."
    if name: return name
    if os.environ.get("SOLVEIT_DIALOG"): return os.environ["SOLVEIT_DIALOG"]
    for d in [Path.cwd(), *Path.cwd().parents]:
        f = d / DIALOG_FILE
        if f.exists(): return f.read_text().strip()
    sys.exit(f"no dialog: pass --name, set SOLVEIT_DIALOG, or run `sicx use <dialog>` to write {DIALOG_FILE}")


def client(url=None):
    c = SolveItClient(url or os.environ.get("SOLVEIT_URL") or "http://localhost:5001"); c.cli.timeout = httpx.Timeout(120.0); return c


def retry(fn, tries=5, wait=3.0):
    "The server answers slowly while a cell runs; a transport timeout is a reason to ask again, not to give up."
    for i in range(tries):
        try: return fn()
        except (httpx.TimeoutException, httpx.TransportError):
            if i == tries - 1: raise
            time.sleep(wait)


def as_text(output, chars=3000, tables=True):
    "A message's stored output as readable text: html tables as ` | `-joined rows, other tags stripped, tail-truncated."
    o = str(output or "")
    o = re.sub(r"<style.*?</style>", "", o, flags=re.S); o = re.sub(r"<img[^>]*>", "[image]", o)
    if tables:
        def table_rows(m):
            rows = re.findall(r"<tr>(.*?)</tr>", m.group(0), flags=re.S)
            return "\n" + "\n".join(" | ".join(html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, flags=re.S)) for r in rows) + "\n"
        o = re.sub(r"<table.*?</table>", table_rows, o, flags=re.S)
    o = html.unescape(re.sub(r"<[^>]+>", " ", o)); o = re.sub(r"[ \t]+", " ", o); o = re.sub(r"\n\s*\n+", "\n", o).strip()
    return o if len(o) <= chars else "…[" + str(len(o) - chars) + " chars trimmed]…\n" + o[-chars:]


def state(dlg, id):
    "(run flag, time_run, output) of one message, read through the message list so a running cell never blocks the read."
    for m in retry(lambda: dlg.messages):
        if m.id == id: return m.data.get("run"), m.data.get("time_run"), m.data.get("output")
    sys.exit(f"message {id} not found in {dlg.name}")


def queued(dlg):
    "Ids of messages queued or running (their `run` flag is set)."
    return [m.id for m in retry(lambda: dlg.messages) if m.data.get("run")]


def wait_idle(dlg, timeout, poll=2.0):
    t0 = time.time()
    while (q := queued(dlg)):
        if time.time() - t0 > timeout: sys.exit(f"kernel still busy with {q} after {timeout}s; `sicx stop` restarts it")
        time.sleep(poll)


def probe_kernel(dlg, timeout=8.0, poll=0.5):
    "Is the kernel alive? A one-line code cell is added, queued and deleted; True when its run flag clears in `timeout` s. A dead ipymini (OOM-killed under the 4 GiB cgroup, 2026-09-20 twice) leaves every message's run flag unset, so `status` said idle and `run` waited its full timeout on nothing; only a real execution tells."
    if queued(dlg): return True      # something is running, so the kernel is alive
    m = retry(lambda: dlg.add_msg("pass  # sicx liveness probe", msg_type="code"))
    try:
        retry(lambda: dlg.cli("/add_runq_", dlg_name=dlg.name, id_=m.id, api="true")); t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(poll); flag, t_run, _ = state(dlg, m.id)
            if not flag and t_run: return True
        return False
    finally:
        try: retry(lambda: Message(m.id, dlg).delete())
        except Exception: pass

def run(dlg, id, timeout=3600, poll=2.0, keep_output=False, chars=3000):
    "Queue-safe execution: wait until nothing is queued, queue the cell, wait until its run flag clears and its time_run advances; return (ok, output_text)."
    wait_idle(dlg, timeout, poll)
    if not probe_kernel(dlg): sys.exit(f"the kernel of {dlg.name} is not answering (dead ipymini?); `sicx stop` then `sicx open` starts a fresh one, `sicx bootstrap` reloads the exports")
    m = Message(id, dlg)
    if not keep_output: retry(lambda: m.update(output="[]"))
    _, t_before, _ = state(dlg, id)
    retry(lambda: dlg.cli("/add_runq_", dlg_name=dlg.name, id_=id, api="true"))
    t0 = time.time()
    while True:
        time.sleep(poll); flag, t_run, out = state(dlg, id)
        if not flag and t_run and t_run != t_before: break
        if time.time() - t0 > timeout: sys.exit(f"timeout after {timeout}s waiting for {id}; the kernel may need `sicx stop`")
    return "Traceback (most recent call last)" not in str(out or ""), as_text(out, chars)


def export_cells(dlg, pattern=r"^#\|(default_exp|export(?! selector_tinker))"):
    "Code messages whose first line matches `pattern`, in dialog order."
    return [m for m in retry(lambda: dlg.messages) if m.msg_type == "code" and re.match(pattern, (m.content or "").split("\n", 1)[0])]


import hashlib
CACHE_DIR = Path.home() / ".local" / "state" / "sicx"

def content_hash(text) -> str: return hashlib.sha1((text or "").encode()).hexdigest()[:12]

def cache_path(name: str) -> Path: return CACHE_DIR / (name.replace("/", "__") + ".json")

def remember(name: str, messages) -> dict:
    "Record the content hash of every message seen by a view (list, out, run, edit), the address book an edit is checked against."
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    seen = {m.id: content_hash(m.content) for m in messages}
    cache_path(name).write_text(json.dumps(seen)); return seen

def remembered(name: str) -> dict:
    try: return json.loads(cache_path(name).read_text())
    except (OSError, ValueError): return {}

def assert_unchanged(name: str, msg, force: bool = False):
    "Refuse to overwrite a cell whose content differs from the last view, unless forced: the dialog's twin of exhash's stale-address check."
    seen = remembered(name).get(msg.id)
    live = content_hash(msg.content)
    if seen is None and not force: sys.exit(f"{msg.id}: not seen since the last `sicx list`; view it first (or --force)")
    if seen is not None and seen != live and not force: sys.exit(f"{msg.id}: its content changed since your last view (the author, or another session); `sicx list` to refresh, then edit again (or --force)")

def dialog(name: str | None = None, url: str | None = None) -> Dialog:
    "The Dialog to work on: `name`, else $SOLVEIT_DIALOG, else the nearest .solveit-dialog file. Pass it to run/state/queued."
    return Dialog(find_dialog(name), client(url))




def file_cells(path) -> list:
    "A notebook file's cells as (id, msg_type, source) in order, typed the way the server types messages: markdown is a note, markdown the AI answered is a prompt."
    nb = json.loads(Path(path).read_text(encoding="utf-8")); out = []
    for i, c in enumerate(nb.get("cells", [])):
        md = c.get("metadata", {}) or {}; src = c.get("source", ""); src = "".join(src) if isinstance(src, list) else src
        kind = "code" if c.get("cell_type") == "code" else ("prompt" if md.get("solveit_ai") else "note")
        if kind == "prompt": src = re.split(r"\n\n##### 🤖Reply🤖<!-- SOLVEIT_SEPARATOR_[0-9a-f]+ -->", src)[0]      # the file keeps the reply in the source; the server keeps it as output
        out.append((c.get("id") or md.get("id") or f"#{i}", kind, src))
    return out


def plan_apply(cells: list, live: list) -> tuple:
    """Bring a live dialog into line with a notebook's cells without touching the file: the ops to send, in order, and the live cells the file lacks.

    `cells` and `live` are (id, msg_type, content) lists. A file cell is matched to the live cell of the same id, or, when the
    server assigned a different id to the same content (an earlier add), to an unmatched live cell with the same type and content.
    Matched cells whose content or type differs become ("update", live_id, type, content); unmatched file cells become
    ("add", file_id, type, content, anchor), where anchor is the preceding file cell's live id, the placeholder ("new", file_id)
    of a preceding cell this plan adds, or None for the first cell. Nothing is ever deleted: live cells absent from the file are
    returned for the caller to report."""
    live_by_id = {lid: (kind, content or "") for lid, kind, content in live}
    file_ids = {fid for fid, _, _ in cells}
    spare = [lid for lid, _, _ in live if lid not in file_ids]              # live cells the file does not name: content-match candidates
    ops, prev = [], None
    for fid, kind, src in cells:
        if fid in live_by_id:
            lkind, lcontent = live_by_id[fid]
            if lkind != kind or lcontent != src: ops.append(("update", fid, kind, src))
            prev = fid; continue
        twin = next((lid for lid in spare if live_by_id[lid] == (kind, src)), None)
        if twin is not None: spare.remove(twin); ops.append(("match", fid, twin)); prev = twin; continue
        ops.append(("add", fid, kind, src, prev)); prev = ("new", fid)
    return ops, spare


def apply(dlg, path, dry=False, run_cells=False):
    "Execute plan_apply against the live dialog; returns (added ids, updated ids, extra live ids)."
    live = [(m.id, m.msg_type, m.content) for m in retry(lambda: dlg.messages)]
    ops, extra = plan_apply(file_cells(path), live)
    new_ids, added, updated = {}, [], []; live_types = {lid: kind for lid, kind, _ in live}
    for op in ops:
        if op[0] == "match": continue
        if op[0] == "update":
            _, lid, kind, src = op; print(f"update {lid} ({kind})")
            if not dry: Message(lid, dlg).update(content=src, **({"msg_type": kind} if live_types.get(lid) != kind else {}))
            updated.append(lid); continue
        _, fid, kind, src, anchor = op
        anchor_id = new_ids.get(anchor[1]) if isinstance(anchor, tuple) else anchor
        placement = "add_after" if anchor_id else ("add_before" if live else "at_end"); ref = anchor_id or (live[0][0] if live else None)
        print(f"add {fid} ({kind}) {placement} {ref or ''}")
        if dry: new_ids[fid] = f"new:{fid}"; continue
        m = dlg.add_msg(src, msg_type=kind, placement=placement, id=ref); new_ids[fid] = m.id; added.append(m.id); print(f"  -> {m.id}")
    if extra: print("live cells the file lacks (left in place): " + " ".join(extra))
    if run_cells and not dry:
        for lid in updated + added:
            m = Message(lid, dlg); m._refresh()
            if m.msg_type == "code": ok, out = run(dlg, lid, timeout=1800, chars=300); print(("ok  " if ok else "ERR ") + lid + ("" if ok else "\n" + out))
    return added, updated, extra

def main(argv=None):
    p = argparse.ArgumentParser(prog="sicx", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", help="dialog name (else $SOLVEIT_DIALOG, else the nearest .solveit-dialog)"); p.add_argument("--url", help="server url (default $SOLVEIT_URL or http://localhost:5001)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("use", help="write .solveit-dialog in the cwd"); s.add_argument("dialog")
    sub.add_parser("open", help="create-or-open the dialog on the server (required after a server restart)")
    s = sub.add_parser("apply", help="bring the live dialog into line with a notebook FILE through the API: update edited cells, add missing ones, never delete, never touch the file"); s.add_argument("file"); s.add_argument("--dry", action="store_true"); s.add_argument("--run", action="store_true", help="run the code cells that were added or updated"); s.add_argument("--if-open", action="store_true", help="do nothing when the server has not loaded the dialog (its file already holds the pushed state)")
    sub.add_parser("status", help="queued cells and the last few messages")
    sub.add_parser("stop", help="stop the kernel (a fresh one starts on the next run); state is lost, see bootstrap")
    s = sub.add_parser("run", help="execute a cell queue-safely and wait; prints its output as text"); s.add_argument("id"); s.add_argument("--timeout", type=float, default=3600); s.add_argument("--chars", type=int, default=3000); s.add_argument("--keep-output", action="store_true")
    s = sub.add_parser("out", help="print a cell's stored output as text"); s.add_argument("id"); s.add_argument("--chars", type=int, default=3000)
    s = sub.add_parser("add", help="add a message whose body is read from a file"); s.add_argument("--after", help="anchor id"); s.add_argument("--before", help="anchor id"); s.add_argument("--type", default="code", choices=["code", "note", "prompt"]); s.add_argument("--file", required=True); s.add_argument("--run", action="store_true", help="run it after adding (code only)")
    s = sub.add_parser("edit", help="replace a message's content from a file (refused when the cell changed since your last view)"); s.add_argument("id"); s.add_argument("--file", required=True); s.add_argument("--run", action="store_true"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("replace", help="replace one exact substring in a message, checked live (the safe edit for a shared dialog)"); s.add_argument("id"); s.add_argument("--old", required=True, help="file holding the exact text to replace"); s.add_argument("--new", required=True, help="file holding the replacement"); s.add_argument("--run", action="store_true")
    s = sub.add_parser("bootstrap", help="run every export cell in order (after a restart)"); s.add_argument("--pattern", default=r"^#\|(default_exp|export(?! selector_tinker))"); s.add_argument("--also", nargs="*", default=[], help="extra cell ids to run after the exports"); s.add_argument("--dry", action="store_true")
    s = sub.add_parser("slim", help="list the largest stored outputs; --truncate replaces those above --min-bytes with a tail"); s.add_argument("--min-bytes", type=int, default=200_000); s.add_argument("--truncate", action="store_true"); s.add_argument("--keep", type=int, default=4000)
    s = sub.add_parser("list", help="one line per message: id, type, head of the content, output size; a * marks a cell changed since the previous list"); s.add_argument("--chars", type=int, default=70); s.add_argument("--changed", action="store_true", help="only the cells changed since the previous list")
    s = sub.add_parser("dump", help="every message as JSON (id, msg_type, content, output) to stdout or --out FILE: the way to read a run of cells, e.g. the author's pages, in one go"); s.add_argument("--out", help="write here instead of stdout"); s.add_argument("--ids", nargs="*", help="only these ids")
    s = sub.add_parser("delete", help="delete messages by id (your own scratch cells; the author's are theirs)"); s.add_argument("ids", nargs="+")
    a = p.parse_args(argv)
    if a.cmd == "use": Path(DIALOG_FILE).write_text(a.dialog + "\n"); print(f"{DIALOG_FILE} -> {a.dialog}"); return
    cli = client(a.url); name = find_dialog(a.name)
    if a.cmd == "open": cli.create_dialog(name); print("open", name); return
    dlg = Dialog(name, cli)
    if a.cmd == "status":
        q = queued(dlg); ms = retry(lambda: dlg.messages); alive = probe_kernel(dlg) if not q else True
        print(f"{name}\nkernel: {'busy with ' + ', '.join(q) if q else ('idle' if alive else 'DEAD (no answer to a probe cell; `sicx stop` then `sicx open`, then `sicx bootstrap`)')} | {len(ms)} messages | mode {dlg.mode}")
        for m in ms[-5:]: print(f"  {m.id} {m.msg_type:5s} {(m.content or '')[:60]!r}")
    elif a.cmd == "stop": dlg.stop(); print("stopped; the next run starts a fresh kernel (state lost: `sicx bootstrap`)")
    elif a.cmd == "dump":
        ms = retry(lambda: dlg.messages); want = set(a.ids or [])
        rows = [dict(id=m.id, msg_type=m.msg_type, content=m.content or "", output=m.output) for m in ms if not want or m.id in want]
        text = json.dumps(rows, indent=1, default=str)
        if a.out: Path(a.out).write_text(text); print(f"dumped {len(rows)} messages to {a.out}")
        else: print(text)
    elif a.cmd == "delete":
        for i in a.ids: retry(lambda: Message(i, dlg).delete()); print("deleted", i)
    elif a.cmd == "apply":
        if a.if_open:
            try: retry(lambda: dlg.messages)
            except Exception as e:
                if "not found" in str(e).lower(): print(f"apply {a.file}: dialog {name} is not open on the server; its file already holds the pushed state"); return
                raise
        added, updated, extra = apply(dlg, a.file, dry=a.dry, run_cells=a.run); remember(name, retry(lambda: dlg.messages))
        print(f"apply {'(dry) ' if a.dry else ''}{a.file}: {len(added)} added, {len(updated)} updated, {len(extra)} live-only")
    elif a.cmd == "run":
        ok, out = run(dlg, a.id, a.timeout, keep_output=a.keep_output, chars=a.chars); print(out); sys.exit(0 if ok else 1)
    elif a.cmd == "out": print(as_text(state(dlg, a.id)[2], a.chars))
    elif a.cmd == "add":
        body = Path(a.file).read_text(); placement, anchor = ("add_after", a.after) if a.after else (("add_before", a.before) if a.before else ("at_end", None))
        m = dlg.add_msg(body, msg_type=a.type, placement=placement, id=anchor); print(m.id)
        if a.run: ok, out = run(dlg, m.id); print(out); sys.exit(0 if ok else 1)
    elif a.cmd == "edit":
        m = Message(a.id, dlg); assert_unchanged(name, m, a.force)
        m.update(content=Path(a.file).read_text()); remember(name, retry(lambda: dlg.messages)); print("edited", a.id)
        if a.run: ok, out = run(dlg, a.id); print(out); sys.exit(0 if ok else 1)
    elif a.cmd == "replace":
        m = Message(a.id, dlg); old_s, new_s = Path(a.old).read_text(), Path(a.new).read_text()
        if (m.content or "").count(old_s) != 1: sys.exit(f"{a.id}: the old text occurs {(m.content or '').count(old_s)} times in the live cell; it must occur exactly once")
        m.update(content=(m.content or "").replace(old_s, new_s)); remember(name, retry(lambda: dlg.messages)); print("replaced in", a.id)
        if a.run: ok, out = run(dlg, a.id); print(out); sys.exit(0 if ok else 1)
    elif a.cmd == "bootstrap":
        cells = export_cells(dlg, a.pattern); ids = [m.id for m in cells] + list(a.also)
        print(f"{len(ids)} cells" + (" (dry run)" if a.dry else ""))
        for i in ids:
            if a.dry: print(" ", i, (Message(i, dlg).content or "")[:60].replace("\n", " ")); continue
            ok, out = run(dlg, i, timeout=1800, chars=400); print(("ok  " if ok else "ERR ") + i + ("" if ok else "\n" + out))
            if not ok: sys.exit(1)
    elif a.cmd == "slim":
        ms = sorted(retry(lambda: dlg.messages), key=lambda m: -len(str(m.output or "")))
        for m in ms[:12]: print(f"{len(str(m.output or '')):>10,}  {m.id}  {(m.content or '')[:60]!r}")
        if a.truncate:
            for m in ms:
                o = str(m.output or "")
                if len(o) < a.min_bytes: continue
                text = as_text(o, a.keep, tables=True)
                m.update(output=json.dumps([{"output_type": "stream", "name": "stdout", "text": "[output trimmed by sicx slim]\n" + text}])); print("trimmed", m.id)
    elif a.cmd == "list":
        before = remembered(name); ms = retry(lambda: dlg.messages); remember(name, ms)
        for m in ms:
            changed = before.get(m.id) not in (None, content_hash(m.content)) if before else False
            if a.changed and not changed: continue
            print(f"{m.id} {m.msg_type[0]}{'*' if changed else ' '} {(m.content or '')[:a.chars]!r} {'[' + str(len(str(m.output or ''))) + ']' if m.output else ''}")


if __name__ == "__main__": main()
