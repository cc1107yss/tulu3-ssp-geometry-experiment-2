#!/usr/bin/env bash
set -Eeuo pipefail

export SSP_TULU_ROOT=/home/ai/projects/ssp-tulu-repro
export PATH="/home/ai/.local/opt/tmux-3.0a/usr/bin:${PATH}"
source "${SSP_TULU_ROOT}/.venv/bin/activate"
export PYTHONPATH="${SSP_TULU_ROOT}"
export TOKENIZERS_PARALLELISM=false
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export CUDA_VISIBLE_DEVICES=0
cd "${SSP_TULU_ROOT}"
