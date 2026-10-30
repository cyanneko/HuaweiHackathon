"""Regression checks for the standalone scheduler's legal dependency boundary."""
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent

class Contract(unittest.TestCase):
    def test_submission_only_and_hidden_input_boundary(self):
        code = (HERE / 'MySpillScheduler.cpp').read_text()
        self.assertIn('class MySpillScheduler : public SpillScheduler', code)
        for forbidden in ['int main(', 'class HashJoinEngine', 's.miss_penalty',
                          'state.miss_penalty', 'op_lines', 'getenv(', 'ifstream',
                          'std::cin', 'freopen(', 'fopen(']:
            self.assertNotIn(forbidden, code)

    def test_frozen_framework_preserved(self):
        import json, hashlib
        m = json.loads((HERE / 'build_manifest.json').read_text())
        for record in m['builds']:
            tu = (HERE / record['translation_unit']).read_text()
            policy = (HERE / record['policy']).read_text()
            self.assertEqual(tu.count(policy), 1)
            skeleton = tu.replace(policy, '<SCHEDULER>')
            self.assertEqual(hashlib.sha256(skeleton.encode()).hexdigest(),
                             m['framework_skeleton_sha256'])

if __name__ == '__main__':
    unittest.main()
