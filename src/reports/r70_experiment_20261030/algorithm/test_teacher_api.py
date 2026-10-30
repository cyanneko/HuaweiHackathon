import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from teacher_portfolio import Case,Context,complete_rollout

class TeacherAPITests(unittest.TestCase):
    def test_mixed_rejects_interval_and_dynamic_paths_complete(self):
        c=Case(2,2,6,1,1,1,100,[('INSERT',0,0,2),('SWITCH',0),('PROBE',0,0),
            ('INSERT',1,1,2),('SWITCH',1),('PROBE',1,1),('PROBE',0,0)])
        ctx=Context(c);self.assertFalse(ctx.static)
        with self.assertRaises(ValueError):ctx.chooser('interval_density')
        for method in ctx.supported_methods():self.assertEqual(complete_rollout(c,method,ctx).raw,len(c.ops))
    def test_static_all_six_complete_without_mutating_input(self):
        c=Case(1,3,4,1,1,1,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,2),
            ('SWITCH',0),('PROBE',0,0),('PROBE',0,1),('PROBE',0,2),('PROBE',0,0)])
        ctx=Context(c);self.assertTrue(ctx.static);self.assertEqual(len(ctx.supported_methods()),6)
        before=repr(c.ops)
        for method in ctx.supported_methods():self.assertEqual(complete_rollout(c,method,ctx).raw,len(c.ops))
        self.assertEqual(repr(c.ops),before)

if __name__=='__main__':unittest.main()
