"""Release boundaries: prevent stale uniform tests and eval-to-training leakage."""
import copy
import hashlib
from pathlib import Path
import shutil
import random
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PACKAGE/'tools'))
import release_v21 as release
from verify_v21 import validate_contract


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def contract_fixture(self):
        # Only contract metadata is read in these tests; large inputs are not copied.
        for relative in ('manifest.json','recipe.json','selection.json','expansion.json','expansion_manifest.json','eval/VERSION',
                         'provenance/v2.0.0/manifest.json','provenance/v2.0.0/recipe.json',
                         'provenance/v2.0.0/validation.json','provenance/v2.1-initial-plan/expansion.json'):
            target = self.root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(PACKAGE/relative,target)
        manifest = release.load(self.root/'manifest.json')
        for row in manifest['cases']+manifest['diagnostics']:
            for suffix in ('.txt','.meta.json'):
                target = (self.root/row['path']).with_suffix(suffix)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.touch()
        return manifest

    def test_selection_keeps_all_three_families_and_never_promotes_eval(self):
        parent = release.load(PACKAGE/'provenance/v2.0.0/manifest.json')
        active,retired,diagnostic,training = release.select(parent)
        self.assertEqual([len(r) for r in (active,retired,diagnostic,training)],[36,13,1,270])
        self.assertEqual({r['family'] for r in active},set(release.FAMILIES))
        self.assertEqual({r['family'] for r in retired},{'random_uniform','empty_partition_probe'})
        self.assertTrue(all(r['split']=='train' and not r['is_edge'] for r in training))
        self.assertFalse({r['sha256'] for r in training}&{r['sha256'] for r in active+retired+diagnostic})
        broken = copy.deepcopy(parent)
        broken['cases'].remove(next(r for r in broken['cases'] if r['split']=='eval' and release.selected(r)))
        with self.assertRaisesRegex(ValueError,'family counts'):
            release.select(broken)

    def test_stale_nested_eval_is_rejected_even_with_valid_manifest(self):
        self.contract_fixture()
        validate_contract(self.root)
        stale = self.root/'eval/old/eval_001_random_uniform.txt'
        stale.parent.mkdir()
        stale.touch()
        with self.assertRaisesRegex(ValueError,'Unexpected/missing .txt files in eval'):
            validate_contract(self.root)

    def test_rehashed_eval_training_leak_is_still_rejected(self):
        manifest = self.contract_fixture()
        selection = release.load(self.root/'selection.json')
        selection['recommended_training_paths'][0] = selection['retained_eval_paths'][0]
        (self.root/'selection.json').write_bytes(release.encoded(selection))
        recipe = release.load(self.root/'recipe.json')
        recipe['selection_sha256'] = manifest['selection_sha256'] = release.sha(self.root/'selection.json')
        (self.root/'recipe.json').write_bytes(release.encoded(recipe))
        manifest['recipe_sha256'] = release.sha(self.root/'recipe.json')
        (self.root/'manifest.json').write_bytes(release.encoded(manifest))
        with self.assertRaisesRegex(ValueError,'Training profile differs'):
            validate_contract(self.root)

    def test_fast_allocation_matches_frozen_generator_exactly(self):
        from random_workloads import _allocate
        from fast_allocation import allocate
        rng = random.Random(20261030)
        for _ in range(400):
            n = rng.randint(1,40)
            lower = [rng.randint(0,5) for i in range(n)]
            upper = [value+rng.randint(0,100) for value in lower]
            weights = [rng.lognormvariate(0,1.5) for i in range(n)]
            total = rng.randint(sum(lower),sum(upper))
            self.assertEqual(_allocate(total,weights,lower,upper),allocate(total,weights,lower,upper))

    def test_expansion_has_new_split_seeds_and_stays_within_operation_limits(self):
        from expand_v21 import check_plan
        plan = release.load(PACKAGE/'expansion.json')
        check_plan(plan)
        seeds = {r['seed'] for r in plan['generated_cases']}
        self.assertEqual(len(seeds),306)
        old = release.load(PACKAGE/'provenance/v2.0.0/recipe.json')
        self.assertFalse(seeds & {r['seed'] for r in old['generated_cases']})
        for row in plan['generated_cases']:
            spec = row['spec']
            n = spec['build_count']+spec['probe_count']+spec['k']
            self.assertTrue(65536<=n<=5000000)
        tampered = copy.deepcopy(plan)
        tampered['generated_cases'][0]['seed'] += 1
        with self.assertRaisesRegex(ValueError,'specifications differ'):
            check_plan(tampered)

    def test_export_refuses_changed_bytes_without_overwriting_them(self):
        source,dest = self.root/'source',self.root/'dest'
        (source/'train').mkdir(parents=True)
        raw,meta = b'frozen input\n',b'{}\n'
        (source/'train/a.txt').write_bytes(raw)
        (source/'train/a.meta.json').write_bytes(meta)
        row = dict(path='train/a.txt',sha256=hashlib.sha256(raw).hexdigest(),
                   metadata_sha256=hashlib.sha256(meta).hexdigest())
        release.copy_record(source,dest,row)
        (dest/'train/a.txt').write_bytes(b'other data')
        with self.assertRaisesRegex(ValueError,'Refuse to replace'):
            release.copy_record(source,dest,row)
        self.assertEqual((dest/'train/a.txt').read_bytes(),b'other data')
        self.assertEqual((source/'train/a.txt').read_bytes(),raw)

    def test_training_destination_cannot_contain_old_eval(self):
        (self.root/'eval').mkdir()
        (self.root/'eval/test.txt').touch()
        with self.assertRaisesRegex(ValueError,'outside the selected export'):
            release.check_destination(self.root,[dict(path='train/train.txt')])


if __name__=='__main__':
    unittest.main()
