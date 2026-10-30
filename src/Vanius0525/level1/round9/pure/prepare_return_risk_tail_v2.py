"""Bind old successful training logs and inputs before any first-difference replay."""
import ast
import json
from pathlib import Path
from replay_return_risk_tail_v2 import ROOT, HERE, sha, save, experiment_lock


def main():
    with experiment_lock():
        pp = HERE/'RETURN_RISK_MAIN60_PLAN_V1.json'
        plan = json.loads(pp.read_text())
        oldp = HERE/'COLD_BUILD_PLAN_V1.json'; old = json.loads(oldp.read_text())
        rp = HERE/'RETURN_RISK_MAIN60_RESULTS_V1.json'; results = json.loads(rp.read_text())
        lockp = HERE.parent/'V21_DATASET_LOCK.json'; lock = json.loads(lockp.read_text())
        assert results['complete'] and results['new_audited_runs'] == 180
        cf = HERE/'RETURN_RISK_MAIN60_FINAL_FREEZE_V1.json'; frozen = json.loads(cf.read_text())
        for name, value in frozen['files'].items(): assert sha(HERE/name) == value, name
        candidates = ['risk_pool100', 'risk_flat100', 'risk_scale100']
        files = [pp, oldp, rp, lockp, cf,
                 HERE/'RETURN_RISK_TAIL_ATTRIBUTION_PLAN_V1.md',
                 HERE/'RETURN_RISK_TAIL_ATTRIBUTION_CONTRACT_V2.md',
                 HERE/'replay_return_risk_tail_v2.py', HERE/'prepare_return_risk_tail_v2.py',
                 HERE/'return_risk_core_v1.hpp', ROOT/'workflow.py']
        for method in ['paired100', *candidates]:
            src = ROOT/plan['methods'][method]['path']
            assert sha(src) == plan['methods'][method]['sha256']; files.append(src)
            generated = ROOT/plan['executables'][method]['audit']['path']
            generated = generated.with_suffix('.cpp')
            assert sha(generated) == plan['executables'][method]['audit']['generated_source_sha256']
            files.append(generated)
        cases = []
        def bind(path): return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
        for number in (592, 519):
            c = next(c for c in plan['cases'] if c['case'].startswith('train/train_'+str(number)+'_'))
            assert c['case'] in lock['train'] and c['case'] not in lock['dev']
            rr = next(r for r in results['records'] if r['case'] == c['case'])
            oo = next(r for r in old['cases'] if r['case'] == c['case'])
            stem = Path(c['case']).stem
            inp = ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset'/c['case']
            assert sha(inp) == c['input_sha256']
            ref = ROOT/c['reference_record_path']; assert sha(ref) == c['reference_record_sha256']
            cr = ROOT/'build/round9_pure_return_risk_main60_v1'/(stem+'.json')
            assert json.loads(cr.read_text()) == rr and rr['all_checks_passed']
            logs = {'paired100': {}}
            for ext in ('stdout', 'stderr'):
                path = ROOT/oo['reference_'+ext+'_path']
                assert sha(path) == oo['reference_'+ext+'_sha256']
                logs['paired100'][ext] = bind(path)
            for method in candidates:
                logs[method] = {}
                for ext in ('stdout', 'stderr'):
                    path = cr.parent/(stem+'_attempt0')/(method+'_audit.'+ext)
                    assert sha(path) == rr['audit'][method][ext+'_sha256']
                    logs[method][ext] = bind(path)
            cases.append({'case': c['case'], 'seed': c['seed'], 'family': c['family'], 'input': bind(inp),
                          'reference_record': bind(ref), 'candidate_record': bind(cr), 'logs': logs})
        for path in (HERE/'replay_return_risk_tail_v2.py', HERE/'prepare_return_risk_tail_v2.py'):
            ast.parse(path.read_text())
        freeze = {'stage': 'train592-519-first-divergence-v2', 'candidate_order': candidates,
                  'cases': cases, 'files': {str(p.relative_to(ROOT)): sha(p) for p in files},
                  'stop_rule': 'first returned-action difference per pair, else complete original input; no 20k cap',
                  'max_pairs': 6, 'new_solver_runs': 0, 'new_compiles': 0, 'new_teacher_runs': 0,
                  'dev_eval_dyna_inputs_read': 0}
        fp = HERE/'RETURN_RISK_TAIL_ATTRIBUTION_EXECUTION_FREEZE_V2.json'; save(fp, freeze)
        print('frozen', sha(fp), 'pairs', len(cases)*len(candidates))


if __name__ == '__main__': main()
