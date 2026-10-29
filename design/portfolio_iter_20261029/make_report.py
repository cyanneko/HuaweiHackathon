"""Create the Chinese portfolio checkpoint PDF from completed, frozen evidence."""
from pathlib import Path
import json,os
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parent
D=ROOT.parent
OUT=D/'topic20_portfolio_iteration_report.pdf'
def read(p):return json.loads(p.read_text(encoding='utf8'))

def admission_evidence(result):
    """Short historical comparisons; omit any metrics absent from the record."""
    if not isinstance(result,dict):return []
    lines=[];train=result.get('train',{});members=result.get('members',{})
    trained=[k for k,r in train.get('candidates',{}).items() if r.get('status')=='complete']
    measured=[k for k,r in members.get('candidates',{}).items() if r.get('status')=='complete']
    missing=[k for k,r in members.get('candidates',{}).items() if r.get('status')=='unavailable']
    if trained and train.get('cases'):
        line=f'{len(trained)}档候选已完成{train["cases"]}份train评分'
        if measured and members.get('cases') and members.get('repeats'):
            line+=f'；{members.get("tag","成员回归轮")}为{members["cases"]}例×{members["repeats"]}次，已测mode '+ '/'.join(measured)
        if missing:line+='；'+ '/'.join(missing)+'无本批成员结果'
        lines.append(line+'。')
    comparisons=[]
    for mode in ['98','99','108']:
        record=members.get('candidates',{}).get(mode,{})
        metric=record.get('overall',{}).get('metrics',{}).get('Total_Score',{})
        rate=metric.get('decrease_percent')
        if record.get('status')!='complete' or not isinstance(rate,(int,float)):continue
        comparisons.append(f'{mode}平均Score'+(f'上升{-rate:.6f}%' if rate<0 else f'下降{rate:.9f}%'))
    if comparisons:lines.append('同批相对mode '+str(result.get('baseline_mode','父方案'))+'：'+'，'.join(comparisons)+'。')
    overall=members.get('candidates',{}).get('108',{}).get('overall',{})
    delta=overall.get('metrics',{}).get('Physical_Cost_Without_D',{}).get('delta_mean_candidate_minus_baseline')
    outcomes=overall.get('physical_case_outcomes',{})
    if isinstance(delta,(int,float)):
        line='108剔D成本平均'+(f'减少{-delta:,.2f}' if delta<=0 else f'增加{delta:,.2f}')+' μs/例'
        if all(k in outcomes for k in ['improved','regressed','tolerance']):
            line+=f'，{outcomes["improved"]}例改善/{outcomes["regressed"]}例退化（{outcomes["tolerance"]} μs公差）'
        lines.append(line+'；微小收益及CPU波动须与坏例共同披露。')
    return lines

def full_horizon_status(record,model=None):
    if not isinstance(record,dict):return '完整后缀采集状态以对应provenance为准。'
    status=record.get('status')
    if status=='collected':
        validation=record.get('validation',{});details=[]
        if 'label_rows' in validation:details.append(f'{validation["label_rows"]}个状态')
        if 'represented_training_inputs' in validation:details.append(f'覆盖{validation["represented_training_inputs"]}份train')
        if record.get('training_cases'):details.append(f'{record["training_cases"]}份train inventory')
        suffix='；已用于当前类别节点更新，并完成完整Score回归及独立部署复测。' if isinstance(model,dict) and model.get('training_horizon')=='full_remaining' else '；训练与完整Score结论见各轮绑定记录。'
        return '完整后缀标签已采集'+('，'+'、'.join(details) if details else '')+suffix
    if status=='collecting':return '完整后缀标签正在采集，不能计作已完成结果。'
    if status=='prepared':return '完整后缀教师已准备，尚未开始采集。'
    if status=='failed':return '完整后缀采集未成功完成，不作为已验证训练结果。'
    return '完整后缀采集状态见对应provenance。'


def category_ids(mask):
    return '{'+','.join(str(i) for i in range(8) if mask&(1<<i))+'}'


def member_tradeoff_line(record,mode):
    if not isinstance(record,dict):return '当前按全部案例raw平均Score选择，不要求各成员分别最优。'
    changes=[]
    for member,values in record.get('by_member',{}).items():
        if str(mode) not in values or '108' not in values:continue
        base=values['108']['mean_score'];value=values[str(mode)]['mean_score']
        if base<=0:continue
        change=100*(value/base-1)
        changes.append(member+(f'上升{change:.4f}%' if change>0 else f'下降{-change:.4f}%'))
    return ('同批相对108，成员平均Score：'+'，'.join(changes)+'。' if changes else '')+'选择目标是785例raw平均Score，而非每个成员分别最优。'

def main():
    checkpoint=read(ROOT/'published_checkpoint.json')
    member=read(D/'member_eval_20261030'/checkpoint['member_report'])
    chosen=member['candidates'][str(checkpoint['mode'])]
    model=read(ROOT/checkpoint['model'])
    admission_model='periodic_admission_shift' in model or 'admission_model' in model
    admission_result=read(ROOT/'admission_result.json') if (ROOT/'admission_result.json').is_file() else None
    admission_factor=(1<<model['periodic_admission_shift']) if type(model.get('periodic_admission_shift')) is int and 0<=model['periodic_admission_shift']<=3 else None
    standalone='standalone' in checkpoint.get('sdk_report','').lower() or 'independently' in checkpoint.get('deployment','').lower()
    full_path=ROOT/'members_full108_r1_provenance.json'
    full_record=read(full_path) if full_path.is_file() else None
    category=model.get('category_transition',{})
    category_proposal=category.get('proposal',{})
    round9_path=ROOT/'members_r9_summary.json'
    round9=read(round9_path) if round9_path.is_file() else None
    train6_path=ROOT/'train_g6_840_summary.json'
    train6=read(train6_path) if train6_path.is_file() else None
    old=read(ROOT/'progress.json')
    candidates=[]
    if os.environ.get('CHINESE_PDF_FONT'):candidates.append(Path(os.environ['CHINESE_PDF_FONT']))
    if os.environ.get('WINDIR'):candidates.append(Path(os.environ['WINDIR'])/'Fonts'/'simsun.ttc')
    candidates.append(Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc'))
    font=next((p for p in candidates if p.is_file()),None)
    if font is None:raise FileNotFoundError('Set CHINESE_PDF_FONT to a Chinese TrueType font')
    pdfmetrics.registerFont(TTFont('Song',str(font),subfontIndex=0))
    pdfmetrics.registerFontFamily('Song',normal='Song',bold='Song',italic='Song',boldItalic='Song')
    blue=colors.HexColor('#153C57');teal=colors.HexColor('#087C83')
    styles={
      'title':ParagraphStyle('title',fontName='Song',fontSize=24,leading=33,textColor=blue,spaceAfter=14,wordWrap='CJK'),
      'h':ParagraphStyle('h',fontName='Song',fontSize=17,leading=24,textColor=blue,spaceAfter=13,wordWrap='CJK'),
      'sub':ParagraphStyle('sub',fontName='Song',fontSize=11.5,leading=18,textColor=teal,spaceBefore=8,spaceAfter=5,wordWrap='CJK'),
      'body':ParagraphStyle('body',fontName='Song',fontSize=10,leading=16,spaceAfter=8,wordWrap='CJK'),
      'small':ParagraphStyle('small',fontName='Song',fontSize=8.1,leading=12.5,spaceAfter=6,wordWrap='CJK'),
      'cell':ParagraphStyle('cell',fontName='Song',fontSize=8.5,leading=13,wordWrap='CJK')}
    story=[]
    def p(s,style='body'):story.append(Paragraph(s,styles[style]))
    def h(s):p(s,'sub')
    def page(n,title):
        if story:story.append(PageBreak())
        p(f'{n:02d} / {title}','h')
    def table(rows,widths):
        t=Table([[Paragraph(escape(str(x)),styles['cell']) for x in r] for r in rows],colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDECF1')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F4F7F8')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(t);story.append(Spacer(1,8))

    p('第20题 · 跨算子动态落盘调度','sub')
    p('8专家与微型决策树\u3000<br/>三成员数据集迭代报告','title')
    p('已完成测量的阶段记录 | 2026-10-30 | C++14 / CPU','small')
    p('方案将策略选择建模为成本敏感分类：读取合法状态和自身历史，小树输出专家编号。'+('公共证书可直接提前处置，其余执行所选专家。' if admission_model else '只执行被选中的专家。')+'训练与部署均已实现；下表Score包含公开执行器实测回调耗时。')
    h('当前本地最佳：'+escape(chosen['name']))
    v=chosen['all_case_summary']
    p(f'785例平均Score为 <b>{v["mean_score"]:,.2f} μs</b>，相对同批官方Naive下降 <b>{v["decrease_vs_naive_percent"]:.4f}%</b>。这是反复观察的开发/回归数据上的结果，尚无官方隐藏测试成绩，也不是全输入最优证明。')
    table([['成员 / 版本','例数','平均Score / μs','比Naive下降','原逐例分均值 / 10']]+[[r['member']+' / '+r['version'],r['case_count'],f'{r["mean_score_us"]:,.2f}',f'{r["decrease_vs_naive_percent"]:.2f}%',f'{r["mean_case_points_0_10"]:.4f}'] for r in chosen['members']],[118,36,158,75,120])
    p('每例串行测量3次，先取逐例算术均值，再对样例取算术均值。三人数据分别为209、48、528例；Vanius0525的17个合法边界例全部计入。空member2/member3未计入。','small')
    raw=read(ROOT/checkpoint['sdk_report'])
    timing_rows=[['同批方法','平均完整决策时间 / μs每例','miss总数']]
    for key,label in [('0','原NN'),('2','官方Naive')]:
        r=raw['summary'][key];timing_rows.append([label,f'{r["mean_decision_us"]:,.2f}',f'{r["miss_count"]:,.0f}'])
    timing_rows.append(['当前方案',f'{v["mean_decision_us"]:,.2f}',f'{v["miss_count"]:,.0f}'])
    table(timing_rows,[118,242,147])
    p('计时接入方式：'+escape(checkpoint.get('deployment','见本轮记录'))+'。D包含状态获取、规划及所有实际回调；其高低以同批数值为准，不能从树深度推断，也不把比较次数当作回调时间。','small')
    h('两种指标分别保留')
    score=chosen['public_score_summary']['score_final']
    p(f'仓库主归一化汇总：先对每成员原逐例贡献求和、不做50分总封顶，再对3个成员等权平均，本轮为 <b>{score:.4f}</b>。原封顶50分汇总在三份集合上均已饱和为50，难以区分方案。主归一化分与raw平均Score是不同指标，后者越低越好。')
    p('数据固定提交：e119c2326e198922243306eac062785420ed8156。<br/>套件指纹：'+member['suite_id'],'small')

    page(2,'选择哪些决策方法')
    p('8种专家提供互补的容量、复用、代价与多算子管理能力。文献思想经过本题接口适配，不能直接继承原论文的收益或竞争比。编号0至7才是在线分类标签；评测mode只是完整调度器的离线编号。')
    table([['ID / 方法','本题实现与用途','借鉴与严格性边界'],
      ['0 最大分区','跨算子按驻留字节降序释放空间。','Velox官方落盘文档[1]；快速启发式。'],
      ['1 精确最小写出覆盖','候选≤10时枚举子集，满足缺口且写出字节最少；更大时回退。','当前规划子问题严格最优；不保证后续总代价。'],
      ['2 观测最近访问','按接口实际观测的访问时刻选择。','LRU思想；普通hit无回调，非完整LRU。'],
      ['3 观测热度密度','按(1+衰减热度)/字节评价保留价值。','LHD单位空间价值[2]；未实现原概率模型。'],
      ['4 恢复代价密度','比较[s/W+q·(s/R+32)]/s，兼顾读写。','代价感知缓存[3]；q、32是启发尺度。'],
      ['5 观测GDS','维护通胀值及H=L+c/s，更新可见访问。','GreedyDual-Size[3]；原竞争界不直接适用于本题。'],
      ['6 阶段与算子软配额','跨算子分配软预算，BUILD和PROBE分别规划。','DuckDB多算子内存管理[4]；本实现为启发式。'],
      ['7 自适应反馈控制器','ghost回访反馈切换规则，结合配额和保守next_op。','本项目前版；参考LeCaR反馈思想[5]。']],[97,216,194])
    h('跨算子、阶段与动态感知')
    p('候选分区覆盖全部算子，而非只在当前算子内找牺牲者。BUILD关注当前新增空间，PROBE关注恢复与回访；观测到的miss率、ghost回访、热度及相位持续变化，并输入下一次选择。最终树未必使用全部8类，但候选库保留全部方法。')
    p('缺口D=max(0,d-(M-U))。M是容量，U是当前使用量；溢出时d为新增元组大小，miss时为完整目标分区大小，联合规划时为两分区大小之和。','small')

    page(3,'本项目贡献及局部证明')
    h('贡献一：必落盘集合与学习选择器共用')
    p('令locked为当前请求必须保留的总字节：BUILD含目标已有数据和新增元组，PROBE含目标分区；若另有必须保护的驻留分区，再计入其大小且不重复。任意候选x若s(x)&gt;M-locked，则它无法与locked共存，必定需要落盘。')
    p('令F为所有上述必落盘分区。若Σ(x∈F)s(x)≥D，只落盘F就满足容量；任何合法方案又必须包含F，故其立即写出量至少为Σs(x)。返回F达到该下界。该保证只针对已固定需求及保护条件的立即写出量，不能推出完整未来Score最优。')
    p('例：M=100、必须保留70，驻留候选40与20、缺口30。40无法与70共存，必落盘；它单独覆盖缺口，于是无需运行复杂子集搜索。若所有候选都不构成必落盘，则继续使用被选专家。')
    h('贡献二：按决策事件频率纠正训练权重')
    p('有限采样会低估高频miss/overflow输入。对文件f、回调类k，记录完整轨迹事件数T及采样数S，给每条状态权重T/S。叶子选择argmin_e Σw_i·Loss(C_i,e)，分裂以左右叶子的最小成本下降为目标；不用普通分类准确率代替成本。')
    p('早期父模型使用640份train采样的15,801个状态；扩展三成员后采集20,764个状态，后续树轨迹又采集20,854个状态。当前完整后缀来源见第4页。无决策事件的输入仍保留在完整评测；旧窗口和当前重叠后缀均为代理标签。')
    h('贡献三：沿树路径付出特征成本')
    p(f'当前模型深度{model["max_depth"]}、{model["node_count"]}节点、{model["leaf_count"]}叶子。路由展开为内嵌if/else，最多{model["max_depth"]}次判断（含类别位测试）；cheap特征按路径懒计算，避免先汇总全部分区统计。无需在线模型文件或推理库。')
    p('这不表示整个回调O(1)：公开getSystemState复制、专家候选收集和规划仍可能O(Q)。真正收益必须由实际回调时间和完整Score检验。')
    h('贡献四：完整train Score筛选与类别切换')
    p('前一轮曾限制每次只改一个子叶，保留另一侧原专家；变化侧约占父叶10.18%的训练事件质量。其变更是在原热度密度叶遇到极低读带宽时改用恢复代价密度。这是历史父模型调整，不是本轮唯一变化，也不构成部署风险界。')
    if category and type(category_proposal.get('category_mask')) is int:
        mask=category_proposal['category_mask'];parent_mask=category.get('parent_mask',7)
        p(f'本轮把原节点{category["node"]}的上次专家数值阈值改成类别集合：左侧ID由{category_ids(parent_mask)}改为{category_ids(mask)}（mask={mask}），仍为深度{model["max_depth"]}。只改这一处路由，保留子树与8类专家。经840份完整train筛选、785例回归和独立部署复测采用；公共周期层见第7页。')
    else:p('本轮实际采用变化以current_model与绑定测量为准；所有局部变更均经完整Score评测，不主张首次见于文献。')

    page(4,'在线运行与训练边界')
    periodic_insert=('先分类；证书通过时提前落盘正大小目标，让下条INSERT磁盘追加；否则按所选专家跨算子腾空间。' if admission_model else '提前分类与释放空间，减少之后的压力。')
    table([['触发时机','实际行为'],['首次及后续PROBE miss','每次重新分类，再更新当前可观测反馈，执行所选专家并把当前目标LOAD放在最后。'],['INSERT内存溢出','每次重新分类，排除当前插入目标，跨算子落盘。'],['周期回调看到下一INSERT将溢出',periodic_insert],['周期回调看到下一PROBE','不进行树分类；仅在空闲空间或强制集合条件下保守预载，并更新部分可见历史。'],['普通hit','无对应回调，不编造完整访问时间线。']],[143,364])
    h('next_op只是一条已知操作')
    p('只使用接口给出的next_op，做保守的目标保护、无需额外落盘的联合加载等。没有下一步之后的未来访问流，也看不到真实miss罚分p、总操作数N或周期B。若接口中的pair_fits历史特征有同分区重复计数，它仅为训练特征，容量判断始终由精确动作层完成。')
    h('离线标签与信息隔离')
    p('教师复制同一状态，让8个专家分别执行首动作，再由共同父策略续行。成本含ΔIO+p·Δmiss及离线回调计时代理，后者不是正式引擎D。未来流和真实p只用于离线评分，不进入在线特征。')
    if model.get('training_horizon')=='full_remaining':
        sampling=model.get('sampling',{});inventory=model.get('data_isolation',{}).get('train_inputs',category.get('train_input_count'))
        p(f'当前training_horizon=full_remaining：每个首动作一直续行至输入末尾，采集{sampling.get("rows",3854)}个状态、覆盖{sampling.get("represented_inputs",783)}份输入，训练inventory共{inventory or 840}份。早期384步、BUILD最多2048步属于历史标签设置。完整后缀仍有固定续行偏差及T/S重叠，不是全局oracle。')
    else:p('历史有限窗口为384步，BUILD可延伸至SWITCH后128步且最多2048步；当前使用的标签horizon以模型及provenance记录为准。')
    p('训练检查了输入字节、原始操作流和按key%P归一的操作流，避免同一流跨train/eval；标签实际只来自train。用于比较或反复查看的eval已是开发/回归数据，不能称为未见盲测。')
    h('时间与容量边界')
    diagnosis_path=ROOT/(checkpoint['sdk_report'].replace('_summary.json','_diagnosis.json'))
    if diagnosis_path.is_file():
        dr=read(diagnosis_path)['candidates'][str(checkpoint['mode'])]['aggregate']
        p(f'本批sum(D)/sum(Score)约{dr["global_decision_share_percent"]:.8f}%，即使把D全部消除，对总体原始Score的收益也受此比例限制；但有{dr["decision_dominant_ge_90_percent_cases"]}个正成本案例的D占比≥90%，逐例归一化仍对回调开销敏感。两种目标须分别衡量。')
    callbacks_path=ROOT/checkpoint['sdk_report'].replace('_summary.json','_callback_cost.json')
    if callbacks_path.is_file():
        cb=read(callbacks_path);pair=cb.get('candidates',{});key=str(checkpoint['mode'])
        if cb.get('status')=='passed' and '0' in pair and key in pair:
            nn=pair['0']['aggregate'];tr=pair[key]['aggregate']
            p(f'独立计数（原NN/当前树）：回调{nn["callbacks_per_suite_pass"]:,}/{tr["callbacks_per_suite_pass"]:,}次，分类{nn["classifications_per_suite_pass"]:,}/{tr["classifications_per_suite_pass"]:,}次；混合D/回调{nn["D_per_callback_mixed_us"]:.6f}/{tr["D_per_callback_mixed_us"]:.6f} μs，D/分类{nn["D_per_classification_mixed_us"]:.5f}/{tr["D_per_classification_mixed_us"]:.5f} μs。两种比值都含其他回调与规划，不是纯推理耗时；见对应callback_cost.json。','small')
    p('完整Score=IO时间+p·miss次数+实际决策时间。保留官方计时范围，包含状态获取；不把路由比较数当成实测速度。所有动作独立核对容量、插入目标排除、LOAD阶段、miss末动作及lazy特征预测一致性。')

    page(5,'迭代证据与复现')
    p(f'旧固定568例：NN平均约96,578,213,902.12 μs，第一轮树94,273,432,606.00，加入强制集合94,247,452,742.66，事件加权cheap树{old["best"]["mean_score"]:,.2f}。后者比旧快照Naive下降28.7795%。旧数据与新785例分母不同，不直接比较两者平均值大小。')
    p('新785例：增加Vanius0525的209例，并纳入cyanneko 0.6.0的48例。新train重拟合模型曾在cyanneko上达到50.06%降幅，但全库差于父树；因此未仅因一份集合改善就替换。全部负结果与逐例坏例保留在结果文件。')
    if checkpoint.get('search_note'):p(escape(checkpoint['search_note']))
    scratch=ROOT/'scratch_result.json'
    if scratch.is_file():
        sr=read(scratch)
        p(f'随后单独验证数组复用：785例动作完全一致，3次完整回调D均更慢，平均由{sr["parent_mean_D_us"]:,.2f}升至{sr["scratch_mean_D_us"]:,.2f} μs（增加{-sr["D_reduction_percent"]:.2f}%），未采用。该轮保留版本Score为{sr["parent_score"]:,.2f} μs。')
    p('尾部须结合绝对成本与IO看：父树某次最差241倍来自无IO、无miss的小例，约182 μs对照0.75 μs；而未采用模型曾在hot-small例引发约440万μs真实IO。两个现象都保留，含义不同。')
    h('单文件接入与复测')
    p('交付文件：design/MySpillScheduler_tree.cpp。定义MySpillScheduler、无main，接入公开C++14框架。编译运行：python design/tools/run.py --policy tree --input &lt;正式输入文件&gt;。原rule/NN版本保留便于比较。','small')
    p('训练、生成、评测：portfolio_iter_20261029/README.txt。数据在GitHub datasets分支的独立worktree，固定e119c23；原数据、截图、二进制及临时快照不混入源码分支。结果按suite_id、源码SHA、重复数绑定，重新测量CPU值会波动。','small')
    p('当前交付源码SHA-256：'+checkpoint['source_sha256'],'small')
    h('文献与业界来源（思想借鉴）')
    refs=[
      ('[1] Velox: Spilling','https://facebookincubator.github.io/velox/develop/spilling.html'),
      ('[2] Beckmann等, LHD, NSDI 2018','https://www.usenix.org/conference/nsdi18/presentation/beckmann'),
      ('[3] Cao与Irani, GreedyDual-Size, USITS 1997','https://pages.cs.wisc.edu/~cao/papers/gd-size.html'),
      ('[4] Kuiper等, DuckDB多算子内存管理, PVLDB 18','https://www.vldb.org/pvldb/vol18/p2748-kuiper.pdf'),
      ('[5] Vietri等, LeCaR, HotStorage 2018','https://www.usenix.org/conference/hotstorage18/presentation/vietri'),
      ('[6] Optimal Sparse Decision Trees, NeurIPS 2019','https://proceedings.neurips.cc/paper/2019/hash/ac52c626afc10d4075708ac4c778ddfc-Abstract.html')]
    for title,url in refs:p(f'<link href="{url}" color="#087C83">{escape(title)}</link>','small')
    p('小树采用成本敏感贪心CART，不是文献[6]的全局最优树求解器。更多来源、实现差异及保证边界见catalog.json、research_sources.json。','small')
    page(6,'局部近似保证与离线成本下界')
    h('专家1的大规模回退也有局部保证')
    p('对固定需求和候选集，候选按字节升序取覆盖缺口D的前缀，并比较最小覆盖单分区；最后只删冗余。若前缀末项不大于D，则总写量小于2D、不超过2OPT；若末项大于D，所有更小项之和仍不足D，任何可行解必须含一个覆盖单项，比较最小单项即局部最优。')
    p('该论证适用于当前flags351的专家1、固定保护排除与可行请求；不适用于开启干扰权重后的排序，也不是完整Score或next_op改规划后的保证。n≤10的子集枚举另有立即写出精确最优保证。')
    h('新的耦合下界：把已写数据与后缀缓存一起考虑')
    p('以最后一个SWITCH后为边界，所有分区大小固定，余下只有PROBE。令A为总字节，S为可行驻留集合、s(S)≤M。非驻留分区的全部字节在边界前必已写出，所以prefix写时间≥(A-s(S))/W。')
    p('离线DP用完整后缀计算F(S)：命中无miss回调；miss先付p，回调后的集合必须含当前目标；周期回调在当前PROBE之后发生。转移成本为SPILL(S\\T)/W+LOAD(T\\S)/R。全case下界：LB=min可行S[(A-s(S))/W+F(S)]。忽略prefix读取、prefix miss和全部D，使其保持乐观。')
    p('periodic计数包含INSERT、PROBE，排除SWITCH；保留prefix余数。零大小分区的SPILL会被官方忽略，始终resident；其PROBE仍推进计数。终值0，不加结束flush。按位可分的min-plus把转移降到O(Q·2^Q)，代数中间状态不按容量裁剪。')
    h('验证与适用范围')
    bound_path=D/'offline_bounds_20261030/bound_comparison_members_r6_mode92.json'
    if bound_path.is_file():
        br=read(bound_path)
        p(f'实现已通过6个手算边界与24个随机小Q的Fraction暴力DP核对，并扫描全部785例：185例可计算，500例Q超限、100例预算超限，均明确跳过且不补0。R6开发程序中，对小树92的同一185例，总成本/计算下界≈{br["ratio_C_over_LB"]:.6f}，最多进一步降低的上限约{100*br["maximum_improvement_fraction_upper_bound"]:.4f}%。')
    p('该结论只针对这185例，不能推广到其余600例；差距不是可实现收益。数学证明按实数I/O计价；数值用long double与下调余量，未做机器认证。完整未来、真实p/B只用于这个离线工具，绝不进入在线专家或特征。')
    p('推导与源代码：portfolio_iter_20261029/offline_suffix_bound_proof.txt、expert1_cover_approx_proof.txt，以及offline_bounds_20261030。当前只实现后缀耦合松弛，并未声称求出整题全输入最优策略。','small')
    page(7,'完整后缀与类别切换：已完成验证')
    p('完整后缀重拟合与类别切换均已完成候选实验；当前采用类别节点更新，公共admission层继续保留。“原创”指本项目自行设计和实现，不主张文献首次提出。')
    h('一、用完整剩余轨迹提高教师标签保真度')
    p('教师让每种首动作推进到输入末尾，以冻结父树共同续行，每文件最多采6个状态。已拟合8棵实际深度3至6的小树；其中118/121在840份train胜出，785例回归却比108退化，均未采用。完整后缀提高观测范围，仍不能消除固定续行与重叠采样偏差。')
    if isinstance(round9,dict) and '108' in round9.get('summary',{}):
        baseline=round9['summary']['108']['mean_score']
        comparison=[['mode','840 train比108下降','785回归比108变化','785回归平均Score / μs']]
        for mode in ['113','118','121']:
            if mode not in round9['summary']:continue
            rr=round9['summary'][mode];change=100*(rr['mean_score']/baseline-1)
            training='见train_g6'
            if isinstance(train6,dict) and all(k in train6.get('summary',{}) for k in ['108',mode]):
                training=f'{100*(1-train6["summary"][mode]["mean_score"]/train6["summary"]["108"]["mean_score"]):.6f}%'
            comparison.append([mode,training,(f'上升{change:.4f}%' if change>0 else f'下降{-change:.4f}%'),f'{rr["mean_score"]:,.2f}'])
        table(comparison,[42,112,132,221])
        p('表内成员回归取members_r9同批3次均值；train取train_g6的完整轨迹筛选，不能把训练获益当作泛化证明。','small')
    h('二、把上次专家当类别，学习策略切换集合')
    if category and type(category_proposal.get('category_mask')) is int:
        mask=category_proposal['category_mask'];parent_mask=category.get('parent_mask',7)
        p(f'已生成8个类别掩码候选；当前采用mode {checkpoint["mode"]}，节点{category["node"]}由左侧集合{category_ids(parent_mask)}改为{category_ids(mask)}、mask={mask}，仍为深度{model["max_depth"]}。在线用一次位测试，未观察类别保留父侧。局部代理最优不等于闭环最优；本候选经完整Score回归和独立部署785例×3次确认。')
    p(member_tradeoff_line(round9,checkpoint['mode']),'small')
    h('三、周期回调提前将增长目标转为磁盘追加')
    p('periodic看到下一INSERT将溢出，若正大小驻留目标b满足(s+t)·2^k≤最小其他正大小分区，可提前SPILL b，下一INSERT磁盘追加；k=0..3。该局部证书只覆盖已知写入体、截止其后periodic动作之前，后续增长、Probe与D仍可反转收益。')
    admission_lines=admission_evidence(admission_result)
    if admission_lines:p(escape('历史admission研究：'+' '.join(admission_lines)),'small')
    if admission_model:
        factor_text=f'、阈值factor {admission_factor}' if admission_factor is not None else ''
        state='独立接入复测已完成' if standalone else '独立接入复测待完成'
        p(f'当前已启用公共层{factor_text}，仍为8专家；{state}。checkpoint mode {checkpoint["mode"]}平均Score {checkpoint["summary"]["mean_score"]:,.2f} μs、D {checkpoint["summary"]["mean_decision_us"]:,.2f} μs/例；绑定'+escape(checkpoint['sdk_report'])+'。','small')
    elif admission_result:
        p('候选实验已完成；当前模型未启用该公共层，结论以admission_result.json和各轮绑定记录为准。仍为8专家。','small')
    else:
        p('状态：admission_patch.py、prepare_admission.py及推导已准备，尚未评测；公共层不增加第9类专家。','small')

    page(8,'新MLP对照与全785例可扩展下界')
    h('一、微型MLP已实测，本轮仍保留小树')
    p('在同一完整后缀标签上训练8个微型MLP：20个便宜数值特征＋8类上次专家，隐藏层8/16，参数304/600，部署仅乘加和argmax。840份完整train评分均未胜过113；按训练侧选择127/128/131，在785例各测3次仍退化，保持小树。')
    r10_path=ROOT/'members_r10_summary.json'
    if r10_path.is_file():
        r10=read(r10_path);scores=r10.get('summary',{})
        if '113' in scores:
            base=scores['113']['mean_score']
            compare=[['同批方法 / mode','平均Score / μs','平均D / μs每例','比树Score变化']]
            for mode,label in [('113','小树'),('127','MLP'),('128','MLP'),('131','MLP')]:
                if mode not in scores:continue
                value=scores[mode];delta=100*(value['mean_score']/base-1)
                compare.append([label+' / '+mode,f'{value["mean_score"]:,.2f}',f'{value["mean_decision_us"]:,.2f}',('基准' if mode=='113' else (f'上升{delta:.4f}%' if delta>0 else f'下降{-delta:.4f}%'))])
            table(compare,[86,179,115,127])
    p('以上取members_r10同批数据，与首页独立部署批次区分。差距主要来自I/O及动作选择；本批MLP的D/例更低，不能把失利归因于“NN太慢”。回调数量、类型及规划内容也会变化，D/例或混合D/分类都不能单独证明路由快慢。','small')
    kernel_path=ROOT/'cheap_mlp_kernel_verification.json'
    audit_path=ROOT/'mlp_r10_audit_summary.json'
    if kernel_path.is_file() and audit_path.is_file():
        kernel=read(kernel_path);audited=read(audit_path)
        passed=[row for row in audited.values() if row.get('strict_actions') is True and row.get('feature_prediction_parity') is True and row.get('cases')==785]
        comparisons=len(kernel.get('models',[]))*kernel.get('rows',0)
        p(f'实现核查：实际C++数值内核对Windows NumPy部署语义，{len(kernel.get("models",[]))}模型×{kernel.get("rows",0)}状态、{comparisons:,}次分类，失配{kernel.get("mismatches",0)}；另有{len(passed)}模型各785例动作/特征核查通过。一致性通过不代表策略质量更优。','small')
    h('二、字节守恒把后缀读下界扩展到完整case')
    p('令A为全部INSERT字节，Rtot为全程LOAD字节，V为全程写出字节，m为结束时驻留字节。从空内存开始且不删除数据，逐动作守恒给出V=A+Rtot-m，且0≤m≤M。若后缀读取已有乐观下界L，则Rtot≥L，得到：')
    p('<b>IO下界 = max(0, A+L-M)/W + L/R</b>。这里W、R为写/读带宽；忽略miss罚分与全部D仍保持乐观。L来自固定大小PROBE后缀的窗口容量与不兼容分区路径约束，允许有利初始驻留，不等于可实现策略。')
    window_dir=D/'window_bounds_20261030'
    suite_path=window_dir/'suite_verification.json';toy_path=window_dir/'toy_verification_final.json'
    if suite_path.is_file() and toy_path.is_file():
        suite=read(suite_path);toy=read(toy_path);coverage=suite['aggregate'];cross=suite.get('old_suffix_crosscheck',{})
        p(f'验证状态{suite["status"]}：{suite["case_count"]}例中{coverage["eligible"]}例已计算，跳过{coverage["skipped"]}、错误{coverage["errors"]}；{toy["hand_cases"]}个手算例及{toy["random_cases"]}个随机toy通过，并与旧后缀工具{cross.get("compared",0)}个可算例的raw界完成交叉核对。当前113同一全库ΣC/ΣLB≈{coverage["sum_C_over_sum_LB"]:.6f}。此界较松，不能把界与现价的间隙当作可达收益，也不能据此宣称已近最优。')
    p('整数读写字节使用int64精确计算；最终带宽除法为浮点、并非机器认证。该工具只做离线放松分析，完整未来及真实p/B绝不进入在线模型。新全库结果与第6页旧185例子集结论分别保留；来源见window_bounds_20261030的proof.txt及suite_verification.json。','small')

    page(9,'同公共层八固定专家消融')
    p('为区分动态选策与公共证书收益，本轮把分类器改为固定返回一个专家的单叶，同时保持113的专家实现、forced_cover及admission=2。旧100..107沿用历史NN公共层，因此另建134..141作同层对照；e0..e7才是专家标签，mode只是离线实验编号。')
    fixed_path=ROOT/'members_r11_summary.json'
    fixed_train_path=ROOT/'train_g8_840_summary.json'
    if fixed_path.is_file():
        fixed=read(fixed_path);fixed_summary=fixed['summary'];by_member=fixed['by_member']
        catalog={row['id']:row['name'] for row in read(D/'neural_selector/catalog.json')}
        fixed_modes=[str(134+i) for i in range(8)]
        best_mode=min(fixed_modes,key=lambda mode:fixed_summary[mode]['mean_score'])
        best_expert=int(best_mode)-134
        tree_score=fixed_summary['113']['mean_score']
        best_score=fixed_summary[best_mode]['mean_score']
        gain=100*(1-tree_score/best_score)
        p(f'members_r11：785例各{fixed["repeats"]}次，按案例等权取raw平均Score。全部785例的最佳固定方法为e{best_expert}“{catalog[best_expert]}”（mode {best_mode}）；树113相比它'+(f'下降{gain:.4f}%。' if gain>=0 else f'上升{-gain:.4f}%。'))
        p('下表所有成本均为平均Score÷1,000,000，单位“百万微秒”；这是题面计价Score，不是程序墙钟运行时间。越低越好。','small')
        member_columns=['Vanius0525','cyanneko','liunianwww']
        comparison=[['方法 / 本轮mode','Vanius (209)','Cy (48)','Liun (528)','全部 (785)']]
        for expert,mode in enumerate(fixed_modes):
            comparison.append([f'e{expert} {catalog[expert]} / {mode}',
                *[f'{by_member[member][mode]["mean_score"]/1e6:,.3f}' for member in member_columns],
                f'{fixed_summary[mode]["mean_score"]/1e6:,.3f}'])
        for mode,label in [('113','动态树113（同公共层）'),('2','官方Naive2（历史基线）'),('0','原NN0（历史公共层）')]:
            if mode not in fixed_summary:continue
            comparison.append([label,
                *[f'{by_member[member][mode]["mean_score"]/1e6:,.3f}' for member in member_columns],
                f'{fixed_summary[mode]["mean_score"]/1e6:,.3f}'])
        table(comparison,[169,80,80,89,89])
        h('逐成员最优不同，不能宣称树在每份集合都最好')
        findings=[]
        for member in member_columns:
            values=by_member[member]
            selected=min(fixed_modes,key=lambda mode:values[mode]['mean_score'])
            expert=int(selected)-134;best=values[selected]['mean_score']
            change=100*(values['113']['mean_score']/best-1)
            findings.append(f'{member}最佳固定为e{expert}（{selected}），树相对它'+(f'上升{change:.4f}%' if change>0 else f'下降{-change:.4f}%'))
        p('；'.join(findings)+'。逐成员最优是事后分析，成员ID和数据来源绝不进入在线特征；总体目标是785案例等权rawmean。','small')
        if fixed_train_path.is_file():
            ft=read(fixed_train_path)
            p(f'固定对照另已完成train_g8的{ft["case_count"]}份train评分。观测最近访问不是全访问LRU，热度密度和观测GDS也不是标准LHD/GDS复现；Naive与原NN公共层不同，仅作历史参照，不能归入同层消融。','small')
    fixed_check=D/'member_eval_20261030/members_r11_candidate_verification.json'
    verified=read(fixed_check) if fixed_check.is_file() else None
    p('可复核源码包：portfolio_iter_20261029/fixed_expert_sources.zip；测量包：fixed_expert_measurements.zip。'+('8个固定方法均通过785例严格动作/特征审计；18,840次SDK的IO、hit与miss逐条匹配独立审计，源代码与原输入哈希均绑定。' if verified and verified.get('status')=='passed' else '严格动作与特征审计状态以fixed_r11_audit_summary.json及源码绑定为准，不将评分完成等同于独立审计通过。'),'small')
    def footer(c,doc):
        c.setStrokeColor(colors.HexColor('#D1DDE2'));c.line(44,39,551,39)
        c.setFont('Song',8);c.setFillColor(blue);c.drawString(44,25,'第20题 · 三成员数据集 / 专家选择器')
        c.drawRightString(551,25,str(doc.page))
    SimpleDocTemplate(str(OUT),pagesize=(595,842),rightMargin=44,leftMargin=44,topMargin=42,bottomMargin=51,title='第20题8专家小树迭代与三成员实测',author='HuaweiHackathon source/liunianwww').build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUT)

if __name__=='__main__':main()
