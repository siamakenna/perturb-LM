import json
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
        self.root = Path(self.temp.name).resolve()
        self.plan_dir = self.root/'plan'
        self.plan_dir.mkdir()
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
        pilot.write_json(directory/'plan.json',self.plan)
        pilot.write_json(directory/'cohort_LOCAL.json',self.cohort)

    def fake_prepare(self, work, out):
        Path(out).mkdir()
        self.write_plan(Path(out))

    def test_missing_approval_precedes_numeric_reads(self):
        with patch('pilot.load_plate') as loader:
            with self.assertRaises(ValueError):
                pilot.score(self.root,self.plan_dir,'0'*64,self.root/'results')
            loader.assert_not_called()
        self.assertFalse((self.root/'results').exists())

    def test_changed_plan_is_rejected_before_numeric_reads(self):
        def changed(work,out):
            self.fake_prepare(work,out)
            pilot.write_json(Path(out)/'plan.json',dict(self.plan,changed=True))
        with patch('prepare.prepare',side_effect=changed), patch('pilot.load_plate') as loader:
            with self.assertRaises(ValueError): pilot.score(self.root,self.plan_dir,self.approval,self.root/'results')
            loader.assert_not_called()

    def test_cohort_tampering_is_rejected(self):
        pilot.write_json(self.plan_dir/'cohort_LOCAL.json',dict(self.cohort,changed=True))
        with patch('prepare.prepare',side_effect=self.fake_prepare), patch('pilot.load_plate') as loader:
            with self.assertRaises(ValueError): pilot.score(self.root,self.plan_dir,self.approval,self.root/'results')
            loader.assert_not_called()

    def test_synthetic_end_to_end_with_mocked_parquet_reader(self):
        gx=np.zeros((384,3))
        gx[-64:]=np.array([[-1.,-2.,-3.],[1.,2.,3.]]*32)
        gx[:3]=[[2,0,0],[0,2,0],[0,0,2]]
        qx=np.ones((383,3))
        qx[24:27]=[[2,0,0],[0,2,0],[1,1,1]]
        arrays=iter([(self.wells,['Cells_A','Cells_B','Cells_C'],gx),
                     (self.wells[:-1],['Cells_A','Cells_B','Cells_C'],qx)])
        out=self.root/'results'
        with patch('prepare.prepare',side_effect=self.fake_prepare), \
             patch('prepare.resolve_inputs',return_value={'profile_G':Path('fakeG'),'profile_Q':Path('fakeQ')}), \
             patch('pilot.load_plate',side_effect=lambda *args: next(arrays)), \
             patch.dict('sys.modules',{'pyarrow':types.SimpleNamespace(__version__='mock-io-test')}):
            summary=pilot.score(self.root,self.plan_dir,self.approval,out)
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


if __name__=='__main__': unittest.main()
