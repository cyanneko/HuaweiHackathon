from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
train=read('tmp/r83_eval/train/summary.json');dev=read('tmp/r83_eval/dev/summary.json')
data=read('tmp/r83_data_panel/data_manifest.json')
names=[m['name'] for m in read('tmp/r83_eval/train/selection.json')['methods']]
labels=dict(zip(names,['Naive','R75','R79','R80共享概率','R80双方案','R81快算子','R82 single-fit','R82 write1']))
t={m['method']:m for m in train['groups']['all']};d={m['method']:m for m in dev['groups']['all']}
lines=['# R83：完整新覆盖面板实验','',
'日期：2026-10-30。此轮只测试冻结方法，没有修改或训练策略。按用户“完整测试”的新要求，12个TRAIN和6个DEV全部运行八种方法，共144格全部有效。DEV在运行前与TRAIN绑定相同代码和数据身份；没有按训练筛选结果跳过方法。原dyna12/final72加Van的完整回归属于下一轮R84，不与这里混成一个分数。','',
'## 判断','',
'这批新增数据支持继续保留R80双方案版：TRAIN与DEV均分均高于R80共享概率版；代价是决策耗时约为其两倍。R81仍有裁剪均分稍升、原始成本却略变差的情况。R82 single-fit的旧TRAIN38失败结论保留，本轮TRAIN最坏成本/R80仍为1.273，超过预设1.25门槛；不能因换了一批数据就撤销失败记录。没有自动替换默认R75。','',
'## 数据和评测方法','',
'18例各150,000操作，合计2,700,000操作、54,883,188输入字节。TRAIN为6个独立种子，每个种子的完全相同操作流分别设置基础/64倍读写带宽；因此12文件只有6个独立轨迹。DEV使用另外6个种子与8倍带宽，机制参数相同，不能称为OOD或官方盲测。全部输入通过完整合法性检查，无换种子、丢弃或修剪失败输入。六组TRAIN正文、操作流和分区布局SHA一致，仅带宽头字段变化。','',
'一半轨迹沿用原动态概率生成器，算子热度变化快、普通分区内部近均匀；另一半为单独的IID补充轨道，先分配构建字节/条数，再随机INSERT和IID PROBE。两者不是同一模型，也没有替换原dyna数据。动态rare-hot目标压力1.10，实际TRAIN为1.1154、DEV为1.1884，是保留的随机结果。','',
'| 轨迹 | K/P | 内存MiB | 目标压力 | 真实罚值 | 周期间隔 | 基础写/读带宽 |',
'|---|---:|---:|---:|---:|---:|---:|',
'| dynamic slow/shared | 2/16 | 64 | 1.10 | 1 | 17 | 100/80 |',
'| dynamic fast/staggered hot | 4/32 | 256 | 1.10 | 100 | 127 | 80/100 |',
'| dynamic burst/shared | 8/64 | 64 | 2.00 | 1000 | 1000 | 100/100 |',
'| IID Zipf | 2/64 | 256 | 2.00 | 100 | 1000 | 100/80 |',
'| IID hotspot | 4/16 | 64 | 1.25 | 1000 | 17 | 80/100 |',
'| IID lognormal | 8/32 | 1024 | 1.25 | 1 | 127 | 100/100 |','',
'Linux/WSL CPU，g++ -std=c++14 -O2，官方框架不变，复用冻结ELF；串行单次，每格官方墙钟限60秒，每个窗口内部看门狗180秒。TRAIN用时34.674707秒，DEV用时17.175264秒。实测D已经计入成本，不设额外2倍D硬淘汰。单次计时不支持宣称细小D差异稳定。','',
'成本C=模拟IO+该输入真实罚值×miss+D；逐例分数采用已固定case-mean-v1：max(0,min(10,10×(1-C/Naive)))，非正成本/分母时按评测器记0。本轮分母均有效。raw分数不做逐例裁剪，保留负改善。P50/P90采用最近秩；DEV只有6例，所以P90等于最差。模拟成本改善不是实际磁盘端到端加速。算法仍看不到真实罚值，不能将此列当成策略输入。','',
'## 完整结果','',
'| 方法 | TRAIN12均分 | DEV6均分 | DEV未裁剪均分 | DEV成本/Naive P50 | P90/最差 | DEV平均D毫秒 |',
'|---|---:|---:|---:|---:|---:|---:|']
for n in names:
    a,b=t[n],d[n]
    lines.append(f"| {labels[n]} | {a['average_score']:.6f} | {b['average_score']:.6f} | {b['mean_raw_unclipped_points']:.6f} | {b['ratio_to_Naive']['p50']:.6f} | {b['ratio_to_Naive']['p90']:.6f} | {b['D_mean_us']/1000:.3f} |")
lines+=['','R80双方案相对共享概率，TRAIN均分+0.057926，DEV均分+0.190566；DEV原始均分+0.171047、逐例成本倍率均值0.980181，最坏1.035145。DEV平均D由13.400ms升至26.307ms。','',
'R81在DEV裁剪均分+0.030734，未裁剪均分却−0.005760，成本/R80均值1.004137，最坏1.093734。R82 single-fit在DEV裁剪均分+0.069563，未裁剪均分−0.027495，成本/R80均值1.037632。分数裁剪仍可能掩盖退化，不能只展示正的分差。','',
'TRAIN-only诊断按原分数/最坏成本规则选出R80双方案与R81；用户后来要求完整测，因此DEV所有八方法都运行，入选不表示默认晋级。','',
'## 分布和带宽诊断','',
'| 方法 | 动态TRAIN6 | IID TRAIN6 | 低带宽TRAIN6 | 高带宽TRAIN6 |','|---|---:|---:|---:|---:|']
for n in names[1:]:
    values=[next(x['average_score'] for x in train['groups'][g] if x['method']==n) for g in ['track:dynamic','track:iid','bandwidth:1','bandwidth:64']]
    lines.append('| '+labels[n]+' | '+' | '.join(f'{v:.6f}' for v in values)+' |')
lines+=['','R80双方案在动态轨迹与共享概率接近，IID上的增益更明显；这里只各有3个独立TRAIN种子。低/高带宽是同流配对，但分数包含变化后的基线、罚值占比及策略行为，不能把汇总分差简单解释为某个单一原因。TRAIN与DEV均值差还同时包含新种子和不同带宽，不能当作严格单变量泛化实验。','',
'## 逐例分数','']
for title,s in [('TRAIN：全部12例',train),('DEV：全部6例',dev)]:
    lines += ['### '+title,'','| 用例 | '+' | '.join(labels[n] for n in names[1:])+' |','|---|'+'---:|'*(len(names)-1)]
    ids=list(dict.fromkeys(r['case_id'] for r in s['per_case']));index={(r['case_id'],r['method']):r for r in s['per_case']}
    for cid in ids:lines.append('| '+cid+' | '+' | '.join(f"{index[cid,n]['score']:.6f}" for n in names[1:])+' |')
    lines.append('')
lines+=['## 版本、复核和复现入口','',
'代码完整source/TU/ELF身份：`tmp/r83_eval/method_identities.json`。所有源码与之前的对应版本逐字一致；R83不制造新的算法版本。运行入口及四条命令：`tmp/r83_eval/README.md`；精确评测依赖：各窗口`selection.json`。','',
'Root独立重读144份stdout，验证288份stdout/stderr日志指纹、hit+miss计数、成本公式和汇总均分；证据：`tmp/r83_eval/root_review/train/`、`tmp/r83_eval/root_review/dev/`，含逐例CSV、分组CSV和review.json。独立审查器：`tmp/root_full_eval_review.py`。它没有再次启动策略，也没有声称二次全输入合法性扫描。','',
'| 文件 | SHA256 |','|---|---|']
for p in ['tmp/r83_eval/experiment.py','tmp/r83_eval/method_identities.json','tmp/r83_data_panel/data_manifest.json','tmp/r83_eval/train/selection.json','tmp/r83_eval/train/rows.json','tmp/r83_eval/train/summary.json','tmp/r83_eval/dev/selection.json','tmp/r83_eval/dev/rows.json','tmp/r83_eval/dev/summary.json','tmp/r83_eval/root_review/train/review.json','tmp/r83_eval/root_review/dev/review.json']:
    lines.append(f'| `{p}` | `{sha(p)}` |')
lines+=['','发布交Master执行：源码引用、协议/版本身份、144格原始结果、完整新数据和审查一起在用户分支可查；发布后由独立publication manifest映射固定Git提交，不回写冻结selection。当前正文不提前声称本轮远端发布完成。','',
'下一轮R84使用最新版Van和六个既有方法（含Naive），完整评测原dyna12与final72。两个数据集先各自平均再等权，不把84个用例直接等权；R83本轮TRAIN/DEV也不与它们混算。']
target=ROOT/'docs/20261030_R83完整覆盖面板实验.md';assert not target.exists();target.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(str(target));print(hashlib.sha256(target.read_bytes()).hexdigest())
