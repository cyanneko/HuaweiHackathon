"""Standalone fixed-slate tradeoffs and corner-mixture sensitivity."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/level1-matplotlib')
from pathlib import Path
import sys,json,time,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import experiment_lock
ROOT=Path(__file__).resolve().parents[1]
while not (ROOT/'round4/STAGE2_RESULTS.json').exists():time.sleep(5)
with experiment_lock():
 p=ROOT/'round4/STAGE2_RESULTS.json';r=json.loads(p.read_text());assert len(r['members'])==3
 names=['pure','ai','pure_prune_routecount','pure_set025_all_probe_routecount','pure_set025_io_asymmetry_routecount','ai_set025_routecount','pure_prefetch_budget256','pure_prefetch_budget2048','ai_prefetch_budget2048','ai_context_exact_pure_d6_m005_support_fast','ai_context_exact_agg_d6_m005_support_fast']
 labels=['Pure frozen','AI frozen','Pure prune','Pure all-PROBE','Pure I/O asymmetry','AI set','Pure prefetch256','Pure prefetch2048','AI prefetch2048','Context pure','Context dual']
 out=ROOT/'round4/figures';out.mkdir(exist_ok=True);rows=[]
 fig,axes=plt.subplots(1,2,figsize=(13,5.6))
 for i,(n,label) in enumerate(zip(names,labels)):
  mean=r['equal_member_mean'][n];worst=max(v['summary'][n]['worst_io_miss_cases'][0]['io_miss_ratio'] for v in r['members'].values());cpu=sum(v['summary'][n]['sum_decision_us'] for v in r['members'].values())
  color='#2864a0' if n.startswith('pure') else '#c46927';marker='s' if n.startswith('pure') else 'o'
  if 'context' in n:color='#777777';marker='x'
  axes[0].scatter(mean,worst,c=color,marker=marker,s=50);axes[0].annotate(str(i+1),(mean,worst),xytext=((-6,-12) if i==0 else (4,3)),textcoords='offset points',fontsize=8)
  rows.append({'candidate':n,'label':label,'number':i+1,'equal_member_mean_score':mean,'worst_io_miss_ratio':worst,'total_decision_us':cpu})
 axes[0].set_xlabel('Equal-member mean case score (higher is better)');axes[0].set_ylabel('Worst I/O + Miss cost / Naive (lower is better)');axes[0].set_yscale('log');axes[0].grid(True,alpha=.2)
 axes[0].text(.02,.98,'\n'.join(f'{i+1}. {s}' for i,s in enumerate(labels)),transform=axes[0].transAxes,va='top',fontsize=7,bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
 # Vary corner weights separately. Leave unknown cyanneko labels at its full mean.
 left='pure_set025_io_asymmetry_routecount';right='ai_prefetch_budget2048';weights=np.linspace(0,1,101);grid=np.zeros((101,101))
 def mixture(member,n,w):
  d=r['members'][member]['summary'][n];s=d['corner_weight_sensitivity_diagnostic'];return (1-w)*s['0.0']+w*s['1.0']
 for yi,wl in enumerate(weights):
  for xi,wo in enumerate(weights):
   grid[yi,xi]=(mixture('Vanius0525',left,wo)-mixture('Vanius0525',right,wo)+mixture('liunianwww',left,wl)-mixture('liunianwww',right,wl)+r['members']['cyanneko']['summary'][left]['mean_score']-r['members']['cyanneko']['summary'][right]['mean_score'])/3
 bound=max(abs(grid.min()),abs(grid.max()));im=axes[1].imshow(grid,origin='lower',extent=[0,1,0,1],vmin=-bound,vmax=bound,cmap='RdBu',aspect='auto');fig.colorbar(im,ax=axes[1],label='Pure I/O-asymmetry minus AI prefetch2048 score')
 if grid.min()<0<grid.max():axes[1].contour(weights,weights,grid,levels=[0],colors='black',linewidths=.8)
 axes[1].plot(17/209,133/528,'k*',markersize=9,label='Observed case fractions');axes[1].legend(fontsize=7,loc='upper right');axes[1].set_xlabel('Own corner weight (sensitivity only)');axes[1].set_ylabel('liunianwww corner weight (sensitivity only)')
 fig.suptitle('Frozen stage2 slate: average, tail, and mixture sensitivity');fig.text(.5,.01,'785 exposed synthetic inputs, 5 repeats; all cases retained. Unknown cyanneko labels stay fixed. No hidden-distribution claim.',ha='center',fontsize=8);fig.tight_layout(rect=(0,.035,1,.95));fig.savefig(out/'stage2_tradeoffs.svg');fig.savefig(out/'stage2_tradeoffs.png',dpi=170);plt.close(fig)
 (out/'stage2_tradeoffs_data.json').write_text(json.dumps({'source_summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':rows,'mixture_left':left,'mixture_right':right,'mixture_min':float(grid.min()),'mixture_max':float(grid.max()),'mixture_scope':'counterfactual case weights, not an estimate or replacement for official score'},indent=2)+'\n');print(json.dumps({'rows':rows,'mixture_min':float(grid.min()),'mixture_max':float(grid.max())}),flush=True)
