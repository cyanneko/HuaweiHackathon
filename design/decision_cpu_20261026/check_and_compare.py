import collections,json,subprocess,time
from pathlib import Path
from experiment import evaluate,dump
ROOT=Path(__file__).resolve().parent
def main():
    rows=json.loads((ROOT/'development_manifest.json').read_text())
    listing=ROOT/'development_paths.txt';listing.write_text(''.join(r['file'].replace('\\','/') if not r['file'].startswith('C:') else '/mnt/c'+r['file'][2:].replace('\\','/') for r in []))
    from experiment import linux
    listing.write_text(''.join(linux(r['file'])+'\n' for r in rows))
    p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),'previous,static,stack,sample16,dynamic'],capture_output=True,text=True,timeout=120)
    assert p.returncode==0,p.stderr
    xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==len(rows)*5 and all(x['ok'] for x in xs)
    (ROOT/'development_strict.jsonl').write_text(p.stdout)
    by={(Path(x['input']).stem,x['policy']):x for x in xs};diff={}
    for policy in ['static','stack','sample16','dynamic']:
        diff[policy]=[r['id'] for r in rows if any(by[r['id'],policy][key]!=by[r['id'],'previous'][key] for key in ['action_hash','write_bytes','read_bytes','hit','miss'])]
    assert not diff['static'] and not diff['stack'],diff
    dump(ROOT/'development_audit.json',dict(replays=len(xs),all_actions_legal=True,differences=diff))
    print('Exact-equivalence audit passed. Changed traces:',{k:len(v) for k,v in diff.items()},flush=True)
    cpu=json.loads((ROOT/'cpu_manifest.json').read_text());dump(ROOT/'cpu_small_manifest.json',cpu[:3])
    evaluate(ROOT/'cpu_small_manifest.json',['baseline','previous','static','stack','sample16','dynamic'],5,'cpu_development')
if __name__=='__main__':main()
