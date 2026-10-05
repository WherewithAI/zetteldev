"""Where this repo lives and what it talks to, for every zetteldev tool: read from three layers, later winning.

1. `DEFAULTS` below: conventions that hold for any repo, written with `{repo}` and `{other_key}` placeholders, which
   are filled from the resolved settings; a placeholder that names an unset key leaves its own key unset.
2. The repo's `pyproject.toml`: `[project].name` is the `repo`, and `[tool.zetteldev]` holds what everyone
   working on the repo shares (hosts named in its docs, the figure domain).
3. `~/.config/zetteldev/config.toml`, a `[zetteldev]` table: what differs per person (their ssh aliases,
   their scratch path). A `[zetteldev.<repo>]` table there applies to that repo alone.

Keys without a default must be set in one of the last two layers before the tools that need them run;
`setting()` says which key and where. From the shell, `python3 .zetteldev/config.py <key>` prints one value,
and no argument prints every resolved setting.

    from zetteldev.config import setting
    setting('della_repo')     # '~/src/<repo>'
"""
import sys, tomllib
from functools import cache
from pathlib import Path

__all__ = ['ROOT', 'USER_CONFIG', 'DEFAULTS', 'settings', 'setting']

ROOT = Path(__file__).resolve().parent.parent
USER_CONFIG = Path.home()/'.config'/'zetteldev'/'config.toml'

DEFAULTS = dict(
    della_host=None,                 # ssh alias of the SLURM cluster's login node
    della_repo='~/src/{repo}',       # the repo's checkout on the cluster
    della_scratch='{della_user_scratch}/{repo}',   # the bulk-data checkout on the cluster, pulled by `just dellaloot`
    della_account=None,              # the SLURM account jobs charge
    della_group_scratch=None,        # the group's scratch fileset on the cluster
    della_user_scratch=None,         # this user's directory under it: logs, models, environments, the DVC cache
    della_weights_cache='{della_group_scratch}/transformer_cache',   # shared model weights
    della_models='{della_user_scratch}/models',                      # weights not in the shared cache, merged checkpoints
    della_envs='{della_user_scratch}/environments',                  # the serving venvs
    della_vllm_venv='{della_envs}/vllm-env',                         # the default vLLM venv
    della_dvc_cache='{della_user_scratch}/dvc-cache',                # the DVC store, which is also the remote
    della_sync_dirs=['processed_data'],
    solveit_host=None,               # ssh alias of the SolveIt instance
    solveit_root='/app/data/{repo}', # the repo's checkout there; dialog names are paths under its parent
    compute_host=None,               # hostname of the Dask machine; unset means computations run in-process
    figures_bucket='zetteldev-figures',
    figures_url=None,                # public base URL of the figures bucket
    base_url='http://localhost:8000',
)

class _Env(dict):
    "The string settings as a format mapping; asking for an unset or non-string key raises `_Unset`"
    def __missing__(self, k): raise _Unset(k)

class _Unset(Exception): pass

def _fill(v, env: dict):
    if isinstance(v, str):
        try: return v.format_map(_Env({k: x for k, x in env.items() if isinstance(x, str)}))
        except _Unset: return None
    if isinstance(v, list): return [_fill(o, env) for o in v]
    return v


@cache
def settings() -> dict:
    "Every setting for this repo, resolved through the three layers, placeholders filled"
    pp = tomllib.loads((ROOT/'pyproject.toml').read_text())
    repo_cfg = pp.get('tool', {}).get('zetteldev', {})
    repo = repo_cfg.get('repo', pp['project']['name'])
    user = tomllib.loads(USER_CONFIG.read_text()).get('zetteldev', {}) if USER_CONFIG.exists() else {}
    per_repo = user.get(repo, {})
    shared = {k: v for k, v in user.items() if not isinstance(v, dict)}
    merged = DEFAULTS | repo_cfg | shared | per_repo | dict(repo=repo)
    return _resolve(merged)


def _resolve(merged: dict) -> dict:
    "Fill `{key}` placeholders from the other settings until nothing changes; a placeholder naming an unset key leaves the value unset"
    out = dict(merged)
    for _ in range(8):
        prev = dict(out)
        for k, v in prev.items(): out[k] = _fill(v, prev)
        if out == prev: break
    return out

def layers() -> dict:
    "Which layer each setting's value came from: 'default', 'pyproject', 'user' or 'user:<repo>' (for the doctor's report)"
    pp = tomllib.loads((ROOT/'pyproject.toml').read_text())
    repo_cfg = pp.get('tool', {}).get('zetteldev', {}); repo = repo_cfg.get('repo', pp['project']['name'])
    user = tomllib.loads(USER_CONFIG.read_text()).get('zetteldev', {}) if USER_CONFIG.exists() else {}
    out = {k: 'default' for k in DEFAULTS}
    for name, layer in [('pyproject', repo_cfg), ('user', {k: v for k, v in user.items() if not isinstance(v, dict)}), (f'user:{repo}', user.get(repo, {}))]:
        for k in layer: out[k] = name
    return out


def setting(key: str):
    "One setting; raises `KeyError` naming where to set it when it has no value"
    v = settings().get(key)
    if v is None: raise KeyError(f"zetteldev setting {key!r} is unset: add `{key} = ...` under [tool.zetteldev] in "
                                 f"{ROOT/'pyproject.toml'}, or under [zetteldev] in {USER_CONFIG}")
    return v

if __name__ == '__main__':
    if len(sys.argv) < 2: print('\n'.join(f'{k} = {v!r}' for k, v in settings().items()))
    else:
        try: v = setting(sys.argv[1])
        except KeyError as e: sys.exit(e.args[0])
        print(' '.join(v) if isinstance(v, list) else v)
