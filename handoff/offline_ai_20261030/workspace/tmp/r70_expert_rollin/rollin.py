"""Actual VanBest full-action roll-in; separate causal R65 observer, no private H.

The immutable original engine is used, with only factory substitution and an
external scheduler trace decorator. Formal decision timing is not measured.
"""
import argparse,hashlib,json,random,sys,time
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
B=ROOT/'hashjoin_lab/reports/collaboration_20261020'
sys.path.insert(0,str(B/'round69_offline_scale'))
import compact_harness as h
from core import Case,State

SOURCE=ROOT/'tmp/dataset_score_audit_20261030/benchmark/sources/VanBest.policy.cpp'
EXPECTED='2cd6440fb6e78a406a9abac1cab642a98ec94bd07f46f2e55f641d04a23ae1db'
BUILD=OUT/'build';EXE=BUILD/'vanbest_trace'


def apply_actions(s,actions):
    """Strict legal subset of official SPILL/LOAD semantics, including periodic.

    Observer sees public callbacks and actual action intents only. P load uses
    the same load-intent bookkeeping as a miss load but never increments misses.
    This is not VanBest's private history, and cannot be labelled as such.
    """
    kind,target,need=s.callback
    spill=[];load=None;seen=set()
    for typ,o,p in actions:
        assert 0<=o<s.c.k and 0<=p<s.c.p
        i=o*s.c.p+p;assert i not in seen;seen.add(i)
        if typ=='S':
            assert load is None and s.mem[i] and s.sizes[i]>0
            assert kind=='P' or i!=target
            spill.append(i)
        else:
            assert typ=='L' and load is None and kind!='O'
            assert not s.mem[i] and s.phase[o]
            assert kind=='P' or i==target
            load=i
    assert kind!='M' or load==target
    assert kind!='O' or load is None
    released=sum(s.sizes[i] for i in spill)
    assert s.used-released+(s.sizes[load] if load is not None else 0)<=s.c.m
    if kind=='O':assert s.used-released+need<=s.c.m
    if spill or load is not None:
        s.h.record(s,spill,load if load is not None else target,load is not None)
    for i in spill:s.addwrite(s.sizes[i]);s.mem[i]=False
    if load is not None:s.addread(s.sizes[load]);s.mem[load]=True
    s.callback=None


def prepare():
    assert h.sha(SOURCE)==EXPECTED
    BUILD.mkdir(parents=True,exist_ok=True)
    frame=B/'round49_latency_baseline/reference_compilable.cpp'
    raw=frame.read_text(encoding='utf8');start=raw.index('class NaiveSpillScheduler');end=raw.index('class HashJoinEngine')
    wrapper=h.WRAPPER
    a=wrapper.index(' public:CompactDispatch(');b=wrapper.index(' std::vector<Action>onMemoryOverflow',a)
    wrapper=wrapper[:a]+' public:CompactDispatch(){inner=std::make_unique<MySpillScheduler>();}\n'+wrapper[b:]
    suffix=raw[end:];needle='std::make_unique<NaiveSpillScheduler>()';replacement='std::make_unique<CompactDispatch>()'
    assert suffix.count(needle)==1
    changed=suffix.replace(needle,replacement);assert changed.replace(replacement,needle)==suffix
    source=raw[:start]+SOURCE.read_text(encoding='utf8')+'\n'+wrapper+changed
    path=BUILD/'vanbest_trace.cpp';path.write_text(source,encoding='utf8')
    seconds=h.native(['wsl','-d','Ubuntu','--','g++','-std=c++14','-O2',h.linux(path),'-o',h.linux(EXE)],BUILD/'compile.stdout.log',BUILD/'compile.stderr.log',default_timeout=40)
    manifest=dict(policy_sha256=EXPECTED,framework_sha256=h.sha(frame),translation_sha256=h.sha(path),binary_sha256=h.sha(EXE),
                  engine_suffix_identical_except_factory=True,compile_seconds=seconds,formal_D=None)
    (BUILD/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def run_case(row,deadline):
    inputs=ROOT/'tmp/r70_inputs';path=inputs/row['input'];c=Case.read(path)
    assert c.input_hash==row['sha256'];assert h.sha(SOURCE)==EXPECTED
    build=json.loads((BUILD/'manifest.json').read_text());assert h.sha(EXE)==build['binary_sha256']
    dest=OUT/'runs'/row['case_id'];dest.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    h.native(['wsl','-d','Ubuntu','--',h.linux(EXE),h.linux(path)],dest/'stdout.log',dest/'trace.log',deadline)
    s=State(c);seq=0;periodic=0;periodic_nonempty=0;prefetches=0;anchors=[];eligible=0;witness=[];rng=random.Random(70)
    # WSL may prepend a UTF-16 diagnostic before the ASCII trace; retain raw
    # bytes and parse only explicit R69TRACE markers, like the R69 harness.
    for line in (dest/'trace.log').read_text(encoding='utf8',errors='replace').splitlines():
        if 'R69TRACE ' not in line:continue
        h.check(deadline);tok=('R69TRACE '+line.split('R69TRACE ',1)[1]).split()
        assert s.advance(),'extra official callback'
        prefix=h._prefix(s,seq);assert tok[:len(prefix)]==prefix,(seq,'callback aggregate/next-op mismatch')
        count=int(tok[len(prefix)]);tail=tok[len(prefix)+1:];assert len(tail)==3*count
        acts=[(tail[j],int(tail[j+1]),int(tail[j+2])) for j in range(0,len(tail),3)]
        kind=s.callback[0]
        record=dict(raw=s.raw,stage=s.stage,kind=kind,actions=acts)
        if kind=='P':
            periodic+=1;periodic_nonempty+=bool(acts);prefetches+=sum(x[0]=='L' for x in acts)
        else:
            eligible+=1
            # Uniform reservoir selection, never a future-derived feature.
            target=eligible-1 if eligible<=24 else rng.randrange(eligible)
            if target<24:
                anchor=dict(case_id=row['case_id'],input_sha256=c.input_hash,callback_index=seq,
                    snapshot=s.snapshot(),expert_actions=acts,teacher_role='strong_online_rollin',
                    observer_version='r65-causal-with-executed-periodic-intents-v1')
                if eligible<=24:anchors.append(anchor)
                else:anchors[target]=anchor
        apply_actions(s,acts);witness.append(record);seq+=1
    assert not s.advance(),'missing official callback'
    metrics={k:float(v.strip()) for line in (dest/'stdout.log').read_text(encoding='utf8',errors='replace').splitlines() if ':' in line for k,v in [line.split(':',1)]}
    assert metrics['Hit_Count']==s.hit and metrics['Miss_Count']==s.miss
    assert abs(metrics['Total_IO_Time']-s.ordered_io)<=.011
    assert 0<=s.used<=c.m
    for name,data in [('witness',witness),('anchors',sorted(anchors,key=lambda x:x['callback_index']))]:
        (dest/(name+'.json')).write_text(json.dumps(data,separators=(',',':')))
    report=dict(case_id=row['case_id'],input_sha256=c.input_hash,source_sha256=EXPECTED,build=build,
                cost=h.costs(s),callback_count=seq,periodic_callbacks=periodic,nonempty_periodic=periodic_nonempty,
                prefetches=prefetches,anchor_count=len(anchors),observer_version='r65-causal-with-executed-periodic-intents-v1',
                reference_replay_verified=True,all_callbacks_consumed=True,aggregate_public_action_parity=True,
                full_partition_states_logged=False,formal_D=None,elapsed_seconds=time.perf_counter()-started,
                witness_format='vanbest-full-actions-v1',witness_path=str(dest/'witness.json'),
                witness_sha256=h.sha(dest/'witness.json'),anchors_path=str(dest/'anchors.json'),anchors_sha256=h.sha(dest/'anchors.json'))
    (dest/'report.json').write_text(json.dumps(report,indent=2))
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--case');p.add_argument('--all',action='store_true');args=p.parse_args()
    if args.prepare:print(json.dumps(prepare()),flush=True)
    if args.case or args.all:
        rows=json.loads((ROOT/'tmp/r70_inputs/manifests/train.generated.json').read_text())['cases']
        results=[];deadline=time.perf_counter()+60
        for row in rows:
            if args.case and row['case_id']!=args.case:continue
            cached=OUT/'runs'/row['case_id']/'report.json'
            if cached.exists():
                r=json.loads(cached.read_text());assert r['input_sha256']==row['sha256'] and r['source_sha256']==EXPECTED
            else:r=run_case(row,deadline)
            results.append(r)
            print(json.dumps({k:r[k] for k in ('case_id','nonempty_periodic','prefetches','anchor_count','elapsed_seconds')}),flush=True)
        (OUT/'manifest.json').write_text(json.dumps(dict(cases=results,all_verified=all(x['reference_replay_verified'] for x in results),
                 script_sha256=h.sha(__file__),total_prefetches=sum(x['prefetches'] for x in results)),indent=2))

if __name__=='__main__':main()
