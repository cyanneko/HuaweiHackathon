"""Read-only callback-state diagnostics; wrapper only, reference engine unchanged."""
from pathlib import Path
import sys,json,hashlib,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build
from replay import replay,parse_input
from workflow import experiment_lock
ROOT=build.ROOT
SNAP=r'''
    void snapshot(const SystemState& s, char tag, int op, int pid, int64_t z) {
        std::cerr << "STATE " << tag << " " << op << " " << pid << " " << z << " "
          << s.memory_limit << " " << s.memory_used << " " << s.hit_count+s.miss_count << " "
          << s.next_op.type << " " << s.next_op.op_id << " " << s.next_op.key;
        for(const auto& o:s.operators) for(const auto& p:o.partitions)
          std::cerr << " " << o.op_id << "," << p.partition_id << "," << p.data_size << "," << p.in_memory << "," << (o.phase==Phase::PROBE);
        std::cerr << '\n';
    }
'''
def setup():
    build.AUDIT=build.AUDIT.replace('    MySpillScheduler inner_;','    MySpillScheduler inner_;\n'+SNAP)
    for call,tag,args in [('onMemoryOverflow','O','o,p,z'),('onPartitionMiss','M','o,p,0'),('onPeriodicAdjust','P','-1,-1,0')]:
        build.AUDIT=build.AUDIT.replace('auto a=inner_.'+call, "snapshot(s,'"+tag+"',"+args+"); auto a=inner_."+call)

def traces(stderr):
    result=[];state=None
    for line in stderr.splitlines():
        if line.startswith('STATE '):state=line
        elif line.startswith('TRACE '):result.append((state,line))
    return result

def main():
    setup();out=ROOT/'build/round4/case_study';out.mkdir(parents=True,exist_ok=True)
    paths=[ROOT/'build/data/holdout/046_serial_293046.txt',ROOT/'build/data/round3-fresh/012_burst_295012.txt']
    team=ROOT/'build/team_snapshot_923d21e/liunianwww/eval'
    for pattern in ['*almost_M_0897*','*corners_0996*','*builder_vs_prober_1089*','*sequential_scan_0824*']:
        paths.extend(team.glob(pattern))
    records=[]
    with experiment_lock():
        exes={name:build.build(ROOT/src,'case_'+name,audit=True) for name,src in [('pure','MySpillScheduler.cpp'),('ai','MySpillSchedulerAI.cpp')]}
        for path in paths:
            runs={};ts={}
            for name,exe in exes.items():
                r=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=60)
                (out/(path.stem+'_'+name+'.trace')).write_text(r.stderr)
                runs[name]=replay(path,r.stderr,r.stdout);ts[name]=traces(r.stderr)
            diffs=[]
            for index,(a,b) in enumerate(zip(ts['pure'],ts['ai'])):
                if a[0]!=b[0] or sorted(zip(*[iter(a[1].split()[6:])]*3))!=sorted(zip(*[iter(b[1].split()[6:])]*3)):
                    state=a[0].split();resident=[v for v in state[11:] if v.split(',')[3]=='1']
                    diffs.append({'callback_index':index,'same_pre_action_state':a[0]==b[0], 'pure_state':a[0],'ai_state':b[0],'pure_actions':a[1],'ai_actions':b[1]})
                    break
            counts={n:{'multiple_spill_callbacks':sum(sum(t=='S' for t in line.split()[6::3])>1 for _,line in vals),'callbacks':len(vals)} for n,vals in ts.items()}
            records.append({'file':path.name,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'header':parse_input(path)[0],'audit':runs,'counts':counts,'first_set_difference':diffs})
    (ROOT/'round4/CASE_STUDIES.json').write_text(json.dumps(records,indent=2)+'\n')
    for r in records:print(r['file'],r['audit'],flush=True)
if __name__=='__main__':main()
