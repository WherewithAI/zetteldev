"""Unit tests for the registry-driven Della orchestration (zetteldev.della).

Pure-python, no cluster: validates resource derivation, ${var} resolution, the
required-key validator, and worker_shard env parsing. Mirrors the test plan in
the `20260604 Snakemake vLLM Wizardry on Della` zettel (Phase-2 #1).
"""

import textwrap

import pytest

from zetteldev import della


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Write a temp targets.yaml and make it the default registry (so the no-arg
    ``load_targets()`` used by gpu()/n_gpus() reads it). Cache cleared per test."""

    def _write(yaml_text: str):
        path = tmp_path / "targets.yaml"
        path.write_text(textwrap.dedent(yaml_text))
        monkeypatch.setattr(della, "_registry_path", lambda: path)
        della.load_targets.cache_clear()
        return della.load_targets()

    yield _write
    della.load_targets.cache_clear()


def test_resource_derivation_no_embed(registry):
    registry(
        """
        small:
          account: henderson
          partition: pli-c
          model_path: /cache/m
          tensor_parallel: 1
          tool_parser: hermes
          max_model_len: 8192
          runtime: 60
        """
    )
    # monkeypatch the module cache to our temp registry by re-calling gpu via the cached load
    res = della.gpu("small")
    assert della.n_gpus("small") == 1
    assert res["slurm_partition"] == "pli-c"
    assert res["cpus_per_task"] == della.CPUS_PER_GPU * 1
    assert res["mem_mb"] == della.MEM_MB_PER_GPU * 1
    assert res["runtime"] == 60
    # Native plugin keys (NOT slurm_extra — that deadlocks the executor).
    assert res["slurm_account"] == "henderson"
    assert res["gres"] == "gpu:1"
    assert "slurm_extra" not in res


def test_embed_sidecar_adds_no_gpu(registry):
    """The audit of 2026-08-17: a sidecar colocates on the chat model's rank-0 card.

    Until that day this function added a card per sidecar, and those idle cards cost
    51.6 GPU-hours and every long slurm-cancellation in exp38's record. The test kept
    asserting the old arithmetic, so the suite disagreed with both the docstring and
    the submission lint that now rejects a lone embedder.
    """
    registry(
        """
        big:
          account: henderson
          partition: ailab
          model_path: /cache/big
          tensor_parallel: 2
          tool_parser: hermes
          max_model_len: 16384
          runtime: 180
          embed: { model_path: /cache/embed }
        """
    )
    assert della.n_gpus("big") == 2  # tp(2), and the sidecar rides along on card 0
    res = della.gpu("big")
    assert res["cpus_per_task"] == della.CPUS_PER_GPU * 2
    assert res["gres"] == "gpu:2"


def test_var_resolution_in_paths(registry):
    t = registry(
        """
        t:
          account: a
          cache: /scratch/cache
          partition: p
          model_path: ${cache}/model-x
          tensor_parallel: 1
          tool_parser: hermes
          max_model_len: 8192
          runtime: 30
          embed: { model_path: "${cache}/embed-y" }
        """
    )
    assert t["t"]["model_path"] == "/scratch/cache/model-x"
    assert t["t"]["embed"]["model_path"] == "/scratch/cache/embed-y"


def test_overrides_win(registry):
    registry(
        """
        t:
          account: a
          partition: p
          model_path: /m
          tensor_parallel: 1
          tool_parser: hermes
          max_model_len: 8192
          runtime: 30
        """
    )
    res = della.gpu("t", runtime=300, mem_mb=99000)
    assert res["runtime"] == 300
    assert res["mem_mb"] == 99000


def test_explicit_gpu_and_cpu_overrides(registry):
    registry(
        """
        t:
          account: a
          partition: p
          model_path: /m
          tensor_parallel: 4
          tool_parser: hermes
          max_model_len: 8192
          runtime: 30
          gpus: 6
          cpus_per_task: 40
        """
    )
    assert della.n_gpus("t") == 6
    res = della.gpu("t")
    assert res["cpus_per_task"] == 40          # explicit override, not derived
    assert res["gres"] == "gpu:6"


def test_missing_required_key_rejected(registry):
    with pytest.raises(ValueError, match="missing required key"):
        registry(
            """
            broken:
              account: a
              partition: p
              model_path: /m
              tool_parser: hermes
              max_model_len: 8192
              runtime: 30
            """
        )  # tensor_parallel missing


def test_anchors_are_skipped(registry):
    t = registry(
        """
        _defaults: &d
          account: henderson
          cache: /c
        real:
          <<: *d
          partition: p
          model_path: ${cache}/m
          tensor_parallel: 1
          tool_parser: hermes
          max_model_len: 8192
          runtime: 30
        """
    )
    assert "_defaults" not in t
    assert t["real"]["model_path"] == "/c/m"


def test_worker_shard_env(monkeypatch):
    monkeypatch.delenv("WORKER_RANK", raising=False)
    monkeypatch.delenv("WORKER_WORLD", raising=False)
    assert della.worker_shard() == (0, 1)
    monkeypatch.setenv("WORKER_RANK", "2")
    monkeypatch.setenv("WORKER_WORLD", "7")
    assert della.worker_shard() == (2, 7)


def test_endpoints_loud_without_wrapper(monkeypatch):
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    with pytest.raises(RuntimeError, match="della-vllm-run"):
        della.endpoints()
    monkeypatch.setenv("OPENAI_API_BASE", "http://localhost:8013/v1")
    monkeypatch.setenv("EMBEDDING_API_BASE", "http://localhost:8012/v1")
    eps = della.endpoints()
    assert eps["chat"].endswith("8013/v1") and eps["embed"].endswith("8012/v1")


def test_shipped_registry_loads_and_validates():
    """The real .zetteldev/della/targets.yaml parses and gpt-oss-120b derives 2 GPUs."""
    della.load_targets.cache_clear()
    targets = della.load_targets()
    assert "gpt-oss-120b" in targets
    assert della.n_gpus("gpt-oss-120b") == 2
    assert della.gpu("gpt-oss-120b")["slurm_partition"] == "pli-c"
    della.load_targets.cache_clear()
