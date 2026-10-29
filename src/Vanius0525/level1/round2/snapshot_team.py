"""Read only dataset manifests and eval inputs from an immutable Git revision."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE=Path(__file__).resolve().parents[1]
REPO=BASE.parents[2]

def snapshot(revision,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    git=['git','-C',str(REPO),'-c','extensions.partialClone=origin','-c','remote.origin.promisor=true','-c','remote.origin.partialclonefilter=blob:none']
    members={};targets=[]
    for member in ['cyanneko','liunianwww']:
        raw=subprocess.check_output(git+['show',revision+f':datasets/{member}/manifest.json'])
        d=json.loads(raw);entries=[x for x in d['cases'] if x['split']=='eval']
        members[member]={'manifest':raw,'entries':entries,'version':d.get('eval_version',d.get('version'))}
        targets += [x['path'] for x in entries]+[f'datasets/{member}/eval/VERSION']
    size=sum(x['bytes'] for v in members.values() for x in v['entries'])
    assert size<1<<30,'Report and confirm a >1GiB download before running'
    tree=subprocess.check_output(git+['ls-tree','-r','-z',revision,'datasets'])
    objects={}
    for row in tree.split(b'\0'):
        if not row:continue
        meta,path=row.split(b'\t',1);kind=meta.split()
        if kind[1]==b'blob':objects[path.decode()]=kind[2].decode()
    wants=sorted({objects[path] for path in targets})
    print(json.dumps({'revision':revision,'eval_inputs':sum(len(v['entries']) for v in members.values()),'eval_bytes':size,'wanted_blobs':len(wants),'algorithm_content_requested':False}),flush=True)
    # One batch of explicitly selected eval blobs, no algorithm source requests.
    proc=subprocess.run(git+['fetch','--no-tags','--no-write-fetch-head','--filter=blob:none','origin','--stdin'],input='\n'.join(wants)+'\n',capture_output=True,text=True,timeout=240)
    if proc.returncode:raise RuntimeError(proc.stderr[-3000:])
    source={'revision':revision,'members':{},'algorithm_content_read':False}
    for member,v in members.items():
        root=out/member;root.mkdir(exist_ok=True);(root/'manifest.json').write_bytes(v['manifest'])
        for entry in v['entries']:
            path=entry['path'];content=subprocess.check_output(git+['show',revision+':'+path])
            assert len(content)==entry['bytes'] and hashlib.sha256(content).hexdigest()==entry['sha256'],path
            target=out/Path(path).relative_to('datasets');target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert target.read_bytes()==content
            else:target.write_bytes(content)
        version=subprocess.check_output(git+['show',revision+f':datasets/{member}/eval/VERSION'])
        (root/'eval/VERSION').write_bytes(version)
        source['members'][member]={'version':version.decode().strip(),'cases':len(v['entries']),'bytes':sum(x['bytes'] for x in v['entries']),'manifest_sha256':hashlib.sha256(v['manifest']).hexdigest()}
        print(json.dumps({member:source['members'][member]}),flush=True)
    (out/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--revision',required=True);p.add_argument('--out',required=True,type=Path);a=p.parse_args();snapshot(a.revision,a.out)
