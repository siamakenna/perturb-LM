#!/usr/bin/env python3
"""Run three bounded, read-only Perturb-LM readiness jobs with tracked completion."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import traceback

REPO = 'siamakenna/perturb-LM'
PINS = {92: 'c28bd56f56771055e3cc5c7e84bcff0841e76190',
        93: '88d367fa7c7ea224af14de979efcb1831d3518d6'}
SUMMARY_PINS = {
    '1d325458adfffd4488869a6e5c2b19da65ecbf9adb3aa1bc8028b3b1f72ed79e': 'U2OS completed summary',
    '8a431da94933685ec4099a40aae6d8522b0d448dab4d009950ae37f75527a99e': 'A549 completed summary',
    'ba50da1ebd4e49bd090e792612dfd2f5d4cb8c904513b210829fe2a740e46948': 'Context-agreement diagnostic',
    '2fa25b216e6f2f3c0e93a90a4d5c67649da27a79f73e3e8c8e2e337efaa5ceea': 'Production Batch8 descriptive pilot',
    '559dfe73f96614b547f2d24456c9c0a43afd77caf1c5c98e4fd5e07bdcd58d88': 'MOA retrieval summary',
    '9b1523199937c3a93b282705c8d652cbbb2a658d0cbe4e992308cd175fab42cf': 'MOA control-sensitivity summary',
}
MAX_DIRS, MAX_FILES, MAX_ROOTS = 512, 4096, 32


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def bounded_bytes(path, limit):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise ValueError('Expected a bounded regular file')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('File grew beyond the byte limit')
    return data


def clean_environment():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('PYTHON', 'PYTEST', 'PIP_', 'GIT_TRACE'))
           and k not in {'GH_DEBUG', 'GIT_CURL_VERBOSE', 'BASH_ENV', 'ENV'}}
    env.update(GH_HOST='github.com', GH_PROMPT_DISABLED='1', GIT_TERMINAL_PROMPT='0',
               GIT_LFS_SKIP_SMUDGE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    return env


def command(args, *, cwd=None, limit=2 * 1024 * 1024):
    p = subprocess.run(args, cwd=cwd, env=clean_environment(), capture_output=True,
                       timeout=120)
    if p.returncode:
        raise RuntimeError('A public-source command failed; no remote write was attempted')
    if len(p.stdout) > limit:
        raise ValueError('Public-source response exceeded the byte limit')
    return p.stdout


def gh_json(*args):
    gh = shutil.which('gh')
    if not gh:
        raise RuntimeError('Authenticated GitHub CLI is unavailable')
    return json.loads(command([gh, *args]))


def classify_checks(checks):
    if not checks:
        return 'NOT_AVAILABLE'
    states = [c.get('conclusion') or c.get('state') or c.get('status') for c in checks]
    allowed = {'SUCCESS', 'success', 'SKIPPED', 'skipped', 'NEUTRAL', 'neutral'}
    return 'REPORTED_PASS_OR_SKIPPED' if all(s in allowed for s in states) else 'PENDING_OR_NEEDS_REVIEW'


def fetch_pinned_source(out, record, expected):
    gh = shutil.which('gh')
    branch = record.get('headRefName', '')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', branch) or branch.startswith('-') or '..' in branch:
        raise ValueError('Unexpected source branch name')
    target = out / 'source' / ('PR' + str(record['number']))
    target.parent.mkdir(exist_ok=True)
    prefix = ['git', '-c', 'credential.helper=', '-c',
              'credential.helper=!' + shlex.quote(gh) + ' auth git-credential',
              '-c', 'submodule.recurse=false', '-c', 'core.hooksPath=/dev/null']
    command(prefix + ['clone', '--no-checkout', '--no-tags', '--single-branch', '--depth', '1',
                       '--branch', branch, 'https://github.com/' + REPO + '.git', str(target)])
    command(prefix + ['-C', str(target), 'checkout', '--detach', expected])
    actual = command(prefix + ['-C', str(target), 'rev-parse', 'HEAD']).decode().strip()
    dirty = command(prefix + ['-C', str(target), 'status', '--porcelain']).decode().strip()
    if actual != expected or dirty:
        raise ValueError('Public source clone did not match the pinned clean commit')
    return {'relative_path': str(target.relative_to(out)), 'commit': actual,
            'downloaded_code_executed': False}


def github_job(out, downloads, fetch_source=False):
    main_before = gh_json('api', 'repos/' + REPO + '/git/ref/heads/main').get('object', {}).get('sha')
    records, clones = [], []
    for number, expected in PINS.items():
        r = gh_json('pr', 'view', str(number), '--repo', REPO, '--json',
                    'number,state,isDraft,headRefName,headRefOid,url,statusCheckRollup')
        records.append(r)
    snapshot = {'captured_utc': timestamp(), 'main_before': main_before, 'pull_requests': records}
    write_json(out / 'jobs/github-snapshot.json', snapshot)
    mismatched = [r['number'] for r in records if r.get('headRefOid') != PINS.get(r['number'])]
    if mismatched:
        result = {'status': 'BLOCKED_HEAD_CHANGED', 'changed_pull_requests': mismatched,
                  'source_clones': [], 'reason': 'Fresh GitHub heads differ from the handoff; review before execution.'}
    else:
        result = {'status': 'DONE_PINNED_HEADS_VERIFIED', 'source_clones': clones,
                  'checks': {str(r['number']): classify_checks(r.get('statusCheckRollup')) for r in records},
                  'fresh_snapshot': 'jobs/github-snapshot.json', 'remote_writes_performed': False}
    if fetch_source and not mismatched:
        for record in records:
            clones.append(fetch_pinned_source(out, record, PINS[record['number']]))
        # Check for a race while source was copied. Never silently advance the pins.
        for record in records:
            now = gh_json('pr', 'view', str(record['number']), '--repo', REPO, '--json', 'headRefOid')
            if now.get('headRefOid') != record['headRefOid']:
                result.update(status='BLOCKED_HEAD_CHANGED',
                              reason='A PR changed during capture; preserved clones remain pinned historical source.')
    main_after = gh_json('api', 'repos/' + REPO + '/git/ref/heads/main').get('object', {}).get('sha')
    stable = bool(re.fullmatch(r'[0-9a-f]{40}', main_before or '') and main_before == main_after)
    snapshot.update(main_after=main_after, main_stable_during_capture=stable)
    write_json(out / 'jobs/github-snapshot.json', snapshot)
    result.update(main_before=main_before, main_after=main_after, main_stable_during_capture=stable)
    return result


def capped_matches(root, pattern, maximum=MAX_ROOTS):
    result = []
    for path in root.glob(pattern):
        result.append(path)
        if len(result) > maximum:
            raise ValueError('Discovery exceeded its folder limit; specify a narrower Downloads folder')
    return sorted(result)


def summary_candidates(downloads):
    result, directories, files = [], 0, 0
    for folder in capped_matches(downloads, 'perturb-lm-phase5[23]*'):
        if folder.is_symlink() or not folder.is_dir():
            continue
        root = folder / 'repo/outputs'
        if root.is_symlink() or not root.is_dir() or (folder / 'repo').is_symlink():
            continue
        for current, dirs, names in os.walk(root, followlinks=False):
            directories += 1; files += len(names)
            if directories > MAX_DIRS or files > MAX_FILES:
                raise ValueError('Local evidence discovery exceeded its directory or file limit')
            here = Path(current)
            depth = len(here.relative_to(root).parts)
            dirs[:] = [] if depth >= 5 else sorted(d for d in dirs if not (here / d).is_symlink())
            for name in sorted(names):
                if name in {'summary.json', 'context-agreement-summary.json', 'pilot-summary.json',
                            'moa-retrieval-summary.json', 'moa-control-sensitivity-summary.json'}:
                    p = here / name
                    if not p.is_symlink() and p.is_file() and p.stat().st_size <= 2 * 1024 * 1024:
                        result.append(p)
    return result


def local_job(out, downloads, fetch_source=False):
    found, ledger = {}, []
    for path in summary_candidates(downloads):
        raw = bounded_bytes(path, 2 * 1024 * 1024)
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum in SUMMARY_PINS:
            found[SUMMARY_PINS[checksum]] = checksum
            ledger.append({'kind': 'completed_summary', 'path': str(path.resolve()), 'sha256': checksum})
    images, issues = [], []
    candidates = capped_matches(downloads, 'perturb-lm-jump-images.*/staging/jump-image-inventory.json')
    if candidates:
        from channel_contract import inspect_inventory
        for path in candidates:
            try:
                images.append(inspect_inventory(path))
                ledger.append({'kind': 'technical_image_inventory', 'path': str(path.resolve())})
            except (OSError, ValueError, TypeError, KeyError) as error:
                issues.append({'error_type': type(error).__name__, 'reason': 'Local image inventory did not pass its contract'})
    missing = sorted(set(SUMMARY_PINS.values()) - set(found))
    status = ('DONE_AVAILABLE_EVIDENCE_INVENTORIED' if not missing and images else
              'PARTIAL_LOCAL_EVIDENCE' if found or images else 'BLOCKED_LOCAL_INPUTS_UNAVAILABLE')
    write_json(out / 'LOCAL_PATHS_PRIVATE.json', {'keep_local': True, 'paths': ledger})
    result = {'status': status, 'verified_summary_hashes': found, 'missing_summary_evidence': missing,
              'technical_image_inventories': images, 'image_inventory_issues': issues,
              'raw_profile_files_reverified': False, 'profile_values_read': False,
              'new_crispr_image_cohort_established': False,
              'reason': 'Known compound-site images are technical inputs, not the cross-guide image cohort.'}
    write_json(out / 'jobs/local-evidence.json', result)
    return result


def public_text(repository, name, revision):
    data = gh_json('api', 'repos/' + repository + '/contents/' + name + '?ref=' + revision)
    if data.get('encoding') != 'base64' or data.get('type') != 'file':
        raise ValueError('Expected a public source file')
    raw = base64.b64decode(data.get('content', ''), validate=False)
    if len(raw) > 512 * 1024:
        raise ValueError('Public source file exceeded the byte limit')
    return raw


def model_job(out, downloads, fetch_source=False):
    folder = out / 'model-source'; folder.mkdir()
    record = gh_json('api', 'repos/nicoboou/chadavit/commits/main')
    revision = record.get('sha', '')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Author source revision is unavailable')
    files = {}
    for name in ('README.md', 'pyproject.toml'):
        raw = public_text('nicoboou/chadavit', name, revision)
        (folder / name).write_bytes(raw)
        files[name] = hashlib.sha256(raw).hexdigest()
    result = {'status': 'DONE_SOURCE_PINS_CAPTURED_REVIEW_PENDING',
              'architecture': 'ChAda-ViT/16 Moyen', 'author_repository': 'nicoboou/chadavit',
              'author_revision': revision, 'source_sha256': files,
              'weights_downloaded': False, 'model_code_executed': False,
              'training_overlap_reviewed': False, 'weight_license_verified': False,
              'integration_approved': False}
    try:
        raw = command(['curl', '--fail', '--silent', '--show-error', '--location', '--max-time', '45',
                       'https://huggingface.co/api/models/nicoboou/chadavit16-moyen'], limit=1024 * 1024)
        meta = json.loads(raw)
        if meta.get('id') != 'nicoboou/chadavit16-moyen' or not re.fullmatch(r'[0-9a-f]{40}', meta.get('sha', '')):
            raise ValueError('Model metadata identity could not be bound')
        result['checkpoint_repository'] = meta['id']; result['checkpoint_revision'] = meta['sha']
        hashes, missing = {}, []
        for name in ('config.json', 'config_chada_vit.py', 'modeling_chada_vit.py', 'README.md'):
            try:
                text = command(['curl', '--fail', '--silent', '--show-error', '--location', '--max-time', '45',
                                '--max-filesize', str(512 * 1024),
                                'https://huggingface.co/nicoboou/chadavit16-moyen/resolve/' + meta['sha'] + '/' + name],
                               limit=512 * 1024)
                (folder / ('checkpoint-' + name)).write_bytes(text)
                hashes[name] = hashlib.sha256(text).hexdigest()
                if name == 'config.json':
                    config = json.loads(text)
                    result['observed_checkpoint_contract'] = {k: config[k] for k in
                        ('embed_dim', 'patch_size', 'max_channels', 'max_number_channels', 'in_chans',
                         'return_all_tokens', 'image_size', 'num_channels', 'max_num_channels') if k in config}
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
                missing.append(name)
        result.update(checkpoint_text_source_sha256=hashes, missing_checkpoint_text_sources=missing,
                      checkpoint_code_review='PENDING_MANUAL_REVIEW_NO_EXECUTION')
        if missing:
            result['status'] = 'PARTIAL_SOURCE_CAPTURE_REVIEW_PENDING'
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        result['checkpoint_metadata_status'] = 'BLOCKED_PUBLIC_MODEL_METADATA_ACCESS'
        result['status'] = 'PARTIAL_SOURCE_CAPTURE_REVIEW_PENDING'
    write_json(folder / 'source-pins.json', result)
    return result


JOBS = {'github': github_job, 'local_evidence': local_job, 'model_source': model_job}


def render_report(tracker):
    rows = ''.join('<tr><td>' + html.escape(key) + '</td><td>' + html.escape(item['status']) + '</td></tr>'
                   for key, item in tracker['jobs'].items())
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Perturb-LM readiness</title>'
            '<style>body{font:17px/1.55 system-ui;max-width:1000px;margin:40px auto;padding:0 24px;color:#292139;background:#fbf9ff}'
            'h1{color:#62448e}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:14px;border-bottom:1px solid #ded4eb}'
            '</style><h1>Perturb-LM parallel readiness check</h1><p>These jobs inspect evidence and public source. '
            'They do not train a model, score profiles, approve biology or publish to GitHub.</p><table><tr><th>Job</th><th>Observed status</th></tr>'
            + rows + '</table><p>Private paths remain in LOCAL_PATHS_PRIVATE.json. Raw profiles were not reverified. '
            'Missing data or access is a blocker, not completed science.</p></html>')


def execute(out, downloads, fetch_source=False, jobs=None):
    out, downloads = Path(out).expanduser(), Path(downloads).expanduser().resolve()
    if '..' in out.parts or out.is_symlink() or out.exists() or not out.parent.is_dir():
        raise ValueError('Choose a fresh output folder under an existing directory')
    out = out.resolve(); out.mkdir(mode=0o700); (out / 'jobs').mkdir()
    (out / '.gitignore').write_text('*\n')
    tracker = {'schema_version': 1, 'started_utc': timestamp(), 'status': 'RUNNING',
               'scope': 'READ_ONLY_PREFLIGHT_NOT_MODEL_EXECUTION', 'jobs': {}}
    seed = Path(__file__).with_name('tracker_seed.json')
    if seed.is_file() and not seed.is_symlink():
        tracker['historical_tasks'] = json.loads(bounded_bytes(seed, 2 * 1024 * 1024)).get('tasks', [])
        tracker['historical_tasks_note'] = 'Handoff evidence levels are preserved; this runner does not reverify completed science.'
    selected = jobs if jobs is not None else JOBS
    for name in selected:
        tracker['jobs'][name] = {'status': 'RUNNING', 'started_utc': timestamp()}
        print('START: ' + name, flush=True)
    write_json(out / 'tracker.json', tracker)
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {pool.submit(fn, out, downloads, fetch_source): name for name, fn in selected.items()}
        for future in as_completed(pending):
            name = pending[future]
            try:
                result = future.result()
                if not isinstance(result, dict) or not isinstance(result.get('status'), str):
                    raise ValueError('A job did not return an explicit completion state')
            except Exception as error:
                (out / (name + '.PRIVATE.log')).write_text(traceback.format_exc())
                result = {'status': 'BLOCKED_JOB_ERROR', 'error_type': type(error).__name__,
                          'reason': 'Keep the local private job log; this job did not complete.'}
            tracker['jobs'][name].update(result, finished_utc=timestamp())
            write_json(out / 'tracker.json', tracker)
            print(name + ': ' + result['status'], flush=True)
    tracker.update(status='PREFLIGHT_FINISHED_WITH_REPORTED_STATES', finished_utc=timestamp())
    write_json(out / 'tracker.json', tracker)
    (out / 'REPORT.html').write_text(render_report(tracker))
    print('Tracker: ' + str(out / 'tracker.json') + '\nReport: ' + str(out / 'REPORT.html'), flush=True)
    return tracker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--downloads', type=Path, default=Path.home() / 'Downloads')
    parser.add_argument('--fetch-source', action='store_true', help='Copy pinned public source only; execute none of it')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        execute(args.out, args.downloads, args.fetch_source)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
