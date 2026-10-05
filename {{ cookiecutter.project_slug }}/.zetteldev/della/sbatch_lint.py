"""Pre-flight lint for Della submissions: the invariants we bought with GPU-hours.

Every rule here corresponds to a failure that has actually cost this repository
compute, and each was previously guarded only by recollection:

* the embedding sidecar alone on a card, which caps the job at tp/(tp+1) and feeds
  it to Della's 90-minute idle daemon (the audit of 2026-08-17: 51.6 GPU-hours);
* two servers each claiming most of one card's memory (the co-location hang of
  2026-08-10, job 12223731) -- ``--gpu-memory-utilization`` is a fraction of TOTAL
  device memory, and its DEFAULT IS 0.9, so an unflagged chat server plus a 0.12
  embedder is already 1.02;
* a keep-alive whose probes are too thin to register on the utilization sampler
  (exp38's cancelled jobs ran the same 48-token pings as their surviving twins);
* ``from snakemake.script import snakemake``, which fails on Snakemake >= 9;
* verl overrides written at ``actor.engine.*``, which ``__post_init__`` silently
  clobbers (nine wasted GPU jobs);
* ``report.qmd``, retired repo-wide on 2026-08-31.

Two modes, no third-party imports (it must run on the Della login node too)::

    sbatch-lint [paths...]      # no args: every tracked *.sbatch in the repo
    sbatch-lint --hook          # PreToolUse JSON on stdin, decision JSON on stdout

The hook mode also lints the *command string* -- verl overrides and quarto renders
are CLI arguments, not sbatch lines -- and resolves remote paths by suffix, since a
submission is usually ``ssh della 'cd ~/src/<repo>/experiments/X && sbatch
scripts/slurm/y.sbatch'``. The local copy of that file may of course be ahead of or
behind della's; the lint reads what is on this machine and says which path it read.

In hook mode an error in the command itself denies; anything found in a script on
disk only asks, so the author keeps the last word on his own history.
Experiments predating a rule are expected to fire it -- that is the point.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: A vLLM server left without the flag takes 0.9 of the card, not 0.
DEFAULT_GPU_MEM_FRACTION = 0.9
#: launch_colocated_embedder's default share of the chat model's rank-0 card.
COLOCATED_EMBED_FRACTION = 0.12
#: Below this, a keep-alive probe is a ping: too brief for the sampler to catch.
MIN_KEEPALIVE_TOKENS = 512
#: Conservative limits earn queue priority; favour many short jobs over one long.
MAX_RUNTIME_MINUTES = 6 * 60


@dataclass(frozen=True)
class Finding:
    """One rule firing at one place. ``line`` is 1-indexed, 0 for whole-file."""

    rule: str
    level: str  # "error" | "warn"
    path: str
    line: int
    message: str

    def render(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.level.upper():5s} {self.rule:22s} {where}\n      {self.message}"


@dataclass(frozen=True)
class Server:
    """A vLLM server launch found in a script."""

    line: int
    kind: str  # "chat" | "embed"
    cards: frozenset[int] | None  # None = unpinned, so it sees every card
    fraction: float
    colocated: bool  # launched by launch_colocated_embedder, the sanctioned pattern
    text: str


# ---------------------------------------------------------------- text handling


def logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash-continued lines, keeping the first physical line number.

    Every ``vllm serve`` in this repo spans five to eight lines; without this the
    ``--gpu-memory-utilization`` never lands beside its ``CUDA_VISIBLE_DEVICES=``.
    """
    joined: list[tuple[int, str]] = []
    buffer, start = "", 0
    for number, raw in enumerate(text.splitlines(), start=1):
        if not buffer:
            start = number
        if raw.rstrip().endswith("\\"):
            buffer += raw.rstrip()[:-1] + " "
            continue
        joined.append((start, buffer + raw))
        buffer = ""
    if buffer:
        joined.append((start, buffer))
    return joined


def _flag(line: str, name: str) -> str | None:
    """Value of ``--name value`` or ``--name=value``, quotes stripped."""
    match = re.search(rf"{re.escape(name)}[=\s]+([^\s]+)", line)
    return match.group(1).strip("\"'") if match else None


def _cards(value: str | None) -> frozenset[int] | None:
    """Parse a CUDA_VISIBLE_DEVICES value; None when it is not statically knowable.

    Handles ``0,1``, ``"0,1"`` and ``"${TRAIN_GPUS:-0,1,2}"`` -- the last by taking
    the digits after the ``:-`` default, since that is what an unset var yields.
    """
    if value is None:
        return None
    inner = value.strip("\"'")
    if ":-" in inner:
        inner = inner.split(":-", 1)[1].rstrip("}\"'")
    if not re.fullmatch(r"\d+(,\d+)*", inner):
        return None
    return frozenset(int(part) for part in inner.split(","))


def _fraction(line: str, default: float) -> float:
    raw = _flag(line, "--gpu-memory-utilization")
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default  # a shell variable; assume the documented default


# ---------------------------------------------------------------- script model


SERVE_RE = re.compile(r"(?:vllm|\$\{?[A-Za-z_]*VLLM[A-Za-z_]*\}?)[\"']?\s+serve\b", re.IGNORECASE)
EMBED_MODEL_RE = re.compile(r"Embedding|Reranker", re.IGNORECASE)
ASSIGN_IN_COMMENT_RE = re.compile(r"^[^#]*\S[^#]*#.*\b[A-Za-z_][A-Za-z0-9_]*=[\"'$(]")


def registry_targets() -> dict:
    """The target registry, or {} where PyYAML is missing (a bare python3 on the login node)."""
    try:
        import yaml
    except ImportError:
        return {}
    path = Path(__file__).resolve().parent / "targets.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and not k.startswith("_")}


def _served_target(line: str) -> tuple[str, dict] | None:
    """(name, registry record) when the line launches through serve_target."""
    if match := re.search(r"\bserve_target\s+([\w.\-]+)", line):
        name = match.group(1)
        return name, registry_targets().get(name, {})
    return None


def parse_servers(lines: list[tuple[int, str]]) -> list[Server]:
    """Every vLLM server a script launches, whether by flag or by della-lib helper."""
    servers: list[Server] = []
    exported: frozenset[int] | None = None
    embed_gpu = frozenset({0})  # launch_colocated_embedder's EMBED_GPU default
    for number, line in lines:
        if line.lstrip().startswith("#"):
            continue  # a comment naming a helper is not a launch of it
        if match := re.search(r"\bEMBED_GPU=(\S+)", line):
            embed_gpu = _cards(match.group(1)) or embed_gpu
        if match := re.search(r"^\s*export\s+CUDA_VISIBLE_DEVICES=(\S+)", line):
            exported = _cards(match.group(1))
            continue

        inline = re.search(r"CUDA_VISIBLE_DEVICES=(\S+)", line)
        if SERVE_RE.search(line):
            is_embed = bool(
                _flag(line, "--task") == "embed"
                or _flag(line, "--runner") == "pooling"
                or EMBED_MODEL_RE.search(line)
            )
            servers.append(Server(
                line=number,
                kind="embed" if is_embed else "chat",
                cards=_cards(inline.group(1)) if inline else exported,
                fraction=_fraction(line, DEFAULT_GPU_MEM_FRACTION),
                colocated=False,
                text=line.strip(),
            ))
        elif (served := _served_target(line)) is not None:
            name, record = served
            fraction = _flag(line, "--fraction")
            try:
                fraction = float(fraction) if fraction is not None else float(record.get("min_fraction", DEFAULT_GPU_MEM_FRACTION))
            except ValueError:
                fraction = float(record.get("min_fraction", DEFAULT_GPU_MEM_FRACTION))
            servers.append(Server(
                line=number, kind="embed" if record.get("kind") == "embed" else "chat",
                cards=_cards(_flag(line, "--gpu")), fraction=fraction, colocated=False, text=line.strip(),
            ))
        elif re.search(r"\blaunch_vllm_server\b", line):
            args = _split(line, "launch_vllm_server")
            servers.append(Server(
                line=number, kind="chat",
                cards=_cards(args[1]) if len(args) > 1 else exported,
                fraction=DEFAULT_GPU_MEM_FRACTION, colocated=False, text=line.strip(),
            ))
        elif re.search(r"\blaunch_embedding_server\b", line):
            args = _split(line, "launch_embedding_server")
            servers.append(Server(
                line=number, kind="embed",
                cards=_cards(args[1]) if len(args) > 1 else None,
                fraction=DEFAULT_GPU_MEM_FRACTION, colocated=False, text=line.strip(),
            ))
        elif re.search(r"\blaunch_colocated_embedder\b", line):
            servers.append(Server(
                line=number, kind="embed", cards=embed_gpu,
                fraction=COLOCATED_EMBED_FRACTION, colocated=True, text=line.strip(),
            ))
    return servers


def _split(line: str, helper: str) -> list[str]:
    """Positional arguments of a shell helper call, best-effort."""
    tail = line.split(helper, 1)[1]
    try:
        return [helper, *shlex.split(tail)]
    except ValueError:
        return [helper, *tail.split()]


def sbatch_directives(text: str) -> dict[str, str]:
    """``#SBATCH --key=value`` / ``--key value`` pairs, last one winning."""
    found: dict[str, str] = {}
    for raw in text.splitlines():
        if not (match := re.match(r"\s*#SBATCH\s+(.*)", raw)):
            continue
        for key, value in re.findall(r"--([\w-]+)(?:[=\s]+([^\s#]+))?", match.group(1)):
            found[key] = value
    return found


def parse_slurm_time(value: str) -> int | None:
    """SLURM's six accepted shapes -> minutes. MM, MM:SS, HH:MM:SS, D-HH[:MM[:SS]]."""
    value = value.strip()
    if "-" in value:
        days, _, rest = value.partition("-")
        parts = [int(p) for p in rest.split(":")] if rest else [0]
        hours, minutes = parts[0], parts[1] if len(parts) > 1 else 0
        return int(days) * 1440 + hours * 60 + minutes
    parts = value.split(":")
    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        return None
    if len(numbers) == 1:
        return numbers[0]                                   # MM
    if len(numbers) == 2:
        return numbers[0]                                   # MM:SS
    return numbers[0] * 60 + numbers[1]                     # HH:MM:SS


def keepalive_probes(text: str) -> list[int] | None:
    """Token budgets of the curl probes inside a ``while true`` loop.

    None when no such loop exists at all; an empty list when the loop's probes
    declare no budget (an embeddings ping, say), which counts as thin.
    """
    loops = re.findall(r"while\s+true\s*;?\s*do(.*?)\bdone", text, re.DOTALL)
    if not loops:
        return None
    budgets: list[int] = []
    for body in loops:
        if "curl" not in body:
            continue
        budgets.extend(int(n) for n in re.findall(r"max_tokens\\?\"?\s*:\s*(\d+)", body))
    return budgets


# ---------------------------------------------------------------------- rules


HEREDOC_RE = re.compile(r"<<-?\s*[\"']?(\w+)[\"']?")
SSH_DELLA_RE = re.compile(r"\bssh\b[^\n;|&]*\b(della|tigressgateway)")
LOOP_RE = re.compile(r"\b(while|until|for)\b.*\bdo\b")
SLEEP_RE = re.compile(r"\bsleep\s+(\d+)\b")


def lintable_command(command: str) -> str:
    """The parts of a command that are code, with the prose taken out.

    A commit message quoting a forbidden override is not an override, and a heredoc
    describing a retired file does not render it -- this lint denied its own first
    commit until it learned the difference. Heredoc bodies are dropped, and so is any
    ``git commit`` segment, whose whole purpose is to carry prose about the code.
    """
    kept: list[str] = []
    skip_until: str | None = None
    for line in command.splitlines():
        if skip_until is not None:
            if line.strip() == skip_until:
                skip_until = None
            continue
        if match := HEREDOC_RE.search(line):
            skip_until = match.group(1)
        segments = re.split(r"&&|\|\||;", line)
        kept.append(" ".join(s for s in segments if not re.search(r"\bgit\s+commit\b", s)))
    return "\n".join(kept)


def check_text(text: str, path: str) -> list[Finding]:
    """Rules that read a blob of shell or python: sbatch body, or a command line."""
    findings: list[Finding] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "from snakemake.script import snakemake" in raw:
            findings.append(Finding(
                "SNAKEMAKE_SCRIPT_IMPORT", "error", path, number,
                "Snakemake >= 9 injects `snakemake` as a global; the import raises "
                "ImportError. Use the global with `# noqa: F821`.",
            ))
        if "actor.engine." in raw:
            findings.append(Finding(
                "VERL_ENGINE_OVERRIDE", "error", path, number,
                "verl FSDP knobs belong at actor.fsdp_config.*; __post_init__ clobbers "
                "actor.engine.* and hydra accepts it silently (model_dtype falls back "
                "to fp32). Verify with CFG_ONLY=1 on the login node.",
            ))
        if ASSIGN_IN_COMMENT_RE.match(raw) and not raw.lstrip().startswith("#"):
            findings.append(Finding(
                "ASSIGNMENT_IN_COMMENT", "error", path, number,
                "An assignment sits inside a trailing comment on a line that also assigns, so the shell never "
                "runs it (2026-09-09: PPO_MAX_TOKEN_LEN went unbound this way and cost a queued job). Put the "
                "comment on its own line.",
            ))
        if "report.qmd" in raw:
            findings.append(Finding(
                "REPORT_QMD_RETIRED", "error", path, number,
                "report.qmd was retired repo-wide on 2026-08-31; findings belong in "
                "the experiment's 00-<name>-big-picture.ipynb chronicle.",
            ))
    if (SSH_DELLA_RE.search(text) and LOOP_RE.search(text)
            and any(int(s) < 300 for s in SLEEP_RE.findall(text))):
        findings.append(Finding(
            "SSH_POLL_TOO_FAST", "error", path, 0,
            "A loop that opens ssh to Della and sleeps under 300 s: the gateway blocks an address that "
            "connects too often (Athomia was shut out for an evening on 2026-09-23). Watch "
            "~/.cache/della/status.json, written every five minutes by `just della-status run`, and register "
            "what to track with `just della-status add NAME 'snippet'`.",
        ))
    return findings


def check_script(text: str, path: str) -> list[Finding]:
    """Every rule, applied to one sbatch script."""
    findings = check_text(text, path)
    lines = logical_lines(text)
    directives = sbatch_directives(text)
    servers = parse_servers(lines)
    if _single_gpu(directives):
        servers = [s if s.cards else Server(**{**s.__dict__, "cards": frozenset({0})})
                   for s in servers]
    chat = [s for s in servers if s.kind == "chat"]
    embed = [s for s in servers if s.kind == "embed"]

    gres = directives.get("gres", "")
    n_gpus = int(match.group(1)) if (match := re.search(r"gpu:(?:\w+:)?(\d+)", gres)) else 0

    if runtime := directives.get("time"):
        minutes = parse_slurm_time(runtime)
        if minutes is not None and minutes > MAX_RUNTIME_MINUTES:
            findings.append(Finding(
                "TIME_TOO_LONG", "warn", path, 0,
                f"--time={runtime} is {minutes / 60:.1f}h. Conservative limits (3-6h) "
                "earn queue priority; prefer many short resumable jobs to one long one.",
            ))

    if not re.search(r"^\s*set\s+-\w*e", text, re.MULTILINE):
        findings.append(Finding(
            "NO_SET_E", "warn", path, 0,
            "No `set -e`: a server that fails to launch leaves the job burning its "
            "allocation on the steps after it.",
        ))

    findings += _check_cards(chat, embed, n_gpus, lines, path)
    findings += _check_registry(lines, path)
    findings += _check_memory(servers, path)
    findings += _check_keepalive(text, servers, path)
    findings += _check_order(servers, lines, path)
    findings += _check_port_binding(lines, path)
    return sorted(findings, key=lambda f: (f.level != "error", f.line, f.rule))


def _single_gpu(directives: dict[str, str]) -> bool:
    match = re.search(r"gpu:(?:\w+:)?(\d+)", directives.get("gres", ""))
    return bool(match) and int(match.group(1)) == 1


def _check_cards(chat, embed, n_gpus, lines, path) -> list[Finding]:
    findings: list[Finding] = []
    if not chat:
        return findings  # a pure embed-the-corpus shard: the embedder IS the work

    for server in embed:
        if server.colocated:
            continue
        if server.cards is not None and not any(
            c.cards is None or c.cards & server.cards for c in chat
        ):
            findings.append(Finding(
                "EMBED_ALONE", "error", path, server.line,
                f"An embedding/reranking server holds GPU(s) {sorted(server.cards)} "
                "with no chat server. Alone on an H100 it samples ~0% utilization, "
                "caps the job at tp/(tp+1), and trips Della's 90-minute idle fuse. "
                "Colocate it on the chat model's rank-0 card (launch_colocated_embedder, "
                "0.82 + 0.12) and drop --gres by one.",
            ))
        elif "launch_embedding_server" in server.text:
            findings.append(Finding(
                "EMBED_ALONE", "error", path, server.line,
                "launch_embedding_server gives the embedder a card to itself; beside a "
                "chat model use launch_colocated_embedder instead.",
            ))

    # Every card named anywhere -- server prefixes and the trainer's own export.
    mentioned: set[int] = set()
    for _, line in lines:
        for value in re.findall(r"CUDA_VISIBLE_DEVICES=(\S+)", line):
            mentioned |= _cards(value) or set()

    if n_gpus and mentioned:
        idle = sorted(set(range(n_gpus)) - mentioned)
        if idle:
            findings.append(Finding(
                "IDLE_CARD", "warn", path, 0,
                f"--gres requests {n_gpus} GPU(s) but nothing is pinned to {idle}. "
                "An unused card is an idle card, and Della's daemon cancels the job "
                "around it. Check the trainer's CUDA_VISIBLE_DEVICES, or ask for fewer.",
            ))
    return findings


def _check_registry(lines, path) -> list[Finding]:
    """serve_target launches below the registry's minimum fraction, and raw `vllm serve` lines that could use it."""
    findings: list[Finding] = []
    for number, line in lines:
        if line.lstrip().startswith("#"):
            continue
        if (served := _served_target(line)) is not None:
            name, record = served
            if not record:
                findings.append(Finding("UNKNOWN_TARGET", "error", path, number, f"serve_target {name}: no such target in targets.yaml."))
                continue
            raw = _flag(line, "--fraction")
            try:
                fraction = float(raw) if raw is not None else None
            except ValueError:
                fraction = None
            floor = record.get("min_fraction")
            if fraction is not None and floor is not None and fraction < float(floor):
                findings.append(Finding(
                    "MIN_FRACTION", "error", path, number,
                    f"serve_target {name} at --fraction {fraction} is below the registry minimum {floor}: the weights "
                    "will not load, or leave no cache, and the job dies after its queue wait.",
                ))
        elif SERVE_RE.search(line):
            findings.append(Finding(
                "RAW_VLLM_SERVE", "warn", path, number,
                "A hand-written `vllm serve`: model path, venv, flags and memory fraction are retyped here. Prefer "
                "`serve_target NAME --port P --gpu G` (lib/vllm_server.sh), which reads them from targets.yaml.",
            ))
    return findings


def _check_memory(servers, path) -> list[Finding]:
    """Fractions on one card must sum below 1 -- counted only where we know the card.

    A server whose GPUs come from a shell variable is left out rather than assumed to
    be everywhere: an unprovable overlap is not worth a false alarm.
    """
    findings: list[Finding] = []
    known = [s for s in servers if s.cards]
    for card in sorted({c for s in known for c in s.cards}):
        occupants = [s for s in known if card in s.cards]
        total = sum(s.fraction for s in occupants)
        if len(occupants) > 1 and total >= 1.0:
            detail = ", ".join(f"L{s.line}:{s.fraction:g}" for s in occupants)
            findings.append(Finding(
                "GPU_MEM_OVERSUBSCRIBED", "error", path, occupants[0].line,
                f"GPU {card} is claimed {total:.2f}x over ({detail}). "
                "--gpu-memory-utilization is a fraction of TOTAL device memory, not of "
                "what is free, and it defaults to 0.9 when the flag is absent. The "
                "fractions on one card must sum below 1 (0.82 chat + 0.12 embed).",
            ))
    return findings


def _check_keepalive(text, servers, path) -> list[Finding]:
    if not servers:
        return []
    probes = keepalive_probes(text)
    if probes is None:
        return [Finding(
            "KEEPALIVE_MISSING", "warn", path, 0,
            "This job serves a model but has no `while true` keep-alive loop. Della "
            "cancels any job with a GPU at 0% for 90 minutes, and a serving GPU "
            "flatlines between waves.",
        )]
    if not any(n >= MIN_KEEPALIVE_TOKENS for n in probes):
        seen = f"largest max_tokens seen: {max(probes)}" if probes else "no max_tokens declared"
        return [Finding(
            "KEEPALIVE_THIN", "warn", path, 0,
            f"The keep-alive probes are too thin ({seen}; want >= {MIN_KEEPALIVE_TOKENS}). "
            "A 5ms ping on a 60s cycle is a 0.04% duty cycle: the sampler almost never "
            "looks while the GPU is awake, the job still reads 0.0%, and still dies. "
            "Exp38's cancelled jobs ran the same pings as their surviving twins.",
        )]
    return []


def _check_order(servers, lines, path) -> list[Finding]:
    """Servers sharing a card must start one at a time, each confirmed before the next.

    Concurrent profiling on one GPU dies: the co-location hang of 2026-08-10 (job
    12223731) was two servers each claiming 0.9 of the same card, brought up together.
    The remedy is a wait_for_server between them, not merely a smaller fraction.
    """
    waits = [n for n, line in lines if re.search(r"\bwait_for_server\b|\bwait200\b|\bwait_for_port\b", line)]
    findings: list[Finding] = []
    ordered = sorted(servers, key=lambda s: s.line)
    for earlier, later in zip(ordered, ordered[1:]):
        if not (earlier.cards and later.cards and earlier.cards & later.cards):
            continue
        if any(earlier.line < w < later.line for w in waits):
            continue
        findings.append(Finding(
            "CONCURRENT_STARTUP", "warn", path, later.line,
            f"A server starts on a card shared with the one launched at line "
            f"{earlier.line}, with no wait_for_server between them. Bring the chat "
            "server up first and let wait_for_server confirm it, so the large "
            "allocation profiles uncontended (the co-location hang of 2026-08-10).",
        ))
    return findings


def _check_port_binding(lines, path) -> list[Finding]:
    """A server's port is chosen just before its launch, not minutes earlier.

    Ports picked free at job start are claimed by another of our jobs on the same node
    while the first servers come up (2026-09-29: a training segment's retrieval server
    died with "address already in use", an eval job having landed on the same node). The
    rule: between the line that assigns a port variable and the launch that uses it there
    must be no other server's launch-and-wait. Re-pick the port right before the bind.
    """
    assigns: dict[str, int] = {}
    for n, line in lines:
        for name in re.findall(r"\b(P_[A-Z0-9_]+|[A-Z0-9_]*PORT[A-Z0-9_]*)=", line):
            assigns[name] = n            # the latest assignment wins, as in the shell
        if match := re.match(r"\s*read\s+-r\s+((?:P_[A-Z0-9_]+\s+)+)", line):
            for name in match.group(1).split(): assigns[name] = n
    launches = [(n, line) for n, line in lines if _is_launch(line)]
    waits = [n for n, line in lines if re.search(r"\bwait_for_server\b|\bwait200\b|\bwait_for_port\b", line)]
    findings: list[Finding] = []
    for n, line in launches:
        for name in re.findall(r"\$\{?(P_[A-Z0-9_]+|[A-Z0-9_]*PORT[A-Z0-9_]*)\}?", line):
            if name not in assigns: continue
            picked = assigns[name]
            between = [m for m, _ in launches if picked < m < n]
            if between and any(picked < w < n for w in waits):
                findings.append(Finding(
                    "PORT_PICKED_EARLY", "warn", path, n,
                    f"{name} was chosen at line {picked} but bound here, after another server's launch "
                    f"and wait at line {between[0]}. Another of our jobs on the node can take it in "
                    "between (2026-09-29). Re-pick the port immediately before this launch.",
                ))
                break
    return findings


def _is_launch(line: str) -> bool:
    return bool(re.search(r"\bserve_target\b|\blaunch_vllm_server\b|\blaunch_embedding_server\b|\blaunch_colocated_embedder\b|\bvllm\s+serve\b|serve_news_rag\.py|--port\s", line)) and not line.lstrip().startswith("#")


# ------------------------------------------------------------------ entrypoints


def repo_root() -> Path:
    """The git work tree containing this file."""
    return Path(__file__).resolve().parents[2]


def repo_name() -> str:
    """The repo's name as ``zetteldev.config`` resolves it, loaded by path: the hook runs outside the venv."""
    spec = importlib.util.spec_from_file_location("zetteldev_config", Path(__file__).resolve().parents[1] / "config.py")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config.settings()["repo"]


def tracked_sbatch() -> list[Path]:
    root = repo_root()
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "*.sbatch"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [root / p for p in out.split("\0") if p]


def lint_paths(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    root = repo_root()
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(Finding("UNREADABLE", "warn", str(path), 0, str(exc)))
            continue
        try:
            shown = str(path.resolve().relative_to(root))
        except ValueError:
            shown = str(path)
        findings += check_script(text, shown)
    return findings


def resolve_command_scripts(command: str) -> tuple[list[Path], list[str]]:
    """Local files for the ``.sbatch`` tokens in a (possibly remote) command.

    Submissions read ``ssh della 'cd ~/src/<repo>/experiments/X && sbatch
    scripts/slurm/y.sbatch'``: the path is remote and relative to a cd. Both known
    repo checkouts (``~/src`` and the scratch checkout, ``della_scratch``) share this
    repo's layout, so anything after ``<repo>/`` is a repo-relative path.
    """
    root = repo_root()
    cds = re.findall(r"\bcd\s+([^\s;&|'\"]+)", command)
    prefix, marker = "", repo_name() + "/"
    for target in cds:
        if marker in target:
            prefix = target.split(marker, 1)[1].rstrip("/") + "/"
    resolved: list[Path] = []
    notes: list[str] = []
    for token in re.findall(r"[^\s;&|'\"]+\.sbatch", command):
        token = token.split(marker)[-1]
        candidates = [root / token]
        if prefix:
            candidates.insert(0, root / (prefix + token))
        local = next((c for c in candidates if c.is_file()), None)
        if local is None:
            matches = list(root.glob(f"**/{Path(token).name}"))
            local = matches[0] if len(matches) == 1 else None
        if local is None:
            notes.append(f"no local copy of {token}; not linted")
        else:
            resolved.append(local)
    return resolved, notes


def run_hook() -> int:
    """PreToolUse mode: read the tool call, decide, never block on what we can't read."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if re.search(r"sbatch-lint|just\s+preflight", command):
        return 0  # running the lint is not a submission; do not lint the linting

    # No cheap pre-gate on the text rules: a `\bpython\b` guard would miss `python3`,
    # which is how the verl override is usually invoked, and the rules cost microseconds.
    findings = check_text(lintable_command(command), "<command>")
    paths, notes = ([], [])
    if re.search(r"\bsbatch\b", command):
        paths, notes = resolve_command_scripts(command)
        findings += lint_paths(paths)
    findings = [f for f in findings if f.level == "error"]      # warnings are advice for `just preflight`, not a prompt on every command
    if not findings:
        return 0

    # A fault in the command being composed right now is worth denying outright; a
    # fault in a script on disk is only worth asking about, since thirty-odd
    # pre-audit scripts are still legitimately submitted and the author, not the
    # lint, decides when history is worth rewriting.
    fatal = [f for f in findings if f.level == "error" and f.path == "<command>"]
    body = "\n".join(f.render() for f in findings)
    if notes:
        body += "\n" + "\n".join(f"      note: {n}" for n in notes)
    reason = (
        "Della pre-flight lint (.zetteldev/della/bin/sbatch-lint):\n" + body + "\n"
        "Each rule marks a failure that has already cost this repository compute. "
        "Fix the script, or re-run the command if you judge the rule inapplicable here."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if fatal else "ask",
            "permissionDecisionReason": reason,
        },
    }))
    return 0


def main(argv: list[str]) -> int:
    if "--hook" in argv:
        return run_hook()
    paths = [Path(a) for a in argv if not a.startswith("-")] or tracked_sbatch()
    findings = lint_paths(paths)
    for finding in findings:
        print(finding.render())
    errors = sum(1 for f in findings if f.level == "error")
    warns = len(findings) - errors
    print(f"\n{len(paths)} script(s): {errors} error(s), {warns} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
