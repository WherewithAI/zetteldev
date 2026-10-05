"""Long-lived services on Della, by name: up, status, tunnel, down. Registry: .zetteldev/services.yaml.

    just service status            every service: where it runs, health, time left
    just service up rag            start it (a SLURM job, or a tmux session on a viz node)
    just service tunnel rag        laptop:<port> -> the service, solveit:<port> -> laptop; writes ~/.config/zetteldev/services.env
    just service down rag
    zetteldev.services.url("rag")  -> the URL a notebook should call, from the env file (or the env var)

A service publishes "<node>:<port>" into an address file in $HOME on Della when it is ready; `up` waits for it.
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys, time
from pathlib import Path
import yaml
from zetteldev.config import settings

__all__ = ["url", "registry", "status", "up", "tunnel", "down", "ENV_FILE"]

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / ".zetteldev" / "services.yaml"
ENV_FILE = Path.home() / ".config" / "zetteldev" / "services.env"
DELLA, DELLA_REPO, SOLVEIT = (settings()[k] for k in ('della_host', 'della_repo', 'solveit_host'))


def registry() -> dict: return yaml.safe_load(REGISTRY.read_text())


def ssh(host, cmd, timeout=60) -> str:
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", host, cmd], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return r.stdout.strip()


def url(name: str) -> str:
    "The URL for a service, from the env var of the same name in the environment or in the services env file."
    var = registry()[name]["env_var"]
    if os.environ.get(var): return os.environ[var]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith(var + "="): return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{name}: no {var} set; run `just service tunnel {name}`")


def addr(svc) -> str | None:
    out = ssh(DELLA, f"cat ~/{svc['addr_file']} 2>/dev/null"); return out or None


def job_for(svc) -> dict | None:
    "The SLURM job serving an sbatch-mode service: id, state, time used, time limit; None when none is queued or running."
    name = Path(svc["sbatch"]).stem.replace("_", "-")
    out = ssh(DELLA, f'squeue -u $USER -h -o "%i %T %M %l %j" | grep -- "exp35-{name}\\|{name}" | head -n 1')
    if not out: return None
    i, st, used, lim, jn = out.split()[:5]; return dict(id=i, state=st, used=used, limit=lim, name=jn)


def viz_session(svc) -> str | None:
    return ssh(DELLA, f"ssh -o ConnectTimeout=10 {svc['viz_host']} 'tmux has-session -t zdev-{svc['addr_file'].split('.')[0]} 2>/dev/null && echo up'") or None


def health(svc) -> str:
    a = addr(svc)
    if not a: return "no address"
    code = ssh(DELLA, f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 10 http://{a}{svc["health"]}')
    return f"{a} -> {code}"


def cmd_status(reg, names):
    for n in names:
        svc = reg[n]; where = job_for(svc) if svc["mode"] == "sbatch" else ("tmux on " + svc["viz_host"] if viz_session(svc) else None)
        print(f"{n:11s} {svc['mode']:6s} {str(where) if where else 'not running':60s} {health(svc)}")


def cmd_up(reg, name, wait=True, force_sbatch=False):
    svc = reg[name]
    if svc["mode"] == "sbatch" or force_sbatch:
        if svc.get("shares_job_with"): return cmd_up(reg, svc["shares_job_with"], wait)
        j = job_for(svc)
        if j: print(f"{name}: job {j['id']} already {j['state']} ({j['used']}/{j['limit']})")
        else: print(f"{name}: " + ssh(DELLA, f"cd {DELLA_REPO}/{Path(svc['sbatch']).parent.parent.parent} && sbatch {svc['sbatch'].split('/', 2)[-1] if svc['sbatch'].startswith('experiments/') else svc['sbatch']}"))
    else:
        sess = "zdev-" + svc["addr_file"].split(".")[0]
        if viz_session(svc): print(f"{name}: tmux session {sess} already up on {svc['viz_host']}")
        else:
            free = viz_free_mb(svc); need = int(svc.get("viz_min_free_mb", 24000))
            if free is not None and free < need:
                if svc.get("sbatch"):
                    print(f"{name}: {svc['viz_host']} has {free} MiB free on its best card, below the {need} MiB the service needs (other users' jobs); falling back to the job form {svc['sbatch']}")
                    return cmd_up(reg, name, wait, force_sbatch=True)
                sys.exit(f"{name}: {svc['viz_host']} has {free} MiB free on its best card, below the {need} MiB needed, and no sbatch form is registered")
            print(f"{name}: starting {sess} on {svc['viz_host']}" + (f" ({free} MiB free)" if free is not None else ""))
            print(ssh(DELLA, f"ssh -o ConnectTimeout=10 {svc['viz_host']} 'cd {DELLA_REPO} && rm -f ~/{svc['addr_file']} && tmux new-session -d -s {sess} \"bash {svc['viz_script']}\" && echo started'"))
    if wait:
        limit = int(svc.get("up_timeout", 900))
        for i in range(limit // 15):
            a = addr(svc)
            if a: print(f"{name}: ready at {a}"); return
            time.sleep(15); print(f"  waiting ({(i + 1) * 15}s)", flush=True)
        print(f"{name}: no address after {limit}s; the last lines of its log:", file=sys.stderr)
        print(service_tail(svc), file=sys.stderr); sys.exit(1)


def viz_free_mb(svc) -> int | None:
    "Free memory on the viz host's best card, in MiB; None when it cannot be read."
    out = ssh(DELLA, f"ssh -o ConnectTimeout=10 {svc['viz_host']} 'nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits' 2>/dev/null | sort -n | tail -n 1")
    try: return int(out.strip())
    except ValueError: return None


def service_tail(svc, lines: int = 25) -> str:
    "The tail of a service's log: the tmux pane on a viz node, or the SLURM job's output file."
    if svc["mode"] == "viz":
        sess = "zdev-" + svc["addr_file"].split(".")[0]
        return ssh(DELLA, f"ssh -o ConnectTimeout=10 {svc['viz_host']} 'tmux capture-pane -p -t {sess} -S -{lines} 2>/dev/null'") or "(no pane)"
    j = job_for(svc)
    if not j: return "(no job in the queue)"
    return ssh(DELLA, f"f=$(scontrol show job {j['id']} | grep -o 'StdOut=[^ ]*' | cut -d= -f2); tail -n {lines} \"$f\" 2>/dev/null") or f"(job {j['id']} {j['state']}, no output yet)"


def cmd_down(reg, name):
    svc = reg[name]
    if svc["mode"] == "sbatch":
        j = job_for(svc); print(f"{name}: " + (ssh(DELLA, f"scancel {j['id']} && echo cancelled {j['id']}") if j else "no job"))
    else:
        sess = "zdev-" + svc["addr_file"].split(".")[0]
        print(f"{name}: " + ssh(DELLA, f"ssh -o ConnectTimeout=10 {svc['viz_host']} 'tmux kill-session -t {sess} 2>/dev/null && rm -f ~/{svc['addr_file']} && echo stopped' "))


def cmd_tunnel(reg, name):
    svc = reg[name]; a = addr(svc)
    if not a: sys.exit(f"{name}: no address published on Della; `just service up {name}` first")
    node, port = a.split(":"); lp = svc["local_port"]
    subprocess.run(f"for p in $(pgrep -f '^ssh .*{lp}:'); do kill $p; done", shell=True); time.sleep(1)
    # A forward the multiplexed master holds (one an earlier session opened without ControlPath=none) survives that kill and
    # blocks the rebind with "Address already in use" (2026-09-20: the previous node's 8010). Ask the master to cancel it.
    subprocess.run(["ssh", "-O", "cancel", "-L", f"{lp}:{node}:{port}", DELLA], capture_output=True)
    subprocess.run(["ssh", "-O", "cancel", "-L", f"{lp}:127.0.0.1:{port}", DELLA], capture_output=True)
    busy = subprocess.run(["ss", "-ltn", f"sport = :{lp}"], capture_output=True, text=True).stdout.count("LISTEN")
    if busy: sys.exit(f"{name}: local port {lp} is still held by another process after cancelling the master's forwards; `ss -ltnp sport = :{lp}` names it")
    # ControlPath=none: a forward opened inside a multiplexed master cannot be killed by port, and the stale one blocks the rebind
    # Jump through the login node to the service's node and bind its loopback, so a server bound to 127.0.0.1 is reachable
    # too (2026-09-09: the registry-launched Qwen service bound loopback and the plain login-node forward could not reach it).
    user = subprocess.run(["ssh", "-G", DELLA], capture_output=True, text=True).stdout.split("\nuser ")[1].split("\n")[0].strip()
    if node.startswith("della-vis"):
        # The visualization nodes demand a Duo prompt after the public key, so a jump to them hangs unattended (2026-09-10: the
        # supervisor sat 41 min in this call). Their servers bind all interfaces, so the login node forwards to them directly.
        subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-o", "ControlPath=none", "-fN", "-L", f"{lp}:{node}:{port}", DELLA], check=True, stdin=subprocess.DEVNULL)
    else:
        subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-o", "ControlPath=none", "-o", "StrictHostKeyChecking=accept-new", "-o", f"ProxyJump={DELLA}",
                        "-fN", "-L", f"{lp}:127.0.0.1:{port}", f"{user}@{node}"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-o", "ControlPath=none", "-fN", "-R", f"{lp}:localhost:{lp}", SOLVEIT], check=True, stdin=subprocess.DEVNULL)
    local = subprocess.run(["curl", "-s", "--max-time", "30", f"http://localhost:{lp}{svc['health']}"], capture_output=True, text=True).stdout[:80]
    remote = ssh(SOLVEIT, f"curl -s --max-time 30 http://localhost:{lp}{svc['health']}")[:80]
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [l for l in (ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []) if not l.startswith(svc["env_var"] + "=")]
    lines.append(f"{svc['env_var']}=http://localhost:{lp}{svc['url_suffix']}"); ENV_FILE.write_text("\n".join(lines) + "\n")
    subprocess.run(["scp", "-q", str(ENV_FILE), f"{SOLVEIT}:/app/data/.config/zetteldev/services.env"], stdin=subprocess.DEVNULL) if ssh(SOLVEIT, "mkdir -p /app/data/.config/zetteldev && echo ok") else None
    print(f"{name}: laptop:{lp} -> {a} [{local or 'no answer'}] | solveit:{lp} [{remote or 'no answer'}] | {svc['env_var']} written to {ENV_FILE}")


def status(*names: str) -> None:
    "Print where each service runs, its health and its address (all services when no names are given)."
    reg = registry(); cmd_status(reg, list(names) or list(reg))


def up(name: str, wait: bool = True) -> None:
    "Start a service (a SLURM job, or a tmux session on its viz node) and, by default, wait for its address."
    cmd_up(registry(), name, wait)


def tunnel(name: str) -> None:
    "Open laptop:<port> to the service and solveit:<port> back to the laptop; write its URL to the services env file."
    cmd_tunnel(registry(), name)


def down(name: str) -> None:
    "Stop a service: cancel its job, or kill its viz-node session."
    cmd_down(registry(), name)



def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "up", "tunnel", "down", "url"]); ap.add_argument("names", nargs="*"); ap.add_argument("--no-wait", action="store_true")
    a = ap.parse_args(); reg = registry(); names = a.names or list(reg)
    if a.cmd == "status": cmd_status(reg, names)
    elif a.cmd == "url": [print(n, url(n)) for n in names]
    else:
        if not a.names: sys.exit("name a service")
        for n in a.names: {"up": lambda: cmd_up(reg, n, not a.no_wait), "tunnel": lambda: cmd_tunnel(reg, n), "down": lambda: cmd_down(reg, n)}[a.cmd]()


if __name__ == "__main__": main()
