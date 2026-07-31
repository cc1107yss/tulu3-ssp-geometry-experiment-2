#!/usr/bin/env bash
set -Eeuo pipefail

experiment_root=${EXPERIMENT_ROOT:-/home/ai/projects/ssp-tulu-repro}
export_root=${EXPORT_ROOT:-/home/ai/projects/ssp-tulu-github-export}
repo_ssh=${REPO_SSH_URL:-git@github.com:cc1107yss/tulu3-ssp-geometry-experiment-2.git}
deploy_key=${GITHUB_DEPLOY_KEY:-${export_root}/credentials/deploy_key}
known_hosts=${GITHUB_KNOWN_HOSTS:-${export_root}/credentials/known_hosts}

if [[ ! -f ${deploy_key} || ! -f ${known_hosts} ]]; then
  echo "deploy key or verified known_hosts is missing" >&2
  exit 2
fi
if [[ ! -x ${export_root}/bin/git-lfs ]]; then
  echo "verified user-local git-lfs is missing at ${export_root}/bin/git-lfs" >&2
  exit 2
fi

mkdir -p "${export_root}" "${HOME}/.config/systemd/user"
install -m 0755 ops/github-publisher/git-ssh.sh "${export_root}/git-ssh.sh"
export GIT_SSH="${export_root}/git-ssh.sh"
export GITHUB_DEPLOY_KEY=${deploy_key}
export GITHUB_KNOWN_HOSTS=${known_hosts}
export PATH="${export_root}/bin:${PATH}"

if [[ ! -d ${export_root}/main/.git ]]; then
  git clone --branch main --single-branch "${repo_ssh}" "${export_root}/main"
fi
if [[ ! -d ${export_root}/run-status/.git ]]; then
  git clone --branch run-status --single-branch "${repo_ssh}" "${export_root}/run-status"
fi

for clone in "${export_root}/main" "${export_root}/run-status"; do
  git -C "${clone}" config user.name "experiment-2-status-bot"
  git -C "${clone}" config user.email "cc1107yss@users.noreply.github.com"
done
git -C "${export_root}/main" lfs install --local

env_file=${export_root}/publisher.env
printf '%s\n' \
  "EXPERIMENT_ROOT=${experiment_root}" \
  "EXPORT_ROOT=${export_root}" \
  "MAIN_REPO=${export_root}/main" \
  "STATUS_REPO=${export_root}/run-status" \
  "GITHUB_DEPLOY_KEY=${deploy_key}" \
  "GITHUB_KNOWN_HOSTS=${known_hosts}" \
  "GIT_SSH=${export_root}/git-ssh.sh" \
  "TMUX_BINARY=${HOME}/.local/opt/tmux-3.0a/usr/bin/tmux" \
  "PATH=${export_root}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  "DISABLE_TIMER_ON_COMPLETE=1" >"${env_file}"
chmod 0600 "${env_file}"

install -m 0644 \
  "${export_root}/main/ops/github-publisher/systemd/ssp-tulu-github-publisher.service" \
  "${HOME}/.config/systemd/user/ssp-tulu-github-publisher.service"
install -m 0644 \
  "${export_root}/main/ops/github-publisher/systemd/ssp-tulu-github-publisher.timer" \
  "${HOME}/.config/systemd/user/ssp-tulu-github-publisher.timer"

systemctl --user daemon-reload
systemctl --user enable --now ssp-tulu-github-publisher.timer
systemctl --user start ssp-tulu-github-publisher.service
systemctl --user status --no-pager ssp-tulu-github-publisher.timer
