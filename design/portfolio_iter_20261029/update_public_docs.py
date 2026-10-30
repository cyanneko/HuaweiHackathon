"""Refresh the curated entry notes from the frozen, verified checkpoint."""
from pathlib import Path
import json
from pypdf import PdfReader
if __package__:
    from .snapshot_reader import read_json, available
else:
    from snapshot_reader import read_json, available
ROOT=Path(__file__).resolve().parent;D=ROOT.parent
def read(p):return read_json(p)
def full_horizon_status(record,model=None):
    if not isinstance(record,dict):return '完整后缀采集状态以对应provenance为准。'
    status=record.get('status')
    if status=='collected':
        validation=record.get('validation',{});details=[]
        if 'label_rows' in validation:details.append(f'{validation["label_rows"]}个状态')
        if 'represented_training_inputs' in validation:details.append(f'覆盖{validation["represented_training_inputs"]}份train')
        if record.get('training_cases'):details.append(f'{record["training_cases"]}份train inventory')
        if isinstance(model,dict) and model.get('training_horizon')=='full_remaining':
            suffix=('；用于前轮类别节点更新，本轮继续沿用；当前部署状态另见checkpoint。' if 'next_deficit_shift' in model else '；已用于当前类别节点更新，并完成完整Score回归及独立部署复测。')
        else:suffix='；训练与完整Score结论见各轮绑定记录。'
        return '完整后缀标签已采集'+('，'+'、'.join(details) if details else '')+suffix
    if status=='collecting':return '完整后缀标签采集中，不能计作已完成结果。'
    if status=='prepared':return '完整后缀教师已准备，尚未开始采集。'
    if status=='failed':return '完整后缀采集未成功完成，不作为已验证训练结果。'
    return '完整后缀采集状态见provenance。'


def category_ids(mask):
    return '{'+','.join(str(i) for i in range(8) if mask&(1<<i))+'}'


def independent_checkpoint(checkpoint):
    return (checkpoint.get('status','').startswith('completed')
        and 'standalone' in checkpoint.get('sdk_report','').lower()
        and 'independently' in checkpoint.get('deployment','').lower())


def current_category_note(model,checkpoint):
    transition=model.get('category_transition',{});proposal=transition.get('proposal',{})
    if not transition or type(proposal.get('category_mask')) is not int:
        return '当前类别更新以current_model和测量绑定记录为准。'
    before=category_ids(transition.get('parent_mask',7));after=category_ids(proposal['category_mask'])
    if 'next_deficit_shift' in model:
        return (f'前轮类别113已验证采用：节点{transition["node"]}左侧ID集合{before}→{after}，mask={proposal["category_mask"]}。'
            f'本轮沿用{model["node_count"]}节点、深度{model["max_depth"]}，仅扩展next目标保护比较，不重新训练类别树。')
    state='当前checkpoint已确认独立部署完成。' if independent_checkpoint(checkpoint) else '独立部署完成状态以checkpoint为准。'
    return (f'当前类别更新mode {checkpoint["mode"]}已采用：节点{transition["node"]}左侧ID集合{before}→{after}，'
        f'mask={proposal["category_mask"]}；仍为深度{model["max_depth"]}。'+state)


def round9_notes():
    path=ROOT/'members_r9_summary.json'
    if not available(path):return [],None
    report=read(path);summary=report.get('summary',{})
    if '108' not in summary:return [],report
    baseline=summary['108']['mean_score'];parts=[]
    for mode in ['118','121']:
        if mode not in summary:continue
        change=100*(summary[mode]['mean_score']/baseline-1)
        parts.append(mode+(f'上升{change:.4f}%' if change>0 else f'下降{-change:.4f}%'))
    lines=[]
    if parts:lines.append('完整后缀全树重拟合已生成8候选；118/121在840份train优胜，但members_r9同批785例相对108的平均Score'+ '、'.join(parts)+'，未采用。')
    if '113' in summary:
        row=summary['113'];change=100*(1-row['mean_score']/baseline)
        lines.append(f'历史类别113在members_r9同批平均Score为{row["mean_score"]:,.2f} us，相对108'+(f'下降{change:.4f}%' if change>=0 else f'上升{-change:.4f}%')+'；不含后续next保护公共层，最终交付另以checkpoint为准。')
    return lines,report


def member_tradeoff_note(report,mode,baseline='108'):
    regressed=[]
    if isinstance(report,dict):
        for member,values in report.get('by_member',{}).items():
            if str(mode) in values and baseline in values and values[str(mode)]['mean_score']>values[baseline]['mean_score']:
                regressed.append(member)
    prefix='当前方案相对'+baseline+'，'+ '、'.join(regressed)+'的原始平均Score略退步；' if regressed else ''
    return prefix+'选择目标是785例raw平均Score，并非每个成员分别最优；原NN在部分成员原始均值上仍更好。'


def next_deficit_notes(model,checkpoint):
    if 'next_deficit_shift' not in model:return [],None
    shift=model['next_deficit_shift']
    prefix='当前继承142的' if 'exact_next_credit_shift' in model else '当前启用'
    lines=[f'{prefix}next_deficit_shift={shift}（按字段存在性判断，0也有效），树和8类专家不变；保留forced_cover及admission=2。',
        'next目标q保护：d=max(0,qsize-(M-used+f1-sizep))，阈值qRead+max(1,floor(d/2^k)/W)。',
        '只有新增接受区有两已知PROBE服务前缀IO证书；q可periodic预载，不能假设必miss。范围排除q服务后的periodic，不保证D、未知未来或全Score。']
    path=ROOT/'members_r12_summary.json';report=read(path) if available(path) else None
    if isinstance(report,dict) and '113' in report.get('summary',{}):
        summary=report['summary'];base=summary['113']['mean_score'];parts=[]
        for mode in ['142','143','144']:
            if mode not in summary:continue
            gain=100*(1-summary[mode]['mean_score']/base)
            parts.append(mode+(f'下降{gain:.5f}%' if gain>=0 else f'上升{-gain:.5f}%'))
        if parts:lines.append('members_r12同批785例×3，相对父113平均完整Score：'+'、'.join(parts)+'。额外收益不挪作历史r10/r11同层消融成绩。')
    state='当前checkpoint已确认独立接入复测完成。' if independent_checkpoint(checkpoint) else '当前checkpoint尚未确认独立接入复测完成，研究批次不替代独立接入。'
    lines.append(state)
    lines.append('正式固定expert1范围诊断见next_deficit_scope_verification.json；其前缀收益与追加未知访问后的反转均不等于当前在线树路由成绩。')
    return lines,report


def exact_credit_notes(model,checkpoint):
    if 'exact_next_credit_shift' not in model:return [],None
    shift=model['exact_next_credit_shift']
    lines=[f'当前额外启用exact_next_credit_shift={shift}（0也有效），保留142的旧缺口条件；树、8类专家和admission=2不变。',
        '旧比较失败后，先检查(f2-f1)/W<=sizeq/R+floor(sizep/2^k)/W；可能通过时，扫描已计算的other，核对其每个牺牲分区都满足s(x)>M-sizep-sizeq。',
        '合法且无重复的other由强制集合组成时，达到固定p、q共存需求的立即写量下界。原方案在q服务时若还保留p，必须已写出该集合且额外写读q；若p已不在，则至少额外写过sizep且读q。',
        '新增接受区的局部IO证书截止q服务结束、q之后的periodic之前；原启发式区域、D、未知未来、全Score与浮点机器认证均不保证。额外只扫描other，不新增规划或全分区扫描。']
    path=ROOT/'members_r13_summary.json';report=read(path) if available(path) else None
    if isinstance(report,dict) and '142' in report.get('summary',{}):
        scores=report['summary'];base=scores['142']['mean_score'];parts=[]
        for mode in ['145','146','147']:
            if mode not in scores:continue
            delta=100*(scores[mode]['mean_score']/base-1)
            parts.append(mode+(f'上升{delta:.5f}%' if delta>0 else f'下降{-delta:.5f}%'))
        if parts:lines.append('members_r13同批785例×3，相对142完整平均Score：'+'、'.join(parts)+'；研究程序D已计入，独立部署采用当前checkpoint数据。')
        lines.append('完整train_g10最优145在回归反而退化；146按已观察开发回归结果选择，不能把该集合当作未见盲测。')
    effects_path=ROOT/'exact_credit_result.json';effects=read(effects_path) if effects_path.is_file() else None
    if (isinstance(effects,dict) and effects.get('status')=='passed'
        and effects.get('source_identity',{}).get(str(checkpoint['mode']),{}).get('sha256')==checkpoint['source_sha256']):
        aggregate=effects.get('comparisons',{}).get(str(checkpoint['mode']),{}).get('aggregate',{})
        if all(key in aggregate for key in ['action_digest_changed_cases','physical_improved_cases','physical_regressed_cases','physical_equal_cases','mean_delta']):
            benefit=-aggregate['mean_delta']['physical_cost_delta_us']
            lines.append(f'同批r13仅{aggregate["action_digest_changed_cases"]}例动作改变（{aggregate["physical_improved_cases"]}例改善/{aggregate["physical_regressed_cases"]}例退化，均liunianwww），{aggregate["physical_equal_cases"]}例物理相同；剔D平均净收益{benefit:,.2f} us，主要集中一例。Vanius/Cy微小差异仅D，不称普遍提升；来源exact_credit_result.json。')
    lines.append('固定expert1的全量补偿正例及未知A尾部反转见exact_next_credit_scope_verification.json。该例shift1/2保持父方案，不能冒充当前树路由或完整Score的理论保证。')
    return lines,report

def admission_notes(result):
    if not isinstance(result,dict):return []
    lines=[];train=result.get('train',{});members=result.get('members',{})
    trained=[k for k,r in train.get('candidates',{}).items() if r.get('status')=='complete']
    measured=[k for k,r in members.get('candidates',{}).items() if r.get('status')=='complete']
    missing=[k for k,r in members.get('candidates',{}).items() if r.get('status')=='unavailable']
    if trained and train.get('cases'):
        line=f'admission：{len(trained)}档候选已完成{train["cases"]}份train评分'
        if measured and members.get('cases') and members.get('repeats'):
            line+=f'；{members["cases"]}例×{members["repeats"]}次已测mode '+ '/'.join(measured)
        if missing:line+='；'+ '/'.join(missing)+'无本批成员结果'
        lines.append(line+'。')
    comparisons=[]
    for mode in ['98','99','108']:
        record=members.get('candidates',{}).get(mode,{})
        rate=record.get('overall',{}).get('metrics',{}).get('Total_Score',{}).get('decrease_percent')
        if record.get('status')=='complete' and isinstance(rate,(int,float)):
            comparisons.append(mode+(f'上升{-rate:.6f}%' if rate<0 else f'下降{rate:.9f}%'))
    if comparisons:lines.append('admission研究配对轮相对mode '+str(result.get('baseline_mode','父方案'))+'的平均Score：'+'，'.join(comparisons)+'；微小收益不等于隐藏测试保证。')
    return lines

def main():
    c=read(ROOT/'published_checkpoint.json');m=read(ROOT/c['model']);v=c['summary'];pages=len(PdfReader(D/'topic20_portfolio_iteration_report.pdf').pages)
    admission_model='periodic_admission_shift' in m or 'admission_model' in m
    factor=(1<<m['periodic_admission_shift']) if type(m.get('periodic_admission_shift')) is int and 0<=m['periodic_admission_shift']<=3 else None
    admission_result=read(ROOT/'admission_result.json') if (ROOT/'admission_result.json').is_file() else None
    full_path=ROOT/'members_full108_r1_provenance.json'
    full_status=full_horizon_status(read(full_path) if full_path.is_file() else None,m)
    category_status=current_category_note(m,c)
    full_round_notes,round9=round9_notes()
    next_notes,round12=next_deficit_notes(m,c)
    exact_notes,round13=exact_credit_notes(m,c)
    tradeoff=(member_tradeoff_note(round13,c['mode'],'142') if 'exact_next_credit_shift' in m
        else member_tradeoff_note(round12,c['mode'],'113') if 'next_deficit_shift' in m
        else member_tradeoff_note(round9,c['mode']))
    deployment_status='当前checkpoint已确认独立程序部署复测完成。' if independent_checkpoint(c) else '当前checkpoint记录研究程序测量；独立程序部署完成状态以后续checkpoint为准。'
    admission_status=('周期admission公共层已实现并启用'+(f'，factor={factor}' if factor is not None else '')+'，保持8专家。' if admission_model else '当前模型未启用周期admission公共层。')
    periodic_insert=('periodic下一INSERT将溢出时先分类；证书通过可落盘正大小目标，令下条INSERT走磁盘追加。' if admission_model else 'periodic只有下一INSERT将溢出时分类。')
    proof=D/'member_eval_20261030'/(c['member_report'].replace('_members.json','_action_verification.json'))
    assert proof.is_file() and read(proof)['source_sha256']==c['source_sha256']
    rows=[f"{r['member']} {r['version']}/{r['case_count']}：平均Score {r['mean_score_us']:,.2f} us，比Naive下降{r['decrease_vs_naive_percent']:.4f}%；原逐例分均值{r['mean_case_points_0_10']:.4f}/10。" for r in c['members']]
    current=["第20题当前方案 | 2026-10-30",'',
        '本地785例平均完整Score目标推荐：MySpillScheduler_tree.cpp。',
        f"8专家，最大{m['max_depth']}层、{m['node_count']}节点、{m['leaf_count']}叶子；路径最多{m['max_depth']}次判断（含类别位测试）。",
        'C++14单文件，无main；只使用合法当前状态和自身观测历史，不依赖推理库。',
        '跨算子候选、阶段/软配额、ghost反馈及保守next_op处理；overflow/miss重选。',
        periodic_insert+'periodic PROBE仍不分类，用保守预载。',admission_status,'',
        '最新实际接入方式：'+c['deployment'],deployment_status,
        f"785例各3次，平均Score {v['mean_score']:,.2f} us，比同批Naive下降{v['decrease_vs_naive_percent']:.4f}%。",
        f"平均完整决策耗时{v['mean_decision_us']:.2f} us/例；该时间已计入Score。",*rows,
        '仓库成员未封顶sum等权主分：'+f"{c['public_score_summary']['score_final']:.6f}。原cap50三份集合均为50。",
        '原始均值、未封顶sum、逐例均分是不同指标，不混用；坏例完整保留。',
        tradeoff,
        '这是已观察开发/回归数据上的结果，不预测官方未知分布或声称全输入最优。','',
        '独立核查：785例动作/容量/lazy特征，2355次对应SDK I/O与hit/miss一致；接入方式与独立部署状态见上文。',
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
        '旧耦合下界在185例上核对、600例跳过；新window_bounds界已覆盖785例，二者各自绑定原记录，均不等于可达收益或已证近最优。',
        'admission只证明已知下一INSERT写入体的局部写量，截止其后新periodic动作之前，不保证完整Score。',
        '教师labeltimer为离线回调成本代理，不能替代正式引擎D；正式Score始终计入实际回调时间。',
        full_status,category_status,*next_notes,*exact_notes,*full_round_notes,*admission_notes(admission_result),
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
        '目前按原始平均Score选推荐。未封顶成员sum与真实成本同时展示，不宣称各集都优于所有版本。',tradeoff,'',
        '中文PDF：topic20_portfolio_iteration_report.pdf（实现、创新、文献、局部证明、实测与限制）。',
        '当前冻结状态：portfolio_iter_20261029/published_checkpoint.json。',
        '训练、Score搜索与解包复现：portfolio_iter_20261029/README.txt。',
        '当前测量接入方式：'+c['deployment']+'；源码、二进制身份及重复数以checkpoint绑定记录为准。',deployment_status,
        '离线下界工具：offline_bounds_20261030；读取未来/p/B仅为评测，绝不能接入在线调度。',
        '文件列表与SHA256：project_manifest.json。','',
        '仍保留旧568例、NN和规则历史报告，各自日期/集合/重复数不迁移为本轮成绩。',
        '原始截图、批量输入、工作树、二进制和临时预览不提交。',
        full_status,
        category_status,*next_notes,*exact_notes,*full_round_notes,
        admission_status,*admission_notes(admission_result),
        'admission为公共提前处置层，非第9类专家；局部证书截止下条INSERT写入结束、其后periodic动作之前。',
        '后续增长、Probe与回调D可能改变收益，不宣称完整Score的理论保证。',
        '训练labeltimer仅为离线成本代理，最终性能以正式框架回调计时与完整Score为准。']
    (D/'README.txt').write_text('\n'.join(readme)+'\n',encoding='utf8')
    result=D/'results_summary.json';s=read(result);s['portfolio_20261030']=c;s['leaf_refinement_development_rounds']=[dict(tag=tag,summary=read(ROOT/(tag+'_summary.json'))['summary']) for tag in ['members_r5','members_r6']];result.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Entry notes updated',c['name'],v['mean_score'])
if __name__=='__main__':main()
