import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    rows=json.loads((ROOT/'cpu_manifest.json').read_text());out=[]
    for row in rows:
        p=subprocess.run([str(ROOT/'bin_profile'),row['file']],capture_output=True,text=True,timeout=60)
        assert p.returncode==0,p.stderr
        summaries=[]
        for line in p.stderr.splitlines():
            if not line.startswith('PROFILE '):continue
            a=list(map(int,line.split()[1:]));kind,count,samples,ns,*hist=a
            def quantile(q):
                acc=0
                for b,n in enumerate(hist):
                    acc+=n
                    if acc>=samples*q:return 2**(b+1)
                return 0
            summaries.append(dict(type=kind,calls=count,samples=samples,mean_sampled_ns=ns/max(1,samples),p50_bucket_upper_ns=quantile(.5),p95_bucket_upper_ns=quantile(.95)))
        x=dict(case=row['id'],callbacks=summaries,public_output=p.stdout);out.append(x)
        print(json.dumps(x),flush=True)
        (ROOT/'callback_profile.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
