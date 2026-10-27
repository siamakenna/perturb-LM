#!/usr/bin/env python3
"""Publish only reviewed readiness source in a new draft PR stacked on PR93."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

REPO = 'siamakenna/perturb-LM'
URL = 'https://github.com/' + REPO + '.git'
BASE = '88d367fa7c7ea224af14de979efcb1831d3518d6'
DEST = 'research/phase5_3_readiness'
FILES = ('run_parallel_preflight.py', 'channel_contract.py', 'test_channel_contract.py',
         'test_run_parallel_preflight.py', 'tracker_seed.json', 'batch_usage.json',
         'batch_usage_notes.md', 'model_readiness.md', 'model_public_audit.json',
         'model_public_audit.md', 'README.md', 'DEVELOPMENT_FLOW.mmd',
         'DEVELOPMENT_FLOW.svg', 'PROTOCOL.json', 'DEVELOPMENT_FLOW.png',
         'LOCAL_RUNBOOK.md', 'CONTINUE_IN_CODEX.txt', 'READ_FIRST.html',
         'VALIDATION.json', 'publish_handoff.py', 'test_publish_handoff.py')
ALLOWED = {DEST + '/' + n for n in FILES} | {DEST + '/SHA256SUMS'}


def payload(kit):
    kit = Path(kit).resolve()
    manifest = kit / 'SHA256SUMS'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 65536:
        raise ValueError('Expected the bounded kit SHA256SUMS file')
    hashes = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
        if not match or match[2] in hashes:
            raise ValueError('Malformed or duplicate kit checksum entry')
        hashes[match[2]] = match[1]
    if set(hashes) != set(FILES):
        raise ValueError('The checksum manifest must contain only the reviewed handoff files')
    result = {}
    for name in FILES:
        path = kit / name
        if (path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024):
            raise ValueError('A reviewed payload file is unavailable or oversized')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes.get(name):
            raise ValueError('A readiness payload checksum changed')
        result[DEST + '/' + name] = raw
    result[DEST + '/SHA256SUMS'] = manifest.read_bytes()
    return result


class Publisher:
    def __init__(self, source, kit, work, gh, python=sys.executable):
        self.source, self.kit, self.work = Path(source).resolve(), Path(kit).resolve(), Path(work).resolve()
        self.gh, self.python, self.code = gh, python, self.work / 'repo'
        self.receipt = self.work / 'publication-receipt.json'
        self.state = json.loads(self.receipt.read_text()) if self.receipt.exists() else {
            'task': 'oct27-readiness-source-only-v1', 'repository': REPO, 'base_sha': BASE,
            'status': 'STARTED', 'research_outputs_published': False,
            'model_or_scientific_analysis_run': False}
        if (self.state.get('task') != 'oct27-readiness-source-only-v1'
                or self.state.get('repository') != REPO or self.state.get('base_sha') != BASE):
            raise ValueError('Publication folder belongs to another task')
        self.log = (self.work / 'publication.PRIVATE.log').open('a')
        self.env = {k:v for k,v in os.environ.items()
                    if not k.startswith(('PYTHON','PYTEST','PIP_','GIT_TRACE'))
                    and k not in {'GH_DEBUG','GIT_CURL_VERBOSE','BASH_ENV','ENV'}}
        self.env.update(GH_HOST='github.com', GH_PROMPT_DISABLED='1', GIT_TERMINAL_PROMPT='0',
                        PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', GIT_LFS_SKIP_SMUDGE='1')
        self.prefix = ['git','-c','credential.helper=','-c',
                       'credential.helper=!' + shlex.quote(gh) + ' auth git-credential',
                       '-c','submodule.recurse=false','-c','core.hooksPath=/dev/null']
        self.save()

    def save(self):
        self.receipt.write_text(json.dumps(self.state, indent=2) + '\n')

    def run(self, args, cwd=None):
        self.log.write('COMMAND: ' + repr(args) + '\n'); self.log.flush()
        p = subprocess.run(args, cwd=cwd or self.code, env=self.env, text=True,
                           stdout=subprocess.PIPE, stderr=self.log, timeout=600)
        self.log.write(p.stdout); self.log.flush()
        if p.returncode:
            raise RuntimeError('Command failed; retain publication.PRIVATE.log and resume this folder')
        return p.stdout.strip()

    def git(self, *args, repo=None):
        return self.run(self.prefix + ['-C', str(repo or self.code), *args], cwd=self.work)

    def base_pr(self):
        r = json.loads(self.run([self.gh,'api','repos/' + REPO + '/pulls/93'], cwd=self.work))
        if (r.get('state') != 'open' or r.get('head',{}).get('sha') != BASE
                or r.get('head',{}).get('repo',{}).get('full_name') != REPO
                or not re.fullmatch(r'science/[A-Za-z0-9_./-]+', r.get('head',{}).get('ref',''))):
            raise ValueError('PR93 changed or closed; review its fresh state before publishing a stacked PR')
        return r

    def changed(self):
        paths = self.git('diff','--name-only','HEAD','-z').split('\0')
        paths += self.git('ls-files','--others','--exclude-standard','-z').split('\0')
        # Repository/global ignore rules can hide reviewed public images or JSON.
        # Account for ignored files only within the fixed hash-verified payload.
        paths += self.git('ls-files','--others','--ignored','--exclude-standard',
                          '-z','--',*sorted(ALLOWED)).split('\0')
        return set(filter(None, paths))

    def remote(self):
        rows = self.git('ls-remote','--heads','origin','refs/heads/' + self.state['branch']).splitlines()
        if not rows:
            return None
        if (len(rows) != 1 or len(rows[0].split()) != 2
                or rows[0].split()[1] != 'refs/heads/' + self.state['branch']):
            raise ValueError('Ambiguous remote publication branch')
        return rows[0].split()[0]

    def commit_scope(self, head):
        paths = set(filter(None, self.git('diff-tree','--no-commit-id','--name-only','-r','-z',head).split('\0')))
        if self.git('show','-s','--format=%P',head) != BASE or paths != ALLOWED:
            raise ValueError('The publication commit contains an unexpected parent or file')
        if any((self.code / name).read_bytes() != raw for name,raw in self.files.items()):
            raise ValueError('Committed readiness files differ from the verified package')

    def prepare(self):
        self.files = payload(self.kit)
        for args in [('get-url','--all'), ('get-url','--push','--all')]:
            origin = self.git('remote',*args,'origin',repo=self.source)
            if origin not in {URL, URL[:-4], 'git@github.com:' + REPO + '.git', 'ssh://git@github.com/' + REPO + '.git'}:
                raise ValueError('Unexpected source origin destination')
        if (self.git('rev-parse','HEAD',repo=self.source) != BASE
                or self.git('status','--porcelain',repo=self.source)):
            raise ValueError('Preserve the source checkout; expected a clean pinned PR93 clone')
        base = self.base_pr()['head']['ref']
        if 'branch' not in self.state:
            self.state.update(branch='science/phase5-3-parallel-readiness-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'),
                              base_branch=base)
            self.save()
        if self.state['base_branch'] != base:
            raise ValueError('The stacked PR base branch changed')
        if not self.code.exists():
            self.git('worktree','add','-b',self.state['branch'],str(self.code),BASE,repo=self.source)
        if self.git('branch','--show-current') != self.state['branch']:
            raise ValueError('Publication checkout is on another branch')
        self.head = self.git('rev-parse','HEAD')
        if self.head != BASE:
            self.commit_scope(self.head)
            self.state['commit'] = self.head; self.save()
        if self.changed() - ALLOWED:
            raise ValueError('Unrelated publication work was preserved')
        for name, raw in self.files.items():
            path = self.code / name
            for part in (path, *path.parents):
                if part == self.code:
                    break
                if part.is_symlink():
                    raise ValueError('Publication destination contains a symlink')
            if self.git('ls-tree','--name-only',BASE,'--',name):
                raise ValueError('Readiness destination already exists in the pinned source')
            if path.exists() and path.read_bytes() != raw:
                raise ValueError('Preserve an unexpected existing readiness file')
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(raw)

    def test(self):
        self.run([self.python,'-m','unittest','discover','-s',DEST,'-p','test_*.py','-v'])
        if (self.code / 'scripts/check_public_copy_consistency.py').is_file():
            self.run([self.python,'scripts/check_public_copy_consistency.py'])
        self.git('diff','--check')
        self.state.update(synthetic_checks='PASS'); self.save()

    def publish(self):
        if self.state.get('synthetic_checks') != 'PASS':
            raise ValueError('Readiness synthetic tests must pass before publication')
        if any((self.code / name).read_bytes() != raw for name,raw in self.files.items()):
            raise ValueError('Readiness payload changed after its tests')
        self.base_pr()
        if self.head == BASE:
            if self.changed() != ALLOWED:
                raise ValueError('Only reviewed readiness files may be committed')
            self.git('add','--force','--',*sorted(ALLOWED))
            staged = set(filter(None, self.git('diff','--cached','--name-only','-z').split('\0')))
            if staged != ALLOWED:
                raise ValueError('Unexpected staged publication file')
            user = json.loads(self.run([self.gh,'api','user']))
            if type(user.get('id')) is not int or not re.fullmatch(r'[A-Za-z0-9-]+',user.get('login','')):
                raise ValueError('Cannot establish the authenticated GitHub author')
            self.git('-c','user.name=' + str(user.get('name') or user['login']),
                     '-c','user.email=' + str(user['id']) + '+' + user['login'] + '@users.noreply.github.com',
                     'commit','-m','Add tracked parallel readiness checks and data-use handoff (#30, #52)')
            self.head = self.git('rev-parse','HEAD')
            self.state.update(commit=self.head, status='COMMITTED'); self.save()
        self.commit_scope(self.head)
        if self.git('status','--porcelain'):
            raise ValueError('Publication checkout must be clean')
        remote = self.remote()
        if remote is None:
            self.state.update(status='PUSH_ATTEMPTED'); self.save()
            self.git('push','origin','HEAD:refs/heads/' + self.state['branch'])
        elif remote != self.head:
            raise ValueError('Remote publication branch changed; no force push is allowed')
        records = self.pr_records()
        if not records:
            body = self.work / 'draft-pr-body.md'
            body.write_text('Adds bounded, read-only parallel readiness checks, synthetic inventory tests and a source-bounded development handoff.\n\nStacked on PR #93 to retain its verified package repair. Existing PRs #92/#93 are unchanged. The ChAda-ViT experiment remains proposed; no weights, private research rows, raw images or new scientific outputs are included.\n\nValidation: standalone readiness synthetic suites and public-copy consistency passed locally. No model or scientific scoring ran. Related: #30, #52.\n')
            self.run([self.gh,'pr','create','--repo',REPO,'--draft','--base',self.state['base_branch'],
                      '--head',self.state['branch'],'--title','Add parallel readiness checks and updated development handoff (#30, #52)',
                      '--body-file',str(body)])
        for attempt in range(6):
            records = self.pr_records()
            if (len(records) == 1 and records[0].get('state') == 'OPEN'
                    and records[0].get('isDraft') is True and records[0].get('headRefOid') == self.head
                    and records[0].get('baseRefName') == self.state['base_branch'] and self.remote() == self.head):
                break
            if attempt == 5:
                raise ValueError('Publication may have succeeded; resume this folder rather than repushing blindly')
            time.sleep(2)
        self.state.update(status='PUBLISHED_SOURCE_VERIFIED', pr=records[0]); self.save()
        print('VERIFIED: ' + records[0]['url'] + '\nRemote SHA: ' + self.head, flush=True)
        print('New draft PR is stacked on PR93. No existing PR was changed or merged.', flush=True)

    def pr_records(self):
        return json.loads(self.run([self.gh,'pr','list','--repo',REPO,'--state','all','--head',self.state['branch'],
                                    '--json','number,url,state,isDraft,headRefOid,baseRefName']))

    def watch_checks(self):
        self.state.pop('checked_commit', None)
        self.state['reported_checks'] = 'PENDING'; self.save()
        records = self.pr_records()
        if len(records) != 1 or records[0].get('headRefOid') != self.head or self.remote() != self.head:
            raise ValueError('The published head changed before checking CI')
        print('Source is pushed. Watching the new draft PR checks...', flush=True)
        result = subprocess.run([self.gh,'pr','checks',str(records[0]['number']),
                                 '--repo',REPO,'--watch'],cwd=self.code,env=self.env,timeout=1800)
        records = self.pr_records()
        if len(records) != 1 or records[0].get('headRefOid') != self.head or self.remote() != self.head:
            raise ValueError('The published head changed during CI; saved checks need reconciliation')
        self.state.update(checked_commit=self.head, checks_exit_status=result.returncode,
                          reported_checks='PASS' if result.returncode == 0 else 'NEEDS_REVIEW')
        self.save()
        if result.returncode:
            print('SOURCE REMAINS PUSHED. New-head checks need review; no check was suppressed.', flush=True)
            return False
        print('PASS: readiness source is pushed and reported checks pass at the verified commit.', flush=True)
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repo', required=True, type=Path)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--watch-checks', action='store_true')
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    if not args.publish:
        parser.error('Use --publish to save only reviewed readiness source in a new draft PR')
    os.umask(0o077)
    source = args.source_repo.expanduser().resolve()
    if not source.is_dir():
        parser.error('Pinned PR93 source clone is unavailable')
    gh = shutil.which('gh')
    if not gh:
        parser.error('Authenticated GitHub CLI was not found')
    pointer = source.parent / 'readiness-publication-location.txt'
    if args.resume:
        work = args.resume.expanduser().resolve()
    elif pointer.exists() or pointer.is_symlink():
        if pointer.is_symlink() or not pointer.is_file() or pointer.stat().st_size >= 8192:
            parser.error('Publication pointer must be a bounded regular file')
        work = Path(pointer.read_text().strip()).resolve()
    else:
        work = Path(tempfile.mkdtemp(prefix='readiness-publication.',dir=source.parent))
        pointer.write_text(str(work) + '\n')
    if not work.is_dir() or work.parent != source.parent or not work.name.startswith('readiness-publication.'):
        parser.error('Expected the preserved publication folder beside the source clone')
    print('Publication folder: ' + str(work), flush=True)
    app = None
    try:
        app = Publisher(source, Path(__file__).resolve().parent, work, gh)
        app.prepare(); app.test(); app.publish()
        if args.watch_checks and not app.watch_checks():
            return 2
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as error:
        if app:
            app.state.update(last_error=str(error)[:800]); app.save()
        print('STOP: ' + str(error), flush=True)
        print('Preserve the publication folder. Resume it to avoid duplicate publication.', flush=True)
        return 1
    finally:
        if app:
            app.log.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
