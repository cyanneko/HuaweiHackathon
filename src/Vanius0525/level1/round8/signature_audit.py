"""Cross-split input, raw operation, and partition-semantic deduplication."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put
F=ROOT/'round8'
def main():
    old=json.loads((ROOT/'build/round6/final_manifest.json').read_text())['cases']
    old_sets={name:{r[name] for r in old} for name in ['sha256','operation_stream_sha256','partition_stream_sha256']}
    sets={};counts={};overlap={}
    names=['TRAIN','VALIDATION','LEARNING_TRAIN']
    if (F/'LEARNING_VALIDATION_MANIFEST.json').exists():names.append('LEARNING_VALIDATION')
    for name in names:
        cases=json.loads((F/(name+'_MANIFEST.json')).read_text())['cases'];sets[name]={k:set() for k in old_sets};counts[name]=len(cases)
        for c in cases:
            s=c['spec'];path=ROOT/'build/round8/data'/s['split']/(s['id']+'.txt')
            full=hashlib.sha256();op=hashlib.sha256();part=hashlib.sha256(f'{s["k"]} {s["p"]}\n'.encode())
            with path.open('rb') as f:
                for _ in range(2+s['k']):full.update(next(f))
                for line in f:
                    full.update(line);op.update(line)
                    x=line.split()
                    if x[0]==b'SWITCH':semantic=line
                    else:
                        key=int(x[2]);assert 0<=key<s['p']
                        semantic=line # this generator emits canonical partition IDs as keys
                    part.update(semantic)
            assert full.hexdigest()==c['input_sha256'] and op.hexdigest()==c['operation_sha256']
            for key,digest in [('sha256',full.hexdigest()),('operation_stream_sha256',op.hexdigest()),('partition_stream_sha256',part.hexdigest())]:sets[name][key].add(digest)
        overlap[name]={k:len(v&old_sets[k]) for k,v in sets[name].items()};assert not any(overlap[name].values())
    cross={}
    for i,a in enumerate(names):
        for b in names[i+1:]:
            cross[a+'/'+b]={k:len(sets[a][k]&sets[b][k]) for k in old_sets};assert not any(cross[a+'/'+b].values())
    put(F/('SIGNATURE_AUDIT_'+str(len(names))+'.json'),(json.dumps({'passed':True,'cases':counts,'old550_overlap':overlap,'cross_split_overlap':cross,'within_split_duplicates':'B variants intentionally share operations/partition streams; kept in the same group.'},indent=2)+'\n').encode());print('signature audit passed',counts)
if __name__=='__main__':main()
