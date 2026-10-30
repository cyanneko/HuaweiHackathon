"""Freeze and audit existing AI weights across Python/exported C++14, no training."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,itertools,json,math,random,re,struct,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
from build import FROZEN,FROZEN_SHA,REPO
from round9.cost_replay_precise import parse_input
from audit_next_action_v1 import Ledger,trace_lines
from ai100_model_io_v1 import f32,bits32,bits64,frombits32,read_model,flat,forward,export,declarations,function_span,features
SOURCE=ROOT/'round9/candidates/ai_penalty100.cpp'
SOURCE_SHA='e721f4a030fd519df8946230ab44660b1d69508a43a23ba8e65cae017527b2fa'
OUT=HERE/'build/ai100_export_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,s):
    if p.exists():assert p.read_text()==s,p
    else:p.write_text(s)
def save(p,x):put(p,json.dumps(x,indent=2)+'\n')
def make_vectors(model):
    rng=random.Random(99103014);rows=[]
    for j in range(4096):
        v=[f32(rng.random()) for _ in range(12)]
        for i in [4,5,6]:v[i]=float(rng.randrange(2))
        v[10]=rng.randrange(9)/8;p=rng.choice([2,4,8,16,32,64]);v[11]=f32(rng.randint(1,p)/p)
        rows.append({'kind':'seeded_component_domain','f':v})
    continuous=[0,1,2,3,7,8,9]
    for level in [0.,1.]:
        v=[level]*12;v[11]=1.;rows.append({'kind':'closed_component_boundary','f':v})
    base=[.5]*12;base[4:7]=[1.,1.,0.];base[10]=0.;base[11]=1.
    relu=[]
    for j in range(16):
        for i in continuous:
            if model['W0'][i][j]==0:continue
            b=model['B0'][j]
            for l in range(12):
                if l!=i:b+=base[l]*model['W0'][l][j]
            root=-b/model['W0'][i][j]
            if not 0<root<1:continue
            center=bits32(f32(root))
            for offset in [-1,0,1]:
                v=base.copy();v[i]=frombits32(center+offset);rows.append({'kind':'relu_boundary','unit':j,'axis':i,'offset':offset,'f':v})
            relu.append(j);break
    clamp_found=[];search_rng=random.Random(9910301401)
    for target in [0.,1.]:
        found=False
        for categorical in itertools.product([0.,1.],repeat=3):
            candidates=[]
            for _ in range(128):
                v=[f32(search_rng.random()) for _ in range(12)];v[4:7]=list(categorical);v[10]=0.;v[11]=1.
                candidates.append((forward(model,v,raw=True)[0],v))
            low=min(candidates,key=lambda x:x[0]);high=max(candidates,key=lambda x:x[0])
            if not low[0]<target<high[0]:continue
            lo,hi=0.,1.
            for _ in range(64):
                mid=(lo+hi)/2;v=[f32(a+(b-a)*mid) for a,b in zip(low[1],high[1])]
                if forward(model,v,raw=True)[0]<target:lo=mid
                else:hi=mid
            for label,t in [('below',lo),('above',hi)]:
                rows.append({'kind':'output_clip_boundary','target':target,'side':label,'f':[f32(a+(b-a)*t) for a,b in zip(low[1],high[1])]})
            clamp_found.append(target);found=True;break
        if not found:clamp_found.append({'target':target,'not_bracketed_by_fixed_search':True})
    return rows,{'seed':99103014,'base_vectors':4096,'relu_units_bracketed':relu,'output_clip_search':clamp_found,'component_domain_not_joint_reachability':True}
def feature_cases():
    rows=[]
    for j in range(64):
        m=[64<<20,4<<30][j%2];p=[2,8,64][j%3];known=j%8!=0;phase=1 if known else j%2
        q=2000000+j;age=[0,1,2,65534,65535,65536,1000000,7][j%8];gap=[1,2,65534,65535,65536][j%5]
        last=q-age if known else -1;previous=last-gap if known and last>=gap and j%4 else -1
        size=[1,m//16,m//2,m][j%4];used=max(size,[size,m][j%2]);need=[1,size,m//2,m][(j//4)%4]
        streak=[0,3,6,8][j%4];distance=[1,p//2,p][j%3]
        rows.append({'id':j,'p':p,'memory':m,'size':size,'used':used,'need':need,'q':q,'previous':previous,'last':last,
                     'count':min(16.,(j%23)*.75) if known else 0.,'observed':q//2 if known else 0,
                     'streak':streak,'distance':distance,'phase':phase,'same_context':j%2})
    return rows
def make_fixture(index):
    rng=random.Random(99103015+index);m=64<<20;k=2;p=8;b=[1,17,64,1021][index%4];w=r=10000
    if index<4:sizes=[8<<20]*16
    elif index<8:sizes=[x<<20 for x in [1,2,4,8,16,12,10,6]*2]
    elif index<12:sizes=[m]+[1<<20]*15
    else:
        p=2;sizes=[m,10240000+[-1,0,1,0][index-12],1,1];b=1
    builds=[0]*k;ops=[]
    # Complete valid INSERT streams; the original scheduler sees every overflow.
    for flat_id,total in enumerate(sizes):
        op,pid=divmod(flat_id,p);remaining=total
        while remaining:
            z=min(1<<20,remaining);ops.append(f'INSERT {op} {pid} {z}');builds[op]+=1;remaining-=z
    ops.extend(['SWITCH 0','SWITCH 1']);probes=[0]*k
    for j in range(512):
        if index>=12:id=0 if j%2==0 else 1
        elif index%4==0:id=j%(k*p)
        elif index%4==1:id=rng.randrange(k*p)
        elif index%4==2:id=rng.choice([0,1,2]) if j%5 else rng.randrange(k*p)
        else:id=(j//32+j%3)%(k*p)
        op,pid=divmod(id,p);ops.append(f'PROBE {op} {pid}');probes[op]+=1
    return '\n'.join([f'{k} {p} {m} {w} {r} 100',f'{len(ops)} {b}']+[f'{o} {builds[o]} {probes[o]}' for o in range(k)]+ops)+'\n'
def weight_dump(name,decl,bias):
    return 'static std::vector<double> '+name+'(){\n'+'\n'.join(decl)+'\nstd::vector<double> v;for(int i=0;i<12;++i)for(int j=0;j<16;++j)v.push_back(W0[i][j]);for(double x:B0)v.push_back(x);for(double x:W1)v.push_back(x);v.push_back('+bias+');return v;}\n'
def make_source(source,model,original_decls,bias):
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    official=next(x for x in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in x).replace('\xa0',' ')
    decl=official.split('class NaiveSpillScheduler',1)[0]
    original=source.replace('MySpillScheduler','OriginalAI').replace('class OriginalAI : public SpillScheduler {','class OriginalAI : public SpillScheduler {\npublic:')
    original=original.replace('    double neural(const float* f) const {','    double neural(const float* f) const {\n        ++original_neural_calls;')
    start,end=function_span(source);replacement='    double neural(const float* f) const { ++exported_neural_calls; return ai100_exported_neural(f); }'
    exported=(source[:start]+replacement+source[end:]).replace('MySpillScheduler','ExportedAI').replace('class ExportedAI : public SpillScheduler {','class ExportedAI : public SpillScheduler {\npublic:')
    # Final planner code outside the neural function stays byte-for-byte equal.
    assert source[:start]+source[end:]==(source[:start]+replacement+source[end:])[:start]+(source[:start]+replacement+source[end:])[start+len(replacement):]
    text=(HERE/'ai100_export_check_v1.cpp').read_text()
    return text.replace('// OFFICIAL_DECLARATIONS',decl).replace('// EXPORTED_NEURAL',export(model)).replace('// ORIGINAL_POLICY',original).replace('// EXPORTED_POLICY',exported).replace('// WEIGHT_DUMPS',weight_dump('originalWeights',original_decls,bias)+weight_dump('exportedWeights',declarations(model),format(model['b'],'.17g')))
def fixture_audit(path,trace,reported):
    header,ops=parse_input(path);ledger=Ledger(header);lines=trace_lines(trace);pointer=0;actions=0
    coverage={'overflow_callbacks':0,'miss_callbacks':0,'periodic_callbacks':0,'periodic_load_callbacks':0,'multi_spill_callbacks':0,'exact_release_callbacks':0,
              'periodic_pressure_lower_risk_below2048':0,'periodic_pressure_lower_risk_equal2048':0,'periodic_pressure_lower_risk_above2048':0}
    for raw,op in enumerate(ops):
        def callback(tag,o,pid,z):
            nonlocal pointer,actions
            need=0
            if tag=='O':coverage['overflow_callbacks']+=1;need=max(0,z-(ledger.m-ledger.used))
            elif tag=='M':coverage['miss_callbacks']+=1;need=max(0,ledger.sizes[o*ledger.p+pid]-(ledger.m-ledger.used))
            else:
                coverage['periodic_callbacks']+=1
                if raw+1<len(ops) and ops[raw+1][0]=='PROBE':
                    _,next_o,next_p=ops[raw+1];id=next_o*ledger.p+next_p
                    if not ledger.mem[id]:
                        need=max(0,ledger.sizes[id]-(ledger.m-ledger.used))
                        if need:
                            risk=need*(1/ledger.w+1/ledger.r);key='equal' if abs(risk-2048)<1e-9 else 'below' if risk<2048 else 'above'
                            coverage['periodic_pressure_lower_risk_'+key+'2048']+=1
            acts=ledger.apply(lines[pointer],tag,o,pid,z);pointer+=1;actions+=len(acts)
            spills=[a for a in acts if a[0]=='S'];freed=sum(ledger.sizes[a[1]*ledger.p+a[2]] for a in spills)
            coverage['multi_spill_callbacks']+=len(spills)>1;coverage['exact_release_callbacks']+=bool(need and freed==need)
            coverage['periodic_load_callbacks']+=tag=='P' and any(a[0]=='L' for a in acts)
        ledger.step(op,callback)
    assert pointer==len(lines)
    for key in ['writes','reads','hits','misses','used']:assert reported[key]==getattr(ledger,key)
    assert reported['callbacks']==pointer and reported['actions']==actions
    return {'input_legal':True,'independent_actions_bytes_counts_pass':True,'coverage':coverage,'neural_calls_per_copy':reported['neural_calls_per_copy'],'callbacks':pointer}
def main():
  OUT.mkdir(exist_ok=True)
  with experiment_lock():
    assert sha(SOURCE)==SOURCE_SHA;source=SOURCE.read_text();model,decls,bias=read_model(source)
    assert len(flat(model))==225
    save(HERE/'AI100_MODEL_V1.json',{'source_sha256':SOURCE_SHA,**model})
    reloaded=json.loads((HERE/'AI100_MODEL_V1.json').read_text());assert list(map(bits64,flat(model)))==list(map(bits64,flat(reloaded)))
    put(HERE/'ai100_neural_export_v1.hpp',export(model))
    vectors,vector_scope=make_vectors(model);feature_rows=feature_cases();save(OUT/'vectors.json',vectors);save(OUT/'feature_cases.json',feature_rows)
    put(OUT/'vectors.txt',''.join(str(i)+' '+' '.join(format(x,'.17g') for x in row['f'])+'\n' for i,row in enumerate(vectors)))
    keys=['p','memory','size','used','need','q','previous','last','count','observed','streak','distance','phase','same_context']
    put(OUT/'features.txt',''.join(str(c['id'])+' '+' '.join(str(c[k]) for k in keys)+'\n' for c in feature_rows))
    fixture_files=[]
    for i in range(16):
      f=OUT/('fixture_'+str(i)+'.txt');put(f,make_fixture(i));parse_input(f);fixture_files.append(f)
    cpp=OUT/'check.cpp';put(cpp,make_source(source,model,decls,bias));exe=OUT/'check'
    if not exe.exists():
      proc=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic',str(cpp),'-o',str(exe)],capture_output=True,text=True)
      put(OUT/'compile.log',proc.stderr);proc.check_returncode()
    names=['AI100_EXPORT_PLAN_V1.md','AI100_MODEL_V1.json','ai100_neural_export_v1.hpp','ai100_model_io_v1.py','ai100_export_check_v1.cpp','run_ai100_export_v1.py']
    freeze={'scope':'existing ai100 export/feature/action engineering only; no training or dataset evaluation','files':{n:sha(HERE/n) for n in names},
            'source_sha256':SOURCE_SHA,'official_declarations_source_sha256':FROZEN_SHA,'generated_cpp_sha256':sha(cpp),
            'vector_generation':vector_scope,'feature_cases':64,'total_numeric_vectors':len(vectors),
            'input_files':{p.name:sha(p) for p in [OUT/'vectors.json',OUT/'vectors.txt',OUT/'feature_cases.json',OUT/'features.txt']+fixture_files},
            'fixture_seed':99103015,'fixtures':16,'probes_per_fixture':512,'compile':['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic'],
            'python_cpp_abs_tolerance':1e-12,'cpp_original_export_bits_equal_required':True,'weights_bits_equal_required':True,'features_bits_equal_required':True,
            'independent_parser_sha256':sha(ROOT/'round9/cost_replay_precise.py'),'independent_ledger_sha256':sha(HERE/'audit_next_action_v1.py')}
    save(HERE/'AI100_EXPORT_BUILD_FREEZE_V1.json',freeze)
  if '--prepare-only' in sys.argv:print('AI100 export prepared, no binary tests',flush=True);return
  with experiment_lock():
    if (OUT/'started.json').exists():raise RuntimeError('attempt exists; do not silently rerun')
    save(OUT/'started.json',{'build_freeze_sha256':sha(HERE/'AI100_EXPORT_BUILD_FREEZE_V1.json')})
    def run(name,args):
      with (OUT/(name+'.stdout')).open('x') as stdout,(OUT/(name+'.stderr')).open('x') as stderr:
        p=subprocess.run([str(exe)]+args,stdout=stdout,stderr=stderr,timeout=60);assert p.returncode==0,(name,p.returncode)
      return (OUT/(name+'.stdout')).read_text()
    weight_lines=run('weights',['weights']).splitlines();assert len(weight_lines)==225
    for i,line in enumerate(weight_lines):
      _,idx,a,b=line.split();assert int(idx)==i and int(a)==int(b)==bits64(flat(model)[i])
    feature_lines=run('features',['features',str(OUT/'features.txt')]).splitlines();assert len(feature_lines)==64
    for i,line in enumerate(feature_lines):
      parts=line.split();assert parts[0]=='F' and int(parts[1])==i;expected=list(map(bits32,features(feature_rows[i])))
      assert list(map(int,parts[2:14]))==list(map(int,parts[14:]))==expected,(i,parts,expected)
    numeric_lines=run('numeric',['numeric',str(OUT/'vectors.txt')]).splitlines();assert len(numeric_lines)==len(vectors)
    max_abs=0.;max_ulp=0;identical=0;output_zero=output_one=0
    for i,line in enumerate(numeric_lines):
      parts=line.split();assert parts[0]=='N' and int(parts[1])==i;abits,bbits=map(int,parts[2:4]);assert abits==bbits
      assert list(map(int,parts[4:]))==list(map(bits32,vectors[i]['f']))
      expected=forward(model,vectors[i]['f']);actual=struct.unpack('<d',struct.pack('<Q',abits))[0]
      error=abs(expected-actual);assert error<=1e-12,(i,expected,actual,error)
      max_abs=max(max_abs,error);max_ulp=max(max_ulp,abs(bits64(expected)-abits));identical+=bits64(expected)==abits
      output_zero+=actual==0;output_one+=actual==1
    print('Weights/features/numeric passed',len(vectors),'vectors; Python identical',identical,flush=True)
  audits=[]
  for i,path in enumerate(fixture_files):
    with experiment_lock():
      trace=OUT/('fixture_'+str(i)+'.trace');out=run('fixture_'+str(i),['fixture',str(path),str(trace)]);reported=json.loads(out)
      checked=fixture_audit(path,trace,reported);audits.append({'fixture':i,'input_sha256':sha(path),'trace_sha256':sha(trace),'cpp':reported,'audit':checked})
      print('Fixture',i+1,'/16 passed; callbacks',reported['callbacks'],flush=True)
  with experiment_lock():
    assert sha(SOURCE)==SOURCE_SHA
    result={'complete':True,'scope':freeze['scope'],'build_freeze_sha256':sha(HERE/'AI100_EXPORT_BUILD_FREEZE_V1.json'),
      'weight_double_bits_identical':225,'feature_vectors_float32_bits_identical':64,'feature_values_float32_bits_identical':64*12,
      'numeric_vectors':len(vectors),'cpp_original_export_output_bits_identical':len(vectors),'python_cpp_output_bits_identical':identical,
      'python_cpp_max_abs_error':max_abs,'python_cpp_max_ulp':max_ulp,'clipped_zero_vectors':output_zero,'clipped_one_vectors':output_one,
      'vector_scope':vector_scope,'fixture_results':audits,'fixture_callbacks_exact':sum(r['cpp']['callbacks'] for r in audits),
      'fixture_neural_calls_per_copy':sum(r['cpp']['neural_calls_per_copy'] for r in audits),
      'fixture_coverage':{k:sum(r['audit']['coverage'][k] for r in audits) for k in audits[0]['audit']['coverage']},
      'source_unchanged':True,'training_runs':0,'dataset_solver_runs':0,'dev_eval_accesses':0,'performance_or_quality_claim':False}
    save(HERE/'AI100_EXPORT_RESULTS_V1.json',result);print('AI100 export audit complete',flush=True)
if __name__=='__main__':main()
