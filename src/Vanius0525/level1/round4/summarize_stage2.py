"""Fixed-slate descriptive analysis; no hidden-distribution or significance claim."""
from pathlib import Path
import sys,json,statistics,hashlib,collections
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from summarize import summarize,score
ROOT=Path(__file__).resolve().parents[1]
def member_metadata(member):
 metadata={}
 if member!='Vanius0525':
  records=json.loads((ROOT/'build/team_snapshot_923d21e'/member/'manifest.json').read_text())['cases']
  return {Path(r['path']).name:{**r,'corner':r.get('family')=='corners' if member=='liunianwww' else None} for r in records if r['split']=='eval'}
 for folder in ['holdout','ood','round3-fresh','round3-ood']:
  metadata.update({r['file']:{**r,'corner':False} for r in json.loads((ROOT/'build/data'/folder/'manifest.json').read_text())['cases']})
 for r in json.loads((ROOT/'results/balanced-own-corners.json').read_text())['cases']:
  if r['file']!='end_insert.txt':metadata[r['file']]={'family':'corner','corner':True}
 return metadata

def effect_panel(reports,names):
 # Conditional, paired input-level resampling: no claim these inputs were random population samples.
 rng=np.random.default_rng(503100);output={};B=4000
 for reference in ['pure','ai']:
  for name in names:
   if name==reference:continue
   draws=np.zeros(B);diffmeans=[];casewins=losses=ties=0
   for r in reports:
    diffs=np.asarray([score(c,name)-score(c,reference) for c in r['cases']]);diffmeans.append(float(diffs.mean()))
    casewins+=int((diffs>1e-9).sum());losses+=int((diffs< -1e-9).sum());ties+=int((abs(diffs)<=1e-9).sum())
    # Chunk bounded arrays; do not consume a huge sample matrix on full suites.
    for start in range(0,B,100):draws[start:start+100]+=diffs[rng.integers(len(diffs),size=(100,len(diffs)))].mean(axis=1)/len(reports)
   output[name+'_vs_'+reference]={'mean_difference':statistics.mean(diffmeans),'conditional_input_bootstrap_percentile_95':np.quantile(draws,[.025,.975]).tolist(),'case_wins':casewins,'case_losses':losses,'case_ties':ties}
 return {'pairs':output,'resamples':B,'unit':'input case, separately within each fixed member; repeated timings already averaged at per-case score level','scope':'Descriptive sensitivity to this fixed case slate. Synthetic nonrepresentative inputs, shared generator dependence, adaptive design and timing uncertainty prevent hidden-population or confirmatory significance claims. These intervals do not measure all system noise.'}

def main(stage='stage2'):
 output={'members':{},'generated':{},'scope':'all frozen nominees retained; official member case means and equal-member mean; family/corner and I/O tails separately, no hidden-mixture estimate','score':'per repetition clamp(10*(1-VAL/BASE),0,10), then repeats, cases, equal members; zero VAL/BASE maps to0'};reports=[]
 for member in ['Vanius0525','cyanneko','liunianwww']:
  p=ROOT/'results'/('round4-'+stage+'-member-'+member+'.json' if stage=='stage2' else 'round4-phase-member-'+member+'.json')
  if not p.exists():continue
  r=json.loads(p.read_text());reports.append(r);output['members'][member]={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scheduler_sha256':r['scheduler_sha256'],'repeats':r['repeats'],'summary':summarize(r,member_metadata(member))}
 if len(reports)==3:
  names=list(reports[0]['scheduler_sha256']);assert all(list(r['scheduler_sha256'])==names for r in reports)
  output['equal_member_mean']={n:statistics.mean(d['summary'][n]['mean_score'] for d in output['members'].values()) for n in names}
  output['conditional_paired_effects']=effect_panel(reports,names)
 for suite in ['fresh2','challenge'] if stage=='stage2' else []:
  p=ROOT/'results'/('round4-stage2-'+suite+'.json')
  if not p.exists():continue
  r=json.loads(p.read_text());manifest=json.loads((ROOT/'build/data'/('round4-'+suite)/'manifest.json').read_text());metadata={c['file']:{**c,'corner':c.get('corner_axis',False)} for c in manifest['cases']}
  output['generated'][suite]={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scheduler_sha256':r['scheduler_sha256'],'repeats':r['repeats'],'summary':summarize(r,metadata)}
 (ROOT/'round4'/('STAGE2_RESULTS.json' if stage=='stage2' else 'PHASE_RESULTS.json')).write_text(json.dumps(output,indent=2)+'\n')
 print(json.dumps({'equal_member_mean':output.get('equal_member_mean'),'generated':{k:{n:d['mean_score'] for n,d in v['summary'].items()} for k,v in output['generated'].items()}},indent=2))
if __name__=='__main__':
 sys.path.insert(0,str(ROOT))
 from workflow import experiment_lock
 with experiment_lock():main(sys.argv[1] if len(sys.argv)>1 else 'stage2')
