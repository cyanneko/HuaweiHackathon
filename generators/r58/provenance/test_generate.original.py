import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import generate as g

class GeneratorTests(unittest.TestCase):
    def test_all_counts_and_temporal_boundaries(self):
        for spec in g.specs():
            text,meta,ops=g.generate_case(spec)
            self.assertEqual(len(ops),spec['N'])
            inserts=[x for x in ops if x[0]=='INSERT'];probes=[x for x in ops if x[0]=='PROBE']
            self.assertEqual(len(inserts),spec['build_INSERTs'])
            self.assertEqual(len(probes),spec['probe_count'])
            self.assertIsNone(meta['q_observed'])
            if spec['family']=='temporal_alignment_mix' or (spec['family']=='no_op_controls' and spec['variant']==0):
                self.assertEqual(len(inserts),120);self.assertEqual(len(inserts)%8,0)
                self.assertEqual(sum(x[3]==g.MiB//2 for x in inserts),8)
            if spec['family']=='temporal_alignment_mix':
                pids=[x[2] for x in probes];boundary=8*spec['aligned_cycles']
                self.assertEqual(pids[boundary:boundary+2],[7,7])
                self.assertEqual(pids[boundary-1],7)
                self.assertEqual(pids[boundary+2:boundary+9][-1]!=7,True)
                self.assertEqual(pids[boundary+9],7)

    def test_structural_build_patterns(self):
        for spec in g.specs():
            _,meta,ops=g.generate_case(spec);ins=[x for x in ops if x[0]=='INSERT']
            if spec['family']=='low_opportunity_mix':
                expected=[(o,p) for o in range(2) for p in range(8)]
                self.assertEqual([(x[1],x[2]) for x in ins[:16]],expected)
                self.assertEqual(len(ins),132)
                probes=[x for x in ops if x[0]=='PROBE']
                self.assertEqual(sum(x[1]==0 for x in probes),3*len(probes)//4)
                self.assertEqual(sum(x[1]==1 for x in probes),len(probes)//4)
            else:
                seen_large=False
                for x in ins:
                    if x[2]==7:seen_large=True
                    else:self.assertFalse(seen_large)
            if spec['family']=='no_op_controls' and spec['variant']==1:
                self.assertEqual(len(ins),56)
                self.assertFalse(any(x[2]==7 for x in ins))
                self.assertEqual(meta['partition_bytes'][0][7],0)

    def test_all16_twice_temp_no_selection_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='r58_repro_') as tmp:
            a=Path(tmp)/'one';b=Path(tmp)/'two'
            ra=g.generate_all(a);rb=g.generate_all(b)
            self.assertEqual(len(ra['cases']),16);self.assertEqual(len(rb['cases']),16)
            self.assertEqual([r['case_id'] for r in ra['cases']],[s['case_id'] for s in g.specs()])
            semantic=[]
            for spec in g.specs():
                rel=Path(spec['split'])/(spec['case_id']+'.txt')
                self.assertEqual((a/rel).read_bytes(),(b/rel).read_bytes())
                ma=json.loads((a/rel.with_suffix('.meta.json')).read_text())
                mb=json.loads((b/rel.with_suffix('.meta.json')).read_text())
                self.assertEqual(ma,mb)
                self.assertTrue(ma['independent_audit']['passed'])
                semantic.append(ma['semantic_modulo_P_stream_sha256'])
            self.assertEqual(len(set(semantic)),16)
            with self.assertRaises(FileExistsError):g.generate_all(a)

if __name__=='__main__':unittest.main()
