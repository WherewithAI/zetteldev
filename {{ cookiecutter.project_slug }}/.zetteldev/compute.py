"""The interactive tier: run a notebook's expensive-but-bounded computations on Dask, wherever the notebook is.

The rule (zettel "Walking with Phones", 2026-09-07): computations that take minutes to an hour, in tight loops,
are defined in the notebook and run on Dask, so they can be rerun from the notebook later. They run on
Athomia's GPUs; Della is reached only through its services (see `zetteldev.services`).

    from zetteldev import compute
    client = compute.client()                 # Athomia's cluster, from Athomia or from SolveIt; None if unreachable
    results = compute.map(fit_variant, configs)   # Dask when a client exists, in-process otherwise (with a warning)

    @compute.cached("processed_data/fb_sweeps")   # results keyed by the function's source and its arguments
    def fit_variant(cfg): ...

Functions shipped to the cluster must be importable there: put them in `#|export` cells, so the exported
module, which git carries to every machine, defines them. A closure over notebook-only state pickles by value
and may fail on the worker.

`cached` writes one pickle per call under the given directory (small ones travel by the small data tier), so
a rerun of the notebook reads what an earlier session computed, on any machine.
"""
from __future__ import annotations
import functools, hashlib, inspect, json, os, pickle, socket, warnings
from pathlib import Path
from .config import settings

__all__ = ["client", "map", "submit", "cached", "status"]

_CLIENT = None
_REMOTE_HOST = os.environ.get("ZDEV_COMPUTE_HOST") or settings()["compute_host"]


def _on_compute_host() -> bool:
    return socket.gethostname().split(".")[0].lower() == _REMOTE_HOST


def client(name: str = "default", **kw):
    "A Dask client to Athomia's cluster: local when we are on Athomia, tunnelled over ssh otherwise; None if it cannot be reached."
    global _CLIENT
    if _CLIENT is not None:
        try:
            _CLIENT.scheduler_info(); return _CLIENT
        except Exception: _CLIENT = None
    from . import cluster as zdask
    try:
        _CLIENT = zdask.client(name, **kw) if _on_compute_host() else zdask.connect(_REMOTE_HOST, name=name)
    except Exception as e:
        warnings.warn(f"no Dask cluster reachable ({type(e).__name__}: {str(e)[:120]}); computations run in-process")
        _CLIENT = None
    return _CLIENT


def map(fn, items, *, resources: dict | None = None, **kw) -> list:
    "fn over items on the cluster, gathered in order; in-process when no cluster is reachable."
    cl = client()
    if cl is None: return [fn(x, **kw) for x in items]
    futures = cl.map(fn, list(items), pure=False, resources=resources, **kw)
    return cl.gather(futures)


def submit(fn, *args, **kw):
    "One task on the cluster (a Future), or its result computed in-process when no cluster is reachable."
    cl = client()
    return cl.submit(fn, *args, pure=False, **kw) if cl is not None else fn(*args, **kw)


def _key(fn, args, kwargs) -> str:
    try: src = inspect.getsource(fn)
    except (OSError, TypeError): src = fn.__qualname__
    blob = json.dumps({"src": src, "args": args, "kwargs": kwargs}, default=repr, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def cached(directory: str):
    "Memoise a function's results on disk under `directory/<fn name>/<key>.pkl`, keyed by its source and its arguments."
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            d = Path(directory) / fn.__name__; d.mkdir(parents=True, exist_ok=True)
            p = d / f"{_key(fn, args, kwargs)}.pkl"
            if p.exists():
                with open(p, "rb") as f: return pickle.load(f)
            out = fn(*args, **kwargs)
            tmp = p.with_suffix(".tmp")
            with open(tmp, "wb") as f: pickle.dump(out, f)
            os.replace(tmp, p)
            (d / f"{p.stem}.json").write_text(json.dumps({"fn": fn.__qualname__, "args": args, "kwargs": kwargs}, default=repr, indent=1))
            return out
        wrapper.cache_dir = lambda: Path(directory) / fn.__name__
        return wrapper
    return deco


def status() -> dict:
    "Where computations would run right now."
    cl = client()
    if cl is None: return {"mode": "in-process", "host": socket.gethostname()}
    info = cl.scheduler_info()
    return {"mode": "dask", "via": "local" if _on_compute_host() else f"ssh tunnel to {_REMOTE_HOST}", "workers": len(info.get("workers", {})),
            "threads": sum(w.get("nthreads", 0) for w in info.get("workers", {}).values()), "dashboard": cl.dashboard_link}
