#!/usr/bin/env bash
set -Eeuo pipefail

root=/home/ai/projects/ssp-tulu-repro
base_python=/home/ai/limit-of-RLVR/.venv/bin/python
private_python=${root}/.venv/bin/python
base_site=/home/ai/limit-of-RLVR/.venv/lib/python3.10/site-packages

mkdir -p "${root}/artifacts" "${root}/logs" "${root}/status"
if [[ ! -x "${private_python}" ]]; then
  "${base_python}" -m venv "${root}/.venv"
fi
private_site=$("${private_python}" -c 'import site; print(site.getsitepackages()[0])')
printf '%s\n' "${base_site}" > "${private_site}/limit_of_rlvr_runtime.pth"
"${private_python}" -m pip install \
  --disable-pip-version-check \
  --no-deps \
  -r "${root}/requirements-remote.txt"

export PYTHONPATH="${root}"
"${private_python}" -m pip freeze | sort > "${root}/artifacts/environment-freeze.txt"
"${private_python}" - <<'PY'
import accelerate
import bitsandbytes
import peft
import torch
import transformers
print({
    "torch": torch.__version__,
    "transformers": transformers.__version__,
    "peft": peft.__version__,
    "accelerate": accelerate.__version__,
    "bitsandbytes": bitsandbytes.__version__,
    "cuda": torch.version.cuda,
})
PY
