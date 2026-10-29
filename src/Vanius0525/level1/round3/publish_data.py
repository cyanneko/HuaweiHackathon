"""Export only our immutable inputs to a separate datasets worktree."""
from pathlib import Path
import argparse,hashlib,json,shutil
BASE=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def main(dest):
 dest=Path(dest)/'datasets/Vanius0525';assert not dest.exists(),'Refuse to overwrite an existing release'
 dest.mkdir(parents=True);records=[]
 for split,suites in [('train',['dev','train','val']),('eval',['holdout','ood','round3-fresh','round3-ood','edges'])]:
  (dest/split).mkdir()
  for suite in suites:
   folder=BASE/'build/edges' if suite=='edges' else BASE/'build/data'/suite
   manifest=folder/'manifest.json';meta={r['file']:r for r in json.loads(manifest.read_text())['cases']} if manifest.exists() else {}
   for p in sorted(folder.glob('*.txt')):
    raw=p.read_bytes();lines=raw.decode().splitlines();k=int(lines[0].split()[0]);group=sha(('\n'.join(lines[2+k:])+'\n').encode())
    name=suite.replace('-','_')+'_'+p.name;out=dest/split/name;out.write_bytes(raw)
    m=dict(meta.get(p.name,{}));m.update({'member':'Vanius0525','split':split,'cohort':suite,'corner_case':suite=='edges','source_file':p.name,'sha256':sha(raw),'group_sha256':group,'historically_used_in_development':split=='train','independent_unseen_test':False,'official_representative_claim':False})
    mp=out.with_suffix('.meta.json');mp.write_text(json.dumps(m,indent=2)+'\n')
    records.append({'path':'datasets/Vanius0525/'+split+'/'+name,'split':split,'cohort':suite,'family':m.get('family','edge_diagnostic'),'corner_case':suite=='edges','sha256':sha(raw),'metadata_sha256':sha(mp.read_bytes()),'bytes':len(raw),'group_sha256':group})
 a={r['group_sha256'] for r in records if r['split']=='train'};b={r['group_sha256'] for r in records if r['split']=='eval'}
 overlap=a&b
 # Keep source bytes; explicitly exclude any overlapping eval from selection rather than hiding leakage.
 for r in records:r['evaluation_eligible']=r['split']=='eval' and r['group_sha256'] not in overlap
 report={'member':'Vanius0525','version':'0.1.0','source_revision':'aaa92a0','cases':records,'cross_split_operation_overlap_groups':sorted(overlap),'counts':{s:sum(r['split']==s for r in records) for s in ['train','eval']},'input_bytes':sum(r['bytes'] for r in records),'official_hidden_distribution_claim':False,'evaluation_exposure':'All eval has been inspected locally; this is a reproducible regression release, not a blind test.'}
 (dest/'diagnostics').mkdir()
 for r in records:
  if r['path'].endswith('/edges_end_insert.txt'):
   for suffix in ['.txt','.meta.json']:
    src=dest/'eval'/('edges_end_insert'+suffix);src.rename(dest/'diagnostics'/src.name)
   mp=dest/'diagnostics/edges_end_insert.meta.json';m=json.loads(mp.read_text());m.update(split='diagnostics',evaluation_eligible=False,exclusion_reason='Missing required SWITCH; legacy framework tolerance diagnostic only');mp.write_text(json.dumps(m,indent=2)+'\n')
   r.update(path='datasets/Vanius0525/diagnostics/edges_end_insert.txt',split='diagnostics',evaluation_eligible=False,exclusion_reason='Missing required SWITCH',metadata_sha256=sha(mp.read_bytes()))
 report['counts']={'train':192,'eval':209,'diagnostics':1}
 (dest/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(dest/'eval/VERSION').write_text('0.1.0\n')
 (dest/'generators').mkdir()
 for f in ['generate.py','generate_ood.py']:shutil.copyfile(BASE/f,dest/'generators'/f)
 (dest/'README.md').write_text('''# Vanius0525 自造工作负载 v0.1.0

train包含dev64、train96、val32，都是开发/拟合来源，不能作为盲测。eval包含holdout64、OOD64、第三轮fresh32、第三轮OOD32和17个合法边界诊断，共209例。名称增加cohort前缀，输入字节未修改。生成种子、参数、SHA256、操作流分组及corner分类见相邻meta与manifest。

全部eval现已曝光，仅用于可复现回归，不宣称代表官方隐藏分布。离线模型没有用eval拟合，但后续已查看结果。manifest明确记录跨split重复操作组和evaluation_eligible；不得把不合格组算作无泄漏外推证据。

内部选型按成员等权，每成员常规80%、corner20%，组内先按相同操作流去重；此权重不是题面官方规则。corner仅17例明确构造的边界/精确oracle诊断，正常热点、扫描、倾斜和OOD不自动算极端。所有例都保留，风险另报最差成本比，不用低权重掩盖非法动作。

生成器为generators/generate.py与generate_ood.py；边界构造来源source/Vanius0525分支src/Vanius0525/level1/check_edges.py（提交aaa92a0）。完整输入可直接复现，不需要框架或其他成员算法。
''')
 (dest/'HANDOFF.md').write_text('2026-10-29：首次发布；仅本成员目录。原输入保持字节，manifest+逐例meta提供来源和指纹。train192、eval209，常规192/corner17，另有diagnostics1例不计分。公共校验报告见VALIDATION.json；本发布不修改其他成员数据或算法。\n')
 print(json.dumps({'counts':report['counts'],'bytes':report['input_bytes'],'cross_split_overlap_groups':len(overlap)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('destination_worktree');main(p.parse_args().destination_worktree)
