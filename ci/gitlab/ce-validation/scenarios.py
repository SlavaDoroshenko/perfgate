#!/usr/bin/env python3
"""Runs the GitLab CE validation scenarios against an instance prepared by
up.sh and bootstrap.sh, and asserts their outcomes (standard library only).

  python3 scenarios.py --state DIR --out DIR [--image perfgate:ci] [--runs 20]

Scenarios: a merge request with a 400 ms blocking script (perfgate exit 1, one
regression note), an A/A merge request (exit 0), a new push to the regression
merge request (same note updated), a merge request with an empty net diff
(merge-base fallback), the comment job without a token, a foreign note with the
marker, and masking/scoping of the token variable. Exits 1 if any check fails.
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MARKER = '<!-- perfgate-comment:default -->'
SLOWDOWN = '''    <script>
      // deliberate slowdown: 400 ms of blocking work before the first paint
      (function () { var end = performance.now() + 400; while (performance.now() < end) {} })();
    </script>
  </head>'''
MASKCHECK = '''in-env:
  image: alpine:3.22
  environment: { name: perfgate-comment, action: access }
  variables: { GIT_STRATEGY: none }
  script:
    - echo "token=$PERFGATE_GITLAB_TOKEN"
    - test -n "$PERFGATE_GITLAB_TOKEN"
out-of-env:
  image: alpine:3.22
  variables: { GIT_STRATEGY: none }
  script:
    - test -z "${PERFGATE_GITLAB_TOKEN:-}" && echo "absent outside the environment"
'''
ACTIVE = {'created', 'pending', 'running', 'waiting_for_resource', 'preparing', 'scheduled'}


class GitLab:
    def __init__(self, api, token, pid):
        self.api, self.token, self.pid = api, token, pid

    def call(self, method, path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.api + path, data=data, method=method,
                                     headers={'PRIVATE-TOKEN': self.token, 'content-type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode()
        return text if raw else (json.loads(text) if text else None)

    def p(self, path):
        return f'/projects/{self.pid}{path}'

    def tree(self, ref):
        try:
            items = self.call('GET', self.p(f'/repository/tree?recursive=true&per_page=100&ref={urllib.parse.quote(ref)}'))
        except urllib.error.HTTPError:
            return set()
        return {i['path'] for i in items if i['type'] == 'blob'}

    def commit(self, branch, message, files, start=None):
        existing = self.tree(branch) or (self.tree(start) if start else set())
        actions = [{'action': 'update' if path in existing else 'create', 'file_path': path, 'encoding': 'base64',
                    'content': base64.b64encode(content).decode()} for path, content in files.items()]
        body = {'branch': branch, 'commit_message': message, 'actions': actions}
        if start and not self.tree(branch):
            body['start_branch'] = start
        return self.call('POST', self.p('/repository/commits'), body)['id']

    def variable(self, key, value, **extra):
        scope = extra.get('environment_scope', '*')
        try:
            self.call('DELETE', self.p(f'/variables/{key}?filter%5Benvironment_scope%5D={urllib.parse.quote(scope)}'))
        except urllib.error.HTTPError:
            pass
        if value is not None:
            self.call('POST', self.p('/variables'), {'key': key, 'value': value, **extra})

    def pipeline_for(self, sha, source, timeout=300):
        end = time.time() + timeout
        while time.time() < end:
            found = [p for p in self.call('GET', self.p(f'/pipelines?sha={sha}&per_page=20')) if p['source'] == source]
            if found:
                return found[0]['id']
            time.sleep(3)
        raise RuntimeError(f'no {source} pipeline for {sha}')

    def wait_pipeline(self, pid, timeout=5400):
        end = time.time() + timeout
        while time.time() < end:
            p = self.call('GET', self.p(f'/pipelines/{pid}'))
            if p['status'] not in ACTIVE:
                return p
            time.sleep(15)
        raise RuntimeError(f'pipeline {pid} did not finish')

    def wait_job(self, jid, timeout=1800):
        end = time.time() + timeout
        while time.time() < end:
            j = self.call('GET', self.p(f'/jobs/{jid}'))
            if j['status'] not in ACTIVE:
                return j
            time.sleep(3)
        raise RuntimeError(f'job {jid} did not finish')

    def jobs(self, pid):
        latest = {}
        for j in sorted(self.call('GET', self.p(f'/pipelines/{pid}/jobs?per_page=100')), key=lambda j: j['id']):
            latest[j['name']] = j
        return latest

    def trace(self, jid):
        return self.call('GET', self.p(f'/jobs/{jid}/trace'), raw=True)

    def notes(self, iid):
        return self.call('GET', self.p(f'/merge_requests/{iid}/notes?sort=asc&order_by=created_at&per_page=100'))


class Run:
    def __init__(self, gl, out, note_token):
        self.gl, self.out, self.note_token = gl, out, note_token
        self.failures, self.results, self.traces = [], [], []

    def check(self, condition, message):
        print(('ok   ' if condition else 'FAIL ') + message, flush=True)
        if not condition:
            self.failures.append(message)
        return condition

    def save_trace(self, job, label):
        text = self.gl.trace(job['id'])
        (self.out / 'logs' / f'job{job["id"]}-{label}.log').write_text(text)
        self.traces.append(text)
        return text

    def perfgate_notes(self, iid):
        return [n for n in self.gl.notes(iid) if not n['system'] and n['body'].startswith(MARKER)]

    def save_notes(self, iid, label):
        notes = self.gl.notes(iid)
        (self.out / 'notes' / f'mr{iid}-{label}.json').write_text(json.dumps(notes, indent=1))
        for n in notes:
            if not n['system'] and n['body'].startswith(MARKER):
                (self.out / 'notes' / f'mr{iid}-{label}-note{n["id"]}.md').write_text(n['body'])
        return notes

    def mr_pipeline(self, name, iid, sha, expect_exit, headline, bot_id=None, extra=()):
        """Waits for the merge request pipeline of sha and checks the two jobs and the note."""
        pid = self.gl.pipeline_for(sha, 'merge_request_event')
        time.sleep(20)
        same = [p['id'] for p in self.gl.call('GET', self.gl.p(f'/pipelines?sha={sha}&per_page=20')) if p['source'] == 'merge_request_event']
        self.check(len(same) == 1, f'{name}: one merge request pipeline for {sha[:7]} (found {same})')
        pid = max(same)
        pipeline = self.gl.wait_pipeline(pid)
        jobs = self.gl.jobs(pid)
        perfgate, comment = jobs.get('perfgate'), jobs.get('perfgate-comment')
        ok = self.check(perfgate is not None and comment is not None, f'{name}: pipeline {pid} has perfgate and perfgate-comment')
        if not ok:
            return None
        log = self.save_trace(perfgate, f'{name}-perfgate')
        clog = self.save_trace(comment, f'{name}-comment')
        expected_status = 'success' if expect_exit == 0 else 'failed'
        self.check(perfgate['status'] == expected_status, f'{name}: perfgate {perfgate["status"]} (expected {expected_status})')
        if expect_exit:
            self.check(f'Job failed: exit code {expect_exit}' in log, f'{name}: perfgate exit code {expect_exit}')
        self.check('PERFGATE_GITLAB_TOKEN absent in perfgate job' in log, f'{name}: token absent in perfgate job')
        self.check(comment['status'] == 'success', f'{name}: perfgate-comment {comment["status"]}')
        kinds = {a['file_type'] for a in perfgate.get('artifacts', [])}
        self.check({'archive', 'dotenv'} <= kinds, f'{name}: perfgate artifacts uploaded ({", ".join(sorted(kinds))})')
        for text in extra:
            self.check(text in log, f'{name}: perfgate log contains {text!r}')
        notes = self.perfgate_notes(iid)
        self.save_notes(iid, name)
        self.check(len(notes) == 1, f'{name}: exactly one perfgate note on !{iid} (found {len(notes)})')
        note = notes[0] if notes else None
        if note:
            self.check(f'### perfgate: {headline}' in note['body'], f'{name}: note headline "{headline}"')
            self.check('[measurement run](http' in note['body'] and '[report artifact](http' in note['body'],
                       f'{name}: note links to the job and the artifact')
            self.check(f'commit `{sha[:7]}`' in note['body'], f'{name}: note names commit {sha[:7]}')
        self.results.append({'scenario': name, 'mr': iid, 'pipeline': pid, 'pipeline_status': pipeline['status'],
                             'mr_pipelines_for_sha': len(same), 'perfgate_job': perfgate['id'], 'perfgate_status': perfgate['status'],
                             'perfgate_seconds': perfgate.get('duration'), 'comment_seconds': comment.get('duration'),
                             'note_id': note and note['id'], 'note_updated_at': note and note['updated_at'],
                             'comment_log': [l.split(' ', 2)[-1] for l in clog.splitlines() if ' note ' in l][-1:]})
        return {'pipeline': pid, 'perfgate': perfgate, 'comment': comment, 'note': note}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--api', default='http://127.0.0.1:8929/api/v4')
    ap.add_argument('--image', default='perfgate:ce')
    ap.add_argument('--runs', default='20', choices=['10', '20'])
    args = ap.parse_args()
    state, out = Path(args.state), Path(args.out)
    (out / 'logs').mkdir(parents=True, exist_ok=True)
    (out / 'notes').mkdir(parents=True, exist_ok=True)
    gl = GitLab(args.api, (state / 'root-token').read_text().strip(), (state / 'project-id').read_text().strip())
    run = Run(gl, out, (state / 'note-token').read_text().strip())
    started = time.time()

    # Project variables take precedence over the demo's .gitlab-ci.yml values.
    gl.variable('PERFGATE_IMAGE', args.image)
    gl.variable('PERFGATE_RUNS', args.runs)

    public = REPO / 'apps/demo-static/public'
    index = (public / 'index.html').read_bytes()
    assert index.count(b'  </head>') == 1
    slow = index.replace(b'  </head>', SLOWDOWN.encode(), 1)
    files = {f'public/{p.name}': p.read_bytes() for p in sorted(public.iterdir()) if p.is_file()}
    files.update({
        'serve.mjs': (HERE / 'demo/serve.mjs').read_bytes(),
        'perfgate-refs.json': (HERE / 'demo/perfgate-refs.json').read_bytes(),
        '.gitlab-ci.yml': (HERE / 'demo/gitlab-ci.yml').read_bytes(),
        'ci/perfgate.gitlab-ci.yml': (REPO / 'ci/gitlab/perfgate.gitlab-ci.yml').read_bytes(),
    })
    main_sha = gl.commit('main', 'Demo application with perfgate', files)

    def mr(source, title):
        # Let GitLab finish processing the branch push first; otherwise the push
        # refresh can start a second merge request pipeline for the same commit.
        time.sleep(30)
        return gl.call('POST', gl.p('/merge_requests'), {'source_branch': source, 'target_branch': 'main', 'title': title})['iid']

    # 1. Regression merge request.
    sha1 = gl.commit('slowdown', 'Add 400 ms blocking script in head', {'public/index.html': slow}, start='main')
    iid1 = mr('slowdown', 'Deliberate slowdown')
    r1 = run.mr_pipeline('regression', iid1, sha1, 1, 'Performance regression detected')

    # 2. A/A merge request (README only).
    sha2 = gl.commit('aa', 'Add README (no page change)', {'README.md': b'# perfgate demo\n'}, start='main')
    iid2 = mr('aa', 'A/A: README only')
    r2 = run.mr_pipeline('aa', iid2, sha2, 0, 'No regression detected')

    # 3. New push to the regression merge request: slowdown removed, diff not empty.
    sha3 = gl.commit('slowdown', 'Remove the blocking script', {'public/index.html': index, 'NOTES.md': b'Slowdown removed.\n'})
    r3 = run.mr_pipeline('regression-push', iid1, sha3, 0, 'No regression detected')
    if r1 and r3 and r1['note'] and r3['note']:
        run.check(r3['note']['id'] == r1['note']['id'], f'regression-push: same note id {r1["note"]["id"]} updated')
        run.check(r3['note']['updated_at'] != r1['note']['updated_at'], 'regression-push: note updated_at changed')
        run.check('updated note' in run.traces[-1], 'regression-push: comment job reports "updated note"')

    # 4. Empty net diff: change and revert.
    gl.commit('revert', 'Add blocking script', {'public/index.html': slow}, start='main')
    sha4 = gl.commit('revert', 'Revert blocking script', {'public/index.html': index})
    iid4 = mr('revert', 'A/A: change and revert (empty diff)')
    r4 = run.mr_pipeline('empty-diff', iid4, sha4, 0, 'No regression detected',
                         extra=(f'merge request diff base unavailable; using merge-base {main_sha}',))

    # 5. Comment job without the token: renders, does not post.
    if r4 and r4['note']:
        gl.variable('PERFGATE_GITLAB_TOKEN', None, environment_scope='perfgate-comment')
        job = gl.wait_job(gl.call('POST', gl.p(f'/jobs/{r4["comment"]["id"]}/retry'))['id'])
        log = run.save_trace(job, 'no-token-comment')
        run.check(job['status'] == 'success', 'no-token: comment job succeeds')
        run.check('PERFGATE_GITLAB_TOKEN is not available; rendering without posting' in log, 'no-token: rendered without posting')
        after = run.perfgate_notes(iid4)
        run.check(len(after) == 1 and after[0]['updated_at'] == r4['note']['updated_at'], 'no-token: note unchanged')
        gl.variable('PERFGATE_GITLAB_TOKEN', run.note_token, masked=True, environment_scope='perfgate-comment')

    # 6. A note by another user with the same marker is never edited.
    if r2 and r2['note']:
        forged = gl.call('POST', gl.p(f'/merge_requests/{iid2}/notes'), {'body': f'{MARKER}\nforged by root'})
        job = gl.wait_job(gl.call('POST', gl.p(f'/jobs/{r2["comment"]["id"]}/retry'))['id'])
        log = run.save_trace(job, 'foreign-comment')
        notes = {n['id']: n for n in gl.notes(iid2)}
        run.check(notes[forged['id']]['body'].endswith('forged by root'), 'foreign: root note untouched')
        # GitLab keeps updated_at when the body is unchanged, so check the job's own report.
        run.check(f'updated note {r2["note"]["id"]} on !{iid2}' in log, f'foreign: bot note {r2["note"]["id"]} updated')
        run.check(len(run.perfgate_notes(iid2)) == 2, 'foreign: no third marker note created')
        run.save_notes(iid2, 'foreign')

    # 7. Token masked in the environment, absent outside it, and in no job log.
    sha7 = gl.commit('maskcheck', 'Mask check', {'.gitlab-ci.yml': MASKCHECK.encode()}, start='main')
    pid7 = gl.pipeline_for(sha7, 'push')
    gl.wait_pipeline(pid7, timeout=600)
    jobs7 = gl.jobs(pid7)
    run.check('token=[MASKED]' in run.save_trace(jobs7['in-env'], 'mask-in-env'), 'mask: token printed as [MASKED]')
    run.check('absent outside the environment' in run.save_trace(jobs7['out-of-env'], 'mask-out-of-env'), 'mask: absent outside the environment')
    run.check(not any(run.note_token in t for t in run.traces), 'mask: note token in no job log')

    summary = {'image': args.image, 'runs': int(args.runs), 'total_seconds': round(time.time() - started),
               'version': gl.call('GET', '/version'), 'results': run.results, 'failures': run.failures}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    sys.exit(1 if run.failures else 0)


main()
