"""Plot actual recorded R72 generator probabilities (not inferred access frequencies)."""
import csv
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = BASE/'tmp/r72_hierarchical'
os.environ.setdefault('MPLCONFIGDIR',str(HERE/'mpl_cache'))
sys.path.insert(0,str(BASE/'hashjoin_lab/.report_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

def main():
    manifest=json.loads((DATA/'manifest.json').read_text())
    case=next(c for c in manifest['cases'] if c['case_id']=='train_slow_shared_01')
    meta=json.loads((DATA/case['metadata']).read_text())
    with (DATA/case['windows']).open() as f: op=list(csv.DictReader(f))
    with (DATA/case['partition_windows']).open() as f: part=list(csv.DictReader(f))
    k,p=meta['K'],meta['P']
    rare_op=meta['rare']['operator']; rare_pid=meta['rare']['partition']
    ordinary=(rare_op+1)%k
    font=FontProperties(fname='<LOCAL_PATH>')
    fig,axs=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
    x=[int(w['end_step'])/1e6 for w in op]
    for i in range(k):
        axs[0].plot(x,[float(w[f'mean_p_{i}']) for w in op],label=f'Operator {i}',lw=1.2)
    axs[0].set_title('算子之间：概率持续变化',fontproperties=font,loc='left')
    axs[0].set_ylim(0,1);axs[0].set_ylabel('Probability');axs[0].legend(ncol=k,fontsize=8)
    normal=[w for w in part if int(w['operator'])==ordinary]
    nx=[int(w['global_end'])/1e6 for w in normal]
    q=[[float(w[f'mean_q_{i}'])*p for i in range(p)] for w in normal]
    axs[1].fill_between(nx,[min(a) for a in q],[max(a) for a in q],alpha=.3,color='#367a70',label='Range across all partitions')
    for i in range(min(4,p)):
        axs[1].plot(nx,[a[i] for a in q],lw=.8,alpha=.6)
    axs[1].axhline(1,color='black',lw=1,ls='--',label='Uniform: 1/P')
    axs[1].set_title(f'普通算子 {ordinary} 内部：各分区接近均匀，缓慢波动',fontproperties=font,loc='left')
    axs[1].set_ylim(.88,1.12);axs[1].set_ylabel('Probability / (1/P)');axs[1].legend(fontsize=8,ncol=2)
    special=[w for w in part if int(w['operator'])==rare_op]
    sx=[int(w['global_end'])/1e6 for w in special]
    axs[2].plot(sx,[float(w[f'mean_q_{rare_pid}']) for w in special],color='#b86733',lw=1.5,label=f'Hot partition {rare_pid}')
    axs[2].axhline(1/p,color='black',lw=1,ls='--',label='Uniform: 1/P')
    axs[2].set_title(f'少量异常：算子 {rare_op} 内的一个分区持续偏热',fontproperties=font,loc='left')
    axs[2].set_ylim(0,1);axs[2].set_ylabel('Probability');axs[2].legend(fontsize=8,ncol=2)
    axs[2].set_xlabel('Global operation index (million)')
    for ax in axs:ax.grid(alpha=.2)
    fig.savefig(HERE/'probability_example.png',dpi=160)
    plt.close(fig)
    (HERE/'plot_provenance.json').write_text(json.dumps(dict(case_id=case['case_id'],input_sha256=case['sha256'],
        windows_sha256=case['windows_sha256'],partition_windows_sha256=case['partition_windows_sha256'],
        plotted='window mean latent sampling probabilities, not empirical frequencies',
        global_window=meta['window'],partition_local_window=meta['partition_window']),indent=2)+'\n')
    print(HERE/'probability_example.png')

if __name__=='__main__':main()
