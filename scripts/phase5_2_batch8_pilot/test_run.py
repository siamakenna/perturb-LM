import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pilot


class ApprovalAndRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()/'work'
        self.root.mkdir()
        self.repo = self.root/'repo'
        self.repo.mkdir()
        (self.repo/'.gitignore').write_text('/outputs/\n')
        subprocess.run(['git','init','-q',str(self.repo)],check=True,capture_output=True)
        self.outputs = self.repo/'outputs'
        self.outputs.mkdir()
        self.plan_dir = self.outputs/'plan'
        self.plan_dir.mkdir()
        self.out = self.outputs/'results'
        self.inputs = self.outputs/'inputs'
        self.inputs.mkdir()
        self.profile_paths = {}
        for plate in ('G','Q'):
            path=self.inputs/(plate+'.parquet')
            path.write_bytes(b'SYNTHETIC MOCKED PROFILE '+plate.encode())
            self.profile_paths['profile_'+plate]=path
        self.profile_pins = {name: (path.stat().st_size,pilot.digest(path))
                             for name,path in self.profile_paths.items()}
        self.wells = [f'{r}{c:02d}' for r in 'ABCDEFGHIJKLMNOP' for c in range(1,25)]
        row = lambda plate,well,broad: dict(plate=plate,well=well,broad_sample=broad,jcp2022=broad)
        self.cohort = dict(gallery_plate='G', query_plate='Q',
            gallery=[row('G','A01','a'),row('G','A02','b'),row('G','A03','c')],
            queries=[dict(row('Q','B01','a'),candidate_count=3,evaluable=True),
                     dict(row('Q','B02','b'),candidate_count=3,evaluable=True),
                     dict(row('Q','B03','z'),candidate_count=3,evaluable=False)],
            dmso_wells={'G':self.wells[-64:], 'Q':self.wells[-64:]})
        self.plan={'scope':'SYNTHETIC TEST ONLY', 'limitations':['Invented matrices, mocked Parquet reader.']}
        self.write_plan(self.plan_dir)
        self.approval = pilot.digest(self.plan_dir/'plan.json')

    def write_plan(self, directory):
        # Fixture setup deliberately writes invented bytes directly. Production
        # output writers must refuse overwriting existing files.
        (directory/'plan.json').write_text(json.dumps(self.plan,indent=2,sort_keys=True)+'\n')
        (directory/'cohort_LOCAL.json').write_text(json.dumps(self.cohort,indent=2,sort_keys=True)+'\n')

    def fake_prepare(self, work, out):
        Path(out).mkdir()
        self.write_plan(Path(out))

    def test_missing_approval_precedes_numeric_reads(self):
        with patch('pilot.load_plate') as loader:
            with self.assertRaises(ValueError):
                pilot.score(self.root,self.plan_dir,'0'*64,self.out)
            loader.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_changed_plan_is_rejected_before_numeric_reads(self):
        def changed(work,out):
            self.fake_prepare(work,out)
            (Path(out)/'plan.json').write_text(json.dumps(dict(self.plan,changed=True)))
        with patch('prepare.prepare',side_effect=changed), patch('pilot.load_plate') as loader:
            with self.assertRaises(ValueError): pilot.score(self.root,self.plan_dir,self.approval,self.out)
            loader.assert_not_called()

    def test_cohort_tampering_is_rejected(self):
        (self.plan_dir/'cohort_LOCAL.json').write_text(json.dumps(dict(self.cohort,changed=True)))
        with patch('prepare.prepare',side_effect=self.fake_prepare), patch('pilot.load_plate') as loader:
            with self.assertRaises(ValueError): pilot.score(self.root,self.plan_dir,self.approval,self.out)
            loader.assert_not_called()

    def run_synthetic(self, *, before_load=None, out=None, plan_dir=None):
        gx=np.zeros((384,3))
        gx[-64:]=np.array([[-1.,-2.,-3.],[1.,2.,3.]]*32)
        gx[:3]=[[2,0,0],[0,2,0],[0,0,2]]
        qx=np.ones((383,3))
        qx[24:27]=[[2,0,0],[0,2,0],[1,1,1]]
        arrays=iter([(self.wells,['Cells_A','Cells_B','Cells_C'],gx),
                     (self.wells[:-1],['Cells_A','Cells_B','Cells_C'],qx)])
        out=self.out if out is None else out
        plan_dir=self.plan_dir if plan_dir is None else plan_dir
        def mocked_load(*args):
            if before_load is not None:
                before_load(*args)
            return next(arrays)
        with patch('prepare.prepare',side_effect=self.fake_prepare), \
             patch('prepare.resolve_inputs',return_value=self.profile_paths), \
             patch.dict('prepare.EXPECTED',self.profile_pins), \
             patch('pilot.load_plate',side_effect=mocked_load), \
             patch.dict('sys.modules',{'pyarrow':types.SimpleNamespace(__version__='mock-io-test')}):
            return pilot.score(self.root,plan_dir,self.approval,out)

    def test_synthetic_end_to_end_with_mocked_parquet_reader(self):
        out=self.out
        summary=self.run_synthetic()
        self.assertEqual(summary['evaluable_query_count'],2)
        self.assertEqual(summary['no_positive_query_count'],1)
        self.assertEqual(summary['metrics_conditional_on_evaluability']['morphology']['reciprocal_rank'],1.)
        self.assertFalse(summary['target_plate_used_to_fit_preprocessing'])
        self.assertFalse(summary['pretrained_inference_performed'])
        self.assertTrue((out/'retrieval-summary.svg').is_file())
        self.assertIn('conditional metric means',(out/'REPORT.html').read_text())
        for line in (out/'SHA256SUMS').read_text().splitlines():
            checksum,name=line.split('  ',1)
            self.assertEqual(pilot.digest(out/name),checksum)

    def assert_path_failure_before_numeric_reads(self, *, out=None, plan_dir=None):
        with patch('prepare.prepare') as preparation, patch('pilot.load_plate') as loader:
            with self.assertRaises((ValueError,OSError)):
                pilot.score(self.root,self.plan_dir if plan_dir is None else plan_dir,
                            self.approval,self.out if out is None else out)
            loader.assert_not_called()
            preparation.assert_not_called()

    def test_outside_or_plan_nested_output_is_rejected_before_any_recheck(self):
        outside=self.root/'outside-results'
        for out in (outside,self.plan_dir/'nested-results'):
            with self.subTest(out=out):
                self.assert_path_failure_before_numeric_reads(out=out)
                self.assertFalse(out.exists())

    def test_existing_output_is_preserved_without_overwrite(self):
        self.out.mkdir()
        marker=self.out/'historical.txt'
        marker.write_text('PRESERVE')
        self.assert_path_failure_before_numeric_reads()
        self.assertEqual(marker.read_text(),'PRESERVE')
        self.assertEqual({p.name for p in self.out.iterdir()},{'historical.txt'})

    def test_internal_output_and_input_symlinks_are_rejected(self):
        outside=self.root/'outside'
        outside.mkdir()
        alias=self.outputs/'redirect'
        alias.symlink_to(outside,target_is_directory=True)
        self.assert_path_failure_before_numeric_reads(out=alias/'new-results')
        self.assertFalse((outside/'new-results').exists())
        plan=self.plan_dir/'plan.json'
        original=plan.read_bytes()
        plan.unlink()
        target=self.inputs/'plan-copy.json'
        target.write_bytes(original)
        plan.symlink_to(target)
        self.assert_path_failure_before_numeric_reads()

    def test_output_tracked_despite_ignore_rule_is_rejected(self):
        self.out.mkdir()
        marker=self.out/'tracked.txt'
        marker.write_text('TRACKED FIXTURE')
        subprocess.run(['git','-C',str(self.repo),'add','-f',str(marker)],check=True,capture_output=True)
        marker.unlink()
        self.out.rmdir()
        self.assert_path_failure_before_numeric_reads()
        self.assertFalse(self.out.exists())

    def test_macos_style_ancestor_alias_uses_canonical_paths(self):
        alias=self.root.parent/'ancestor-alias'
        alias.symlink_to(self.root,target_is_directory=True)
        # The alias is above the trusted work root, just as /var aliases /private/var.
        # Use an alias outside the trusted root, as macOS /var is outside work.
        with patch('prepare.prepare',side_effect=self.fake_prepare), \
             patch('prepare.resolve_inputs',return_value=self.profile_paths), \
             patch('pilot.load_plate') as loader:
            with self.assertRaisesRegex(ValueError,'Approval'):
                pilot.score(alias,alias/'repo/outputs/plan','0'*64,alias/'repo/outputs/results')
            loader.assert_not_called()

    def test_cohort_changed_after_verification_cannot_change_cached_records(self):
        mutated=[]
        def mutate(*_):
            if not mutated:
                (self.plan_dir/'cohort_LOCAL.json').write_text(json.dumps({'gallery_plate':'TAMPERED'}))
                mutated.append(True)
        summary=self.run_synthetic(before_load=mutate)
        self.assertEqual(summary['evaluable_query_count'],2)
        self.assertEqual(json.loads((self.out/'approved-plan.json').read_text()),self.plan)

    def test_profile_changed_while_loading_prevents_completion(self):
        mutated=[]
        def mutate(path,*_):
            if not mutated:
                Path(path).write_bytes(b'CHANGED MOCK PROFILE')
                mutated.append(True)
        with self.assertRaisesRegex(ValueError,'Profile bytes changed'):
            self.run_synthetic(before_load=mutate)
        self.assertFalse((self.out/'pilot-summary.json').exists())
        self.assertEqual(json.loads((self.out/'FAILED.json').read_text())['status'],
                         'INCOMPLETE_DO_NOT_INTERPRET_PARTIAL_RESULTS')

    def test_profile_changed_after_resolve_is_rejected_before_numeric_loading(self):
        def changed_inputs(_):
            self.profile_paths['profile_G'].write_bytes(b'CHANGED BEFORE FIRST LOAD')
            return self.profile_paths
        with patch('prepare.prepare',side_effect=self.fake_prepare), \
             patch('prepare.resolve_inputs',side_effect=changed_inputs), \
             patch.dict('prepare.EXPECTED',self.profile_pins), \
             patch('pilot.load_plate') as loader:
            with self.assertRaisesRegex(ValueError,'reviewed input binding'):
                pilot.score(self.root,self.plan_dir,self.approval,self.out)
            loader.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_checksum_failure_does_not_publish_completed_summary(self):
        with patch('pilot.checksums',side_effect=ValueError('Invented checksum failure')):
            with self.assertRaisesRegex(ValueError,'Invented checksum failure'):
                self.run_synthetic()
        self.assertFalse((self.out/'pilot-summary.json').exists())
        self.assertEqual(json.loads((self.out/'FAILED.json').read_text())['status'],
                         'INCOMPLETE_DO_NOT_INTERPRET_PARTIAL_RESULTS')

    def test_production_json_writer_refuses_overwriting_existing_file(self):
        path=self.outputs/'existing.json'
        path.write_text('PRESERVE')
        with self.assertRaises((ValueError,OSError)):
            pilot.write_json(path,{'replace':True})
        self.assertEqual(path.read_text(),'PRESERVE')


if __name__=='__main__': unittest.main()
