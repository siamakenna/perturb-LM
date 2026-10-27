"""Invented payloads, real temporary Git worktrees and mocked GitHub responses."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('handoff_publisher', Path(__file__).with_name('publish_handoff.py'))
app = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(app)


def git(*args):
    return subprocess.check_output(['git', *map(str,args)], text=True,
                                   stderr=subprocess.DEVNULL).strip()


def make_kit(root, bad_test=False):
    kit = root / 'kit'; kit.mkdir()
    for name in app.FILES:
        text = 'Invented public source\n'
        if name.startswith('test_'):
            text = ('import unittest\nclass Invented(unittest.TestCase):\n'
                    '    def test_fixture(self):\n'
                    + ('        self.fail("invented failure")\n' if bad_test else '        self.assertEqual(2+2,4)\n'))
        elif name.endswith('.py'):
            text = '# Invented placeholder source, not real research\n'
        (kit / name).write_text(text)
    (kit / 'private-result.csv').write_text('KEEP_LOCAL,not real research\n')
    manifest = ''.join(hashlib.sha256((kit/n).read_bytes()).hexdigest() + '  ' + n + '\n'
                       for n in app.FILES)
    (kit / 'SHA256SUMS').write_text(manifest)
    return kit


class LocalPublisher(app.Publisher):
    def __init__(self, *args, **kwargs):
        self.pushes, self.creates, self.commands = 0, 0, []
        self.base_advanced, self.interrupt_after_push = False, False
        super().__init__(*args, **kwargs)
        self.pr_created = bool(self.state.get('pr'))

    def run(self, args, **kwargs):
        self.commands.append(args)
        if args[0] == self.gh:
            if args[1:3] == ['api', 'repos/' + app.REPO + '/pulls/93']:
                return json.dumps({'state':'open','head':{
                    'sha':'a'*40 if self.base_advanced else app.BASE,
                    'ref':'science/pr93','repo':{'full_name':app.REPO}}})
            if args[1:3] == ['api', 'user']:
                return json.dumps({'id':123,'login':'invented-researcher'})
            if args[1:3] == ['pr', 'list']:
                if self.interrupt_after_push:
                    self.interrupt_after_push = False
                    raise RuntimeError('Invented interruption after accepted push')
                return json.dumps([{'number':999,'url':'https://github.com/' + app.REPO + '/pull/999',
                                    'state':'OPEN','isDraft':True,'headRefOid':self.head,
                                    'baseRefName':'science/pr93'}] if self.pr_created else [])
            if args[1:3] == ['pr','create']:
                self.creates += 1; self.pr_created = True
                self.created_args = args
                return 'https://github.com/' + app.REPO + '/pull/999'
            raise AssertionError('Unexpected GitHub command: ' + repr(args))
        return super().run(args, **kwargs)

    def git(self, *args, **kwargs):
        if args and args[0] == 'push':
            self.pushes += 1
        return super().git(*args, **kwargs)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def fixture(self, bad_test=False, ignore_rules=()):
        source = self.root / 'source with spaces'; source.mkdir()
        git('init','-q',source); git('-C',source,'checkout','-qb','science/pr93')
        git('-C',source,'config','user.name','Invented researcher')
        git('-C',source,'config','user.email','invented@localhost')
        (source / 'README.md').write_text('Preserved original source\n')
        (source / '.gitignore').write_text('outputs/\n__pycache__/\n' + ''.join(rule + '\n' for rule in ignore_rules))
        git('-C',source,'add','.'); git('-C',source,'commit','-qm','Invented pinned source')
        base = git('-C',source,'rev-parse','HEAD')
        remote = self.root / 'remote.git'; git('clone','-q','--bare',source,remote)
        git('-C',source,'remote','add','origin',remote)
        (source / 'outputs').mkdir(); (source / 'outputs/private.csv').write_text('KEEP_LOCAL\n')
        kit = make_kit(self.root, bad_test)
        work = self.root / 'publication'; work.mkdir()
        patch.object(app,'BASE',base).start(); patch.object(app,'URL',str(remote)).start()
        patch.object(app.time,'sleep',return_value=None).start(); self.addCleanup(patch.stopall)
        obj = LocalPublisher(source,kit,work,'invented-gh',sys.executable)
        self.addCleanup(obj.log.close)
        return obj, source, remote, kit, work, base

    def test_exact_scope_stacked_draft_real_push_and_private_preservation(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.publish()
        self.assertEqual(obj.state['status'],'PUBLISHED_SOURCE_VERIFIED')
        self.assertEqual(obj.pushes,1); self.assertEqual(obj.creates,1)
        self.assertIn('--draft',obj.created_args)
        self.assertEqual(obj.created_args[obj.created_args.index('--base')+1],'science/pr93')
        paths=set(git('-C',obj.code,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines())
        self.assertEqual(paths,app.ALLOWED)
        self.assertEqual(git('-C',source,'rev-parse','HEAD'),base)
        self.assertEqual(git('-C',source,'status','--porcelain'),'')
        self.assertEqual((source/'outputs/private.csv').read_text(),'KEEP_LOCAL\n')
        self.assertEqual(git('--git-dir',remote,'rev-parse','refs/heads/'+obj.state['branch']),obj.head)
        self.assertFalse((obj.code/app.DEST/'private-result.csv').exists())
        self.assertFalse(any('push' in args and ('--force' in args or '--force-with-lease' in args)
                             for args in obj.commands))

    def test_changed_base_pr_blocks_without_source_mutation(self):
        obj, source, remote, kit, work, base = self.fixture(); obj.base_advanced=True
        with self.assertRaisesRegex(ValueError,'PR93 changed'): obj.prepare()
        self.assertFalse(obj.code.exists()); self.assertEqual(obj.pushes,0)

    def test_production_png_ignore_publishes_only_reviewed_image_and_preserves_private(self):
        obj, source, remote, kit, work, base = self.fixture(ignore_rules=('*.png',))
        obj.prepare(); obj.test()
        private = obj.code / 'private-local-image.png'
        private.write_bytes(b'Invented private image bytes; keep local\n')
        self.assertIn(app.DEST + '/DEVELOPMENT_FLOW.png',obj.changed())
        self.assertNotIn('private-local-image.png',obj.changed())
        obj.publish()
        paths=set(git('-C',obj.code,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines())
        self.assertEqual(paths,app.ALLOWED)
        self.assertEqual(git('-C',obj.code,'ls-files','--',private.name),'')
        self.assertEqual(private.read_bytes(),b'Invented private image bytes; keep local\n')
        self.assertEqual(git('-C',source,'rev-parse','HEAD'),base)
        self.assertEqual(obj.pushes,1)

    def test_json_ignore_accounts_only_for_whitelist_and_preserves_private_json(self):
        obj, source, remote, kit, work, base = self.fixture(ignore_rules=('*.json',))
        obj.prepare(); obj.test()
        private = obj.code / app.DEST / 'private-extra.json'
        private.write_text('{"invented_private": "keep local"}\n')
        self.assertIn(app.DEST + '/tracker_seed.json',obj.changed())
        self.assertNotIn(str(private.relative_to(obj.code)),obj.changed())
        obj.publish()
        paths=set(git('-C',obj.code,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines())
        self.assertEqual(paths,app.ALLOWED)
        self.assertEqual(git('-C',obj.code,'ls-files','--',str(private.relative_to(obj.code))),'')
        self.assertEqual(private.read_text(),'{"invented_private": "keep local"}\n')
        self.assertEqual(obj.pushes,1)

    def test_missing_or_tampered_reviewed_ignored_file_stops_before_push(self):
        obj, source, remote, kit, work, base = self.fixture(ignore_rules=('*.png',))
        obj.prepare(); obj.test()
        approved = obj.code / app.DEST / 'DEVELOPMENT_FLOW.png'
        original = approved.read_bytes()
        approved.write_bytes(b'Unreviewed invented changed image\n')
        with self.assertRaisesRegex(ValueError,'payload changed'):
            obj.publish()
        self.assertEqual(obj.pushes,0)
        approved.unlink()
        with self.assertRaises((OSError,ValueError)):
            obj.publish()
        self.assertEqual(obj.pushes,0)
        self.assertEqual(git('-C',obj.code,'rev-parse','HEAD'),base)
        approved.write_bytes(original)

    def test_changed_kit_hash_blocks_before_worktree(self):
        obj, source, remote, kit, work, base = self.fixture()
        (kit/app.FILES[0]).write_text('unreviewed change')
        with self.assertRaisesRegex(ValueError,'checksum'): obj.prepare()
        self.assertFalse(obj.code.exists()); self.assertEqual(obj.pushes,0)

    def test_unreviewed_manifest_entry_is_not_published(self):
        obj, source, remote, kit, work, base = self.fixture()
        with (kit/'SHA256SUMS').open('a') as stream:
            stream.write(hashlib.sha256(b'KEEP_LOCAL').hexdigest()+'  private-extra.csv\n')
        with self.assertRaisesRegex(ValueError,'only the reviewed'):
            obj.prepare()
        self.assertFalse(obj.code.exists()); self.assertEqual(obj.pushes,0)

    def test_published_manifest_and_publisher_source_are_preserved(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.publish()
        for name in ('SHA256SUMS','publish_handoff.py','test_publish_handoff.py'):
            self.assertEqual((obj.code/app.DEST/name).read_bytes(),(kit/name).read_bytes())
        self.assertNotIn(app.DEST+'/private-result.csv',app.ALLOWED)

    def test_dirty_source_is_preserved(self):
        obj, source, remote, kit, work, base = self.fixture()
        (source/'README.md').write_text('Uncommitted user work\n')
        with self.assertRaisesRegex(ValueError,'clean pinned'): obj.prepare()
        self.assertEqual((source/'README.md').read_text(),'Uncommitted user work\n')
        self.assertEqual(obj.pushes,0)

    def test_unrelated_staged_private_file_cannot_publish(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test()
        (obj.code/'private.csv').write_text('Invented PRIVATE row\n')
        git('-C',obj.code,'add','private.csv')
        with self.assertRaises(ValueError): obj.publish()
        self.assertEqual(obj.pushes,0); self.assertEqual(git('-C',obj.code,'rev-parse','HEAD'),base)

    def test_failed_synthetic_suite_prevents_push(self):
        obj, source, remote, kit, work, base = self.fixture(bad_test=True)
        obj.prepare()
        with self.assertRaises(RuntimeError): obj.test()
        with self.assertRaises(ValueError): obj.publish()
        self.assertEqual(obj.pushes,0)

    def test_resume_after_accepted_push_never_pushes_twice(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.interrupt_after_push=True
        with self.assertRaisesRegex(RuntimeError,'Invented interruption'): obj.publish()
        self.assertEqual(obj.pushes,1)
        obj.log.close()
        resumed=LocalPublisher(source,kit,work,'invented-gh',sys.executable); self.addCleanup(resumed.log.close)
        resumed.prepare(); resumed.test(); resumed.publish()
        self.assertEqual(resumed.pushes,0); self.assertEqual(resumed.creates,1)
        self.assertEqual(resumed.state['status'],'PUBLISHED_SOURCE_VERIFIED')

    def test_completed_resume_does_not_commit_or_push_again(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.publish(); head=obj.head; obj.log.close()
        resumed=LocalPublisher(source,kit,work,'invented-gh',sys.executable); self.addCleanup(resumed.log.close)
        resumed.prepare(); resumed.test(); resumed.publish()
        self.assertEqual(resumed.head,head); self.assertEqual(resumed.pushes,0); self.assertEqual(resumed.creates,0)

    def test_symlinked_resume_pointer_is_rejected_without_overwriting_target(self):
        obj, source, remote, kit, work, base = self.fixture()
        target=self.root/'preserve.txt'; target.write_text('Preserve pointer target\n')
        (source.parent/'readiness-publication-location.txt').symlink_to(target)
        with patch.object(sys,'argv',['publish_handoff.py','--source-repo',str(source),'--publish']), \
             patch.object(app.shutil,'which',return_value='invented-gh'):
            with self.assertRaises(SystemExit) as error:
                app.main()
        self.assertEqual(error.exception.code,2)
        self.assertEqual(target.read_text(),'Preserve pointer target\n')

    def watched_checks(self, obj, code, during_watch=None):
        original=app.subprocess.run
        def dispatch(args, *positional, **kwargs):
            if args[:3] == [obj.gh,'pr','checks']:
                if during_watch:
                    during_watch()
                return subprocess.CompletedProcess(args,code)
            return original(args,*positional,**kwargs)
        return patch.object(app.subprocess,'run',side_effect=dispatch)

    def test_passing_ci_is_bound_to_the_published_commit(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.publish()
        with self.watched_checks(obj,0):
            self.assertTrue(obj.watch_checks())
        self.assertEqual(obj.state['reported_checks'],'PASS')
        self.assertEqual(obj.state['checked_commit'],obj.head)
        self.assertEqual(obj.state['checks_exit_status'],0)
        self.assertEqual(obj.pushes,1)

    def test_failing_ci_preserves_verified_push_and_records_need_for_review(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.publish()
        with self.watched_checks(obj,1):
            self.assertFalse(obj.watch_checks())
        self.assertEqual(obj.state['status'],'PUBLISHED_SOURCE_VERIFIED')
        self.assertEqual(obj.state['reported_checks'],'NEEDS_REVIEW')
        self.assertEqual(obj.state['checked_commit'],obj.head)
        self.assertEqual(git('--git-dir',remote,'rev-parse','refs/heads/'+obj.state['branch']),obj.head)
        self.assertEqual(obj.pushes,1)

    def test_remote_head_race_after_green_ci_cannot_leave_stale_pass_metadata(self):
        obj, source, remote, kit, work, base = self.fixture()
        obj.prepare(); obj.test(); obj.publish()
        obj.state.update(reported_checks='PASS',checked_commit=obj.head)
        def move_remote():
            git('--git-dir',remote,'update-ref','refs/heads/'+obj.state['branch'],base)
        with self.watched_checks(obj,0,move_remote):
            with self.assertRaisesRegex(ValueError,'changed during CI'):
                obj.watch_checks()
        self.assertEqual(obj.state['reported_checks'],'PENDING')
        self.assertNotIn('checked_commit',obj.state)
        self.assertEqual(obj.pushes,1)


if __name__=='__main__':
    unittest.main()
