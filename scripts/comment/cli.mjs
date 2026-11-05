#!/usr/bin/env node
// perfgate pull/merge request comment.
//
//   node scripts/comment/cli.mjs render --reports DIR [--key K] [--run-url URL] [--sha SHA] [--out FILE]
//   node scripts/comment/cli.mjs github --reports DIR [--key K] [--dry-run]
//   node scripts/comment/cli.mjs gitlab --reports DIR [--key K] [--dry-run]
//
// `github` runs in a trusted workflow_run job: the PR and run come from the event
// payload, never from the downloaded artifact. `gitlab` runs in a merge request
// pipeline and reads predefined CI variables plus PERFGATE_GITLAB_TOKEN.
// Exit status is 0 whenever the comment was rendered (and posted), regardless of
// the verdict: the measuring job carries the pass/fail status.
import { appendFile, readFile, writeFile } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { loadReports, marker, renderComment } from './render.mjs';
import { artifactLinks, findPullRequest, upsertGithubComment, upsertGitlabNote } from './publish.mjs';

const log = message => process.stderr.write(`${message}\n`);

async function output(status) {
  if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT, `status=${status}\n`);
}

function env(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

async function main() {
  const [command, ...argv] = process.argv.slice(2);
  const { values } = parseArgs({ args: argv, strict: true, options: {
    reports: { type: 'string' }, key: { type: 'string', default: 'default' },
    'run-url': { type: 'string' }, sha: { type: 'string' }, out: { type: 'string' },
    'dry-run': { type: 'boolean', default: false }, author: { type: 'string', default: 'github-actions[bot]' },
  } });
  if (!['render', 'github', 'gitlab'].includes(command) || !values.reports) {
    throw new Error('usage: cli.mjs render|github|gitlab --reports <directory> [options]');
  }
  const reports = await loadReports(values.reports);
  const key = values.key;

  if (command === 'render') {
    const { status, body } = renderComment(reports, { key, runUrl: values['run-url'], sha: values.sha });
    if (values.out) await writeFile(values.out, body); else process.stdout.write(body);
    log(`perfgate comment: ${status}, ${reports.length} report(s)`);
    return;
  }

  if (command === 'github') {
    const event = JSON.parse(await readFile(env('GITHUB_EVENT_PATH'), 'utf8'));
    const run = event.workflow_run;
    if (!run) throw new Error('github mode must run on a workflow_run event');
    if (run.event !== 'pull_request') { log(`skipped: measuring run was triggered by ${run.event}`); return; }
    if (['cancelled', 'skipped'].includes(run.conclusion)) { log(`skipped: measuring run ${run.conclusion}`); return; }
    const api = process.env.GITHUB_API_URL ?? 'https://api.github.com';
    const server = process.env.GITHUB_SERVER_URL ?? 'https://github.com';
    const repo = env('GITHUB_REPOSITORY');
    const token = env('GITHUB_TOKEN');
    const pr = await findPullRequest({ api, repo, run, token });
    let links = {};
    try { links = await artifactLinks({ api, server, repo, runId: run.id, token }); }
    catch (error) { log(`artifact links unavailable: ${error.message}`); }
    const { status, body } = renderComment(reports, { key, runUrl: run.html_url, sha: run.head_sha, artifactLinks: links });
    if (values.out) await writeFile(values.out, body);
    await output(status);
    if (!pr.number) { log(`not commenting: ${pr.reason}`); return; }
    if (values['dry-run']) { process.stdout.write(body); log(`dry run: would comment on #${pr.number} (${status})`); return; }
    const result = await upsertGithubComment({ api, repo, number: pr.number, body, marker: marker(key), token, author: values.author });
    log(`${result.action} comment ${result.id} on #${pr.number}: ${status}`);
    return;
  }

  const runUrl = process.env.PERFGATE_RUN_URL ?? process.env.CI_PIPELINE_URL;
  const links = {};
  if (process.env.PERFGATE_ARTIFACT_URL) for (const report of reports) if (report.artifact) links[report.artifact] = process.env.PERFGATE_ARTIFACT_URL;
  const { status, body } = renderComment(reports, { key, runUrl, sha: process.env.CI_COMMIT_SHA, artifactLinks: links });
  if (values.out) await writeFile(values.out, body);
  const mrIid = process.env.CI_MERGE_REQUEST_IID;
  if (!mrIid) { log('not commenting: CI_MERGE_REQUEST_IID is not set (not a merge request pipeline)'); return; }
  if (values['dry-run']) { process.stdout.write(body); log(`dry run: would comment on !${mrIid} (${status})`); return; }
  const result = await upsertGitlabNote({
    api: env('CI_API_V4_URL'), projectId: env('CI_PROJECT_ID'), mrIid, body, marker: marker(key),
    token: env('PERFGATE_GITLAB_TOKEN'),
  });
  log(`${result.action} note ${result.id} on !${mrIid}: ${status}`);
}

main().catch(error => { log(`perfgate comment failed: ${error.message}`); process.exitCode = 1; });
