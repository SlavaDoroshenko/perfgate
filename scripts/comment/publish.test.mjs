import test from 'node:test';
import assert from 'node:assert/strict';
import { artifactLinks, findPullRequest, upsertGithubComment, upsertGitlabNote } from './publish.mjs';

const SHA = 'c'.repeat(40);
const API = 'https://api.github.test';

/** Fake fetch: routes are [method, url-prefix, response-body]; records every call. */
function fakeFetch(routes) {
  const calls = [];
  const impl = async (url, init) => {
    calls.push({ method: init.method, url, body: init.body ? JSON.parse(init.body) : undefined, headers: init.headers });
    const route = routes.find(([method, prefix]) => method === init.method && url.startsWith(prefix));
    if (!route) return { ok: false, status: 404, text: async () => 'no route', json: async () => ({}) };
    return { ok: true, status: 200, json: async () => route[2], text: async () => '' };
  };
  return { impl, calls };
}

const run = (extra = {}) => ({ id: 7, head_sha: SHA, head_branch: 'feature', event: 'pull_request',
  head_repository: { owner: { login: 'contributor' } }, pull_requests: [], ...extra });

test('same-repository PR comes from the event payload and is checked against the head', async () => {
  const { impl, calls } = fakeFetch([['GET', `${API}/repos/o/r/pulls/5`, { head: { sha: SHA }, state: 'open' }]]);
  const pr = await findPullRequest({ api: API, repo: 'o/r', token: 't', fetchImpl: impl,
    run: run({ pull_requests: [{ number: 5, head: { sha: SHA } }, { number: 6, head: { sha: 'd'.repeat(40) } }] }) });
  assert.deepEqual(pr, { number: 5, reason: null });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].headers.authorization, 'Bearer t');
});

test('fork PR is found by head owner and branch', async () => {
  const { impl, calls } = fakeFetch([
    ['GET', `${API}/repos/o/r/pulls?`, [{ number: 8, head: { sha: SHA } }, { number: 9, head: { sha: 'e'.repeat(40) } }]],
    ['GET', `${API}/repos/o/r/pulls/8`, { head: { sha: SHA }, state: 'open' }],
  ]);
  const pr = await findPullRequest({ api: API, repo: 'o/r', token: 't', fetchImpl: impl, run: run() });
  assert.equal(pr.number, 8);
  assert.match(calls[0].url, /head=contributor%3Afeature/);
});

test('stale or closed pull requests are not commented', async () => {
  const stale = fakeFetch([['GET', `${API}/repos/o/r/pulls/5`, { head: { sha: 'f'.repeat(40) }, state: 'open' }]]);
  const result = await findPullRequest({ api: API, repo: 'o/r', token: 't', fetchImpl: stale.impl,
    run: run({ pull_requests: [{ number: 5, head: { sha: SHA } }] }) });
  assert.equal(result.number, null);
  assert.match(result.reason, /newer commits/);
  const closed = fakeFetch([['GET', `${API}/repos/o/r/pulls/5`, { head: { sha: SHA }, state: 'closed' }]]);
  assert.match((await findPullRequest({ api: API, repo: 'o/r', token: 't', fetchImpl: closed.impl,
    run: run({ pull_requests: [{ number: 5, head: { sha: SHA } }] }) })).reason, /closed/);
  const none = fakeFetch([['GET', `${API}/repos/o/r/pulls?`, []]]);
  assert.equal((await findPullRequest({ api: API, repo: 'o/r', token: 't', fetchImpl: none.impl, run: run() })).number, null);
  await assert.rejects(findPullRequest({ api: API, repo: 'o/r', token: 't', fetchImpl: none.impl, run: run({ head_sha: 'x' }) }));
});

test('existing bot comment with the marker is updated; others are ignored', async () => {
  const marker = '<!-- perfgate-comment:default -->';
  const { impl, calls } = fakeFetch([
    ['GET', `${API}/repos/o/r/issues/5/comments`, [
      { id: 1, user: { login: 'mallory' }, body: `${marker}\nfake` },
      { id: 2, user: { login: 'github-actions[bot]' }, body: 'unrelated' },
      { id: 3, user: { login: 'github-actions[bot]' }, body: `${marker}\nold` },
    ]],
    ['PATCH', `${API}/repos/o/r/issues/comments/3`, { id: 3 }],
  ]);
  const result = await upsertGithubComment({ api: API, repo: 'o/r', number: 5, body: `${marker}\nnew`, marker, token: 't', fetchImpl: impl });
  assert.deepEqual(result, { action: 'updated', id: 3 });
  assert.deepEqual(calls.at(-1).body, { body: `${marker}\nnew` });
});

test('a new comment is created when no sticky comment exists', async () => {
  const marker = '<!-- perfgate-comment:web -->';
  const { impl, calls } = fakeFetch([
    ['GET', `${API}/repos/o/r/issues/5/comments`, [{ id: 3, user: { login: 'github-actions[bot]' }, body: '<!-- perfgate-comment:other -->' }]],
    ['POST', `${API}/repos/o/r/issues/5/comments`, { id: 11 }],
  ]);
  assert.deepEqual(await upsertGithubComment({ api: API, repo: 'o/r', number: 5, body: marker, marker, token: 't', fetchImpl: impl }),
    { action: 'created', id: 11 });
  assert.equal(calls.at(-1).method, 'POST');
});

test('API errors are reported with status', async () => {
  const { impl } = fakeFetch([]);
  await assert.rejects(upsertGithubComment({ api: API, repo: 'o/r', number: 5, body: 'x', marker: 'x', token: 't', fetchImpl: impl }), /HTTP 404/);
});

test('artifact names map to download pages', async () => {
  const { impl } = fakeFetch([['GET', `${API}/repos/o/r/actions/runs/7/artifacts`, { artifacts: [{ id: 42, name: 'perfgate-1' }] }]]);
  assert.deepEqual(await artifactLinks({ api: API, server: 'https://github.test', repo: 'o/r', runId: 7, token: 't', fetchImpl: impl }),
    { 'perfgate-1': 'https://github.test/o/r/actions/runs/7/artifacts/42' });
});

test('GitLab note by the token user is updated, otherwise created', async () => {
  const GL = 'https://gitlab.test/api/v4';
  const marker = '<!-- perfgate-comment:default -->';
  const notes = `${GL}/projects/group%2Fapp/merge_requests/3/notes`;
  const update = fakeFetch([
    ['GET', `${GL}/user`, { id: 99 }],
    ['GET', `${notes}?`, [{ id: 1, author: { id: 5 }, body: marker }, { id: 2, author: { id: 99 }, system: false, body: `${marker} old` }]],
    ['PUT', `${notes}/2`, { id: 2 }],
  ]);
  assert.deepEqual(await upsertGitlabNote({ api: GL, projectId: 'group/app', mrIid: '3', body: `${marker} new`, marker, token: 'glpat', fetchImpl: update.impl }),
    { action: 'updated', id: 2 });
  assert.equal(update.calls[0].headers['private-token'], 'glpat');
  const create = fakeFetch([['GET', `${GL}/user`, { id: 99 }], ['GET', `${notes}?`, []], ['POST', notes, { id: 4 }]]);
  assert.deepEqual(await upsertGitlabNote({ api: GL, projectId: 'group/app', mrIid: '3', body: marker, marker, token: 'glpat', fetchImpl: create.impl }),
    { action: 'created', id: 4 });
});
