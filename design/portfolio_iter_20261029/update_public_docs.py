"""Refresh the curated entry notes from the frozen, verified checkpoint."""
from pathlib import Path
import json
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent;D=ROOT.parent
def read(p):return json.loads(p.read_text('utf8'))
def main():
    c=read(ROOT/'published_checkpoint.json');m=read(ROOT/'current_model.json');v=c['summary'];pages=len(PdfReader(D/'topic20_portfolio_iteration_report.pdf').pages)
    proof=D/'member_eval_20261030'/(c['member_report'].replace('_members.json','_action_verification.json'))
    assert proof.is_file() and read(proof)['source_sha256']==c['source_sha256']
    rows=[f"{r['member']} {r['version']}/{r['case_count']}：平均Score {r['mean_score_us']:,.2f} us，比Naive下降{r['decrease_vs_naive_percent']:.4f}%；原逐例分均值{r['mean_case_points_0_10']:.4f}/10。" for r in c['members']]
    current=["第20题当前方案 | 2026-10-30",'',
        '本地785例平均完整Score目标推荐：MySpillScheduler_tree.cpp。',
        f"8专家，最大{m['max_depth']}层、{m['node_count']}节点、{m['leaf_count']}叶子；路径最多{m['max_depth']}次比较。",
        'C++14单文件，无main；只使用合法当前状态和自身观测历史，不依赖推理库。',
        '跨算子候选、阶段/软配额、ghost反馈及保守next_op处理；overflow/miss重选。',
        'periodic只有下一INSERT将溢出时分类；periodic PROBE用保守预载。','',
        '最新实际接入方式：'+c['deployment'],
        f"785例各3次，平均Score {v['mean_score']:,.2f} us，比同批Naive下降{v['decrease_vs_naive_percent']:.4f}%。",
        f"平均完整决策耗时{v['mean_decision_us']:.2f} us/例；该时间已计入Score。",*rows,
        '仓库成员未封顶sum等权主分：'+f"{c['public_score_summary']['score_final']:.6f}。原cap50三份集合均为50。",
        '原始均值、未封顶sum、逐例均分是不同指标，不混用；坏例完整保留。',
        'Vanius单集仍比早期父树ID30退步约10.78%；原NN在部分成员原始均值上更好。',
        '这是已观察开发/回归数据上的结果，不预测官方未知分布或声称全输入最优。','',
        '独立核查：785例动作/容量/lazy特征，2355次部署SDK I/O与hit/miss一致。',
        '源码SHA256：'+c['source_sha256'],
        '数据提交：'+c['dataset_commit'],'suite_id：'+c['suite_id'],
        '运行：python design/tools/run.py --policy recommended --input <正式输入文件>',
        'tree同推荐；rule为旧规则；neural为原NN；baseline为官方Naive。','',
        f'中文说明：topic20_portfolio_iteration_report.pdf（{pages}页）。',
        '当前模型/状态：portfolio_iter_20261029/current_model.json、published_checkpoint.json。',
        '成员分项：member_eval_20261030/'+c['member_report'],
        '动作核查：'+proof.relative_to(D).as_posix(),
        '原字节结果包：portfolio_iter_20261029/'+c['measurement_bundle'],
        '可移植源码快照：portfolio_iter_20261029/'+c['source_bundle'],
        '更多理论：expert1局部2近似和offline_bounds_20261030离线成本下界。',
        '下界只在185可计算例上核对；其余600例明确跳过，不作为已证近最优。',
        '截图、批量原始输入、工作目录、二进制和预览图不提交到源码分支。']
    (D/'CURRENT_SOLUTION.txt').write_text('\n'.join(current)+'\n',encoding='utf8')
    readme=["第20题关键项目文件 | source/liunianwww | 2026-10-30",'',
        '当前本地平均完整Score目标推荐：MySpillScheduler_tree.cpp。',
        f"8专家，由最大{m['max_depth']}层小树动态选择；C++14、仅CPU、无外部推理库。",
        '正式框架仅替换调度器，保持执行、容量和计时范围不变。','',
        '编译/运行：python design/tools/run.py --policy recommended --input <正式输入文件>',
        '只编译：python design/tools/run.py --policy tree',
        'policy还支持rule、neural、baseline、scan-fused、experimental、cross-feedback。',
        '每次只接入一个同名MySpillScheduler实现，输出在design/build，禁止混编多个。','',
        f"最新785例×3：平均Score {v['mean_score']:,.2f} us，比Naive下降{v['decrease_vs_naive_percent']:.4f}%。",
        '三成员209/48/528，版本及完整分项见CURRENT_SOLUTION.txt。',
        '目前按原始平均Score选推荐。未封顶成员sum与真实成本同时展示，不宣称各集都优于所有版本。','',
        '中文PDF：topic20_portfolio_iteration_report.pdf（实现、创新、文献、局部证明、实测与限制）。',
        '当前冻结状态：portfolio_iter_20261029/published_checkpoint.json。',
        '训练、Score搜索与解包复现：portfolio_iter_20261029/README.txt。',
        '单文件部署源码包的引用已归一为相对路径；重编译三程序与计时二进制SHA逐字节相同。',
        '离线下界工具：offline_bounds_20261030；读取未来/p/B仅为评测，绝不能接入在线调度。',
        '文件列表与SHA256：project_manifest.json。','',
        '仍保留旧568例、NN和规则历史报告，各自日期/集合/重复数不迁移为本轮成绩。',
        '原始截图、批量输入、工作树、二进制和临时预览不提交。',
        '准备中的collect_full_horizon、categorical_transition、admission工具尚未产生本轮结果；',
        '当前交付模型不包含这些未验证方案。']
    (D/'README.txt').write_text('\n'.join(readme)+'\n',encoding='utf8')
    result=D/'results_summary.json';s=read(result);s['portfolio_20261030']=c;s['leaf_refinement_development_rounds']=[dict(tag=tag,summary=read(ROOT/(tag+'_summary.json'))['summary']) for tag in ['members_r5','members_r6']];result.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Entry notes updated',c['name'],v['mean_score'])
if __name__=='__main__':main()
