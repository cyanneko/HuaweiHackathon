"""Small schedule invariants; no input files, compiler, or solver."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent

class ScheduleTests(unittest.TestCase):
    def module(self):
        path=ROOT/'generate.py'
        self.assertTrue(path.is_file(),'fixed schedule generator is not implemented yet')
        spec=importlib.util.spec_from_file_location('mx_generator',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    def case(self,split,index):
        path=ROOT/'recipe.frozen.json'
        if not path.exists():path=ROOT.parents[3]/'recipe.frozen.json'
        return json.loads(path.read_text(encoding='utf-8'))['cases'][(8 if split=='eval' else 0)+index]
    def test_cold_events_visit_every_cold_partition(self):
        module=self.module();case=self.case('train',0);schedule=module.ProbeSchedule(case);seen=[set() for _ in range(case['K'])]
        for _ in range(8192):
            op,pid=schedule.next()
            if pid not in case['parameters']['hot_logical_ids']:seen[op].add(pid)
        expected=set(range(case['P']))-set(case['parameters']['hot_logical_ids'])
        self.assertTrue(all(group==expected for group in seen))
    def test_global_anchor_gaps_cross_64_exactly(self):
        module=self.module();case=self.case('eval',2);schedule=module.ProbeSchedule(case);positions=[]
        for i in range(3000):
            if schedule.next()==(0,0):positions.append(i)
        gaps=[b-a for a,b in zip(positions,positions[1:])];expected=case['parameters']['global_probe_interarrival_cycle']
        self.assertEqual(gaps,[expected[i%len(expected)] for i in range(len(gaps))])
    def test_size_heat_reversal_includes_large_hot_and_large_cold(self):
        module=self.module()
        for split in ('train','eval'):
            case=self.case(split,4);schedule=module.ProbeSchedule(case);length=case['parameters']['global_phase_length'];counts=[[0,0],[0,0]]
            for g in range(2*length):
                op,pid=schedule.next()
                if op==0:
                    if pid in case['parameters']['hot_A']:counts[g//length][0]+=1
                    if pid in case['parameters']['hot_B']:counts[g//length][1]+=1
            a,b=counts
            if split=='train':self.assertGreater(a[0],4*a[1]);self.assertGreater(b[1],4*b[0])
            else:self.assertGreater(a[1],4*a[0]);self.assertGreater(b[0],4*b[1])
    def test_memory_boundary_active_sets_are_exactly_M_and_one_more_block(self):
        module=self.module();case=self.case('train',6);schedule=module.ProbeSchedule(case);length=case['parameters']['global_phase_length'];sets=[set(),set()]
        for g in range(2*length):sets[g//length].add(schedule.next())
        totals=[sum(case['logical_partition_bytes'][o][p] for o,p in group) for group in sets]
        self.assertEqual(totals,[case['M'],case['M']+case['parameters']['extra_partition_bytes']])
    def test_prelude_advances_global_and_class_event_counters(self):
        module=self.module();case=self.case('eval',1);schedule=module.ProbeSchedule(case)
        prefix=[schedule.next(forced_op=0) for _ in range(64)]
        self.assertTrue(all(op==0 for op,pid in prefix));self.assertEqual(schedule.global_index,64)
        self.assertEqual(schedule.local_counts[0],64)
        self.assertEqual(schedule.hot_counts[0]+schedule.cold_counts[0],64)
        self.assertEqual(len({pid for op,pid in prefix if pid in case['parameters']['hot_logical_ids']}),4)

if __name__=='__main__':unittest.main()
