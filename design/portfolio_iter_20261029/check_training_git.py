"""Bind frozen train measurements to exact blobs in the pinned Git commit."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
COMMIT='e119c2326e198922243306eac062785420ed8156'
def read(path):return json.loads(path.read_text('utf8'))
def main():
    tags=['train_g0_840','train_g1_840','train_g2_840'];reports=[read(ROOT/(tag+'_summary.json')) for tag in tags]
    identity=reports[0]['input_identity'];assert len(identity)==840 and all(r['input_identity']==identity for r in reports)
    wanted=[]
    for row in identity:
        assert '/train/' in row['input'] and '/eval/' not in row['input']
        wanted.append((COMMIT+':datasets/'+row['input'],row['sha256']))
        if row['metadata_sha256']:
            wanted.append((COMMIT+':datasets/'+row['input'][:-4]+'.meta.json',row['metadata_sha256']))
    for start in range(0,len(wanted),128):
        block=wanted[start:start+128];data=subprocess.run(['git','cat-file','--batch'],cwd=PROJECT,input=('\n'.join(path for path,expected in block)+'\n').encode('utf8'),capture_output=True,check=True).stdout;offset=0
        for path,expected in block:
            end=data.index(b'\n',offset);fields=data[offset:end].split();assert len(fields)==3 and fields[1]==b'blob',path
            count=int(fields[2]);body=data[end+1:end+1+count];assert hashlib.sha256(body).hexdigest()==expected,path
            offset=end+count+2
        assert offset==len(data)
    result=dict(pinned_git_commit=COMMIT,train_inputs=840,metadata_files=len(wanted)-840,all_frozen_input_and_metadata_sha256_match_git_blobs=True,
        train_suite_id=reports[0]['train_suite_id'],reports=tags,
        original_report_revision_fields=[r['dataset_revision'] for r in reports],
        note='Frozen WSL reports kept dataset_revision=unknown because their Windows worktree locator is not readable by WSL git. This separate native Git blob check binds all originally recorded file digests to the pinned commit without editing those reports.')
    (ROOT/'training_git_provenance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
