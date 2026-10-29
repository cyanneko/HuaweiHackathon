"""Explicit-only admission checks. Never builds/runs the shared SDK implicitly.

Pure patch checks: python test_admission.py --patch-only --tag patch-001
C++ branch harness: python test_admission.py --harness --tag harness-001
Existing SDK toy: python test_admission.py --sdk --ids 92,98,99,108,109 --tag sdk-001
All generated sources, toys and results stay under admission_checks/<new-tag>/.
Do not run --harness/--sdk during another timing window. No shared files change.
"""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, os, re, subprocess

ROOT=Path(__file__).resolve().parent
DESIGN=ROOT.parent
MIB=1<<20

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text('utf8'))
def relative(p,run):return os.path.relpath(p,run).replace('\\','/')
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def rejected(fn,kind):
    try:fn()
    except kind:return
    raise AssertionError('Expected '+kind.__name__)

def periodic_window(source):
    start=source.index('    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {')
    depth=0
    for i in range(source.index('{',start),len(source)):
        if source[i]=='{':depth+=1
        elif source[i]=='}':
            depth-=1
            if depth==0:return start,i+1
    raise AssertionError('Unclosed periodic function')

def pure_checks(source):
    patch_path=ROOT/'admission_patch.py';body=patch_path.read_text('utf8');tree=ast.parse(body)
    for node in tree.body:
        assert isinstance(node,(ast.Assign,ast.FunctionDef,ast.Expr))
        if isinstance(node,ast.Expr):assert isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)
        if isinstance(node,ast.Assign):assert not any(isinstance(x,ast.Call) for x in ast.walk(node.value))
    # Import into a module namespace from the audited AST without .pyc writes.
    spec=importlib.util.spec_from_file_location('admission_patch_pure_test',patch_path)
    module=importlib.util.module_from_spec(spec);exec(compile(tree,patch_path.name,'exec'),module.__dict__)
    lf=source.replace('\r\n','\n');patched={};checks=0
    for ending,original in [('LF',lf),('CRLF',lf.replace('\n','\r\n'))]:
        begin,end=periodic_window(original)
        for shift in range(4):
            result=module.patch(original,shift);a,b=periodic_window(result)
            assert result[:a]==original[:begin] and result[b:]==original[end:]
            assert result.count('// PERIODIC_ADMISSION_V1')==1
            assert f'const int64_t admission_factor=int64_t(1)<<{shift};' in result
            if ending=='LF':assert '\r' not in result
            else:assert '\n' not in result.replace('\r\n','') and '\r' not in result.replace('\r\n','')
            rejected(lambda:module.patch(result,shift),ValueError)
            rejected(lambda:module.patch(result,(shift+1)%4),ValueError)
            checks+=1
            if ending=='LF':patched[shift]=result
    for bad in [-1,4,True,False,None,1.0,'0']:
        rejected(lambda bad=bad:module.patch(lf,bad),ValueError);checks+=1
    rejected(lambda:module.patch(None,0),TypeError)
    rejected(lambda:module.patch(lf.replace('\n','\r'),0),ValueError)
    rejected(lambda:module.patch(lf.replace('onPeriodicAdjust(', 'renamedPeriodic(',1),0),ValueError)
    return patched,dict(status='passed',patch_sha256=sha(patch_path),LF_CRLF_shift_checks=8,
                        invalid_shift_checks=7,repeat_rejection=True,non_periodic_source_identity=True,
                        module_loaded_without_bytecode_writes=True,extra_rejection_checks=3)

HARNESS=r'''
#include <stdexcept>
#include <iostream>
#include "@TYPES@"
#define MySpillScheduler AdmissionBase
#include "@BASE@"
#undef MySpillScheduler
@CANDIDATES@
static const int64_t MiB=1LL<<20;
static SystemState state(int64_t a,int64_t b,int64_t c){
    SystemState s{};s.memory_limit=64*MiB;s.memory_used=a+b+c;s.num_partitions=3;
    s.write_bandwidth=100;s.read_bandwidth=100;s.hit_count=1;s.miss_count=0;s.total_io_bytes=0;
    OperatorState o;o.op_id=0;o.phase=Phase::BUILD;o.partitions.resize(3);
    const int64_t sizes[3]={a,b,c};for(int i=0;i<3;++i){o.partitions[i].partition_id=i;o.partitions[i].data_size=sizes[i];o.partitions[i].in_memory=true;}
    s.operators.push_back(o);s.next_op.type="INSERT";s.next_op.op_id=0;s.next_op.key=1;s.next_op.tuple_size=MiB;return s;
}
static void require(bool value,const char* why){if(!value)throw std::runtime_error(why);}
template<class Scheduler>static void check(SystemState s,int expectation,bool consistent=true){
    Scheduler policy(0); // Fixed expert0 removes router/history ambiguity in the fallback.
    auto actions=policy.onPeriodicAdjust(s);
    if(expectation==1)require(actions.size()==1&&actions[0].partition_id==1,"target admission not selected");
    if(expectation==0)require(!actions.empty(),"expected positive fallback victim");
    if(expectation==-1)require(actions.empty(),"no-pressure/no-other should return empty");
    bool removed[3]={false,false,false};int64_t used=s.memory_used;
    for(const auto& a:actions){
        require(a.type==Action::SPILL&&a.op_id==0&&a.partition_id>=0&&a.partition_id<3,"invalid action");
        const int p=a.partition_id;require(!removed[p]&&s.operators[0].partitions[p].data_size>0,"duplicate or zero SPILL");
        if(expectation<=0)require(p!=1,"admission target should be rejected");
        removed[p]=true;used-=s.operators[0].partitions[p].data_size;
    }
    if(consistent){require(used>=0&&used<=s.memory_limit,"post-action memory invariant");}
}
template<class Scheduler>static int suite(int shift){
    check<Scheduler>(state(63*MiB,MiB,0),1); // Growing tiny B, giant A.
    check<Scheduler>(state(64*MiB,0,0),0);  // Zero B must not be admitted.
    const int64_t cutoff=(2*MiB)*(1LL<<shift);
    check<Scheduler>(state(cutoff,MiB,63*MiB-cutoff),1); // Equality is accepted.
    check<Scheduler>(state(cutoff-1,MiB,63*MiB-cutoff+1),0); // One-byte-smaller victim rejects.
    check<Scheduler>(state(0,MiB,0),-1); // Physically valid no-other/no-pressure state.
    auto synthetic=state(0,MiB,0);synthetic.memory_used=64*MiB;
    check<Scheduler>(synthetic,-1,false); // Defensive branch only: intentionally inconsistent accounting.
    return 6;
}
int main(){try{check<AdmissionBase>(state(63*MiB,MiB,0),0);
    int n=1+suite<Admission0>(0)+suite<Admission1>(1)+suite<Admission2>(2)+suite<Admission3>(3);
    std::cout<<"passed "<<n<<" branch checks\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
'''

def harness(run,base,patched,cxx):
    includes=''
    for shift,text in patched.items():
        p=run/f'patched_shift{shift}.cpp';p.write_bytes(text.encode('utf8'))
        includes+=f'#define MySpillScheduler Admission{shift}\n#include "{p.name}"\n#undef MySpillScheduler\n'
    body=HARNESS.replace('@TYPES@',relative(DESIGN/'neural_selector/reference_types.hpp',run)).replace('@BASE@',relative(base,run)).replace('@CANDIDATES@',includes)
    cpp=run/'branch_harness.cpp';binary=run/('branch_harness.exe' if os.name=='nt' else 'branch_harness');cpp.write_bytes(body.encode('utf8'))
    subprocess.run([cxx,'-std=c++14','-O2',str(cpp),'-o',str(binary)],check=True)
    out=subprocess.run([str(binary)],capture_output=True,text=True,check=True)
    return dict(status='passed',stdout=out.stdout.strip(),binary_sha256=sha(binary),
                note='The no-other-pressure synthetic state is only a defensive branch test; not a formal workload or timing result.')

def sdk_toy(run,args,registry):
    ops=[('INSERT',0,0,MIB)]*63+[('INSERT',0,1,MIB)]*10+[('SWITCH',0)]+[('PROBE',0,0)]*128+[('PROBE',0,1)]
    path=run/'admission_A63_B1_to10.txt';text=f'1 2 {64*MIB} 100 100 1000\n{len(ops)} 1\n0 73 129\n'+'\n'.join(' '.join(map(str,o)) for o in ops)+'\n';path.write_bytes(text.encode('ascii'))
    public=DESIGN/'member_eval_20261030/worktree/evaluation/scripts/audit_datasets.py'
    spec=importlib.util.spec_from_file_location('admission_toy_public_auditor',public);module=importlib.util.module_from_spec(spec)
    exec(compile(public.read_bytes(),public.name,'exec'),module.__dict__)
    stats=module.audit_case(path,enforce_limits=True);assert stats['sha256']==sha(path)
    modes=list(map(int,args.ids.split(',')));assert len(modes)==len(set(modes)) and args.base_id in modes
    assert all(m in registry for m in modes)
    binary_hash=sha(args.engine);rows=[]
    for rep in range(args.repeats):
        for mode in (modes if rep%2==0 else modes[::-1]):
            p=subprocess.run([str(args.engine),str(path),str(mode)],capture_output=True,text=True,check=True,timeout=60)
            v={k:float(x) for k,x in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([\d.eE+-]+)',p.stdout)}
            assert len(v)==5 and v['Hit_Count']+v['Miss_Count']==129
            assert abs(v['Total_Score']-v['Total_IO_Time']-1000*v['Miss_Count']-v['Total_Decision_Time'])<.015001
            rows.append(dict(mode=mode,repeat=rep,**v))
    assert sha(args.engine)==binary_hash,'Shared engine changed during explicit toy measurement'
    means={str(m):{k:sum(r[k] for r in rows if r['mode']==m)/args.repeats for k in ['Total_IO_Time','Total_Decision_Time','Miss_Count','Total_Score']} for m in modes}
    baseline=means[str(args.base_id)]['Total_Score']
    for item in means.values():item['score_decrease_vs_base_percent']=100*(1-item['Total_Score']/baseline) if baseline else None
    return dict(input=path.name,input_sha256=sha(path),formal_public_audit=True,engine_sha256=binary_hash,
                modes={str(m):registry[m]['name'] for m in modes},repeats=args.repeats,rows=rows,means=means,
                action_legality='Score/output consistency only; independent full-trace audit remains a separate root step.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True)
    p.add_argument('--patch-only',action='store_true');p.add_argument('--harness',action='store_true');p.add_argument('--sdk',action='store_true')
    p.add_argument('--base-id',type=int,default=92);p.add_argument('--ids',default='92,98,99,108,109');p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--engine',type=Path,default=ROOT/'engine');p.add_argument('--cxx',default='g++');args=p.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',args.tag) and args.repeats>0
    assert not(args.patch_only and(args.harness or args.sdk))
    run=ROOT/'admission_checks'/args.tag
    if run.exists():raise FileExistsError('Choose a unique --tag; prior toys/results are not overwritten')
    registry={v['id']:v for v in read(ROOT/'variants.json')};base=ROOT/registry[args.base_id]['source']
    assert sha(base)==registry[args.base_id]['sha256']
    patched,pure=pure_checks(base.read_bytes().decode('utf8'));run.mkdir(parents=True)
    result=dict(base_id=args.base_id,base_source_sha256=sha(base),pure_patch=pure,
                source_inputs_published=False,generated_data_role='Local toy only; no training/eval files are changed.')
    if args.harness:result['branch_harness']=harness(run,base,patched,args.cxx)
    if args.sdk:result['sdk_toy']=sdk_toy(run,args,registry)
    dump(run/'result.json',result);print('Admission checks saved:',run.relative_to(ROOT).as_posix())
if __name__=='__main__':main()
