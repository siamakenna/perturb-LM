import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from pilot import load_plate


@unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'PyArrow not installed in this test runtime')
class ParquetIOTests(unittest.TestCase):
    def test_real_parquet_projection_and_row_binding(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        data = pa.table({'Metadata_Source': ['source_4']*2, 'Metadata_Plate':['TEST']*2,
                         'Metadata_Well':['A1','B02'], 'Cells_Test':[1.,2.],
                         'Image_NotInBaseline':[float('nan'),float('nan')]})
        schema = [{'name':f.name,'type':str(f.type)} for f in data.schema]
        checksum = hashlib.sha256(json.dumps(schema).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'synthetic.parquet'
            pq.write_table(data,path)
            wells, features, values = load_plate(path,'TEST',2,checksum,1)
            self.assertEqual(wells,['A01','B02'])
            self.assertEqual(features,['Cells_Test'])
            self.assertEqual(values.tolist(),[[1.],[2.]])
            with self.assertRaises(ValueError): load_plate(path,'OTHER',2,checksum,1)
            with self.assertRaises(ValueError): load_plate(path,'TEST',3,checksum,1)

    def test_duplicate_wells_and_nonfinite_features_fail(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'synthetic.parquet'
            for wells,values in [(['A1','A01'],[1.,2.]),(['A01','B01'],[1.,float('nan')])]:
                data=pa.table({'Metadata_Source':['source_4']*2,'Metadata_Plate':['TEST']*2,
                               'Metadata_Well':wells,'Cells_Test':values})
                schema=[{'name':f.name,'type':str(f.type)} for f in data.schema]
                checksum=hashlib.sha256(json.dumps(schema).encode()).hexdigest()
                pq.write_table(data,path)
                with self.assertRaises(ValueError): load_plate(path,'TEST',2,checksum,1)


if __name__=='__main__': unittest.main()
