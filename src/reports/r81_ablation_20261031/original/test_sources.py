import hashlib, unittest
from pathlib import Path
import generate as g

class SourceContract(unittest.TestCase):
    def test_parent_and_order(self):
        self.assertEqual(hashlib.sha256(g.PARENT.read_bytes()).hexdigest(), g.PARENT_SHA)
        self.assertEqual(g.NAMES, ['Naive','Full','FixedShare075','UnifiedSlow2048','NoPeriodicPrefetch','NoNextProtection','UnitMissCost','NoStructurePolicy','UniformOperatorMarginal'])

    def test_exact_reversible_single_mechanism_deltas(self):
        parent=g.PARENT.read_text(encoding='utf-8')
        for name, edits in g.EDITS.items():
            child=g.transform(parent,edits)
            self.assertNotEqual(child,parent)
            restored=child
            for old,new in reversed(edits):
                self.assertEqual(restored.count(new),1,(name,new))
                restored=restored.replace(new,old,1)
            self.assertEqual(restored,parent,name)
            self.assertIn('update(s, -1, -1, true);',child)
            self.assertIn('fast_operator_[op].mass += 1.;',child)
            self.assertIn('(evidence || s.read_bandwidth >= s.write_bandwidth)',child)
            self.assertIn('sampleNext(s.next_op.op_id',child)

    def test_mutated_parent_fails_exact_count(self):
        with self.assertRaises(AssertionError): g.transform('',g.EDITS['FixedShare075'])

    def test_framework_roundtrip(self):
        original=g.ORIGINAL.read_bytes();tu=g.ORIGINAL_TU.read_bytes()
        self.assertEqual(tu.count(original),1)
        before,after=tu.split(original)
        for policy in [g.PARENT.read_bytes(),g.NAIVE.read_bytes()]:
            built=before+policy+after
            self.assertEqual(built[:len(before)],before)
            self.assertEqual(built[-len(after):],after)

if __name__=='__main__': unittest.main()
