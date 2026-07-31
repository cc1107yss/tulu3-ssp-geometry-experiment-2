#!/usr/bin/env sh
set -eu

deploy_key=${GITHUB_DEPLOY_KEY:-"${HOME}/projects/ssp-tulu-github-export/credentials/deploy_key"}
known_hosts=${GITHUB_KNOWN_HOSTS:-"${HOME}/projects/ssp-tulu-github-export/credentials/known_hosts"}

exec /usr/bin/ssh \
  -i "${deploy_key}" \
  -o IdentitiesOnly=yes \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="${known_hosts}" \
  "$@"
