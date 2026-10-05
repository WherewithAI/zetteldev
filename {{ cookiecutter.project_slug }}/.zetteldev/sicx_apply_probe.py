"""Rehearse `sicx apply` on a scratch dialog under tmp/ on the SolveIt instance: seed a dialog, apply a file that edits one cell,
inserts one in the middle and appends two, check the live dialog, apply again and expect nothing, then delete the dialog and its
file.  python .zetteldev/sicx_apply_probe.py   (needs the SolveIt tunnel, like every sicx call)"""
import json, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sicx
from solveit_client.core import Dialog
NAME = "tmp/sicx_apply_probe"; PATH = f"/app/data/{NAME}.ipynb"
def ssh(cmd): return subprocess.run(["ssh", "-o", "BatchMode=yes", "solveit", cmd], capture_output=True, text=True).stdout.strip()
def cell(cid, src, kind="code"): return {"id": cid, "cell_type": "code" if kind == "code" else "markdown", "source": src, "metadata": {"solveit_ai": True} if kind == "prompt" else {}, **({"outputs": [], "execution_count": None} if kind == "code" else {})}
def nbfile(cells): f = tempfile.NamedTemporaryFile("w", suffix=".ipynb", delete=False); json.dump({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}, f); f.close(); return f.name
c = sicx.client()
seed = [cell("s1", "x = 1"), cell("s2", "> a note", "note"), cell("s3", "y = x + 1")]
ssh(f"mkdir -p /app/data/tmp && cat > {PATH} <<'NB'\n{json.dumps({'cells': seed, 'metadata': {}, 'nbformat': 4, 'nbformat_minor': 5})}\nNB")
c.create_dialog(NAME); dlg = Dialog(NAME, c)
def live(): return [(m.id, m.msg_type, m.content) for m in dlg.messages]
print("seeded live:", [l[0] for l in live()])
target = [cell("s1", "x = 10"), cell("mid", "> inserted between", "note"), cell("s2", "> a note", "note"), cell("s3", "y = x + 1"), cell("t4", "> appended note", "note"), cell("t5", "z = y * 2")]
f = nbfile(target)
added, updated, extra = sicx.apply(dlg, f); print("first apply:", len(added), "added", updated, "updated", extra, "extra")
L = live(); print("live now:", [(i, k, (t or "")[:18]) for i, k, t in L])
assert [k for _, k, _ in L] == ["code", "note", "note", "code", "note", "code"], "types/order"
assert [t for _, _, t in L] == [x["source"] for x in target], "contents in file order"
added2, updated2, extra2 = sicx.apply(dlg, f); print("second apply:", len(added2), "added", updated2, "updated", extra2, "extra"); assert not added2 and not updated2
m = dlg.add_msg("the author's own cell", msg_type="note"); added3, updated3, extra3 = sicx.apply(dlg, f); print("after an author cell, apply reports extra:", extra3); assert extra3 == [m.id] and not added3
print("disk untouched by apply? file cells:", ssh(f"python3 -c \"import json; print([c.get('id') for c in json.load(open('{PATH}'))['cells']])\""))
try: dlg.stop()
except Exception: pass
c("/rm_dialog_", dlg_name=NAME, api="true"); ssh(f"rm -f {PATH}"); os.unlink(f); print("PROBE_OK")
