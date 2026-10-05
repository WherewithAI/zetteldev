"""The SolveIt sync's guard against an open dialog writing an older state over newer work (.zetteldev/nb_regression.py and
.zetteldev/solveit_guard.sh). The fixtures mirror the clobber of 2026-09-11: the server re-saved notebook 6 without its last
thirteen cells, every remaining cell byte-identical."""
import json, os, pathlib, shutil, subprocess, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".zetteldev"))
from nb_regression import regression  # noqa: E402


def nb(*cells):
    return {"cells": [{"id": cid, "cell_type": "code", "source": src, "metadata": {}, "outputs": [], "execution_count": None} for cid, src in cells],
            "metadata": {}, "nbformat": 4, "nbformat_minor": 5}


REF = nb(("a1", "import pandas as pd"), ("b2", "df = pd.DataFrame()"), ("c3", "> **The baseline.** paired run"), ("d4", "fig = plot(df)"))


def test_identical_is_not_a_regression():
    assert regression(REF, REF) is None


def test_truncated_tail_is_a_regression():
    clobbered = nb(*[(c["id"], c["source"]) for c in REF["cells"][:2]])
    why = regression(clobbered, REF)
    assert why and "2 cell(s)" in why and "c3" in why


def test_the_newer_file_is_not_a_regression_of_the_older():
    clobbered = nb(*[(c["id"], c["source"]) for c in REF["cells"][:2]])
    assert regression(REF, clobbered) is None


def test_a_new_cell_is_the_authors_work():
    cand = nb(*[(c["id"], c["source"]) for c in REF["cells"][:2]], ("e5", "new thought"))
    assert regression(cand, REF) is None


def test_an_edited_cell_is_the_authors_work():
    cand = nb(("a1", "import pandas as pd, numpy as np"), ("b2", "df = pd.DataFrame()"))
    assert regression(cand, REF) is None


def test_a_deletion_beside_an_addition_is_left_to_the_merge():
    cand = nb(("a1", "import pandas as pd"), ("b2", "df = pd.DataFrame()"), ("z9", "replacement"))
    assert regression(cand, REF) is None


def test_an_empty_candidate_is_a_regression():
    assert regression(nb(), REF)


def test_cells_without_ids_fall_back_to_position():
    ref = {"cells": [{"cell_type": "code", "source": "x"}, {"cell_type": "code", "source": "y"}]}
    cand = {"cells": [{"cell_type": "code", "source": "x"}]}
    assert regression(cand, ref)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    "A checkout shaped like the SolveIt clone: the guard's scripts in .zetteldev, one committed notebook."
    (tmp_path / ".zetteldev").mkdir(); (tmp_path / "experiments").mkdir()
    for name in ("nb_regression.py", "solveit_guard.sh"): shutil.copy(ROOT / ".zetteldev" / name, tmp_path / ".zetteldev" / name)
    git("init", "-q", cwd=tmp_path); git("config", "user.email", "t@t", cwd=tmp_path); git("config", "user.name", "t", cwd=tmp_path)
    (tmp_path / "experiments/nb6.ipynb").write_text(json.dumps(REF))
    git("add", "-A", cwd=tmp_path); git("commit", "-q", "-m", "the machine's state, pushed into SolveIt", cwd=tmp_path)
    return tmp_path


def guard(repo, mode="restore"):
    p = subprocess.run(["bash", ".zetteldev/solveit_guard.sh", mode], cwd=repo, capture_output=True, text=True)
    return p.returncode, p.stdout


def test_guard_restores_a_clobbered_notebook_instead_of_letting_it_be_committed(repo):
    f = repo / "experiments/nb6.ipynb"
    f.write_text(json.dumps(nb(*[(c["id"], c["source"]) for c in REF["cells"][:2]])))       # the server's re-save of an older state
    rc, out = guard(repo)
    assert rc == 3 and "REGRESSION" in out and "RESTORED" in out
    assert json.loads(f.read_text()) == REF                                                 # the machine's version is back on disk
    assert git("status", "--short", cwd=repo).strip() == ""                                  # nothing left for the sync to commit


def test_guard_leaves_real_edits_for_the_merge(repo):
    f = repo / "experiments/nb6.ipynb"
    edited = nb(*[(c["id"], c["source"]) for c in REF["cells"]], ("e5", "the author's new cell"))
    f.write_text(json.dumps(edited))
    rc, out = guard(repo)
    assert rc == 0 and out.strip() == ""
    assert json.loads(f.read_text()) == edited


def test_guard_report_mode_does_not_touch_the_file(repo):
    f = repo / "experiments/nb6.ipynb"; clob = nb(("a1", "import pandas as pd"))
    f.write_text(json.dumps(clob))
    rc, out = guard(repo, "report")
    assert rc == 3 and "RESTORED" not in out and json.loads(f.read_text()) == clob


def _default_branch(repo):
    return git("branch", "--show-current", cwd=repo).strip()


def test_committed_mode_flags_a_regression_on_the_remote_branch(repo):
    "A clobbered notebook that the server committed itself: the sync must refuse to merge it."
    local = _default_branch(repo)
    git("checkout", "-q", "-b", "remote", cwd=repo)
    (repo / "experiments/nb6.ipynb").write_text(json.dumps(nb(("a1", "import pandas as pd"))))
    git("commit", "-q", "-am", "server re-saved an old state", cwd=repo)
    git("checkout", "-q", local, cwd=repo)
    p = subprocess.run(["bash", ".zetteldev/solveit_guard.sh", "committed", local, "remote"], cwd=repo, capture_output=True, text=True)
    assert p.returncode == 3 and "REGRESSION" in p.stdout and "committed on remote" in p.stdout


def test_committed_mode_passes_real_remote_work(repo):
    local = _default_branch(repo)
    git("checkout", "-q", "-b", "remote", cwd=repo)
    (repo / "experiments/nb6.ipynb").write_text(json.dumps(nb(*[(c["id"], c["source"]) for c in REF["cells"]], ("e5", "new"))))
    git("commit", "-q", "-am", "author added a cell on SolveIt", cwd=repo)
    git("checkout", "-q", local, cwd=repo)
    p = subprocess.run(["bash", ".zetteldev/solveit_guard.sh", "committed", local, "remote"], cwd=repo, capture_output=True, text=True)
    assert p.returncode == 0 and p.stdout.strip() == ""


# ---- 2026-09-13: the guard's blind spot. The server wrote back a snapshot 38 hours old; HEAD had since re-transcribed one
# of its cells (penman rewrote c3), so against HEAD alone the snapshot looked like "one edited cell" and its deletions passed.
from nb_regression import reconcile  # noqa: E402

OLD = nb(("a1", "import pandas as pd"), ("b2", "df = pd.DataFrame()"), ("c3", "### On the Epistemic Advantage\npolished by hand"))
MID = nb(("a1", "import pandas as pd"), ("b2", "df = pd.DataFrame()"), ("c3", "On the Epistemic Advantage.\nre-transcribed"))
HEAD = nb(*[(c["id"], c["source"]) for c in MID["cells"]], ("d4", "fig = plot(df)"), ("e5", "> **The 4B pair.** two arms"))


def test_an_old_snapshot_that_head_has_since_edited_is_a_regression():
    assert regression(OLD, HEAD) is None                                   # the HEAD-only rule is blind to this shape
    why = regression(OLD, HEAD, history=[MID, OLD])
    assert why and "snapshot" in why and "d4" in why


def test_real_edits_of_the_current_state_pass_with_history():
    cand = nb(*[(c["id"], c["source"]) for c in HEAD["cells"][:2]], ("c3", "edited now"), ("d4", "fig = plot(df)"), ("e5", "> **The 4B pair.** two arms"))
    assert regression(cand, HEAD, history=[MID, OLD]) is None


def test_a_deliberate_deletion_that_matches_no_ancestor_is_left_to_the_merge():
    cand = nb(("a1", "import pandas as pd"), ("c3", "On the Epistemic Advantage.\nre-transcribed"), ("e5", "> **The 4B pair.** two arms"), ("f6", "new"))
    assert regression(cand, HEAD, history=[MID, OLD]) is None


def test_reconcile_keeps_edits_made_in_the_stale_copy_where_head_left_the_cell_alone():
    cand = nb(("a1", "import pandas as pd, numpy as np"), ("b2", "df = pd.DataFrame()"), ("c3", "### On the Epistemic Advantage\npolished again"))
    merged, applied, conflicts = reconcile(cand, HEAD, OLD)
    got = {c["id"]: c["source"] for c in merged["cells"]}
    assert [c["id"] for c in merged["cells"]] == ["a1", "b2", "c3", "d4", "e5"]       # HEAD's cells and order
    assert got["a1"] == "import pandas as pd, numpy as np" and applied == ["a1"]        # the edit survives
    assert got["c3"] == HEAD["cells"][2]["source"] and conflicts == ["c3"]              # HEAD changed c3 since the snapshot: HEAD wins


def test_guard_reconciles_an_old_snapshot_with_edits(repo):
    f = repo / "experiments/nb6.ipynb"
    for state, msg in ((OLD, "old"), (MID, "penman re-transcribed c3"), (HEAD, "two cells added from the machine")):
        f.write_text(json.dumps(state)); git("commit", "-q", "-am", msg, cwd=repo)
    stale = nb(("a1", "import pandas as pd, numpy as np"), ("b2", "df = pd.DataFrame()"), ("c3", "### On the Epistemic Advantage\npolished by hand"))
    f.write_text(json.dumps(stale))                                                    # the browser's copy, saved with one edit
    rc, out = guard(repo)
    assert rc == 3 and "REGRESSION" in out and "RECONCILED" in out and "a1" in out
    got = json.loads(f.read_text()); srcs = {c["id"]: c["source"] for c in got["cells"]}
    assert [c["id"] for c in got["cells"]] == ["a1", "b2", "c3", "d4", "e5"]
    assert srcs["a1"] == "import pandas as pd, numpy as np" and srcs["c3"] == HEAD["cells"][2]["source"]
    assert "nb6.ipynb" in git("status", "--short", cwd=repo)                            # the kept edit is a real change for the sync to commit


def test_committed_mode_sees_an_old_snapshot_through_history(repo):
    f = repo / "experiments/nb6.ipynb"
    for state, msg in ((OLD, "old"), (MID, "penman re-transcribed c3"), (HEAD, "two cells added from the machine")):
        f.write_text(json.dumps(state)); git("commit", "-q", "-am", msg, cwd=repo)
    local = _default_branch(repo)
    git("checkout", "-q", "-b", "remote", cwd=repo); f.write_text(json.dumps(OLD)); git("commit", "-q", "-am", "server committed its snapshot", cwd=repo)
    git("checkout", "-q", local, cwd=repo)
    p = subprocess.run(["bash", ".zetteldev/solveit_guard.sh", "committed", local, "remote"], cwd=repo, capture_output=True, text=True)
    assert p.returncode == 3 and "snapshot" in p.stdout
