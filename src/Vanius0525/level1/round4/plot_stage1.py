"""Scientific standalone tradeoff figure; fixed first-stage candidate panel."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/level1-matplotlib')
from pathlib import Path
import json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import experiment_lock
ROOT=Path(__file__).resolve().parents[1]
with experiment_lock():
    p=ROOT/'round4/RESULTS.json';r=json.loads(p.read_text());assert len(r['members'])==3
    names=['pure','pure_prune','pure_set1','ai','ai_prune','ai_set0','ai_set025','ai_gate_d3_m00','ai_gate_d5_m02']
    out=ROOT/'round4/figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(10,5.6))
    rows=[]
    for i,n in enumerate(names):
        score=r['equal_member_mean'][n];worst=max(v['summary'][n]['worst_io_miss_cases'][0]['io_miss_ratio'] for v in r['members'].values())
        color='#2864a0' if n.startswith('pure') else '#c46927';marker='s' if n.startswith('pure') else 'o'
        if 'gate' in n:color='#888888';marker='x'
        ax.scatter(score,worst,c=color,marker=marker,s=65,zorder=3)
        offset=[(-45,-18),(7,-23),(5,-12),(-16,15),(8,5),(-88,13),(8,-17),(-65,-37),(-85,18)][i]
        ax.annotate(n,(score,worst),textcoords='offset points',xytext=offset,fontsize=8,arrowprops={'arrowstyle':'-','lw':.45,'color':color})
        rows.append({'candidate':n,'equal_member_mean_score':score,'worst_io_miss_ratio':worst})
    ax.set_yscale('log');ax.set_xlabel('Mean case score, equal weight per member (higher is better)')
    ax.set_ylabel('Worst I/O + Miss cost / Naive (lower is better, log scale)')
    ax.set_title('First-stage candidates: mean gains can hide severe regressions')
    ax.grid(True,which='both',alpha=.2);ax.set_ylim(2.2,80000);ax.margins(x=.12)
    fig.text(.5,.01,'785 exposed synthetic cases; 5 repeats. Worst ratio excludes decision time. No hidden-distribution claim.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(out/'stage1_tradeoffs.svg');fig.savefig(out/'stage1_tradeoffs.png',dpi=170);plt.close(fig)
    (out/'stage1_tradeoffs_data.json').write_text(json.dumps({'source_summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':rows,'scope':'worst I/O+Miss ratio among all cases with positive Naive I/O+Miss; zero-base positive-cost cases reported separately in RESULTS; per-member means retain all cases'},indent=2)+'\n')
