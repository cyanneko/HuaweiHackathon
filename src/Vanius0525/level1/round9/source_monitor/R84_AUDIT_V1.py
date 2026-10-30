"""Recheck cached, fixed Git artifacts; never fetch, compile, or run a scheduler."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
REV = 'caafb937039e74a27e7e6e18269f01825fce2411'
BASE = 'src/reports/r84_20261030/'
METHODS = 'src/experiments/r84_full_comparison_20261030/'
ENV = dict(os.environ, GIT_NO_LAZY_FETCH='1')
GIT = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false']


def git(*args, **kwargs):
    return subprocess.check_output([*GIT, *args], cwd=REPO, env=ENV, **kwargs)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def same(a, b):
    assert math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-8), (a, b)


def stats(values):
    v = sorted(values)
    return dict(n=len(v), mean=statistics.mean(v), p50=v[math.ceil(.5*len(v))-1],
                p90=v[math.ceil(.9*len(v))-1], worst=max(v),
                wins=sum(x < 1 for x in v), ties=sum(x == 1 for x in v),
                losses=sum(x > 1 for x in v))


def main():
    tree = git('ls-tree', '-r', REV, '--', BASE, METHODS).decode().splitlines()
    path_oid = {x.split('\t', 1)[1]: x.split()[2] for x in tree}
    oids = sorted(set(path_oid.values()))
    packed = git('cat-file', '--batch', input=('\n'.join(oids)+'\n').encode())
    blobs = {}
    pos = 0
    for oid in oids:
        end = packed.index(b'\n', pos)
        head = packed[pos:end].decode().split()
        assert head[0] == oid and head[1] == 'blob', head
        n = int(head[2]); pos = end+1
        blobs[oid] = packed[pos:pos+n]
        pos += n+1
    assert pos == len(packed)
    def raw(p): return blobs[path_oid[p]]
    def read(p): return json.loads(raw(p))
    def report(p): return read(BASE+p)

    manifest = report('manifest.json')
    declared = {f['path']: f for f in manifest['files']}
    assert len(declared) == len(manifest['files'])
    for p, f in declared.items():
        b = raw(BASE+p)
        assert sha(b) == f['published_sha256'] and len(b) == f['published_bytes'], p
    method_manifest = read(METHODS+'manifest.json')
    for f in method_manifest['files']:
        b = raw(METHODS+f['path'])
        assert sha(b) == f['source_sha256'] == f['published_sha256']
        assert len(b) == f['source_bytes'] == f['published_bytes']
    def original_sha(p): return declared[p]['source_sha256']
    def cache(p):
        out = HERE/'R84_CACHE'/p
        out.parent.mkdir(parents=True, exist_ok=True)
        b = raw(BASE+p)
        if out.exists(): assert out.read_bytes() == b
        else: out.write_bytes(b)

    combined = report('full_v2/combined_dataset_equal.json')
    expected_methods = [f['path'][:-4] for f in method_manifest['files']]
    phase_results = {}
    case_rows = []
    max_cost_rounding = 0
    log_checks = 0
    frameworks = {}
    windows = {}
    for phase, count in [('dyna', 12), ('final', 72)]:
        prefix = 'full_v2/'+phase+'/'
        selection = report(prefix+'selection.json')
        inventory = report('full_v2/'+phase+'.inventory.json')
        rows = report(prefix+'rows.json')
        summary = report(prefix+'summary.json')
        done = report(prefix+'completion.json')
        finalized = report(prefix+'finalized_summary.json')
        campaign = report(prefix+'campaign.json')
        gate = report(prefix+'input_gate.json')
        assert selection['repeats'] == selection['parallelism'] == 1
        assert selection['official_per_case_seconds'] == 60
        assert selection['combined_dataset_weight'] == .5
        assert selection['no_retries'] and not selection['gpu']
        assert selection['dataset_commit'] == inventory['dataset_commit'] == 'd144cdd1c3b78f9a73702b4facb382e6a3e31212'
        assert selection['dataset_version'] == ('1.0.0' if phase == 'dyna' else '2.1.0')
        assert selection['dataset_tree'] == inventory['dataset_tree']
        assert summary['complete'] and finalized['complete']
        assert all(finalized['completion_guards'].values())
        assert done['status'] == 'ALL_CELLS_TERMINAL' and done['error'] is None
        assert done['changed_artifacts'] == [] and summary['missing_cells'] == [] and summary['invalid_cells'] == []
        assert done['valid'] == done['terminal'] == done['planned'] == count*7 == len(rows)
        assert campaign['selection_sha256'] == original_sha(prefix+'selection.json')
        assert done['rows_sha256'] == original_sha(prefix+'rows.json')
        assert done['summary_sha256'] == original_sha(prefix+'summary.json')
        assert finalized['completion_sha256'] == sha(raw(BASE+prefix+'completion.json'))
        assert selection['input_gate_sha256'] == sha(raw(BASE+prefix+'input_gate.json'))
        assert report(prefix+'cpu_released.json')['active_child_processes'] == 0
        cases = {c['case_id']: c for c in selection['cases']}
        methods = {m['name']: m for m in selection['methods']}
        assert len(cases) == count == inventory['case_count'] and list(methods) == expected_methods
        assert {(c['case_id'], c['input_sha256'], c['metadata_sha256']) for c in selection['cases']} == {(c['case_id'], c['input_sha256'], c['metadata_sha256']) for c in inventory['cases']}
        assert gate['input_count'] == count and gate['status'] == 'PASS_FULL_INPUT_SHA_HEADERS_METADATA'
        assert gate['dataset_commit'] == selection['dataset_commit']
        for c in gate['cases']:
            expected = cases[c['case_id']]
            assert c['status'] == 'PASS' and c['input_sha256'] == expected['input_sha256']
            assert c['metadata_sha256'] == expected['metadata_sha256']
            assert c['header']['global_header'][5] == expected['stats']['penalty'] == expected['parameters']['penalty']
            assert expected['full_input_sha_verified_in_prepare']
        if phase == 'dyna':
            assert Counter(c['original_split'] for c in cases.values()) == {'train': 6, 'dev': 3, 'holdout': 3}
        else:
            assert all(c['split'] == 'eval' for c in cases.values())
            assert Counter(c['family'] for c in cases.values()) == {'random_zipf':28, 'random_hotspot':28, 'random_lognormal':16}
        for name, m in methods.items():
            source = raw(BASE+'measured_sources/'+name+'.class.cpp')
            tu = raw(BASE+'measured_sources/'+name+'.tu.cpp')
            assert sha(source) == m['source_sha256'] and sha(tu) == m['translation_unit_sha256']
            assert source == raw(METHODS+name+'.cpp')
            assert m['compile_flags'] == ['-std=c++14', '-O2'] and not m['instrumented']
            s = source.decode('utf-8-sig').replace('\r\n', '\n')
            t = tu.decode('utf-8-sig').replace('\r\n', '\n')
            assert t.count(s) == 1
            skeleton = t.replace(s, '<SCHEDULER>').encode()
            assert sha(skeleton) == '98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
            frameworks[name] = {k:m.get(k) for k in ['source_sha256','translation_unit_sha256','binary_sha256','framework_sha256','compile_flags']}
            cache('measured_sources/'+name+'.class.cpp')
            cache('measured_sources/'+name+'.tu.cpp')
        expected_order = []
        for i, c in enumerate(selection['cases']):
            names = list(methods); shift = i % 7
            expected_order.extend((c['case_id'], name, i) for name in names[shift:]+names[:shift])
        assert [(r['case_id'],r['method'],r['case_index']) for r in rows] == expected_order
        costs = {}; physical = {}; metrics = {}
        for order, row in enumerate(rows):
            cid, name = row['case_id'], row['method']; c = cases[cid]; m = methods[name]
            assert row['order'] == order and row['valid'] and row['status'] == 'PASS'
            assert row['process']['status'] == 'EXITED' and row['process']['returncode'] == 0
            assert row['effective_timeout'] == row['official_wall_limit'] == 60
            assert row['input_sha256'] == c['input_sha256'] and row['source_sha256'] == m['source_sha256'] and row['binary_sha256'] == m['binary_sha256']
            cell = prefix+'cells/'+f'{row["case_index"]:02d}_{name}/'
            assert report(cell+'result.json') == row
            assert report(cell+'process.json') == row['process']
            parsed = {}
            for log in ['stdout','stderr']:
                b = raw(BASE+cell+log+'.txt')
                assert sha(b) == row['process'][log+'_sha256']; log_checks += 1
                if log == 'stdout':
                    for line in b.decode().splitlines():
                        k, v = line.split(': ', 1)
                        assert k not in parsed
                        parsed[k] = int(v) if k in ['Hit_Count','Miss_Count'] else float(v)
            assert parsed == row['metrics']
            assert parsed['Hit_Count'] + parsed['Miss_Count'] == c['stats']['probe_count']
            assert all(math.isfinite(v) and v >= 0 for v in parsed.values())
            p = parsed['Total_IO_Time'] + c['stats']['penalty']*parsed['Miss_Count']
            discrepancy = abs(parsed['Total_Score']-(p+parsed['Total_Decision_Time']))
            assert discrepancy <= .011, (phase,cid,name,discrepancy)
            max_cost_rounding = max(max_cost_rounding, discrepancy)
            costs[cid,name] = parsed['Total_Score']; physical[cid,name] = p; metrics[cid,name] = parsed
        groups = {g['method']:g for g in summary['groups']['all']}
        phase_results[phase] = {}
        for name in methods:
            values = []; raw_values = []; ratios = []
            for cid,c in cases.items():
                assert costs[cid,'Naive'] > 0
                ratio = costs[cid,name]/costs[cid,'Naive']
                raw_point = 10*(1-ratio); score = min(10,max(0,raw_point))
                values.append(score); raw_values.append(raw_point); ratios.append(ratio)
                case_rows.append(dict(dataset=phase,case_id=cid,input_sha256=c['input_sha256'],method=name,actual_penalty=c['stats']['penalty'],io_us=metrics[cid,name]['Total_IO_Time'],miss=metrics[cid,name]['Miss_Count'],decision_us=metrics[cid,name]['Total_Decision_Time'],physical_us=physical[cid,name],total_us=costs[cid,name],same_window_naive_total_us=costs[cid,'Naive'],score=score,raw_points=raw_point))
            g = groups[name]
            same(g['average_score'], statistics.mean(values)); same(g['mean_raw_unclipped_points'],statistics.mean(raw_values))
            same(g['mean_physical'],statistics.mean(physical[cid,name] for cid in cases))
            same(g['mean_cost'],statistics.mean(costs[cid,name] for cid in cases))
            for k,v in stats(ratios).items(): same(g['ratio_to_Naive'][k],v)
            phase_results[phase][name] = dict(score=statistics.mean(values),raw_points=statistics.mean(raw_values),cost_to_naive=stats(ratios),cost_to_van=stats([costs[cid,name]/costs[cid,'Van_latest'] for cid in cases]),physical_to_van=stats([physical[cid,name]/physical[cid,'Van_latest'] for cid in cases]))
        windows[phase] = dict(cases=count,cells=len(rows),valid=done['valid'],wall_seconds=done['seconds'],started_unix=campaign['started_unix'],platform=campaign['platform'],campaign_cpu_model_recorded=False,repeats=1,parallelism=1,input_hashes_manifest_verified=count)
        for leaf in ['selection.json','input_gate.json','campaign.json','completion.json','summary.json']:
            cache(prefix+leaf)
    assert log_checks == 1176
    assert windows['final']['started_unix'] >= windows['dyna']['started_unix'] + windows['dyna']['wall_seconds']
    assert combined['complete'] and combined['dataset_weights'] == {'dyna':.5,'final':.5} and not combined['pooled84_case_mean_used']
    scores = []
    for entry in combined['methods']:
        name = entry['method']; d = phase_results['dyna'][name]; f = phase_results['final'][name]
        same(entry['dyna_mean_score'],d['score']);same(entry['final_mean_score'],f['score'])
        same(entry['equal_dataset_mean_score'],(d['score']+f['score'])/2)
        same(entry['equal_dataset_raw_points'],(d['raw_points']+f['raw_points'])/2)
        scores.append(dict(method=name,dyna12=d['score'],final72=f['score'],equal_dataset_score=(d['score']+f['score'])/2))
    van = raw(METHODS+'Van_latest.cpp')
    own_van = git('show','d92ceb0262b556eb57aae61127d062174ffe6016:src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp')
    assert van == own_van
    failure = report('full_v2/failed_preparation.json')
    assert failure['solver_runs'] == failure['campaign_files'] == failure['selection_files'] == 0
    essential = ['manifest.json','report_zh.md','full_v2/combined_dataset_equal.json','full_v2/release.json','full_v2/failed_preparation.json','van_binding/latest_proof.json']
    essential += ['full_v2/'+p+'/'+leaf for p in ['dyna','final'] for leaf in ['rows.json','selection.json','input_gate.json','campaign.json','completion.json','summary.json']]
    evidence = dict(status='PASS_STATIC_RECOMPUTATION',source_revision=REV,source_artifact_commit='b7482004d5313c6654629324cb465ef36d6554b1',dataset_commit='d144cdd1c3b78f9a73702b4facb382e6a3e31212',dataset_versions={'dyna':'1.0.0','final':'2.1.0'},publisher_manifest_files_verified=len(declared),method_class_files_verified=7,stdout_reparsed=588,stdout_stderr_sha_checks=log_checks,invalid_cells=0,missing_cells=0,max_display_rounding_error_us=max_cost_rounding,windows=windows,methods=frameworks,framework_skeleton_sha256='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9',framework_patch_scope='All seven normalized TUs identical after replacing the exact submitted class by <SCHEDULER>; no extra engine patch between methods.',Van=dict(source_sha256=sha(van),source_bytes=len(van),upstream_commit='d92ceb0262b556eb57aae61127d062174ffe6016',upstream_path='src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp',byte_equal_upstream=True,joint_included=False),scores=scores,phase_comparisons=phase_results,essential_artifacts=[dict(path=BASE+p,sha256=sha(raw(BASE+p)),bytes=len(raw(BASE+p))) for p in essential],scope='Independent read-only reparse of saved Git artifacts, not independent scheduler execution or raw input body rehash. ELF hash bindings and original pre-sanitization hashes checked as archive records, not regenerated binaries.',new_solver_runs=0,new_training_runs=0,new_compile_runs=0,input_downloaded_bytes=0,network_during_audit=False,fetch_note='First default-negotiation explicit blob batches partly failed with bad revision; explicit OID stdin plus fetch.negotiationAlgorithm=noop and blob:none succeeded. No broad lazy fetch or input objects.')
    env = report('van_binding/environment.json')
    evidence['environment_disclosure'] = dict(path=BASE+'van_binding/environment.json', sha256=sha(raw(BASE+'van_binding/environment.json')), compiler_current=env['compiler_current'], cpu_model=next(line.split(':',1)[1].strip() for line in env['cpu'].splitlines() if line.startswith('Model name:')), scope=env['performance_scope'])
    (HERE/'R84_SOURCE_EVIDENCE_V1.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    out = io.StringIO(); writer = csv.DictWriter(out,fieldnames=list(case_rows[0]));writer.writeheader();writer.writerows(case_rows)
    (HERE/'R84_RECOMPUTED_PER_CASE_V1.csv').write_text(out.getvalue())
    print(json.dumps({k:evidence[k] for k in ['status','stdout_reparsed','stdout_stderr_sha_checks','max_display_rounding_error_us','scores']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
