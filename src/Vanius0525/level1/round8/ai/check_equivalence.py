"""Exact TRACE equality and independent legality checks for both forced modes."""
import json,subprocess,sys
from local_build import HERE,ROOT,official
from make_policy import put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import replay

def main():
    cases=json.loads((ROOT/'round8/TRAIN_MANIFEST.json').read_text())['cases'][:2]
    records=[]
    with experiment_lock():
        for mode,base in [(0,'decay64_fixed_pool.cpp'),(1,'decay64.cpp')]:
            a=official(f'eq_original{mode}',ROOT/'round7'/base,True)
            b=official(f'eq_forced{mode}',HERE/f'forced{mode}.cpp',True)
            for c in cases:
                path=ROOT/'build/round8/data/train'/(c['spec']['id']+'.txt')
                pa=subprocess.run([str(a),str(path)],capture_output=True,text=True,check=True,timeout=120)
                pb=subprocess.run([str(b),str(path)],capture_output=True,text=True,check=True,timeout=120)
                assert pa.stderr==pb.stderr,(mode,path)
                aa=replay(path,pa.stderr,pa.stdout);ab=replay(path,pb.stderr,pb.stdout);assert aa==ab
                records.append({'mode':mode,'input':c['spec']['id'],'input_sha256':c['input_sha256'],'exact_action_trace_match':True,'audit':aa})
                print('exact equivalent',mode,c['spec']['id'],flush=True)
    put(HERE/'FORCED_EQUIVALENCE.json',json.dumps({'complete':True,'runs':records},indent=2)+'\n')
if __name__=='__main__':main()
