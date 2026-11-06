// Creates or updates one sticky perfgate comment through the GitHub or GitLab REST API.
// `fetchImpl` is injectable so the request sequence can be tested without a network.

async function request(fetchImpl, url, { method = 'GET', headers, body } = {}) {
  const response = await fetchImpl(url, {
    method, headers: { ...headers, ...(body ? { 'content-type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`${method} ${url.replace(/\?.*/, '')} failed: HTTP ${response.status} ${text.slice(0, 200)}`);
  }
  return response.status === 204 ? null : response.json();
}

function githubHeaders(token) {
  return { authorization: `Bearer ${token}`, accept: 'application/vnd.github+json', 'x-github-api-version': '2022-11-28' };
}

/**
 * Finds the open pull request measured by a workflow_run event without trusting
 * artifact contents. Returns null when the run is stale (the PR head moved on).
 */
export async function findPullRequest({ api, repo, run, token, fetchImpl = fetch }) {
  const headers = githubHeaders(token);
  const sha = run.head_sha;
  if (!/^[0-9a-f]{40}$/.test(sha ?? '')) throw new Error('workflow_run.head_sha missing');
  let candidates = (run.pull_requests ?? []).filter(pr => pr.head?.sha === sha).map(pr => pr.number);
  if (!candidates.length && run.head_repository?.owner?.login && run.head_branch) {
    // Fork pull requests are not listed in workflow_run.pull_requests.
    const head = encodeURIComponent(`${run.head_repository.owner.login}:${run.head_branch}`);
    const pulls = await request(fetchImpl, `${api}/repos/${repo}/pulls?state=open&head=${head}&per_page=100`, { headers });
    candidates = pulls.filter(pr => pr.head?.sha === sha).map(pr => pr.number);
  }
  if (candidates.length !== 1) return { number: null, reason: candidates.length ? 'several pull requests share this commit' : 'no open pull request for this commit' };
  const number = candidates[0];
  const pull = await request(fetchImpl, `${api}/repos/${repo}/pulls/${number}`, { headers });
  if (pull.head?.sha !== sha) return { number: null, reason: `pull request #${number} has newer commits; a later run will comment` };
  if (pull.state !== 'open') return { number: null, reason: `pull request #${number} is ${pull.state}` };
  return { number, reason: null };
}

/** Maps artifact names of a run to their download pages. */
export async function artifactLinks({ api, server, repo, runId, token, fetchImpl = fetch }) {
  const data = await request(fetchImpl, `${api}/repos/${repo}/actions/runs/${runId}/artifacts?per_page=100`, { headers: githubHeaders(token) });
  return Object.fromEntries((data.artifacts ?? []).map(a => [a.name, `${server}/${repo}/actions/runs/${runId}/artifacts/${a.id}`]));
}

export async function upsertGithubComment({ api, repo, number, body, marker, token, author = 'github-actions[bot]', fetchImpl = fetch }) {
  const headers = githubHeaders(token);
  let existing = null;
  for (let page = 1; page <= 30 && !existing; page++) {
    const comments = await request(fetchImpl, `${api}/repos/${repo}/issues/${number}/comments?per_page=100&page=${page}`, { headers });
    existing = comments.find(c => c.user?.login === author && typeof c.body === 'string' && c.body.startsWith(marker)) ?? null;
    if (comments.length < 100) break;
  }
  if (existing) {
    await request(fetchImpl, `${api}/repos/${repo}/issues/comments/${existing.id}`, { method: 'PATCH', headers, body: { body } });
    return { action: 'updated', id: existing.id };
  }
  const created = await request(fetchImpl, `${api}/repos/${repo}/issues/${number}/comments`, { method: 'POST', headers, body: { body } });
  return { action: 'created', id: created.id };
}

export async function upsertGitlabNote({ api, projectId, mrIid, body, marker, token, fetchImpl = fetch }) {
  const headers = { 'private-token': token };
  const me = await request(fetchImpl, `${api}/user`, { headers });
  const base = `${api}/projects/${encodeURIComponent(projectId)}/merge_requests/${mrIid}/notes`;
  let existing = null;
  for (let page = 1; page <= 30 && !existing; page++) {
    const notes = await request(fetchImpl, `${base}?per_page=100&page=${page}&sort=asc&order_by=created_at`, { headers });
    existing = notes.find(n => n.author?.id === me.id && !n.system && typeof n.body === 'string' && n.body.startsWith(marker)) ?? null;
    if (notes.length < 100) break;
  }
  if (existing) {
    await request(fetchImpl, `${base}/${existing.id}`, { method: 'PUT', headers, body: { body } });
    return { action: 'updated', id: existing.id };
  }
  const created = await request(fetchImpl, base, { method: 'POST', headers, body: { body } });
  return { action: 'created', id: created.id };
}
