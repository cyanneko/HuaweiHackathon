"""Exactly two frozen train cases; no model fitting or external verification."""
from core import *
import argparse, subprocess, sys
O=Path(__file__).resolve().parent
OUT=O/'teacher_two'
IDS=('beam_06','exact_05')

def one(caseid):
    start=time.perf_counter();manifest=json.loads((O/'data/train_manifest.json').read_text())
    entry=next(x for x in manifest['cases'] if x['selection_id']==caseid)
    assert caseid in IDS
    c=Case.read(entry['input']);assert c.input_hash==entry['input_sha256']
    out=OUT/caseid;out.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter();best,stats=search(c,seconds=3,width=8,exact=False);search_wall=time.perf_counter()-t
    (out/'witness.json').write_text(json.dumps(best.path,indent=2))
    (out/'search_stats.json').write_text(json.dumps(stats,indent=2))
    baselines={}
    for name,mode in [('new_pool_base','base'),('r65_style','r65'),('naive_largest_first','naive')]:
        s=rollout(c,mode);replay=rollout(c,witness=s.path);assert s.g==replay.g and s.snapshot()==replay.snapshot()
        (out/(name+'_witness.json')).write_text(json.dumps(s.path,indent=2))
        baselines[name]={'G':s.g,'grouped_objective':s.g/(c.w*c.r),'ordered_objective':s.ordered_io+c.penalty*s.miss,'write_bytes':s.write,'read_bytes':s.read,'misses':s.miss,'path_hash':digest(s.path),'callbacks':len(s.path),'internal_replay_complete':True,'external_replay_verified':False,'same_teacher_witness':best.path==s.path}
    s=State(c);j=multi=different=0;unique=set();anchors=[]
    while s.advance():
        a=tuple(best.path[j]['spill']);plans=pool(s);assert a in plans
        base=min(plans,key=lambda p:plan_order(s,p));key=action_key(s,a);unique.add(key)
        if len(plans)>1:
            multi+=1;different+=a!=base
            anchors.append({'callback_id':j,'raw':s.raw,'stage':s.stage,'candidate_count':len(plans),'candidate_keys':[action_key(s,p) for p in plans],'selected_action_key':key,'same_anchor_base_key':action_key(s,base),'different_from_same_anchor_base':a!=base})
        s.apply(a);j+=1
    assert s.g==best.g
    (out/'teacher_multichoice_anchors.json').write_text(json.dumps(anchors,indent=2))
    report={'selection_id':caseid,'input':entry['input'],'input_sha256':c.input_hash,'core_sha256':hashlib.sha256((O/'core.py').read_bytes()).hexdigest(),'parameters':{'seconds':3,'width':8,'exact':False,'outer_process_timeout_seconds':30},'budget_note':'3s checks bound search loop, not strict end-to-end; complete initial baselines and final replay can add time','search_call_wall_seconds':search_wall,'search_stats_seconds':stats['seconds'],'search_status':stats['status'],'G':best.g,'initial_G':stats['initial_G'],'improvement_G':stats['improvement_G'],'teacher_path_hash':digest(best.path),'callbacks':j,'multi_candidate_states':multi,'different_selected_from_same_anchor_base':different,'unique_selected_action_keys':len(unique),'selected_action_keys':sorted(unique),'baselines':baselines,'internal_replay_complete':True,'replay_verified':False,'external_replay_pending':True,'labels_emitted':False,'end_to_end_worker_seconds':time.perf_counter()-start}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--one',choices=IDS);args=ap.parse_args()
    if args.one:return one(args.one)
    OUT.mkdir(exist_ok=True);reports=[]
    for caseid in IDS:
        start=time.perf_counter()
        try:
            p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--one',caseid],capture_output=True,text=True,encoding='utf-8',timeout=30)
            (OUT/(caseid+'.stdout.log')).write_text(p.stdout,encoding='utf-8');(OUT/(caseid+'.stderr.log')).write_text(p.stderr,encoding='utf-8')
            assert p.returncode==0,p.stderr
            report=json.loads((OUT/caseid/'report.json').read_text());report['parent_subprocess_wall_seconds']=time.perf_counter()-start
            (OUT/caseid/'report.json').write_text(json.dumps(report,indent=2));reports.append(report)
            print(json.dumps({k:report[k] for k in ('selection_id','parent_subprocess_wall_seconds','search_call_wall_seconds','search_status','improvement_G','multi_candidate_states','different_selected_from_same_anchor_base')}),flush=True)
        except subprocess.TimeoutExpired:
            report={'selection_id':caseid,'status':'outer_timeout_no_labels','parent_subprocess_wall_seconds':time.perf_counter()-start,'labels_emitted':False};reports.append(report)
            (OUT/(caseid+'.timeout.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    (OUT/'summary.json').write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
