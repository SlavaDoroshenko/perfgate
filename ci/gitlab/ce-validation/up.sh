#!/usr/bin/env bash
# Starts a disposable GitLab CE instance and a Docker-executor runner on a
# private Docker network. Ports are bound to 127.0.0.1 only.
#
#   GITLAB_VERSION=19.5.5-ce.0 RUNNER_VERSION=alpine-v19.5.3 ./up.sh
#
# Data lives in named volumes (pgce-*); down.sh removes them.
set -euo pipefail

GITLAB_VERSION="${GITLAB_VERSION:-19.5.5-ce.0}"
RUNNER_VERSION="${RUNNER_VERSION:-alpine-v19.5.3}"
NETWORK="${NETWORK:-pgce}"
HTTP_PORT="${HTTP_PORT:-8929}"
GITLAB_MEMORY="${GITLAB_MEMORY:-5g}"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null

# Memory-constrained Omnibus settings: single-mode Puma, fewer Sidekiq threads,
# no monitoring, registry, Pages, KAS or Mattermost.
read -r -d '' OMNIBUS <<'RUBY' || true
external_url 'http://gitlab-ce'
gitlab_rails['gitlab_shell_ssh_port'] = 2222
gitlab_rails['env'] = { 'MALLOC_CONF' => 'dirty_decay_ms:1000,muzzy_decay_ms:1000' }
puma['worker_processes'] = 0
sidekiq['concurrency'] = 10
prometheus_monitoring['enable'] = false
alertmanager['enable'] = false
gitlab_exporter['enable'] = false
registry['enable'] = false
gitlab_kas['enable'] = false
gitlab_pages['enable'] = false
mattermost['enable'] = false
letsencrypt['enable'] = false
gitaly['env'] = { 'MALLOC_CONF' => 'dirty_decay_ms:1000,muzzy_decay_ms:1000', 'GITALY_COMMAND_SPAWN_MAX_PARALLEL' => '2' }
gitlab_rails['usage_ping_enabled'] = false
RUBY

docker run -d --name pgce-gitlab --hostname gitlab-ce \
  --network "$NETWORK" --network-alias gitlab-ce \
  -p "127.0.0.1:${HTTP_PORT}:80" \
  --memory "$GITLAB_MEMORY" --shm-size 256m \
  -e GITLAB_OMNIBUS_CONFIG="$OMNIBUS" \
  -v pgce-config:/etc/gitlab -v pgce-logs:/var/log/gitlab -v pgce-data:/var/opt/gitlab \
  "gitlab/gitlab-ce:${GITLAB_VERSION}" >/dev/null

# The runner talks to the host's Docker daemon; job containers join $NETWORK.
docker run -d --name pgce-runner --network "$NETWORK" \
  --memory 256m \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v pgce-runner:/etc/gitlab-runner \
  "gitlab/gitlab-runner:${RUNNER_VERSION}" >/dev/null

echo "waiting for GitLab on http://127.0.0.1:${HTTP_PORT} ..."
start=$(date +%s)
until [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${HTTP_PORT}/users/sign_in")" = 200 ]; do
  sleep 10
  if [ $(( $(date +%s) - start )) -gt 1200 ]; then echo "GitLab did not become ready" >&2; exit 1; fi
done
echo "GitLab ready after $(( $(date +%s) - start )) s"
