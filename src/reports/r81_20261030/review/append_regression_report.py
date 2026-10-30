from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
audit=read('tmp/r81_review/regression_review.json');assert audit['status']=='PASS'
summaries={w:read(f'tmp/r81_regression_eval/{w}/summary.json') for w in ['dyna','final']}
for w in summaries:
 assert sha(f'tmp/r81_regression_eval/{w}/summary.json')==audit['campaigns'][w]['summary_sha256']
 assert sha(f'tmp/r81_regression_eval/{w}/rows.json')==audit['campaigns'][w]['rows_sha256']
labels={'Naive':'Naive','R75_dense_switch':'R75 原版','R79_adaptive':'R79','R80_next_hier_fast100':'R80 共享概率','R80_paired_hier_fast100':'R80 双方案','R81_op256_cond2048':'R81 算子256'}
text='''
## 原 dyna 与 final 的同轮回归

36/36 dyna 格与144/144 final格全部通过，分别耗时258.515秒和74.088秒。独立重新解析180份输出、核对360份日志SHA、样本与源码继承身份；无缺格、失败或超时。原dyna六例各500万操作，final为R80同一固定24例。这两批已经曝光，明确是回归样本，不是新盲测。R75也在本轮重新运行，以下比较均有同批Naive。

| 方法 | 原dyna6均分 | final24均分 | 两数据集各50%均分 |
|---|---:|---:|---:|
'''
members=read('tmp/r81_review/regression_member_equal_scores.json')
for m in members:
 text+=f"| {labels[m['method']]} | {m['dyna_mean_score']:.6f} | {m['final_mean_score']:.6f} | {m['dataset_equal_mean_score']:.6f} |\n"
text+='''
R81相对R80共享概率，dyna提高0.095561分，final仅提高0.003983分；两数据集均分各占50%后提高0.049772分。相对本轮R75，dyna提高0.108151分、final提高0.843366分，等权提高0.475758分。不能用R75过去的全12例平均分来与这里六例直接比较。

### 尾部问题：均分提高仍不足以替换

**final的`eval_059_random_zipf`成本比R80共享概率增加27.04%，超过事先声明的1.25倍门槛。因此本轮不建议无条件替换原候选，默认提交也不改。** 两版在该例均差于Naive，裁剪分数都为0；仅看最终分数会漏掉退化。R81该例成本为Naive的1.422209倍，原始改善为负42.22%。

final24上，R81对父版本总成本为11胜13负，平均成本倍率1.011696，即平均倍率反而上升1.17%；去掉D仍为1.011619。相对Naive的未裁剪平均成本降幅由父版本39.5471%降至38.3362%，而裁剪后的分数从4.090157升到4.094140。二者并不矛盾：负改善截为0后，损失被部分隐藏。

另外，`eval_003_random_zipf`成本增加5.32%、`eval_080_random_lognormal`增加3.81%、`eval_084_random_lognormal`增加2.09%。这些反例保留，不用换样本或只报胜例掩盖。

| 数据集样本 | R81/父版成本均值 | 中位数 | P90 | 最坏 | 胜/负 |
|---|---:|---:|---:|---:|---:|
'''
for w,s in summaries.items():
 c=next(a for a in s['groups']['all'] if a['method']=='R81_op256_cond2048')['cost_to_parent']
 text+=f"| {w} | {c['mean']:.6f} | {c['p50']:.6f} | {c['p90']:.6f} | {c['worst']:.6f} | {c['wins']}/{c['losses']} |\n"
text+='''
dyna对父版也是三胜三负，并非全胜；最坏增加3.09%，发生在slow_shared_01。但它在fast_staggered_04将分数从1.369500恢复至1.683119，接近本轮R75的1.689127；slow_staggered_07也改善。R81对R79在dyna六例均胜，但这不能替代与更强父版的配对比较。

### 耗时与相对Naive的分位数

| 样本 | 方法 | 成本/Naive中位数 | P90 | 最坏 | 每例累计D（ms） |
|---|---|---:|---:|---:|---:|
'''
for w,s in summaries.items():
 for a in s['groups']['all']:
  n=a['ratio_to_Naive'];text+=f"| {w} | {labels[a['method']]} | {n['p50']:.6f} | {n['p90']:.6f} | {n['worst']:.6f} | {a['D_mean_us']/1000:.3f} |\n"
text+='''
D是完整输入期间累计的决策耗时，再在该数据集样本内平均，不能当作单步耗时。两个运行窗口的D分别报告；单次重复不能支持微小速度优势的显著性结论。模拟IO与miss成本并非实际磁盘端到端时间。
'''
for w,s in summaries.items():
 text+='\n### '+w+'逐例分数\n\n| 用例 | Naive | R75 | R79 | R80共享 | R80双方案 | R81算子256 |\n|---|---:|---:|---:|---:|---:|---:|\n'
 sel=read(f'tmp/r81_regression_eval/{w}/selection.json');idx={(a['case_id'],a['method']):a for a in s['per_case']}
 for c in sel['cases']:
  text+='| '+c['case_id']+' | '+' | '.join(f"{idx[c['case_id'],m['name']]['score']:.6f}" for m in sel['methods'])+' |\n'
text+='''
## 本轮结论与继续推进

R81在所测数据集等权均分最高，但静态分布尾部退步明显，未通过事前的替换约束。保留其作为动态场景专家的研究候选，不宣布普遍优于共享概率版，也不自动改默认。R82已经另行实现两项独立非网络消融：补足全体single-fit候选，以及校准立即写盘权重；它们仍从R80父版出发，不将R81收益或退化混入。

本轮共保存438格性能输出、876份stdout/stderr，分别为228 TRAIN、30 DEV、36 dyna和144 final，不能当成一次连续硬件计时。全部四个窗口均完整，源码/框架不变，候选在TRAIN后没有调参。

补充记录：`tmp/r81_regression_eval/{dyna,final}/`。独立报告和每例的原始成本、物理成本、D、裁剪分数与未裁剪改善见`tmp/r81_review/regression_review.json`、`dyna_regression_per_case.csv`、`final_regression_per_case.csv`、`regression_member_equal_scores.csv`。dyna summary SHA256为`72365df3c39360c48c1ebfcb41cb98606b46dcfcbadc9445bbc8487fa5682c0f`；final summary SHA256为`fb0b226be520dbd33732ee17a7e03d249fb51af970852a950618b724573a675b`。
'''
p=ROOT/'docs/20261030_R81双时间尺度热度实验.md';s=p.read_text(encoding='utf-8');assert '## 原 dyna 与 final 的同轮回归' not in s
lead='\n**最终结论：两数据集样本等权均分4.050745，高于R80共享概率的4.000974；但final单例最坏相对父版退化27.04%，未通过事前尾部门槛，不建议直接替换。原dyna六例同轮R75为3.899200、R80共享概率3.911790、R81为4.007351。**\n'
s=s.replace('\n## 改了什么',lead+'\n## 改了什么',1)
p.write_text(s+text,encoding='utf-8',newline='\n')
print(hashlib.sha256(p.read_bytes()).hexdigest())
