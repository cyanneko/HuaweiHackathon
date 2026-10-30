"""Only three authorized beam06 native calibration runs; no scale experiment."""
import json,unittest,time
from compact_harness import *

class CompactCalibration(unittest.TestCase):
    def test_three_small_runs_match_existing_fulltrace_records(self):
        start=time.perf_counter();old=R67/'runs/beam_06';prior=json.loads((old/'result.json').read_text());input_path=prior['baselines']['actual_naive']['input'];case=Case.read(input_path);reports=[]
        for mode in MODES:
            actual=run_baseline(input_path,mode,O/'validation'/mode,case=case,deadline=start+60)
            expected=prior['baselines'][mode]
            self.assertEqual(actual['cost'],expected['cost']);self.assertEqual(actual['witness_hash'],expected['witness_hash']);reports.append(actual)
        best=json.loads((old/'A_incumbent/best.json').read_text())
        actual=verify_witness(input_path,best['permanent_witness'],O/'validation/r67_best',case=case,deadline=start+60)
        self.assertEqual(actual['cost'],best['cost']);self.assertEqual(actual['witness_hash'],best['witness_hash']);reports.append(actual)
        report={'three_compact_runs_match_old_cost_and_complete_semantic_action_hash':True,'end_to_end_seconds':time.perf_counter()-start,'scope':'compact aggregate/actions calibration against existing fullstate records, not a new fullstate checker run','results':reports}
        (O/'validation/calibration.json').write_text(json.dumps(report,indent=2))
    def test_witness_stream_writer_and_parser(self):
        out=O/'validation';out.mkdir(exist_ok=True);path=out/'stream_fixture.json'
        rows=[{'raw':1,'stage':'insert','kind':'O','spill':[2,1]}]
        metadata=write_witness(iter(rows),path)
        self.assertEqual(list(iter_witness(path)),rows)
        self.assertEqual(metadata['witness_hash'],hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        path.write_text('[{},]')
        with self.assertRaises(ValueError):list(iter_witness(path))
if __name__=='__main__':unittest.main()
