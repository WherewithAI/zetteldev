#!/usr/bin/env python3
"""The setup doctor: one line per item the setup guide (.zetteldev/agents/setup.md) asks for, with a verdict.

    python3 .zetteldev/doctor.py            every section, the cluster and the instance reached through their masters
    python3 .zetteldev/doctor.py --here     this machine and the repository only, no ssh

Verdicts: `ok`, `WARN` (the tools work, something is missing that a pack leans on, or a value sits in the wrong layer),
`FAIL` (a tool will not work until this is fixed). A red line names the guide section that fixes it, and the exit code
is 1 when anything FAILs. The doctor is plain Python 3.11+ with no dependency on the zetteldev package or the venv, so
it runs on a repository that is only half set up; it starts nothing, opens no connection the masters do not already
hold, and never walks data, so it finishes in well under a minute.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, platform, re, socket, subprocess, sys, time, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZD = ROOT / ".zetteldev"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
# the user-level skills the packs lean on: skill -> the pack that reads it
SKILLS = {"persistent-python": "harness", "pyskills": "harness", "marimo-pair": "mo", "solveit-client": "solveit",
          "vllm-model-setup": "della", "della-gpu": "della", "fastanki": "flashcards"}
# .env names and the tool that reads each
ENV_NAMES = {"CLOUDFLARE_ACCOUNT_ID": "figpub / publish-figure", "CLOUDFLARE_R2_ACCESS_KEY_ID": "figpub / publish-figure",
             "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "figpub / publish-figure", "WANDB_API_KEY": "wandb reports"}
ENV_OPTIONAL = {"DATALAB_KEY": "mdify-paper", "ANKI_USER": "flashcards", "ANKI_PASS": "flashcards"}
PER_PERSON_KEYS = ("della_user_scratch",)       # values that differ per person and belong in ~/.config/zetteldev/config.toml

lines: list[tuple[str, str, str]] = []
def ok(sec, msg): lines.append(("ok", sec, msg))
def warn(sec, msg, fix): lines.append(("WARN", sec, f"{msg}  -> {fix}"))
def fail(sec, msg, fix): lines.append(("FAIL", sec, f"{msg}  -> {fix}"))

def sh(cmd: list[str], timeout=20) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e: return 124, str(e)

def remote(host: str, script: str) -> tuple[int, str]: return sh(SSH + [host, script], timeout=30)

def load_config():
    spec = importlib.util.spec_from_file_location("zd_config", ZD / "config.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

# --- the repository's configuration ------------------------------------------------------------------------------
def check_config(cfg):
    s, layers = cfg.settings(), cfg.layers()
    need = ["della_host", "solveit_host", "compute_host", "figures_url", "della_account", "della_group_scratch", "della_user_scratch"]
    for k in need:
        if s.get(k) is None: fail("config", f"{k} is unset", "PER REPOSITORY: [tool.zetteldev] in pyproject.toml, or PER PERSON: ~/.config/zetteldev/config.toml")
        else: ok("config", f"{k} = {s[k]!r} ({layers[k]})")
    for k in PER_PERSON_KEYS:
        if layers.get(k) == "pyproject": warn("config", f"{k} is a per-person value in the shared layer (pyproject.toml)", "PER PERSON: move it under [zetteldev] in ~/.config/zetteldev/config.toml")
    uc = cfg.USER_CONFIG
    ok("config", f"{uc} present") if uc.exists() else warn("config", f"{uc} absent", "PER PERSON: create it with the keys that differ per person")
    return s

# --- per person --------------------------------------------------------------------------------------------------
def check_person(s):
    sshcfg = Path.home() / ".ssh" / "config"; text = sshcfg.read_text() if sshcfg.exists() else ""
    for key in ("della_host", "solveit_host"):
        alias = s.get(key)
        if not alias: continue
        block = re.search(rf"^Host\b[^\n]*\b{re.escape(alias)}\b[^\n]*\n((?:[ \t]+[^\n]*\n?)*)", text, re.M)
        if not block: fail("ssh", f"no Host entry for {alias!r} ({key}) in ~/.ssh/config", "PER PERSON: the ssh aliases"); continue
        opts = block.group(1)
        if "ControlMaster" in opts and "ControlPath" in opts: ok("ssh", f"{alias}: Host entry with a control master")
        else: fail("ssh", f"{alias}: Host entry without ControlMaster/ControlPath", "PER PERSON: every alias carries a master, the gateway counts connections")
    sock = Path.home() / ".ssh" / "agent.sock"
    if sock.is_symlink() and Path(os.readlink(sock)).exists() or sock.exists() and not sock.is_symlink(): ok("ssh", "~/.ssh/agent.sock resolves")
    else: fail("ssh", "~/.ssh/agent.sock missing or dangling", "PER PERSON: the agent socket symlink the login shell keeps current")
    skills = Path.home() / ".claude" / "skills"
    for name, pack in SKILLS.items():
        p = skills / name
        ok("skills", f"{name} ({pack} pack)") if p.exists() else warn("skills", f"skill {name!r} not installed; the {pack} pack leans on it", "PER PERSON: the user-level skills")

# --- per repository ------------------------------------------------------------------------------------------------
def check_repo(s):
    pp = tomllib.loads((ROOT / "pyproject.toml").read_text())
    src = pp.get("tool", {}).get("uv", {}).get("sources", {}).get("zetteldev")
    deps = pp.get("project", {}).get("dependencies", [])
    if src and any(d.split()[0].startswith("zetteldev") for d in deps): ok("repo", "zetteldev is an editable dependency ([tool.uv.sources])")
    else: fail("repo", "pyproject.toml lacks the zetteldev editable dependency or its [tool.uv.sources] entry", "PER REPOSITORY: pyproject.toml")
    env = ROOT / ".env"
    if not env.exists(): fail("repo", ".env absent", "PER REPOSITORY: .env, never committed")
    else:
        names = {l.split("=", 1)[0].strip() for l in env.read_text().splitlines() if "=" in l and not l.lstrip().startswith("#")}
        for n, tool in ENV_NAMES.items(): ok("env", f"{n} ({tool})") if n in names else warn("env", f"{n} missing in .env; {tool} will not work", "PER REPOSITORY: .env")
        for n, tool in ENV_OPTIONAL.items():
            if n not in names: warn("env", f"{n} missing in .env ({tool}; only if used)", "PER REPOSITORY: .env")
    for f, what in [("della/targets.yaml", "the target registry"), ("services.yaml", "the service registry"), ("dvc_experiments.txt", "the DVC-managed experiments")]:
        ok("repo", f"{f} present") if (ZD / f).exists() else fail("repo", f"{f} absent ({what})", "PER REPOSITORY: the registries")
    py = ROOT / ".venv" / "bin" / "python"
    if not py.exists(): fail("repo", ".venv absent", "THE WORKSTATION: uv sync")
    else:
        rc, out = sh([str(py), "-c", "from zetteldev.della import load_targets; t = load_targets(); bad = sorted({v[v.find('$'):v.find('}', v.find('$')) + 1] for c in t.values() for v in c.values() if isinstance(v, str) and '${' in v}); print(len(t)); print('UNRESOLVED ' + ' '.join(bad) if bad else 'resolved')"], timeout=60)
        if rc == 0 and "UNRESOLVED" in out: fail("repo", f"the registry has unresolved placeholders: {out.split('UNRESOLVED')[1].strip()}", "PER REPOSITORY: [tool.zetteldev] or PER PERSON: config.toml"); rc = -1
        ok("repo", f"zetteldev imports; {out.split()[0]} targets resolve") if rc == 0 else fail("repo", f"zetteldev does not import or the registry does not resolve: {out.splitlines()[-1] if out else rc}", "PER REPOSITORY: uv sync, then the registries")
    dvc = ROOT / ".dvc" / "config"
    if dvc.exists() and "remote" in dvc.read_text(): ok("data", ".dvc/config with a remote")
    else: fail("data", ".dvc/config missing or without a remote", "PER REPOSITORY: dvc init and the remotes")
    gi = (ROOT / ".gitignore").read_text() if (ROOT / ".gitignore").exists() else ""
    ok("data", ".gitignore admits pointer files") if re.search(r"^!.*\*\.dvc\s*$", gi, re.M) else fail("data", ".gitignore does not admit *.dvc pointer files", "PER REPOSITORY: the three-line gitignore rule")
    exps = sorted(p for p in (ROOT / "experiments").iterdir() if p.is_dir() and re.match(r"\d", p.name)) if (ROOT / "experiments").exists() else []
    for stub, why in [(".dvcpull", "nothing pulls there"), (".solveit-dialog", "sicx cannot name the dialog"), ("design.md", "no pointer to the zettel")]:
        missing = [p.name for p in exps if not (p / stub).exists()]
        if missing: warn("experiments", f"{len(missing)} of {len(exps)} experiments lack {stub} ({why}): {', '.join(m.split('-')[0] for m in missing)}", "PER EXPERIMENT: the scaffolder's stubs")
        else: ok("experiments", f"every experiment has {stub}")

# --- this machine -------------------------------------------------------------------------------------------------
def check_workstation(s):
    rc, cron = sh(["crontab", "-l"])
    for needle, what in [("solveit_sync.sh", "the notebook sync"), ("data sync", "the data cycle")]:
        ok("cron", f"{what} is scheduled") if needle in cron else fail("cron", f"no cron line for {what}", "THE WORKSTATION: the cron lines")
    if "SSH_AUTH_SOCK" not in cron: warn("cron", "cron lines without SSH_AUTH_SOCK", "THE WORKSTATION: cron has no agent; set it on the line")
    rc, ps = sh(["pgrep", "-f", "della-status run"])
    st = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "della" / "status.json"
    age = (time.time() - st.stat().st_mtime) / 60 if st.exists() else None
    if rc == 0 and age is not None and age < 15: ok("poller", f"della-status running, status file {age:.0f} min old")
    else: fail("poller", f"della-status {'running' if rc == 0 else 'not running'}, status file {'absent' if age is None else f'{age:.0f} min old'}", "THE WORKSTATION: `just della-status run` in a tmux window")
    for name, bin_ in [("della-master", ZD / "della" / "bin" / "della-master"), ("solveit-master", ZD / "solveit-master")]:
        rc, out = sh(["bash", str(bin_), "--status"])
        if "no master" in out or rc != 0: fail("masters", f"{name}: {out.replace(chr(10), '; ')}", f"THE WORKSTATION: `just {name}`")
        elif "down" in out: warn("masters", f"{name}: {out.replace(chr(10), '; ')}", f"THE WORKSTATION: `just {name}` re-arms the forward")
        else: ok("masters", f"{name}: {out.replace(chr(10), '; ')}")
    if s.get("compute_host") == socket.gethostname().split(".")[0]:
        sched = ZD / "dask" / "run" / "scheduler-default.json"
        ok("compute", "Dask scheduler file present (this is compute_host)") if sched.exists() else warn("compute", "this is compute_host but no Dask scheduler file is present", "THE WORKSTATION: the Dask cluster")

# --- the cluster and the instance, over the masters ----------------------------------------------------------------
def check_cluster(s):
    host, repo = s.get("della_host"), s.get("della_repo")
    if not host: return
    rc, out = remote(host, f"cd {repo} && git rev-parse --abbrev-ref HEAD; git rev-parse HEAD; test -x .venv/bin/dvc && echo dvc-ok; test -d {s['della_dvc_cache']} && echo cache-ok; test -d {s['della_weights_cache']} && echo weights-ok; test -f {s['della_vllm_venv']}/bin/activate && echo venv-ok; grep -c '{s['della_dvc_cache']}' .dvc/config.local; git config --get remote.origin.url")
    if rc != 0 and not out: fail("cluster", f"{host}: no answer through the master", "THE CLUSTER: `just della-master`"); return
    toks = out.split("\n")
    if "dvc-ok" in toks: ok("cluster", "clone with a venv that has dvc")
    else: fail("cluster", f"no dvc in the clone's venv at {repo}", "THE CLUSTER: the venv")
    for tag, what in [("cache-ok", "the DVC cache directory"), ("weights-ok", "the weights cache"), ("venv-ok", "the vLLM venv")]:
        ok("cluster", f"{what} exists") if tag in toks else fail("cluster", f"{what} missing", "THE CLUSTER: scratch directories and environments")
    ok("cluster", ".dvc/config.local points the cache at scratch") if any(t.strip().isdigit() and int(t) > 0 for t in toks) else fail("cluster", ".dvc/config.local does not name the scratch cache", "THE CLUSTER: .dvc/config.local")
    ok("cluster", "clone has a GitHub origin") if any("github" in t for t in toks) else fail("cluster", "clone without a GitHub origin (pointer commits leave from here)", "THE CLUSTER: the clone")
    if len(toks) > 1 and re.fullmatch(r"[0-9a-f]{40}", toks[1] or ""):
        branch, head = toks[0], toks[1]
        rc2, local = sh(["git", "-C", str(ROOT), "rev-parse", f"origin/{branch}"])
        ok("cluster", f"clone at origin/{branch} as known here") if local.strip() == head else warn("cluster", f"clone's HEAD {head[:8]} differs from origin/{branch} known here {local.strip()[:8]}", "THE CLUSTER: the gate fast-forwards it on the next submission")

def check_instance(s):
    host, root = s.get("solveit_host"), s.get("solveit_root")
    if not host: return
    rc, out = remote(host, f"cd {root} && git config --get receive.denyCurrentBranch; (command -v dvc || ls /app/data/.local/bin/dvc) >/dev/null && echo dvc-ok; grep -c athomia .dvc/config.local; git remote -v | grep -c origin")
    if rc != 0 and not out: fail("instance", f"{host}: no answer through the master", "THE INSTANCE: `just solveit-master`"); return
    toks = out.split("\n")
    ok("instance", "receive.denyCurrentBranch = updateInstead") if "updateInstead" in toks else fail("instance", "receive.denyCurrentBranch is not updateInstead (the sync's push cannot fast-forward the tree)", "THE INSTANCE: the clone")
    ok("instance", "dvc on the instance") if "dvc-ok" in toks else fail("instance", "dvc not installed on the instance", "THE INSTANCE: pip install dvc into the container's Python")
    ok("instance", ".dvc/config.local names the workstation remote") if any(t.strip().isdigit() and int(t) > 0 for t in toks[1:3]) else fail("instance", ".dvc/config.local lacks the workstation remote", "THE INSTANCE: .dvc/config.local")
    rc, out = sh(["curl", "-s", "-m", "5", "localhost:5001/test_route"])
    ok("instance", "SolveIt answers on the forwarded 5001") if out.strip() == "here" else fail("instance", "nothing answers on localhost:5001", "THE INSTANCE: `just solveit-master`, then the server itself")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--here", action="store_true", help="this machine and the repository only; no ssh")
    a = ap.parse_args()
    cfg = load_config(); s = check_config(cfg)
    check_person(s); check_repo(s); check_workstation(s)
    if not a.here: check_cluster(s); check_instance(s)
    width = max(len(sec) for _, sec, _ in lines)
    for v, sec, msg in lines: print(f"{v:4s} {sec:{width}s} {msg}")
    n = {v: sum(1 for x in lines if x[0] == v) for v in ("ok", "WARN", "FAIL")}
    print(f"\n{n['ok']} ok, {n['WARN']} warn, {n['FAIL']} fail")
    return 1 if n["FAIL"] else 0

if __name__ == "__main__": sys.exit(main())
