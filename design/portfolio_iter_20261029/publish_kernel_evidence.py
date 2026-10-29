"""Make a portable copy of the completed cross-language check; never retime it."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]

def semantic_leaves(value):
    if isinstance(value,dict):return [x for v in value.values() for x in semantic_leaves(v)]
    if isinstance(value,list):return [x for v in value for x in semantic_leaves(v)]
    if isinstance(value,(int,float,bool)) or (isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value)):
        return [value]
    return []

def main():
    source=ROOT/'mlp_checks/full108_cpp_numpy_r1/result.json'
    target=ROOT/'cheap_mlp_kernel_verification.json'
    if target.exists():raise FileExistsError('Existing evidence is immutable')
    raw=source.read_bytes();original=json.loads(raw)
    assert original['status']=='verified' and original['mismatches']==0
    windows=PROJECT.as_posix()
    linux='/mnt/'+windows[0].lower()+windows[2:] if windows[1:2]==':' else windows
    def portable(value):
        if isinstance(value,dict):return {portable(k):portable(v) for k,v in value.items()}
        if isinstance(value,list):return [portable(v) for v in value]
        if isinstance(value,str):
            normalized=value.replace('\\','/')
            if windows in normalized or linux in normalized:
                normalized=normalized.replace(windows+'/','').replace(linux+'/','')
                return normalized.replace(windows,'.').replace(linux,'.')
        return value
    published=portable(original)
    assert semantic_leaves(published)==semantic_leaves(original)
    published['publication']=dict(original_result_sha256=hashlib.sha256(raw).hexdigest(),
        source_result=source.relative_to(PROJECT).as_posix(),
        only_project_path_metadata_normalized=True,numeric_values_and_hashes_unchanged=True,
        original_result_modified=False,no_solver_or_compiler_invoked=True)
    body=(json.dumps(published,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    assert b'/mnt/' not in body and b':/Users/' not in body and b':\\\\Users' not in body
    with target.open('xb') as stream:stream.write(body)
    print('Portable kernel evidence:',target.name)

if __name__=='__main__':main()
