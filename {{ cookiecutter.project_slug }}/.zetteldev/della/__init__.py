"""Registry-driven Della SLURM orchestration (Snakemake vLLM Wizardry).

Pure-python, no cluster dependencies — importable by any Snakefile and by tests.
Reads the single vLLM target registry at ``.zetteldev/della/targets.yaml`` (which
sits beside this file) and derives, for each target, the Snakemake ``resources:``
dict that the snakemake-executor-plugin-slurm consumes. The companion shell wrapper
``.zetteldev/della/bin/della-vllm-run`` reads the *same* registry to launch the
matching vLLM server, so one declaration drives both the allocation and the server.

Typical use in a Snakefile::

    from zetteldev.della import gpu

    rule extract_beliefs:
        input:  script="scripts/belief_extractor.py"
        output: directory("processed_data/beliefs_smallscale")
        resources: **gpu("gpt-oss-120b")
        shell:  "della-vllm-run --target gpt-oss-120b --workers 10 -- "
                "uv run python {input.script} --small-scale --model openai/model"

See ``20260604 Snakemake vLLM Wizardry on Della`` for the design.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from ..config import settings

# Keys every target must declare (anything else is optional / derived).
REQUIRED_KEYS = ("partition", "model_path", "tensor_parallel", "tool_parser", "max_model_len", "runtime")

# Derivation constants (della "8 cores / GPU", node memory ratio).
CPUS_PER_GPU = 8
MEM_MB_PER_GPU = 64_000


def _registry_path() -> Path:
    """Locate targets.yaml (it lives in this package directory, .zetteldev/della/)."""
    return Path(__file__).resolve().parent / "targets.yaml"


@lru_cache(maxsize=1)
def load_targets(path: str | None = None) -> dict:
    """Parse and validate the vLLM target registry (cached).

    Resolves ``${<setting>}`` placeholders (any string setting of ``zetteldev.config``, e.g. ``${della_models}``)
    and ``${cache}`` against each target's ``cache``,
    and validates that every target declares the required keys.

    Args:
        path: Override the registry location (mainly for tests).

    Returns:
        Mapping of target-name -> resolved config dict.

    Raises:
        FileNotFoundError: registry missing.
        ValueError: a target is missing a required key.
    """
    import yaml

    reg_path = Path(path) if path else _registry_path()
    if not reg_path.exists():
        raise FileNotFoundError(f"vLLM target registry not found: {reg_path}")
    raw = yaml.safe_load(reg_path.read_text()) or {}

    targets: dict[str, dict] = {}
    for name, cfg in raw.items():
        if name.startswith("_"):  # YAML anchors like _defaults
            continue
        cfg = dict(cfg)
        # two passes: the group values first (so a `cache` that reads `${della_weights_cache}` resolves), then the
        # target's own `cache` beside them
        group = {k: v for k, v in settings().items() if isinstance(v, str)}
        cfg = _resolve_vars(cfg, group)
        cfg = _resolve_vars(cfg, group | {"cache": cfg.get("cache", "")})
        missing = [k for k in REQUIRED_KEYS if k not in cfg]
        if missing:
            raise ValueError(f"target {name!r} missing required key(s): {', '.join(missing)}")
        targets[name] = cfg
    return targets


def _resolve_vars(cfg: dict, vars_: dict) -> dict:
    """Substitute ${var} placeholders in string-valued fields (one level, incl. nested dicts)."""

    def sub(value):
        if isinstance(value, str):
            return re.sub(r"\$\{(\w+)\}", lambda m: str(vars_.get(m.group(1), m.group(0))), value)
        if isinstance(value, dict):
            return {k: sub(v) for k, v in value.items()}
        return value

    return {k: sub(v) for k, v in cfg.items()}


def n_gpus(name: str) -> int:
    """Total GPUs a target needs: ``tensor_parallel``, and no more.

    An ``embed`` sidecar adds NOTHING here. It is colocated on the chat model's
    rank-0 GPU at a small memory fraction, because an embedding model alone on
    an H100 samples 0% utilisation — which caps the job's efficiency at
    tp/(tp+1) and trips Della's 90-minute idle fuse. Until 2026-08-17 this
    function added a card per sidecar; the audit of that day found 51.6
    GPU-hours burnt on those idle cards and every long slurm-cancellation
    traceable to one. Override with an explicit ``gpus:`` in targets.yaml if a
    target genuinely needs more.
    """
    t = load_targets()[name]
    return int(t.get("gpus", t["tensor_parallel"]))


def gpu(name: str, **overrides) -> dict:
    """Snakemake ``resources:`` kwargs for a target; derives gpus/cpus/mem.

    ``overrides`` bump any field, e.g. ``gpu("qwen3-80b", runtime=300)``.

    Uses the snakemake-executor-plugin-slurm **native** resource keys
    (``slurm_account``, ``gres``). Do NOT route ``--account`` / ``--gres`` /
    ``--partition`` / ``--mem`` etc. through ``slurm_extra``: the plugin's
    ``validate_slurm_extra`` raises ``WorkflowError`` for those plugin-managed
    flags, and because the raise happens inside the submit worker thread the
    exception is swallowed and the controller **deadlocks** at "Execute 1 jobs…"
    with no error. ``gres`` must be an unquoted ``"gpu:N"`` string (the plugin
    rejects tick/quote-wrapped values).
    """
    t = load_targets()[name]
    n = n_gpus(name)
    res = {
        "slurm_partition": t["partition"],
        "slurm_account": t["account"],
        "gres": f"gpu:{n}",
        "cpus_per_task": int(t.get("cpus_per_task", CPUS_PER_GPU * n)),
        "mem_mb": int(t.get("mem_mb", MEM_MB_PER_GPU * n)),
        "runtime": int(t["runtime"]),
    }
    res.update(overrides)
    return res


def worker_shard() -> tuple[int, int]:
    """(rank, world) for self-partitioning, from env set by della-vllm-run.

    Reads ``WORKER_RANK`` / ``WORKER_WORLD``; defaults to (0, 1) so a script run
    outside the wrapper processes everything.
    """
    rank = int(os.getenv("WORKER_RANK", "0"))
    world = int(os.getenv("WORKER_WORLD", "1"))
    return rank, world


def endpoints() -> dict:
    """{'chat': OPENAI_API_BASE, 'embed': EMBEDDING_API_BASE} from env.

    Raises a loud error if the chat endpoint is unset (script run outside
    della-vllm-run, which exports these after the servers are healthy).
    """
    chat = os.getenv("OPENAI_API_BASE")
    if not chat:
        raise RuntimeError(
            "OPENAI_API_BASE is unset — run this script under `della-vllm-run` "
            "(which launches the vLLM server and exports its endpoint)."
        )
    return {"chat": chat, "embed": os.getenv("EMBEDDING_API_BASE")}
