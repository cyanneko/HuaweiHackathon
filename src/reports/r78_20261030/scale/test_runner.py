"""Tiny pure-function checks; no subprocess or data generation."""
import unittest
from runner import parse,summarize
class Checks(unittest.TestCase):
 def test_physical_uses_real_penalty_and_excludes_D(self):
  text='Total_IO_Time: 100\nTotal_Decision_Time: 5\nHit_Count: 8\nMiss_Count: 2\nTotal_Score: 179\n'
  self.assertEqual(parse(text,dict(probe_count=10,penalty=37))['physical_cost_us'],174)
  with self.assertRaises(AssertionError):parse(text,dict(probe_count=10,penalty=100))
 def test_complete_synthetic_groups_and_no_clipping(self):
  cases=[dict(id=f'c{i}',mechanism=f'm{i//2}',target_pressure=3 if i%2==0 else 12,actual_pressure=3 if i%2==0 else 12,penalty=37) for i in range(8)]
  methods=[dict(name=n) for n in ['R75','build0','overflow']];rows=[]
  for c in cases:
   for j,m in enumerate(methods):rows.append(dict(case_id=c['id'],method=m['name'],metrics=dict(physical_cost_us=100+j*10,Total_IO_Time=100+j*10,Miss_Count=0,Hit_Count=10,Total_Decision_Time=5,Total_Score=105+j*10),wall_seconds_nonformal=.01))
  per,groups=summarize(rows,cases,methods);self.assertEqual(len(per),24);self.assertEqual(groups['all8'][1]['mean_ratio'],1.1);self.assertEqual(groups['pressure12'][2]['cases'],4);self.assertEqual(groups['all8'][2]['wins_losses_ties'],[0,8,0]);self.assertLess(per[1]['uncapped_cost_reduction_pct'],0)
if __name__=='__main__':unittest.main()
