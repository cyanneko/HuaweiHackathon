import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from freeze_recipe import cases

class RecipeTest(unittest.TestCase):
    def test_size_and_splits(self):
        rows=cases()
        self.assertEqual(len(rows),40)
        self.assertEqual({s:sum(r['split']==s for r in rows) for s in ['train','dev','eval']},{'train':24,'dev':6,'eval':10})
        self.assertEqual(sum(r['parameters']['n'] for r in rows),168000000)
        self.assertEqual(len({r['parameters']['seed'] for r in rows}),40)
    def test_scope(self):
        rows=cases()
        self.assertTrue(any(r['parameters']['family']=='mixed' for r in rows if r['split']=='eval'))
        for r in rows:
            p=r['parameters'];self.assertNotIn('operator_heat',p);self.assertNotIn('rare',p)
            self.assertIn(p['n'],[1000000,5000000]);self.assertGreaterEqual(p['k']*p['p'],32)
if __name__=='__main__':unittest.main()
