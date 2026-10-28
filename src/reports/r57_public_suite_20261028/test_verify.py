import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent


class PublicResultTests(unittest.TestCase):
    def setUp(self):
        if not (HERE/'verify.py').is_file():
            self.fail('public numeric verifier is not implemented')
        spec=importlib.util.spec_from_file_location('r57_verify',HERE/'verify.py')
        self.v=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.v)

    def test_clip_before_repeat_mean(self):
        scores=[self.v.single_score(1,2),self.v.single_score(3,2)]
        self.assertEqual(sum(scores)/2,2.5)
        self.assertEqual(self.v.single_score((1+3)/2,2),0)

    def inputs(self):
        return ([json.loads(line) for line in (HERE/'measurements.jsonl').read_text(encoding='utf8').splitlines()],
                json.loads((HERE/'case_info.json').read_text(encoding='utf8')),
                json.loads((HERE/'datasets.json').read_text(encoding='utf8')))

    def test_full_bundle(self):
        self.assertEqual(self.v.validate_bundle(HERE)['measurements'],432)

    def test_modified_metric_rejected(self):
        rows,cases,data=self.inputs();rows=copy.deepcopy(rows)
        rows[0]['metrics']['Total_Score']+=1
        with self.assertRaises(ValueError):self.v.compute(rows,cases,data)

    def test_missing_or_duplicate_record_rejected(self):
        rows,cases,data=self.inputs()
        for changed in [rows[:-1],rows+[rows[0]]]:
            with self.assertRaises(ValueError):self.v.compute(changed,cases,data)


if __name__=='__main__':unittest.main()
