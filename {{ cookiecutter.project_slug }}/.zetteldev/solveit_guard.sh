#!/usr/bin/env bash
# The guard the SolveIt sync runs inside a checkout before it commits the server's dialog state: a tracked notebook whose
# working copy is an OLDER state of HEAD (see .zetteldev/nb_regression.py) is not a change to keep but the server's memory
# overwriting newer work. It is judged against HEAD and against the file's recent committed history (a snapshot of an older
# commit is stale whatever HEAD has since rewritten), then rebuilt from HEAD with any edits made on top of the snapshot kept.
# HEAD on the SolveIt clone is what this machine last pushed, so "restore from HEAD" is "merge from the machine".
# Usage: solveit_guard.sh [restore|report]          the working tree against HEAD
#        solveit_guard.sh committed LOCAL REMOTE      notebooks already committed on REMOTE that are older states of LOCAL's
# Exit 0 = nothing regressed, 3 = regression(s) found (and restored or reconciled in restore mode). GUARD_HISTORY (40) commits are consulted.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 2
mode="${1:-restore}"; rc=0

# The distinct older versions of notebook $2 before ref $1, most recent first, as temp files (one path per line).
history_files() {
  local ref="$1" f="$2" seen sha blob t
  seen=$(git rev-parse "$ref:$f" 2>/dev/null)
  for sha in $(git log --format=%H -n "${GUARD_HISTORY:-40}" "$ref" -- "$f"); do
    blob=$(git rev-parse "$sha:$f" 2>/dev/null) || continue
    case " $seen " in *" $blob "*) continue;; esac
    seen="$seen $blob"; t=$(mktemp); git show "$sha:$f" > "$t" && echo "$t"
  done
}

if [ "$mode" = committed ]; then
  local_ref="$2"; remote_ref="$3"
  for f in $(git diff --name-only "$local_ref" "$remote_ref" -- '*.ipynb'); do
    a=$(mktemp); b=$(mktemp); hist=$(history_files "$local_ref" "$f")
    if git show "$remote_ref:$f" > "$a" 2>/dev/null && git show "$local_ref:$f" > "$b" 2>/dev/null && why=$(python3 .zetteldev/nb_regression.py check "$a" "$b" $hist); then
      echo "$why (committed on $remote_ref; $local_ref keeps the newer state)"; rc=3
    fi
    rm -f "$a" "$b" $hist
  done
  exit $rc
fi
for f in $(git diff --name-only -- '*.ipynb'); do
  tmp=$(mktemp); git show "HEAD:$f" > "$tmp" 2>/dev/null || { rm -f "$tmp"; continue; }
  hist=$(history_files HEAD "$f"); out=$(mktemp)
  if why=$(python3 .zetteldev/nb_regression.py check "$f" "$tmp" $hist --write "$out"); then
    echo "$why"
    if [ "$mode" = restore ]; then
      if grep -q "^applied: none" <<< "$why"; then
        git checkout -q -- "$f" && echo "RESTORED $f from HEAD; the dialog open on the server still holds the old state, so re-open it (just sicx open) before editing it"
      else
        mv "$out" "$f" && echo "RECONCILED $f: HEAD plus the edits made on top of the snapshot ($(grep -o '^applied: [^;]*' <<< "$why")); the dialog open on the server still holds the old state"
      fi
    fi
    rc=3
  fi
  rm -f "$tmp" "$out" $hist
done
exit $rc
