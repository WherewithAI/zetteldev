"""Unit tests for the Della submission pre-flight lint (zetteldev.della.sbatch_lint).

Pure-python, no cluster. Each rule is exercised twice: once on the shape that cost us
compute, and once on the shape that fixed it -- a lint that cries wolf at the correct
pattern is worse than none, since it teaches the reader to submit through the warning.
"""

import io
import json
import sys
import textwrap

import pytest

from zetteldev.della import sbatch_lint


def rules(script: str) -> set[str]:
    """Rule names fired by a script given as an indented triple-quoted string."""
    return {f.rule for f in sbatch_lint.check_script(textwrap.dedent(script), "t.sbatch")} - {"RAW_VLLM_SERVE"}   # advisory: the corpus predates serve_target


HEADER = """\
#!/bin/bash
#SBATCH --gres=gpu:2
#SBATCH --account=henderson
#SBATCH --time=03:00:00
set -euo pipefail
"""

KEEPALIVE = """\
(while true; do
    curl -s -d '{"model":"m","messages":[],"max_tokens":2048}' http://localhost:8000/v1/chat/completions
    sleep 90
done) &
"""


# ------------------------------------------------------------------ line joining


def test_continuation_lines_are_joined_before_flags_are_read():
    """The flag and its CUDA_VISIBLE_DEVICES sit five lines apart in every real script."""
    lines = sbatch_lint.logical_lines(
        'CUDA_VISIBLE_DEVICES=0,1 vllm serve M \\\n    --gpu-memory-utilization 0.82 \\\n    --port 8000\n'
    )
    assert len(lines) == 1
    number, joined = lines[0]
    assert number == 1
    assert "CUDA_VISIBLE_DEVICES=0,1" in joined and "0.82" in joined


@pytest.mark.parametrize("value,expected", [
    ("30", 30), ("30:00", 30), ("06:00:00", 360),
    ("1-00", 1440), ("1-02:30", 1590), ("2-00:00:00", 2880),
])
def test_every_slurm_time_shape_parses(value, expected):
    assert sbatch_lint.parse_slurm_time(value) == expected


# -------------------------------------------------------------- the lonely embedder


def test_embedder_alone_on_a_card_is_an_error():
    assert "EMBED_ALONE" in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0 vllm serve chat --gpu-memory-utilization 0.9 &
        wait_for_server http://localhost:8000 chat 30
        CUDA_VISIBLE_DEVICES=1 vllm serve Qwen3-Embedding-8B --task embed &
        """ + KEEPALIVE)


def test_colocated_embedder_is_the_sanctioned_pattern():
    assert not rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        launch_colocated_embedder "$EMBED" 8100 logs/e.log embedding 0.12
        """ + KEEPALIVE)


def test_pure_embed_job_may_keep_its_card():
    """An embed-the-corpus shard is the one exception: the embedder IS the work."""
    assert "EMBED_ALONE" not in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0 vllm serve Qwen3-Embedding-8B --task embed &
        """ + KEEPALIVE)


def test_a_judge_is_a_chat_server_so_its_card_is_not_lonely():
    """exp35's GPU7 carries embed + rerank + judge; the judge redeems the card."""
    assert "EMBED_ALONE" not in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=1 vllm serve Qwen3-Embedding-8B --task embed --gpu-memory-utilization 0.35 &
        wait_for_server http://localhost:8100 embed 30
        CUDA_VISIBLE_DEVICES=1 vllm serve judge --served-model-name qwen3-judge --gpu-memory-utilization 0.25 &
        wait_for_server http://localhost:8104 judge 30
        """ + KEEPALIVE)


# ------------------------------------------------------------------ card arithmetic


def test_absent_memory_flag_counts_as_nine_tenths_not_zero():
    """The trap: an unflagged chat server plus a 0.12 embedder is already 1.02."""
    fired = rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0 vllm serve chat &
        wait_for_server http://localhost:8000 chat 30
        CUDA_VISIBLE_DEVICES=0 vllm serve Qwen3-Embedding-8B --task embed --gpu-memory-utilization 0.12 &
        """ + KEEPALIVE)
    assert "GPU_MEM_OVERSUBSCRIBED" in fired


def test_the_documented_split_passes():
    assert "GPU_MEM_OVERSUBSCRIBED" not in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        CUDA_VISIBLE_DEVICES=0 vllm serve Qwen3-Embedding-8B --task embed --gpu-memory-utilization 0.12 &
        """ + KEEPALIVE)


def test_unknowable_cards_raise_no_alarm():
    """GPUs from a shell variable: an unprovable overlap is not worth a false alarm."""
    assert "GPU_MEM_OVERSUBSCRIBED" not in rules(HEADER + """
        launch_vllm_server "$MODEL" "$GPUS" "$TP" 8000
        wait_for_server http://localhost:8000 chat 30
        """ + KEEPALIVE)


def test_requesting_a_card_nothing_uses_is_flagged():
    assert "IDLE_CARD" in rules("""\
        #!/bin/bash
        #SBATCH --gres=gpu:4
        #SBATCH --time=03:00:00
        set -euo pipefail
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        """ + KEEPALIVE)


def test_two_servers_on_one_card_must_be_serialized():
    assert "CONCURRENT_STARTUP" in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0 vllm serve chat --gpu-memory-utilization 0.5 &
        CUDA_VISIBLE_DEVICES=0 vllm serve Qwen3-Embedding-8B --task embed --gpu-memory-utilization 0.12 &
        wait_for_server http://localhost:8000 chat 30
        """ + KEEPALIVE)


def test_a_comment_naming_a_helper_is_not_a_launch():
    """Half the corpus explains the colocation rule in prose above the launch."""
    assert not rules(HEADER + """
        # We do NOT call launch_embedding_server here; see the audit of 2026-08-17.
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        """ + KEEPALIVE)


# ------------------------------------------------------------------- the keep-alive


def test_a_serving_job_without_a_keepalive_is_flagged():
    assert "KEEPALIVE_MISSING" in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        python scripts/rollout.py
        """)


def test_a_ping_sized_probe_is_still_too_thin():
    """exp38's cancelled jobs ran the same 48-token pings as their surviving twins."""
    assert "KEEPALIVE_THIN" in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        (while true; do
            curl -s -d '{"model":"m","messages":[],"max_tokens":48}' http://localhost:8000/v1/chat/completions
            sleep 60
        done) &
        """)


def test_real_decode_work_satisfies_the_fuse():
    assert "KEEPALIVE_THIN" not in rules(HEADER + """
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:8000 chat 30
        """ + KEEPALIVE)


def test_a_cpu_job_is_asked_for_no_keepalive():
    assert not rules("""\
        #!/bin/bash
        #SBATCH --time=01:00:00
        set -euo pipefail
        python scripts/prepare.py
        """)


# ------------------------------------------------------------------- textual rules


def test_time_beyond_six_hours_warns():
    assert "TIME_TOO_LONG" in rules("#!/bin/bash\n#SBATCH --time=12:00:00\nset -e\n")


def test_missing_set_e_warns():
    assert "NO_SET_E" in rules("#!/bin/bash\n#SBATCH --time=01:00:00\npython x.py\n")


@pytest.mark.parametrize("command", [
    'git commit -m "fix the actor.engine.* trap"',
    "cat <<EOF\nquarto render report.qmd\nEOF",
    "git add -A && git commit -F - <<'MSG'\nfrom snakemake.script import snakemake\nMSG",
])
def test_prose_about_a_trap_is_not_the_trap(command):
    """The lint denied its own first commit for quoting a rule in the message."""
    assert not sbatch_lint.check_text(sbatch_lint.lintable_command(command), "<command>")


def test_a_five_minute_poll_over_the_master_is_allowed():
    """The gateway counts handshakes; one every five minutes over the control master is the sanctioned cadence."""
    ok = "while true; do ssh della squeue -u km5839; sleep 300; done"
    assert not sbatch_lint.check_text(ok, "<command>")


@pytest.mark.parametrize("snippet,rule", [
    ("from snakemake.script import snakemake", "SNAKEMAKE_SCRIPT_IMPORT"),
    ("python train.py actor.engine.model_dtype=bf16", "VERL_ENGINE_OVERRIDE"),
    ("quarto render report.qmd", "REPORT_QMD_RETIRED"),
    ("while true; do ssh della squeue -u km5839; sleep 30; done", "SSH_POLL_TOO_FAST"),
])
def test_command_text_rules(snippet, rule):
    assert {f.rule for f in sbatch_lint.check_text(snippet, "<command>")} == {rule}


# ------------------------------------------------------------------------ hook mode


def test_hook_resolves_a_remote_relative_path(monkeypatch, tmp_path):
    """Submissions read `ssh della 'cd ~/src/reason_reckon/experiments/X && sbatch ...'`."""
    root = tmp_path / "reason_reckon"
    script = root / "experiments" / "42-x" / "scripts" / "slurm" / "j.sbatch"
    script.parent.mkdir(parents=True)
    script.write_text(HEADER + "\nCUDA_VISIBLE_DEVICES=1 vllm serve Qwen3-Embedding-8B --task embed &\n"
                               "CUDA_VISIBLE_DEVICES=0 vllm serve chat &\n" + KEEPALIVE)
    monkeypatch.setattr(sbatch_lint, "repo_root", lambda: root)

    command = "ssh della 'cd ~/src/reason_reckon/experiments/42-x && sbatch scripts/slurm/j.sbatch'"
    resolved, notes = sbatch_lint.resolve_command_scripts(command)
    assert resolved == [script] and not notes


def test_the_hook_does_not_lint_the_linting(monkeypatch, capsys):
    """`sbatch-lint legacy.sbatch` names a script, but running the lint is no submission."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "just preflight experiments/12-baselines/x.sbatch"}})))
    assert sbatch_lint.run_hook() == 0
    assert capsys.readouterr().out == ""


def test_python3_is_python(monkeypatch, capsys):
    """A `\\bpython\\b` pre-gate would miss python3 -- the usual verl invocation."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "python3 train.py actor.engine.model_dtype=bf16"}})))
    assert sbatch_lint.run_hook() == 0
    assert "VERL_ENGINE_OVERRIDE" in capsys.readouterr().out


def test_hook_denies_on_an_error_and_is_silent_on_a_clean_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin",
                        io.StringIO(json.dumps({"tool_input": {"command": "sbatch clean.sbatch"}})))
    assert sbatch_lint.run_hook() == 0
    assert capsys.readouterr().out == ""  # nothing found, nothing said

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "python train.py actor.engine.model_dtype=bf16"}})))
    assert sbatch_lint.run_hook() == 0
    decision = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "actor.fsdp_config" in decision["permissionDecisionReason"]


def test_an_assignment_hidden_in_a_trailing_comment_is_an_error():
    text = textwrap.dedent("""\
        #!/bin/bash
        set -e
        PROMPT_LEN="${PROMPT_LEN:-4096}"; RESP_LEN="${RESP_LEN:-40960}";     # one round is long PPO_MAX_TOKEN_LEN="${PPO_MAX_TOKEN_LEN:-1}"
        echo ok
        """)
    rules = {f.rule for f in sbatch_lint.check_text(text, "x.sbatch")}
    assert "ASSIGNMENT_IN_COMMENT" in rules


def test_a_plain_trailing_comment_is_not_an_error():
    text = 'RESP_LEN="${RESP_LEN:-40960}"     # one round of observations\nX=1 # the answer\n'
    assert not [f for f in sbatch_lint.check_text(text, "x.sbatch") if f.rule == "ASSIGNMENT_IN_COMMENT"]


def test_serve_target_below_the_registry_floor_is_an_error(monkeypatch):
    monkeypatch.setattr(sbatch_lint, "registry_targets", lambda: {"qwen3-embed-8b": {"kind": "embed", "min_fraction": 0.30}})
    lines = [(3, 'serve_target qwen3-embed-8b --port 8100 --gpu 3 --fraction 0.12')]
    rules = {f.rule for f in sbatch_lint._check_registry(lines, "x.sbatch")}
    assert "MIN_FRACTION" in rules
    servers = sbatch_lint.parse_servers(lines)
    assert servers and servers[0].kind == "embed" and servers[0].cards == frozenset({3}) and servers[0].fraction == 0.12


def test_serve_target_at_or_above_the_floor_passes_and_raw_serve_is_advised(monkeypatch):
    monkeypatch.setattr(sbatch_lint, "registry_targets", lambda: {"qwen3.5-9b": {"kind": "chat", "min_fraction": 0.45}})
    lines = [(3, 'serve_target qwen3.5-9b --port 8106 --gpu 3 --fraction 0.55'), (4, 'vllm serve /m --port 1 --gpu-memory-utilization 0.5')]
    rules = [f.rule for f in sbatch_lint._check_registry(lines, "x.sbatch")]
    assert rules == ["RAW_VLLM_SERVE"]


# ------------------------------------------------------------------- the port picked early


def test_a_port_chosen_before_another_servers_launch_is_flagged():
    """2026-09-29: the retrieval port, free at job start, was taken by a sibling job while the vLLM servers came up."""
    assert "PORT_PICKED_EARLY" in rules(HEADER + """
        read -r P_CHAT P_RAG < <(python3 -c 'print(8000, 8009)')
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --port $P_CHAT --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:$P_CHAT chat 30
        python serve_news_rag.py --port $P_RAG &
        wait200 http://127.0.0.1:$P_RAG/health rag 90
        """ + KEEPALIVE)


def test_a_port_repicked_before_its_launch_passes():
    assert "PORT_PICKED_EARLY" not in rules(HEADER + """
        read -r P_CHAT P_RAG < <(python3 -c 'print(8000, 8009)')
        CUDA_VISIBLE_DEVICES=0,1 vllm serve chat --port $P_CHAT --gpu-memory-utilization 0.82 &
        wait_for_server http://localhost:$P_CHAT chat 30
        P_RAG=$(python3 -c 'print(8010)')
        python serve_news_rag.py --port $P_RAG &
        wait200 http://127.0.0.1:$P_RAG/health rag 90
        """ + KEEPALIVE)
