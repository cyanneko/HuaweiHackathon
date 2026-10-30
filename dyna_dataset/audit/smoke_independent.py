"""Independent diagnostic generation and audit; no shared suite mutation."""
import hashlib,importlib.util,json,subprocess,time
from pathlib import Path
from run_audit import compare,records,sha,dump

HERE=Path(__file__).resolve().parent;WS=HERE.parents[1];GEN=WS/'tmp/r72_hierarchical'

def signature(path):
    op=hashlib.sha256();insert=hashlib.sha256()
    with path.open() as f:
        k=int(f.readline().split()[0]);f.readline()
        for _ in range(k):next(f)
        for line in f:
            fields=line.split();op.update((' '.join(fields[:2])+'\n').encode())
            if fields[0]=='INSERT':insert.update((fields[1]+' '+fields[3]+'\n').encode())
    return op.hexdigest(),insert.hexdigest()

def main():
    out=HERE/'independent_smoke';out.mkdir(exist_ok=True);frozen=sha(GEN/'generator.cpp');binary=sha(GEN/'build/generator');started=time.monotonic()
    spec=importlib.util.spec_from_file_location('old',WS/'hashjoin_lab/tools/audit_datasets.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    results=[]
    for name,speed,rare in [('normal',.025,'none'),('faster',.05,'none'),('rare_cold',.025,'cold')]:
        text=out/(name+'.txt');meta=out/(name+'.json');op=out/(name+'.op.csv');part=out/(name+'.part.csv')
        if text.exists():raise FileExistsError(text)
        cmd=[str(GEN/'build/generator'),'--out',str(text),'--meta',str(meta),'--trace',str(op),'--partition-trace',str(part),
             '--n','80008','--k','4','--p','32','--memory','67108864','--seed','202610307299','--pressure','1.5',
             '--build-fraction','.2','--phase','staggered','--profile','burst','--partition-profile','slow',
             '--partition-speed',str(speed),'--rare',rare,'--window','1000','--partition-window','1000']
        child=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
        (out/(name+'.generator.stdout')).write_text(child.stdout);(out/(name+'.generator.stderr')).write_text(child.stderr)
        if child.returncode:raise RuntimeError(child.stderr)
        m=json.loads(meta.read_text());run=subprocess.run([str(HERE/'audit'),str(text),'1000','1000'],capture_output=True,text=True,check=True,timeout=20)
        a=json.loads(run.stdout);checked=compare(m,a,records(op),records(part));legacy=old.audit_case(text,enforce_limits=True)
        assert a['partition_bytes']==legacy['partition_sizes'] and a['partition_probes']==legacy['probe_counts']
        sig,ins=signature(text)
        results.append(dict(name=name,input_sha256=sha(text),source_sha256=frozen,binary_sha256=binary,operator_action_signature=sig,
                            insert_op_size_signature=ins,operations=a['operations'],crosscheck=checked))
        dump(out/(name+'.audit.json'),dict(actual=a,crosscheck=checked))
    assert len({x['operator_action_signature'] for x in results})==1
    assert len({x['insert_op_size_signature'] for x in results})==1
    assert len({x['input_sha256'] for x in results})==3
    assert sha(GEN/'generator.cpp')==frozen and sha(GEN/'build/generator')==binary
    report=dict(status='passed',cases=3,operations=sum(x['operations'] for x in results),elapsed_seconds=time.monotonic()-started,
                partition_speed_and_rare_do_not_change_operator_or_action_sequence=True,
                partition_changes_do_not_change_INSERT_tuple_sizes=True,source_sha256=frozen,binary_sha256=binary,
                results=[{k:v for k,v in x.items() if k!='crosscheck'} for x in results])
    dump(HERE/'independent_smoke.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
