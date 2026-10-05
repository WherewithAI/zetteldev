#!/usr/bin/env python3
"""The data tier on DVC, with Della as the store (plan of 2026-10-01). `just data <cmd> …` on any machine.

    dvc_data.py pull   [exp ...|--all]            pull each experiment's default list (.dvcpull, plus the machine-local override)
    dvc_data.py sweep  [exp ...|--all] [--add] [--quiet-min N]
                                                  report the entries under processed_data no pointer covers; with --add, track the
                                                  quiet ones (newest mtime older than N minutes, default 60) in the DVC-managed
                                                  experiments listed in .zetteldev/dvc_experiments.txt
    dvc_data.py commit-pointers [--push]          commit changed or new *.dvc and processed_data/.gitignore files on the current
                                                  branch (nothing else), then pull --rebase and push when asked
    dvc_data.py status [exp ...|--all]            each listed pointer's state against the workspace, then the sweep report
    dvc_data.py sync                              the hourly cycle on the workstation: master and forward, pull the lists, push the
                                                  cache to Della, commit pointers, then pull the lists on SolveIt

Conventions. A pointer path is written relative to the repository root in every list. `.dvcpull` sits beside an experiment's
notebooks and names what its notebooks read; `~/.config/zetteldev/dvcpull.local` holds `+path` and `-path` lines that add to or
remove from every list on this machine only (SolveIt's only ever removes: its storage is paid for). The sweep never adds outside
the experiments that opted in, because an add hashes the whole tree and the login node reaps long work; and it never adds a directory
that holds pointers below its top level (a bulk directory whose tables are tracked one by one), which it reports as PARTIAL.
"""
from __future__ import annotations
import argparse, os, socket, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS = REPO / "experiments"
MANAGED = REPO / ".zetteldev" / "dvc_experiments.txt"
LOCAL_OVERRIDE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zetteldev" / "dvcpull.local"
SKIP_NAMES = {".gitignore", ".hf_small_cache.json"}


def dvc_bin() -> str:
    for c in (REPO / ".venv" / "bin" / "dvc", Path.home() / ".local" / "bin" / "dvc", Path("/app/data/.local/bin/dvc")):
        if c.exists(): return str(c)
    return "dvc"


def run(*cmd, check=True, capture=False, cwd=REPO):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, check=False, text=True, capture_output=capture)
    if check and r.returncode != 0:
        if capture: sys.stderr.write(r.stderr)
        raise SystemExit(f"{cmd[0]} failed (rc {r.returncode})")
    return r


def experiments_from(names: list[str], managed_only=False) -> list[str]:
    if managed_only or names == ["--all"] or not names:
        if managed_only or not MANAGED.exists():
            return [l.strip() for l in MANAGED.read_text().splitlines() if l.strip() and not l.startswith("#")] if MANAGED.exists() else []
        return sorted(p.name for p in EXPERIMENTS.iterdir() if (p / "processed_data").is_dir() and not p.name.startswith("."))
    out = []
    for n in names:
        hits = [p.name for p in EXPERIMENTS.iterdir() if p.name == n or p.name.startswith(n + "-") or p.name.split("-")[0] == n]
        if not hits: raise SystemExit(f"no experiment matches {n!r}")
        out.append(sorted(hits)[0])
    return out


def pull_list(exp: str) -> list[str]:
    "The pointer paths this machine pulls for `exp`: its .dvcpull, then the local override's + and - lines."
    f = EXPERIMENTS / exp / ".dvcpull"; wanted = []
    if f.exists():
        for l in f.read_text().splitlines():
            l = l.strip()
            if l and not l.startswith("#"): wanted.append(f"experiments/{exp}/{l}")
    if LOCAL_OVERRIDE.exists():
        for l in LOCAL_OVERRIDE.read_text().splitlines():
            l = l.strip()
            if not l or l.startswith("#") or not l[1:].startswith(f"experiments/{exp}/"): continue
            if l[0] == "+" and l[1:] not in wanted: wanted.append(l[1:])
            if l[0] == "-" and l[1:] in wanted: wanted.remove(l[1:])
    return wanted


def pointer_of(path: str) -> Path | None:
    p = REPO / (path + ".dvc"); return p if p.exists() else None


def pull(exps: list[str]) -> int:
    targets = []
    for e in exps:
        for path in pull_list(e):
            ptr = pointer_of(path)
            if ptr is None: print(f"{e}: no pointer for {path} (listed in .dvcpull but never added); skipped"); continue
            targets.append(str(ptr.relative_to(REPO)))
    if not targets: print("nothing to pull"); return 0
    print(f"pulling {len(targets)} pointer(s): " + ", ".join(t.split('/')[1][:2] + '…' + t.rsplit('/', 1)[-1] for t in targets), flush=True)
    r = run(dvc_bin(), "pull", *targets, check=False); return r.returncode


def newest_mtime(p: Path) -> float:
    if p.is_file(): return p.stat().st_mtime
    newest = p.stat().st_mtime
    for root, _dirs, files in os.walk(p):
        for f in files:
            try: newest = max(newest, (Path(root) / f).stat().st_mtime)
            except OSError: pass
    return newest


def sweep(exps: list[str], add=False, quiet_min=60) -> int:
    "Entries directly under processed_data with no pointer: report them, and with --add track the quiet ones of managed experiments."
    managed = set(experiments_from([], managed_only=True)); rc = 0; to_add = []
    for e in exps:
        pd = EXPERIMENTS / e / "processed_data"
        if not pd.is_dir(): continue
        for entry in sorted(pd.iterdir()):
            n = entry.name
            if n in SKIP_NAMES or n.endswith(".dvc") or ".local-" in n or n.startswith("."): continue
            if (pd / (n + ".dvc")).exists(): continue
            if entry.is_dir() and any(entry.rglob("*.dvc")):   # pointers below the top level: tables inside a bulk directory
                print(f"PARTIAL   {e}/processed_data/{n}  (tracked below the top level; the rest is left alone)"); continue
            age_min = (time.time() - newest_mtime(entry)) / 60
            size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) if entry.is_dir() else entry.stat().st_size
            tag = "managed" if e in managed else "unmanaged"
            print(f"UNTRACKED {e}/processed_data/{n}  {size / 1e6:.1f} MB  quiet {age_min:.0f} min  [{tag}]")
            if add and e in managed and age_min >= quiet_min: to_add.append(entry)
    if to_add:
        print(f"adding {len(to_add)} quiet entr{'y' if len(to_add) == 1 else 'ies'} …", flush=True)
        r = run(dvc_bin(), "add", *[str(p.relative_to(REPO)) for p in to_add], check=False); rc = r.returncode
        for p in to_add: print(f"ADDED {p.relative_to(REPO)}")
    return rc


def commit_pointers(push=False) -> int:
    "Commit only pointer files and the .gitignore DVC writes beside them; pull --rebase and push when asked."
    br = run("git", "branch", "--show-current", capture=True).stdout.strip()
    # Never disturb an index someone else is building: `dvc add` stages its own pointer files (core.autostage), which is fine, but
    # anything else already staged means a person is mid-commit, and the tick leaves it all alone.
    is_ptr = lambda f: f.endswith(".dvc") or f.endswith("/.gitignore")
    foreign = [f for f in run("git", "diff", "--cached", "--name-only", capture=True).stdout.split() if not is_ptr(f)]
    if foreign:
        print(f"pointers: the index holds staged changes that are not pointers ({', '.join(foreign[:3])}); skipped this time", file=sys.stderr); return 1
    # Two adds, since one pathspec that matches nothing makes git stage none of the others.
    run("git", "add", "-A", "--", "*.dvc", check=False)
    run("git", "add", "-A", "--", ":(glob)experiments/*/processed_data/**/.gitignore", check=False, capture=True)
    staged = run("git", "diff", "--cached", "--name-only", capture=True).stdout.split()
    if not staged: print("pointers: nothing to commit"); return 0
    host = socket.gethostname().split(".")[0]
    run("git", "-c", f"user.name={host}", "-c", f"user.email={host}@zetteldev", "commit", "-q", "-m", f"data: {len(staged)} pointer file(s) from {host}")
    print(f"pointers: committed {len(staged)} file(s) on {br}: " + " ".join(staged))
    if push:
        r = run("git", "pull", "-q", "--rebase", "origin", br, check=False)
        if r.returncode != 0: print("pointers: rebase on origin failed; left for the next tick", file=sys.stderr); run("git", "rebase", "--abort", check=False); return 1
        r = run("git", "push", "-q", "origin", br, check=False)
        if r.returncode != 0: print("pointers: push refused; left for the next tick", file=sys.stderr); return 1
        print(f"pointers: pushed {br}")
    return 0


def status(exps: list[str]) -> int:
    for e in exps:
        for path in pull_list(e):
            ptr = pointer_of(path)
            if ptr is None: print(f"{e}: {path}: no pointer"); continue
            r = run(dvc_bin(), "status", str(ptr.relative_to(REPO)), capture=True, check=False)
            state = "up to date" if "up to date" in r.stdout else r.stdout.strip().replace("\n", " ")[:120]
            print(f"{e}: {path}: {state}")
    return sweep(exps)


def sync() -> int:
    "The workstation's hourly cycle."
    master = REPO / ".zetteldev" / "della" / "bin" / "della-master"
    if master.exists(): run(master, check=False)
    exps = experiments_from(["--all"]); rc = pull(exps)
    r = run(dvc_bin(), "push", "-r", "della", check=False); rc |= r.returncode
    rc |= commit_pointers(push=True)
    sys.path.insert(0, str(REPO / ".zetteldev"))
    try:
        from config import setting
        host, root = setting("solveit_host"), setting("solveit_root")
        r = run("ssh", "-o", "ConnectTimeout=20", "-o", "BatchMode=yes", host, f"cd {root} && PATH=/app/data/.local/bin:$PATH dvc push && python3 .zetteldev/dvc_data.py pull --all", check=False)
        rc |= r.returncode
    except Exception as e: print(f"solveit pull skipped: {e}", file=sys.stderr)
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["pull", "sweep", "commit-pointers", "status", "sync"]); ap.add_argument("experiments", nargs="*")
    ap.add_argument("--all", action="store_true", help="every experiment with a processed_data directory")
    ap.add_argument("--add", action="store_true"); ap.add_argument("--quiet-min", type=int, default=60); ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    if a.all: a.experiments = ["--all"]
    if a.cmd == "pull": return pull(experiments_from(a.experiments))
    if a.cmd == "sweep": return sweep(experiments_from(a.experiments), add=a.add, quiet_min=a.quiet_min)
    if a.cmd == "commit-pointers": return commit_pointers(push=a.push)
    if a.cmd == "status": return status(experiments_from(a.experiments))
    if a.cmd == "sync": return sync()


if __name__ == "__main__":
    sys.exit(main())
