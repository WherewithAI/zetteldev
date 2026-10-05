#!/usr/bin/env bash
# The git cycle between this machine (the source of truth) and the SolveIt clone, driven entirely from here:
#   1. on SolveIt, commit any dialog changes the server has not committed itself (metadata churn from opening dialogs);
#   2. fetch SolveIt's branch through the `solveit` git remote (ssh; SolveIt holds no GitHub credentials);
#   3. merge it into the local branch (nbdev's merge driver resolves notebook conflicts cell by cell; anything it
#      cannot resolve aborts the merge and leaves a line in the log for a human);
#   4. push the branch to origin, then push it into SolveIt's checked-out branch, which fast-forwards its working
#      tree (receive.denyCurrentBranch=updateInstead on that clone; an untracked file the push would write refuses it, hence step 1 adopts figures).
# Usage: solveit_sync.sh [status|sync]     Log: ~/.local/state/solveit-sync.log     Lock: ~/.local/state/solveit-sync.lock
set -uo pipefail
export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-$HOME/.ssh/agent.sock}"     # cron has no agent; the login shell keeps this symlink current
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
cfg() { python3 .zetteldev/config.py "$1"; }
HOST=$(cfg solveit_host) && RPATH=$(cfg solveit_root) || exit 1
DPREFIX=$(basename "$RPATH")   # dialog names are paths under RPATH's parent
LOG="$HOME/.local/state/solveit-sync.log"; LOCK="$HOME/.local/state/solveit-sync.lock"; mkdir -p "$(dirname "$LOG")"
BR="$(git branch --show-current)"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

status() {
  git fetch -q solveit "$BR" 2>/dev/null || { echo "cannot fetch from $HOST"; exit 1; }
  git fetch -q origin "$BR" 2>/dev/null
  echo "branch $BR"
  echo "  local vs solveit : $(git rev-list --left-right --count "$BR...solveit/$BR" | awk '{print "local ahead "$1", solveit ahead "$2}')"
  echo "  local vs origin  : $(git rev-list --left-right --count "$BR...origin/$BR"  | awk '{print "local ahead "$1", origin ahead "$2}')"
  echo "  local dirty      : $(git status --short | wc -l) paths"
  echo "  solveit dirty    : $(ssh -o ConnectTimeout=20 "$HOST" "cd $RPATH && git status --short | wc -l" </dev/null) paths"
  echo "  last sync        : $(tail -n 1 "$LOG" 2>/dev/null || echo never)"
}

sync() {
  exec 9>"$LOCK"; flock -n 9 || { log "skip: another sync holds the lock"; exit 0; }
  bash .zetteldev/solveit-master >/dev/null || log "warn: solveit-master could not raise the forward; step 5 (apply) will report no answer"
  # 1. SolveIt: first the guard (.zetteldev/solveit_guard.sh): a notebook the server has written back as an OLDER state of what
  #    this machine last pushed is restored from HEAD, not committed; then commit what its server left uncommitted: NOTEBOOKS
  #    only, plus any figure a cell saved under experiments/*/figures (a new file left untracked there would refuse the push in
  #    step 4). Any other tracked file the server touched is restored from HEAD before the push (step 4): prose and scripts are
  #    authored on this machine, and a text file edited on both sides merges line by line and loses lines without a conflict
  #    (2026-09-22: papercuts.md, twice).
  guard_out=$(ssh -o ConnectTimeout=20 "$HOST" "cd $RPATH && test -f .zetteldev/solveit_guard.sh && bash .zetteldev/solveit_guard.sh restore" </dev/null 2>/dev/null)
  [ -n "$guard_out" ] && log "guard on $HOST: $guard_out"
  #    DVC pointer files (*.dvc, and the .gitignore DVC writes beside a tracked directory) are adopted like notebooks (2026-10-01):
  #    a result made on SolveIt and `dvc add`ed there is a pointer this machine must carry on, not restore.
  ssh -o ConnectTimeout=20 "$HOST" "cd $RPATH && git add -u -- '*.ipynb' '*.dvc' 'experiments/*/processed_data/.gitignore' && git ls-files --others --exclude-standard -- 'experiments/*/figures/*' '*.dvc' 'experiments/*/processed_data/.gitignore' | xargs -r git add -- && git diff --cached --quiet || git commit -q -m 'solveit sync: dialog state $(date -u '+%F %T UTC')'" </dev/null \
    || { log "fail: could not commit on $HOST"; exit 1; }
  # 2. fetch
  git fetch -q solveit "$BR" || { log "fail: fetch from $HOST"; exit 1; }
  behind=$(git rev-list --count "$BR..solveit/$BR")
  # 3. merge (only if there is something to merge), unless a notebook committed on SolveIt is an older state of ours
  if [ "$behind" -gt 0 ]; then
    committed_out=$(bash .zetteldev/solveit_guard.sh committed "$BR" "solveit/$BR")
    if [ -n "$committed_out" ]; then
      log "REGRESSION on solveit/$BR, not merging: $committed_out"
      log "fix on $HOST: git checkout $BR -- <notebook> from the newer state, or set its branch back to $(git rev-parse --short HEAD)"; exit 1
    fi
    # A text file (papercuts.md, a script) edited on both sides is merged by git line by line, and a stash-and-merge by hand can
    # lose one side's lines without a conflict (2026-09-22: seven papercut lines twice). Only notebooks and figures are SolveIt's
    # to change; any other path that differs on both sides since the merge base is reported and the merge refused.
    base=$(git merge-base "$BR" "solveit/$BR"); both=$(comm -12 <(git diff --name-only "$base" "$BR" | sort) <(git diff --name-only "$base" "solveit/$BR" | sort) | grep -vE '\.ipynb$|/figures/|/processed_data/.*\.gitignore$' || true)
    if [ -n "$both" ]; then log "REFUSED: edited on both sides since $(git rev-parse --short "$base"), not a notebook: $(echo "$both" | tr '\n' ' '); reconcile by hand, then sync"; exit 1; fi
    if ! git merge --no-edit -m "merge solveit/$BR: $behind SolveIt commit(s)" "solveit/$BR" >>"$LOG" 2>&1; then
      git merge --abort; log "CONFLICT: merge of solveit/$BR aborted; resolve by hand (git merge solveit/$BR)"; exit 1
    fi
  fi
  # 4. push out, then into SolveIt (updateInstead fast-forwards its working tree; refused if its tree is dirty)
  # A non-notebook file the server touched on SolveIt is no longer committed there (step 1); it would refuse the fast-forward
  # push, so it is restored from HEAD first. Prose and scripts are authored here and carried in by the push.
  ssh -o ConnectTimeout=20 "$HOST" "cd $RPATH && git status --porcelain --untracked-files=no | awk '\$2 !~ /\\.ipynb\$/ {print \$2}' | xargs -r git checkout -q HEAD --" </dev/null || true
  git push -q origin "$BR" || { log "fail: push origin"; exit 1; }
  ahead=$(git rev-list --count "solveit/$BR..$BR"); was=$(git rev-parse "solveit/$BR")
  if [ "$ahead" -gt 0 ]; then
    git push -q solveit "$BR" >>"$LOG" 2>&1 || { log "fail: push into $HOST (its working tree is probably dirty; run sync again)"; exit 1; }
    # 5. the push changed files, not the dialogs the server holds in memory (a loaded dialog outlives its kernel and its
    #    file, and writes its memory back over the file), so every notebook the push changed is also applied to its live
    #    dialog through the API (sicx apply: edited cells updated, missing cells added, nothing deleted, the file untouched)
    for nb in $(git diff --name-only "$was" "$BR" -- '*.ipynb'); do
      dname="${DPREFIX}/${nb%.ipynb}"
      out=$(uv run --quiet --with solveit-client python .zetteldev/sicx.py --name "$dname" apply "$nb" --if-open 2>/dev/null); out="${out##*$'\n'}"
      log "apply $nb: ${out:-no answer from the SolveIt api (tunnel down?); the open dialog will not see this push until applied}"
    done
  fi
  log "ok: merged $behind from solveit, pushed $ahead into it, $BR at $(git rev-parse --short HEAD)"
}

case "${1:-sync}" in status) status;; sync) sync;; *) echo "usage: $0 [status|sync]"; exit 2;; esac
