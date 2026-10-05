"""Is one notebook an older state of another?  The guard the SolveIt sync needs.

The SolveIt server holds an open dialog in memory and writes it back to the .ipynb whenever it likes, so a file with a fresh
modification time can carry content that is hours old. Committing and merging such a file deletes the newer cells on every
machine (2026-09-11: the baseline section and the query gallery of exp35's notebook 6 vanished twice this way; 2026-09-13: a
snapshot 38 hours old took the 4B section and two code fixes). Timestamps cannot tell the two apart; content can.

Two shapes are recognised:

1. Against the reference alone: every cell of the candidate appears in the reference with the same id and source, and the
   reference has at least one cell the candidate lacks. Nothing new, nothing edited.
2. Against the reference's history (older committed versions, most recent first): the candidate has exactly the cells, in the
   order, of some older version. That is a stale copy, whatever its sources say: the cells edited on top of it are the
   author's work in a stale tab and are kept by `reconcile`, which rebuilds the file from the reference and overlays those
   edits wherever the reference still has the older version's source (a cell the reference changed since is a conflict and
   the reference wins). Shape 1 missed the 2026-09-13 snapshot because the reference had itself re-written one cell since
   (penman re-transcribed a page), so the snapshot's old text looked like an edit.

Anything else (a new cell, an edited cell of the current state, a deletion beside an addition) is the author's work and is
left to the ordinary merge.

    python .zetteldev/nb_regression.py check CANDIDATE.ipynb REFERENCE.ipynb [OLDER.ipynb ...] [--write OUT.ipynb]
        exit 0 = regression (OUT, when asked, holds the reconciled notebook), 1 = not, 2 = unreadable
"""
import copy, json, sys


def cells(nb: dict) -> dict:
    "Cell id -> source, in the notebook's own order."
    out = {}
    for i, c in enumerate(nb.get("cells", [])):
        cid = c.get("id") or c.get("metadata", {}).get("id") or f"#{i}"
        src = c.get("source", ""); out[cid] = "".join(src) if isinstance(src, list) else src
    return out


def snapshot_of(candidate: dict, history: list) -> tuple:
    "The index of the older version whose cells and order the candidate has exactly, with the fewest cells edited on top (the most recent among ties), and those ids; (None, []) when none."
    cand = cells(candidate); best = (None, [])
    for i, h in enumerate(history):
        old = cells(h)
        if list(old) != list(cand): continue
        edited = [cid for cid, src in cand.items() if old[cid] != src]
        if best[0] is None or len(edited) < len(best[1]): best = (i, edited)
    return best


def regression(candidate: dict, reference: dict, history: list = ()) -> str | None:
    "Why the candidate is an older state of the reference, or None when it is not. `history`: the reference's older versions, most recent first."
    cand, ref = cells(candidate), cells(reference)
    if cand == ref or list(cand) == list(ref): return None                  # identical, or edits of the current state
    i, edited = snapshot_of(candidate, list(history))
    if i is not None:
        missing = [cid for cid in ref if cid not in cand]
        return (f"snapshot of the version {i + 1} commit(s) back: {len(missing)} cell(s) of the reference absent ({', '.join(missing[:4])}{', ...' if len(missing) > 4 else ''})"
                f", {len(edited)} cell(s) edited on top of the snapshot ({', '.join(edited[:4])})")
    new = [cid for cid in cand if cid not in ref]
    if new: return None
    edited = [cid for cid, src in cand.items() if ref[cid] != src]
    if edited: return None
    missing = [cid for cid in ref if cid not in cand]
    if not missing: return None
    return f"{len(missing)} cell(s) of the reference are absent ({', '.join(missing[:4])}{', ...' if len(missing) > 4 else ''}) and nothing is new or edited"


def reconcile(candidate: dict, reference: dict, ancestor: dict) -> tuple:
    "The reference with the candidate's edits (relative to `ancestor`) overlaid where the reference kept the ancestor's source: (notebook, applied ids, conflicting ids)."
    cand, ref, old = cells(candidate), cells(reference), cells(ancestor)
    by_id = {(c.get("id") or c.get("metadata", {}).get("id") or f"#{i}"): c for i, c in enumerate(candidate.get("cells", []))}
    merged = copy.deepcopy(reference); applied, conflicts = [], []
    for i, c in enumerate(merged.get("cells", [])):
        cid = c.get("id") or c.get("metadata", {}).get("id") or f"#{i}"
        if cid not in cand or cid not in old or cand[cid] == old[cid]: continue
        if ref[cid] == old[cid]: merged["cells"][i] = copy.deepcopy(by_id[cid]); applied.append(cid)
        else: conflicts.append(cid)
    return merged, applied, conflicts


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f: return json.load(f)


if __name__ == "__main__":
    args = sys.argv[1:]; out = None
    if "--write" in args: k = args.index("--write"); out = args[k + 1]; args = args[:k] + args[k + 2:]
    if len(args) < 3 or args[0] != "check": print(__doc__); sys.exit(2)
    try:
        candidate, reference, history = load(args[1]), load(args[2]), [load(p) for p in args[3:]]
        why = regression(candidate, reference, history)
    except (OSError, ValueError) as e: print(f"unreadable: {e}"); sys.exit(2)
    if not why: sys.exit(1)
    print(f"REGRESSION {args[1]}: {why}")
    if out:
        i, edited = snapshot_of(candidate, history)
        merged, applied, conflicts = reconcile(candidate, reference, history[i]) if i is not None and edited else (reference, [], [])
        with open(out, "w", encoding="utf-8") as f: json.dump(merged, f, indent=1, ensure_ascii=False); f.write("\n")
        print(f"applied: {', '.join(applied) or 'none'}; conflicts (reference kept): {', '.join(conflicts) or 'none'}")
    sys.exit(0)
