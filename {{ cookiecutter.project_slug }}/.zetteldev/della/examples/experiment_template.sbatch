#!/bin/bash
#SBATCH --job-name=exp-template
# no --account line: della-submit adds the configured one (della_account)
#SBATCH --partition=pli-c
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32      # RULE: 8 cores per GPU (4 GPUs × 8 = 32)
#SBATCH --gres=gpu:4
#SBATCH --mem=120G
#SBATCH --time=03:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

# ============================================================
# EXPERIMENT TEMPLATE - Using Della Shared Library
# ============================================================
# Copy this template and customize the EXPERIMENT CONFIG section.
# The shared library handles all vLLM server management.
# ============================================================

set -e

# Load the shared library first: it sets $DELLA_CACHE, $DELLA_SCRATCH_REPO and the venv paths from zetteldev.config
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$REPO_ROOT/.zetteldev/della/lib/della.sh"

# === EXPERIMENT CONFIG (customize this section) ===
EXPERIMENT_NAME="My Experiment"
WORK_DIR="$REPO_ROOT/experiments/XX-my-experiment"
WORKER_SCRIPT="python run_experiment.py"
NUM_WORKERS=4

# Model config
QWEN_MODEL="$DELLA_CACHE/Qwen3-Next-80B-A3B-Instruct"
EMBED_MODEL="$DELLA_CACHE/Llama-3.1-8B-Instruct"

# GPU allocation: the chat model takes every card; the embedder is colocated on card 0
QWEN_GPUS="0,1,2,3"
QWEN_TP=4

# === END EXPERIMENT CONFIG ===

cd "$WORK_DIR"
mkdir -p logs

# Job header
log_job_header "$EXPERIMENT_NAME"
echo "Args: $@"

# Setup and launch servers
della_vllm_setup

log_section "Launching vLLM servers"
launch_vllm_server "$QWEN_MODEL" "$QWEN_GPUS" "$QWEN_TP" "$VLLM_PORT"
wait_for_server "http://localhost:$VLLM_PORT" "Qwen" 30
# the embedder shares the chat model's rank-0 card at a small fraction: never a card of its own (the idle fuse, see della.md)
EMBED_GPU=0 launch_colocated_embedder "$EMBED_MODEL" "$EMBED_PORT" "logs/embed_${SLURM_JOB_ID}.log"
wait_for_server "http://localhost:$EMBED_PORT" "Embedding" 20

# Switch to experiment environment
log_section "Running experiment"
della_experiment_env "$WORK_DIR"
export OPENAI_API_BASE="http://localhost:$VLLM_PORT/v1"

# Parse --game-ids from args
GAME_IDS=""
OTHER_ARGS=""
for arg in "$@"; do
    if [[ "$arg" == --game-ids=* ]]; then
        GAME_IDS="${arg#--game-ids=}"
    else
        OTHER_ARGS="$OTHER_ARGS $arg"
    fi
done

# Run workers
run_parallel_workers "$NUM_WORKERS" "$WORKER_SCRIPT" "--game-ids" "$GAME_IDS" \
    --embedding-api-base "http://localhost:$EMBED_PORT/v1" \
    --embedding-model "$EMBED_MODEL" \
    $OTHER_ARGS

log_job_footer
