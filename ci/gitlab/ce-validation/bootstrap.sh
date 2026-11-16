#!/usr/bin/env bash
# Creates an admin token, registers the runner (new registration flow), and
# creates the demo project with a Reporter project access token stored as the
# environment-scoped CI/CD variable PERFGATE_GITLAB_TOKEN.
#
#   STATE=/path/outside/the/repo ./bootstrap.sh
#
# Writes the tokens and the project id to $STATE (default: a temporary directory).
set -euo pipefail

STATE="${STATE:-${TMPDIR:-/tmp}/perfgate-ce-state}"
HTTP_PORT="${HTTP_PORT:-8929}"
NETWORK="${NETWORK:-pgce}"
PROJECT="${PROJECT:-perfgate-demo}"
JOB_IMAGE="${JOB_IMAGE:-alpine:3.22}"
API="http://127.0.0.1:${HTTP_PORT}/api/v4"
mkdir -p "$STATE"
chmod 700 "$STATE"

if [ ! -s "$STATE/root-token" ]; then
  docker exec pgce-gitlab gitlab-rails runner "
    u = User.find_by_username('root')
    t = u.personal_access_tokens.create!(name: 'ce-validation', scopes: %w[api admin_mode read_repository write_repository], expires_at: 7.days.from_now)
    puts t.token
  " | tail -1 > "$STATE/root-token"
fi
ROOT="$(cat "$STATE/root-token")"
h=(-H "PRIVATE-TOKEN: $ROOT")
json() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

# Runner: instance runner, docker executor, job containers on $NETWORK so they
# reach GitLab as http://gitlab-ce; local images are used without pulling.
if ! docker exec pgce-runner test -s /etc/gitlab-runner/config.toml; then
  runner_token=$(curl -fsS "${h[@]}" -X POST "$API/user/runners" \
    -d runner_type=instance_type -d run_untagged=true -d description=ce-validation-docker | json "['token']")
  docker exec pgce-runner gitlab-runner register --non-interactive \
    --url http://gitlab-ce --token "$runner_token" \
    --executor docker --docker-image "$JOB_IMAGE" \
    --docker-network-mode "$NETWORK" --docker-pull-policy if-not-present \
    --docker-shm-size 2147483648
fi

pid=$(curl -fsS "${h[@]}" "$API/projects?search=$PROJECT" | json "[0]['id']" 2>/dev/null || true)
if [ -z "$pid" ]; then
  pid=$(curl -fsS "${h[@]}" -X POST "$API/projects" -d name="$PROJECT" -d visibility=private \
    -d initialize_with_readme=false | json "['id']")
fi
echo "$pid" > "$STATE/project-id"

if [ ! -s "$STATE/note-token" ]; then
  curl -fsS "${h[@]}" -X POST "$API/projects/$pid/access_tokens" \
    -H 'content-type: application/json' \
    -d "{\"name\":\"perfgate-comment\",\"scopes\":[\"api\"],\"access_level\":20,\"expires_at\":\"$(date -v+7d +%F 2>/dev/null || date -d +7days +%F)\"}" \
    | json "['token']" > "$STATE/note-token"
fi
curl -fsS "${h[@]}" -X DELETE "$API/projects/$pid/variables/PERFGATE_GITLAB_TOKEN?filter%5Benvironment_scope%5D=perfgate-comment" >/dev/null 2>&1 || true
curl -fsS "${h[@]}" -X POST "$API/projects/$pid/variables" \
  -d key=PERFGATE_GITLAB_TOKEN --data-urlencode value="$(cat "$STATE/note-token")" \
  -d masked=true -d environment_scope=perfgate-comment >/dev/null
echo "project $PROJECT id=$pid; runner registered; PERFGATE_GITLAB_TOKEN set (scope perfgate-comment)"
