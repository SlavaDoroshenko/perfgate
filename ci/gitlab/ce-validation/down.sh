#!/usr/bin/env bash
# Removes the containers, volumes and network created by up.sh, and the job
# containers/volumes the runner left behind.
set -uo pipefail
NETWORK="${NETWORK:-pgce}"
docker rm -f pgce-runner pgce-gitlab >/dev/null 2>&1
for c in $(docker ps -aq --filter "network=$NETWORK"); do docker rm -f "$c" >/dev/null; done
for c in $(docker ps -aq --filter "label=com.gitlab.gitlab-runner.type"); do docker rm -f "$c" >/dev/null; done
for v in $(docker volume ls -q --filter "label=com.gitlab.gitlab-runner.type"); do docker volume rm "$v" >/dev/null; done
docker volume rm pgce-config pgce-logs pgce-data pgce-runner >/dev/null 2>&1
docker network rm "$NETWORK" >/dev/null 2>&1
docker ps -a --filter "name=pgce-" --format '{{.Names}}'
echo "removed GitLab CE validation containers, volumes and network $NETWORK"
