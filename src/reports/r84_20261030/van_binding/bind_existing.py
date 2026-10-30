"""Reuse a verified identical C++14/O2 build after checking latest upstream identity."""
import json,hashlib,copy,platform,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def path(p):return Path(p) if Path(p).is_absolute() else ROOT/p
assert not (HERE/'producer.json').exists()
contract_path=ROOT/'tmp/van_latest_reference_20261030/d92ceb0262b5/contract.json';contract=read(contract_path)
source=contract_path.parent/'paired_penalty100.cpp';assert sha(source)==contract['source_sha256']
assert contract['status']=='FIXED_CURRENT_ENTRY_BLOB_VERIFIED' and not contract['source_modified']
assert contract['remote_commit']=='d92ceb0262b556eb57aae61127d062174ffe6016'
assert hashlib.sha1(b'blob '+str(len(source.read_bytes())).encode()+b'\0'+source.read_bytes()).hexdigest()==contract['git_blob']
reference=ROOT/'tmp/r80_lazy_eval/final/selection.json'
old=next(m for m in read(reference)['methods'] if m['name']=='Van_paired_penalty100')
for field,digest in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(old[field]))==old[digest]
assert source.read_bytes()==path(old['source_path']).read_bytes()
assert old['compile_flags']==['-std=c++14','-O2'] and old['instrumented'] is False
src=source.read_text(encoding='utf-8-sig');tu=path(old['translation_unit_path']).read_text(encoding='utf-8-sig')
assert tu.count(src)==1
assert hashlib.sha256(tu.replace(src,'<SCHEDULER>').encode()).hexdigest()=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
assert path(old['binary']).read_bytes()[:4]==b'\x7fELF'
oldtests=ROOT/'tmp/r79_adaptive_operator/test_summary.json';tests=read(oldtests);assert tests['status']=='PASS'
records=[r for r in tests['records'] if r.get('argv')==['g++','-std=c++14','-O2',str(path(old['translation_unit_path'])),'-o',str(path(old['binary']))]]
assert len(records)==1 and records[0]['returncode']==0
assert records[0]['argv'][:3]==['g++','-std=c++14','-O2']
m=copy.deepcopy(old);m.update(name='Van_latest',source_path=str(source.relative_to(ROOT)),source_commit=contract['remote_commit'],source_branch=contract['branch'],upstream_source_path=contract['source_path'],upstream_url=contract['url'],build_strategy='REUSE_VERIFIED_IDENTICAL_SOURCE_TU_ELF',previous_method_name=old['name'])
proof=dict(status='VERIFIED_LATEST_SUBMITTABLE_AT_CAPTURE',method_name=m['name'],source_commit=m['source_commit'],source_sha256=m['source_sha256'],source_branch=contract['branch'],source_repo_path=contract['source_path'],unmodified_class_behavior=True,evidence_path=str(contract_path.relative_to(ROOT)),evidence_sha256=sha(contract_path),latest_branch_head_at_capture=contract['remote_commit'],same_source_as_prior=True)
save(HERE/'latest_proof.json',proof)
save(HERE/'test_summary.json',dict(status='PASS',scope='Identity/framework and existing successful compile record verification; no new solver test or compilation',source_blob_sha1_verified=True,source_TU_ELF_sha_verified=True,framework_unchanged=True,old_compile_record=records[0],old_test_summary_path=str(oldtests.relative_to(ROOT)),old_test_summary_sha256=sha(oldtests),native_runs=0,compile_runs=0))
producer=dict(status='READY',framework_unchanged=True,variants=[m],source_reference_path=str(reference.relative_to(ROOT)),source_reference_sha256=sha(reference),upstream_evidence_sha256=sha(contract_path),latest_proof_sha256=sha(HERE/'latest_proof.json'),build_strategy=m['build_strategy'],native_runs=0,compile_runs=0)
save(HERE/'producer.json',producer)
save(HERE/'environment.json',dict(platform=platform.platform(),uname=subprocess.check_output(['uname','-a'],text=True).strip(),compiler_current=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],cpu=subprocess.check_output(['lscpu'],text=True),performance_scope='WSL CPU serial single repeat; no GPU; current environment disclosure does not replace immutable prior compiler record'))
save(HERE/'release.json',dict(status='RELEASED',ready=True,final=True,active_child_processes=0,producer_sha256=sha(HERE/'producer.json'),test_summary_sha256=sha(HERE/'test_summary.json')))
print(json.dumps(dict(status='READY',source_sha256=m['source_sha256'],source_commit=m['source_commit'],producer_sha256=sha(HERE/'producer.json'),proof_sha256=sha(HERE/'latest_proof.json'),new_compile_runs=0,new_solver_runs=0)))
