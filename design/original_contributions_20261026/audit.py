import collections,hashlib,json,subprocess,time
from pathlib import Path
from experiment import linux,dump
ROOT=Path(__file__).resolve().parent
def main():
    freeze=json.loads((ROOT/'freeze.json').read_text())
    for name,h in freeze.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
    rows=json.loads((ROOT/'fresh_test'/'manifest.json').read_text());lookup={r['id']:r for r in rows}
    paths=ROOT/'audit_inputs.txt';paths.write_text(''.join(linux(r['file'])+'\n' for r in rows),encoding='utf8')
    begin=time.perf_counter()
    p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(paths),'old,fast_old,351,863,1375,1887,2911'],capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr)
    (ROOT/'strict_audit.jsonl').write_text(p.stdout,encoding='utf8')
    results=[json.loads(x) for x in p.stdout.splitlines()];assert len(results)==610*7 and all(x['ok'] for x in results)
    by={(Path(x['input']).stem,x['policy']):x for x in results}
    differences=[]
    for r in rows:
        a=by[r['id'],'old'];b=by[r['id'],'fast_old']
        if any(a[k]!=b[k] for k in ['write_bytes','read_bytes','hit','miss','action_hash']):differences.append(r['id'])
    assert not differences
    aliases={}
    for policy in ['351','863','1375','1887']:
        a,b=by['alias_A',policy],by['alias_B',policy]
        assert a['observation_hash']==b['observation_hash'] and a['action_hash']==b['action_hash']
        aliases[policy]=dict(observation_hash=a['observation_hash'],action_hash=a['action_hash'],callbacks=a['callbacks'])
    counters={}
    for policy in ['351','863','1375','1887','2911']:
        xs=[x for x in results if x['policy']==policy]
        keys=['switches','epochs','allocations','cross_spills','linear_plans','sorted_plans','advanced_builds','certified_prefetches','target_pre_spills','guard_rejections','interference_returns']
        counters[policy]={k:sum(x[k] for x in xs) for k in keys}
    # Hidden penalty does not reach policy state. Re-run the same operation file
    # after changing only the inaccessible input penalty, including all callbacks.
    checks=[]
    for ident in ['alias_A','preserve_hot_probe_00','grow_then_probe_builder_00']:
        source=Path(linux(lookup[ident]['file']));text=source.read_text();lines=text.splitlines();hdr=lines[0].split();hdr[5]='1' if hdr[5]!='1' else '1000';lines[0]=' '.join(hdr)
        target=ROOT/('penalty_clone_'+ident+'.txt');target.write_text('\n'.join(lines)+'\n')
        p=subprocess.run([str(ROOT/'strict_replay'),str(target),'351,863,1375,1887'],capture_output=True,text=True,timeout=30)
        assert p.returncode==0,p.stderr
        for x in map(json.loads,p.stdout.splitlines()):
            old=by[ident,x['policy']]
            assert x['ok'] and all(x[k]==old[k] for k in ['observation_hash','action_hash','read_bytes','write_bytes','miss'])
            checks.append(dict(case=ident,policy=x['policy'],same_actions=True))
    # Verify public engines have only the permitted scheduler substitution.
    plain=(ROOT/'reference_current.cpp').read_text('utf8')
    for name in ['core','early','externality','combined','relaxed']:
        s=(ROOT/('engine_'+name+'.cpp')).read_text('utf8').replace('\n#include "OriginalScheduler.cpp"\n','')
        import re
        s=re.sub(r'std::make_unique<MySpillScheduler>\(\d+\)','std::make_unique<NaiveSpillScheduler>()',s)
        assert s==plain
    report=dict(all_actions_legal=True,strict_replays=len(results),fast_old_action_and_io_differences=differences,
      aliases=aliases,counters=counters,hidden_penalty_invariance=checks,framework_only_permitted_substitution=True,
      frozen_sources_verified=True,wall_s=time.perf_counter()-begin,
      limitation='Strict replay includes extra observation hashing and is used for legality/counters only. Timing claims use the unchanged public engine.')
    dump(ROOT/'audit_summary.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
