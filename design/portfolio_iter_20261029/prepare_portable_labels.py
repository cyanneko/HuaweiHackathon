"""Publish compact training labels with relative inputs and unchanged numbers."""
from pathlib import Path
import collections,gzip,hashlib,io,json
ROOT=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')
def main():
    out=[]
    for stem in ['round3','members_train_r2']:
        source=ROOT/(stem+'_labels.jsonl');raw=source.read_bytes();numeric=hashlib.sha256();new_numeric=hashlib.sha256();buf=io.BytesIO();members=collections.Counter();groups=set();rows=0
        with gzip.GzipFile(filename='',mode='wb',fileobj=buf,mtime=0,compresslevel=9) as stream:
            for line in raw.splitlines():
                row=json.loads(line);path=row['file'].replace('\\','/');relative=path.rsplit('/datasets/',1)[1]
                assert '/train/' in relative and '/eval/' not in relative
                numbers={k:v for k,v in row.items() if k!='file'};numeric.update(canonical(numbers))
                row['file']='datasets/'+relative;stream.write(canonical(row));new_numeric.update(canonical({k:v for k,v in row.items() if k!='file'}))
                members[relative.split('/')[0]]+=1;groups.add(relative);rows+=1
        packed=buf.getvalue();target=ROOT/(stem+'_labels.portable.jsonl.gz')
        if target.exists():assert target.read_bytes()==packed
        else:target.write_bytes(packed)
        assert numeric.hexdigest()==new_numeric.hexdigest()
        replay=[json.loads(line) for line in gzip.decompress(packed).splitlines()];assert len(replay)==rows
        h=hashlib.sha256()
        for row in replay:h.update(canonical({k:v for k,v in row.items() if k!='file'}))
        assert h.hexdigest()==numeric.hexdigest()
        out.append(dict(source=source.name,source_sha256=sha(raw),portable=target.name,portable_sha256=sha(packed),bytes=len(packed),rows=rows,represented_train_inputs=len(groups),rows_by_member=dict(members),numeric_fields_identical=True,numeric_semantic_sha256=numeric.hexdigest(),only_changed_field='file: datasets/<member>/train/<filename>',eval_rows=0))
    (ROOT/'portable_labels_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
