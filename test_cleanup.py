import csv, hashlib, importlib.util, json, shutil, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('clean_csv', ROOT/'clean_csv.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class IndependentCleanupTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = Path(self.td.name)
    def tearDown(self): self.td.cleanup()
    def run_clean(self, src, rules, name='out'):
        p=self.base/'in.csv'; p.write_bytes(src); d=self.base/name
        return mod.clean(p, rules, d), p, d
    def test_portfolio_hand_expected_counts_and_provenance(self):
        src=ROOT/'examples/inventory-source.csv'; raw=src.read_bytes(); rules=json.loads((src.parent/'rules.json').read_text())
        s,_,d=self.run_clean(raw,rules)
        self.assertEqual((s['input_records'],s['output_records'],s['duplicate_records_removed']),(12,10,2))
        self.assertEqual(s['output_source_records'],[1,2,4,5,6,7,8,9,10,11])
        self.assertEqual(s['source_sha256'],hashlib.sha256(raw).hexdigest())
        with (d/'cleaned.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.reader(f))
        self.assertEqual(rows[1][0],'0007'); self.assertEqual(rows[1][2],'parts'); self.assertEqual(rows[1][3],'2026-09-01')
        self.assertEqual(rows[2][5],'line one\nline two'); self.assertEqual(rows[8][4],'0'); self.assertEqual(rows[9][4],'-3')
        self.assertEqual(rows[4][3],'2026-02-30'); self.assertEqual(rows[3][3],'03/04/2026'); self.assertEqual(rows[5][0],'')
        self.assertEqual((d/'source.csv').read_bytes(),raw)
    def test_rejects_malformed_duplicate_headers_formula_limits_and_rules(self):
        cases=[(b'a,b\n1\n',{}),(b'A,a\n1,2\n',{}),(b'a,b\n=SUM(1,2),x\n',{}),(b'a,b\n+x,y\n',{}),(b'a,b\n-1e3,y\n',{}),(b'a,b\n1,2\n',{'trim':['missing']})]
        for raw,r in cases:
            with self.assertRaises(ValueError): self.run_clean(raw,r)
            self.assertEqual(list(self.base.iterdir()),[self.base/'in.csv'])
            for x in list(self.base.iterdir()): x.unlink()
    def test_edge_rules_dates_and_overwrite(self):
        raw='sku,note,date\n000,  Café,\n001,"a\nb",2024-02-29\n002,x,2023-02-29\n003,x,2024/01/02\n'.encode()
        rules={'trim':['note','date'],'iso_dates':['date'],'required':['sku'],'remove_exact_duplicates':False}
        s,_,d=self.run_clean(raw,rules); self.assertEqual(s['output_records'],4)
        with (d/'cleaned.csv').open(encoding='utf-8-sig',newline='') as f: checked=list(csv.reader(f))
        self.assertEqual(checked[2][1],'a\nb')
        with self.assertRaises(FileExistsError): mod.clean(self.base/'in.csv',rules,d)
    def test_limits_and_determinism(self):
        raw=('a\n'+'x\n'*1001).encode()
        with self.assertRaises(ValueError): self.run_clean(raw,{})
        self.assertEqual(list(self.base.iterdir()),[self.base/'in.csv'])
        raw=b'a\n1\n'; r={}; s,_,d=self.run_clean(raw,r,'one'); first=(d/'cleaned.csv').read_bytes(); shutil.rmtree(d); mod.clean(self.base/'in.csv',r,d); self.assertEqual(first,(d/'cleaned.csv').read_bytes())

if __name__=='__main__': unittest.main(verbosity=2)
