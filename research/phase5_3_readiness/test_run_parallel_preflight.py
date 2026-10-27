import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('parallel_preflight', Path(__file__).with_name('run_parallel_preflight.py'))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.downloads = self.root / 'downloads'; self.downloads.mkdir()

    def prepared(self):
        out = self.root / 'prepared'; out.mkdir(); (out / 'jobs').mkdir()
        return out

    def records(self, changed=False, checks=None):
        return [{'number': n, 'headRefOid': '0' * 40 if changed and n == 93 else sha,
                 'headRefName': 'science/invented-' + str(n), 'state': 'OPEN',
                 'url': 'https://github.com/' + runner.REPO + '/pull/' + str(n),
                 'statusCheckRollup': checks or []} for n, sha in runner.PINS.items()]

    def github_responses(self, changed=False, main_after=None):
        before = {'object': {'sha': 'a' * 40}}
        after = {'object': {'sha': main_after or 'a' * 40}}
        return [before, *self.records(changed=changed), after]

    def test_three_jobs_really_overlap_and_tracker_records_real_states(self):
        barrier = threading.Barrier(3)
        seen = []
        def job(label, state):
            def execute(out, downloads, fetch):
                seen.append(label)
                barrier.wait(timeout=3)
                return {'status': state, 'scope': 'invented test only'}
            return execute
        jobs = {'a': job('a', 'DONE_TEST'), 'b': job('b', 'BLOCKED_TEST'), 'c': job('c', 'DONE_TEST')}
        out = self.root / 'new run with spaces'
        result = runner.execute(out, self.downloads, jobs=jobs)
        self.assertEqual(set(seen), {'a', 'b', 'c'})
        self.assertEqual(result['jobs']['b']['status'], 'BLOCKED_TEST')
        self.assertTrue(all('finished_utc' in r for r in result['jobs'].values()))
        self.assertEqual(json.loads((out / 'tracker.json').read_text()), result)
        self.assertFalse((out / 'tracker.json.tmp').exists())
        self.assertIn('not train a model', (out / 'REPORT.html').read_text())

    def test_failed_job_does_not_kill_other_jobs_or_export_private_error(self):
        def bad(*args):
            raise ValueError('PRIVATE invented path /Users/example/data')
        def good(*args):
            return {'status': 'DONE_TEST'}
        out = self.root / 'new run'
        result = runner.execute(out, self.downloads, jobs={'bad': bad, 'good': good})
        self.assertEqual(result['jobs']['bad']['status'], 'BLOCKED_JOB_ERROR')
        self.assertEqual(result['jobs']['good']['status'], 'DONE_TEST')
        self.assertNotIn('PRIVATE invented', (out / 'tracker.json').read_text())
        self.assertIn('PRIVATE invented', (out / 'bad.PRIVATE.log').read_text())

    def test_existing_output_and_symlink_target_rejected(self):
        out = self.root / 'existing'; out.mkdir()
        (out / 'keep.txt').write_text('preserve')
        with self.assertRaises(ValueError):
            runner.execute(out, self.downloads, jobs={})
        alias = self.root / 'alias'; alias.symlink_to(out, target_is_directory=True)
        with self.assertRaises(ValueError):
            runner.execute(alias, self.downloads, jobs={})
        self.assertEqual((out / 'keep.txt').read_text(), 'preserve')

    def test_mac_style_ancestor_alias_is_allowed_for_fresh_destination(self):
        parent = self.root / 'actual'; parent.mkdir()
        alias = self.root / 'ancestor'; alias.symlink_to(parent, target_is_directory=True)
        result = runner.execute(alias / 'new-run', self.downloads, jobs={})
        self.assertTrue((parent / 'new-run/tracker.json').is_file())
        self.assertEqual(result['status'], 'PREFLIGHT_FINISHED_WITH_REPORTED_STATES')

    def test_missing_local_inputs_are_blocked_not_completed_science(self):
        out = self.prepared()
        result = runner.local_job(out, self.downloads)
        self.assertEqual(result['status'], 'BLOCKED_LOCAL_INPUTS_UNAVAILABLE')
        self.assertEqual(len(result['missing_summary_evidence']), 6)
        self.assertFalse(result['raw_profile_files_reverified'])
        self.assertFalse(result['new_crispr_image_cohort_established'])

    def test_discovery_limits_and_internal_symlink_skip(self):
        for n in range(3):
            (self.downloads / ('match' + str(n))).mkdir()
        with self.assertRaises(ValueError):
            runner.capped_matches(self.downloads, 'match*', maximum=2)
        outputs = self.downloads / 'perturb-lm-phase53.invented/repo/outputs'
        outputs.mkdir(parents=True)
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'summary.json').write_text('do not read')
        (outputs / 'alias').symlink_to(outside, target_is_directory=True)
        self.assertEqual(runner.summary_candidates(self.downloads), [])
        (outputs / 'one.txt').write_text('one'); (outputs / 'two.txt').write_text('two')
        with patch.object(runner, 'MAX_FILES', 1):
            with self.assertRaises(ValueError):
                runner.summary_candidates(self.downloads)

    def test_changed_github_head_blocks_all_source_clones(self):
        out = self.prepared()
        with patch.object(runner, 'gh_json', side_effect=self.github_responses(changed=True)), \
             patch.object(runner, 'fetch_pinned_source') as clone:
            result = runner.github_job(out, self.downloads, fetch_source=True)
        clone.assert_not_called()
        self.assertEqual(result['status'], 'BLOCKED_HEAD_CHANGED')
        self.assertTrue((out / 'jobs/github-snapshot.json').is_file())

    def test_matching_heads_with_no_check_data_never_claim_checks_passed(self):
        out = self.prepared()
        with patch.object(runner, 'gh_json', side_effect=self.github_responses()), \
             patch.object(runner, 'fetch_pinned_source') as clone:
            result = runner.github_job(out, self.downloads)
        clone.assert_not_called()
        self.assertEqual(result['status'], 'DONE_PINNED_HEADS_VERIFIED')
        self.assertEqual(result['checks'], {'92': 'NOT_AVAILABLE', '93': 'NOT_AVAILABLE'})
        self.assertFalse(result['remote_writes_performed'])
        self.assertTrue(result['main_stable_during_capture'])

    def test_changed_main_is_reported_without_advancing_pinned_pr_source(self):
        out = self.prepared()
        with patch.object(runner, 'gh_json', side_effect=self.github_responses(main_after='b' * 40)):
            result = runner.github_job(out, self.downloads)
        self.assertFalse(result['main_stable_during_capture'])
        self.assertEqual(result['status'], 'DONE_PINNED_HEADS_VERIFIED')
        snapshot = json.loads((out / 'jobs/github-snapshot.json').read_text())
        self.assertEqual(snapshot['main_before'], 'a' * 40)
        self.assertEqual(snapshot['main_after'], 'b' * 40)

    def test_pending_and_failing_check_states_are_not_green(self):
        self.assertEqual(runner.classify_checks([{'conclusion': 'SUCCESS'}, {'conclusion': 'SKIPPED'}]),
                         'REPORTED_PASS_OR_SKIPPED')
        for value in ('FAILURE', 'IN_PROGRESS', 'CANCELLED', 'PENDING'):
            self.assertEqual(runner.classify_checks([{'conclusion': value}]), 'PENDING_OR_NEEDS_REVIEW')

    def test_source_clone_is_pinned_and_does_not_run_downloaded_code(self):
        out = self.prepared(); record = self.records()[0]
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            return (record['headRefOid'] + '\n').encode() if 'rev-parse' in args else b''
        with patch.object(runner.shutil, 'which', return_value='/invented/gh'), \
             patch.object(runner, 'command', side_effect=command):
            result = runner.fetch_pinned_source(out, record, record['headRefOid'])
        self.assertFalse(result['downloaded_code_executed'])
        self.assertTrue(any('clone' in args for args in calls))
        self.assertTrue(any('checkout' in args and '--detach' in args for args in calls))
        self.assertFalse(any('push' in args or 'submodule' in args for args in calls))
        self.assertFalse(any(a.endswith('.py') or a.endswith('.safetensors') for args in calls for a in args))

    def test_model_job_captures_only_public_metadata_and_keeps_review_pending(self):
        out = self.prepared(); author_sha, model_sha = 'a' * 40, 'b' * 40
        content = {'encoding': 'base64', 'type': 'file', 'content': base64.b64encode(b'Invented source only\n').decode()}
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            if '/api/models/' in args[-1]:
                return json.dumps({'id': 'nicoboou/chadavit16-moyen', 'sha': model_sha}).encode()
            if args[-1].endswith('/config.json'):
                return json.dumps({'embed_dim': 192, 'patch_size': 16, 'max_number_channels': 10,
                                   'return_all_tokens': True}).encode()
            return b'# Invented public text; never execute.\n'
        with patch.object(runner, 'gh_json', side_effect=[{'sha': author_sha}, content, content]), \
             patch.object(runner, 'command', side_effect=command):
            result = runner.model_job(out, self.downloads)
        self.assertEqual(result['author_revision'], author_sha)
        self.assertEqual(result['checkpoint_revision'], model_sha)
        self.assertFalse(result['weights_downloaded'])
        self.assertFalse(result['model_code_executed'])
        self.assertFalse(result['training_overlap_reviewed'])
        self.assertIn('REVIEW_PENDING', result['status'])
        self.assertFalse(result['weight_license_verified'])
        self.assertEqual(result['observed_checkpoint_contract']['embed_dim'], 192)
        self.assertTrue(result['observed_checkpoint_contract']['return_all_tokens'])
        self.assertEqual(len(result['checkpoint_text_source_sha256']), 4)
        self.assertEqual(len(calls), 5)
        self.assertTrue(calls[0][-1].startswith('https://huggingface.co/api/models/'))
        self.assertTrue(all('/resolve/' + model_sha + '/' in args[-1] for args in calls[1:]))
        self.assertFalse(any('.safetensors' in args[-1] or '.bin' in args[-1] for args in calls))

    def test_partial_checkpoint_text_capture_stays_pending(self):
        out = self.prepared()
        source = {'encoding': 'base64', 'type': 'file', 'content': base64.b64encode(b'Invented public source').decode()}
        def command(args, **kwargs):
            if '/api/models/' in args[-1]:
                return json.dumps({'id': 'nicoboou/chadavit16-moyen', 'sha': 'b' * 40}).encode()
            if args[-1].endswith('/README.md'):
                raise RuntimeError('Invented unavailable public text')
            return b'{}' if args[-1].endswith('/config.json') else b'# Invented source\n'
        with patch.object(runner, 'gh_json', side_effect=[{'sha': 'a' * 40}, source, source]), \
             patch.object(runner, 'command', side_effect=command):
            result = runner.model_job(out, self.downloads)
        self.assertEqual(result['status'], 'PARTIAL_SOURCE_CAPTURE_REVIEW_PENDING')
        self.assertEqual(result['missing_checkpoint_text_sources'], ['README.md'])
        self.assertFalse(result['model_code_executed'])

    def test_report_escapes_status_text(self):
        result = runner.render_report({'jobs': {'invented': {'status': '<script>bad()</script>'}}})
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)


if __name__ == '__main__':
    unittest.main()
