"""`sicx apply`: bring a live SolveIt dialog into line with a notebook file through the API, never through the file. The server
keeps a loaded dialog in memory for the life of its process and writes that memory over the file, so a git push cannot deliver
cells to an open dialog (2026-09-11); this is the route that can. The plan is pure and tested here; the API run is rehearsed on a
scratch dialog by .zetteldev/sicx_apply_probe.py."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / ".zetteldev"))
from sicx import plan_apply, file_cells  # noqa: E402

LIVE = [("a1", "code", "import pandas as pd"), ("b2", "note", "> **The paired run.**"), ("c3", "code", "fig = plot(df)")]


def test_identical_needs_nothing():
    ops, extra = plan_apply(list(LIVE), LIVE)
    assert ops == [] and extra == []


def test_missing_tail_is_added_after_its_predecessor():
    cells = LIVE + [("d4", "note", "> closing"), ("e5", "code", "x = 1")]
    ops, extra = plan_apply(cells, LIVE)
    assert ops == [("add", "d4", "note", "> closing", "c3"), ("add", "e5", "code", "x = 1", ("new", "d4"))] and extra == []


def test_missing_middle_cell_anchors_to_the_cell_before_it():
    cells = [LIVE[0], ("m9", "note", "> inserted"), LIVE[1], LIVE[2]]
    ops, _ = plan_apply(cells, LIVE)
    assert ops == [("add", "m9", "note", "> inserted", "a1")]


def test_missing_first_cell_has_no_anchor():
    cells = [("z0", "note", "# title")] + LIVE
    ops, _ = plan_apply(cells, LIVE)
    assert ops == [("add", "z0", "note", "# title", None)]


def test_edited_cell_is_updated_in_place():
    cells = [("a1", "code", "import pandas as pd, numpy as np"), LIVE[1], LIVE[2]]
    ops, _ = plan_apply(cells, LIVE)
    assert ops == [("update", "a1", "code", "import pandas as pd, numpy as np")]


def test_type_change_is_an_update():
    cells = [LIVE[0], ("b2", "prompt", "> **The paired run.**"), LIVE[2]]
    ops, _ = plan_apply(cells, LIVE)
    assert ops == [("update", "b2", "prompt", "> **The paired run.**")]


def test_same_content_under_a_server_assigned_id_is_matched_not_duplicated():
    "After an earlier add the server holds the cell under its own id; the file still names ours. A second apply must not add it again."
    live = LIVE + [("srv77", "note", "> closing")]
    cells = LIVE + [("d4", "note", "> closing"), ("e5", "code", "x = 1")]
    ops, extra = plan_apply(cells, live)
    assert ops == [("match", "d4", "srv77"), ("add", "e5", "code", "x = 1", "srv77")] and extra == []


def test_live_only_cells_are_reported_never_deleted():
    live = LIVE + [("auth1", "note", "the author's new thought")]
    ops, extra = plan_apply(list(LIVE), live)
    assert ops == [] and extra == ["auth1"]


def test_empty_dialog_gets_everything():
    ops, extra = plan_apply(list(LIVE), [])
    assert [o[0] for o in ops] == ["add"] * 3 and ops[0][4] is None and ops[1][4] == ("new", "a1")


def test_file_cells_types_and_ids(tmp_path):
    nb = {"cells": [{"id": "c1", "cell_type": "code", "source": ["x = 1\n", "x"], "metadata": {}},
                    {"id": "n1", "cell_type": "markdown", "source": "> note", "metadata": {}},
                    {"id": "p1", "cell_type": "markdown", "source": "what is x?", "metadata": {"solveit_ai": True}}]}
    f = tmp_path / "nb.ipynb"; f.write_text(json.dumps(nb))
    assert file_cells(f) == [("c1", "code", "x = 1\nx"), ("n1", "note", "> note"), ("p1", "prompt", "what is x?")]


def test_prompt_cells_carry_only_the_prompt_the_reply_is_output(tmp_path):
    src = "what is x?\n\n##### 🤖Reply🤖<!-- SOLVEIT_SEPARATOR_7f3a9b2c -->\n\nx is one."
    nb = {"cells": [{"id": "p1", "cell_type": "markdown", "source": src, "metadata": {"solveit_ai": True}}]}
    f = tmp_path / "nb.ipynb"; f.write_text(json.dumps(nb))
    assert file_cells(f) == [("p1", "prompt", "what is x?")]
