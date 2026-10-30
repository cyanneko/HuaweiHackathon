"""Copy only reviewed scoring/protocol source, never prior results."""
from pathlib import Path
H=Path(__file__).resolve().parent;ROOT=H.parents[1];OLD=ROOT/'tmp/r84_full_eval_v2'
names=['Naive','R75_dense_switch','R80_next_hier_fast100','R80_paired_hier_fast100','R81_op256_cond2048','Van_latest','R85_fast_prior8','R85_hier_anchor']
s=(OLD/'scoring.py').read_text(encoding='utf-8')
line=next(x for x in s.splitlines() if x.startswith('REFERENCES='))
s=s.replace(line,'REFERENCES='+repr(names)+"\nDIRECT_PARENTS={'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100'}",1)
s=s.replace("dataset_weight=.5,no_default_promotion=True)","dataset_weight=.5,no_default_promotion=True,direct_parent_methods=DIRECT_PARENTS)")
s=s.replace("negative_improvement_hidden=raw is not None and raw<0,ratio_to_Naive=", "negative_improvement_hidden=raw is not None and raw<0,direct_parent=DIRECT_PARENTS.get(name),ratio_to_Naive=")
s=s.replace("method=name,cases=n,average_score=", "method=name,cases=n,direct_parent=DIRECT_PARENTS.get(name),average_score=")
with (H/'scoring.py').open('x',encoding='utf-8',newline='\n') as f:f.write(s)
t=(OLD/'test_protocol.py').read_text(encoding='utf-8').replace('terminal=84,valid=84,planned=84','terminal=96,valid=96,planned=96')
with (H/'test_protocol.py').open('x',encoding='utf-8',newline='\n') as f:f.write(t)
with (H/'test_paths.py').open('x',encoding='utf-8',newline='\n') as f:f.write((OLD/'test_paths.py').read_text(encoding='utf-8'))
print('R85 scorer and synthetic tests copied; no results copied')
