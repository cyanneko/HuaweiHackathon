from pathlib import Path
import json
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'topic20_neural_selector_report.pdf'
pdfmetrics.registerFont(TTFont('Song','C:/Windows/Fonts/simsun.ttc',subfontIndex=0))
blue=colors.HexColor('#123A56'); teal=colors.HexColor('#007E87'); gray=colors.HexColor('#4E5B66')
styles={
 'title':ParagraphStyle('title',fontName='Song',fontSize=25,leading=34,textColor=blue,spaceAfter=18,wordWrap='CJK'),
 'h':ParagraphStyle('h',fontName='Song',fontSize=17,leading=24,textColor=blue,spaceAfter=13,wordWrap='CJK'),
 'sub':ParagraphStyle('sub',fontName='Song',fontSize=12,leading=19,textColor=teal,spaceBefore=12,spaceAfter=6,wordWrap='CJK'),
 'body':ParagraphStyle('body',fontName='Song',fontSize=10.5,leading=17,spaceAfter=9,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='Song',fontSize=8.5,leading=13,spaceAfter=7,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='Song',fontSize=9,leading=14,wordWrap='CJK'),
}
story=[]
def p(s,style='body'):story.append(Paragraph(s,styles[style]))
def h(s):p(s,'sub')
def page(n,title):
    if story:story.append(PageBreak())
    p(f'{n:02d} / {title}','h')
def table(rows,widths):
    t=Table([[Paragraph(escape(str(x)),styles['cell']) for x in r] for r in rows],colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DCECF2')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F4F7F9')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.6,teal)]))
    story.append(t);story.append(Spacer(1,11))

p('第20题 · 动态落盘调度','sub')
p('8种专家策略<br/>与微型神经网络选择器','title')
p('方案实现、学术依据与最终本地验证 | 2026-10-29','small')
p('已实现：从当前可见状态和自身历史提取32维特征，由32→16→8网络输出策略编号，再运行对应专家生成SPILL / LOAD动作。默认构造函数直接启用网络，权重内嵌单个C++14文件。')
table([['项目','当前交付'],['网络规模','664个float32参数；权重2656字节；约640次乘加'],['训练输入','600个本地输入 + GitHub datasets分支8个train输入'],['交付模型训练状态','15,255条；另有3,889条验证状态'],['最终Score验证','150例调参集、378例新测试、8例GitHub回归、6例规模测试'],['冻结后新测试比值','377个非零基线例几何均值0.975361；最差2.241042'],['版本定位','本地验证完成；神经网络为候选，旧版继续默认']],[116,379])
h('运行流程')
p('实际需要选择落盘策略 → 汇总可见特征 → 微型网络输出ID 0..7 → 执行一个专家 → 公共容量与next_op处理 → 返回合法动作 → 更新可见历史。')
p('网络替代了顶层策略选择；专家内部仍采用可解释的规则或精确子问题算法。全局候选覆盖所有算子的驻留分区，支持跨算子落盘。')
h('结论先行')
p('新测试上Score几何均值约下降2.46%，GitHub回归集和规模诊断上则分别升高约5.68%与1.29%。网络增加回调成本，收益依赖负载。本轮完成所列本地测试并交付候选，继续保留旧版为默认。')

page(2,'候选策略：容量与复用')
p('筛选目标是互补性与部署成本。初步在128个训练输入上运行各固定专家，随后比较选择器与旧版、强单专家。某专家在某类负载有效，不代表它在所有输入上都“较好”。')
table([['ID / 方法','做法与适用情形','依据与边界'],['0 最大分区优先','从所有算子候选中优先落盘大分区，快速释放内存；BUILD可作为低成本起点。','Velox官方实现思想[1]；可能牺牲热点，不保证Score最优。'],['1 小规模最小写出覆盖','候选数≤10时枚举子集，选择满足缺口且总字节最小者；更大时回退启发式。','容量覆盖子问题精确算法；交付版O(2^n)，最多1023个非空子集。'],['2 观测最近访问','优先驱逐已观测访问时间较早的分区，捕获时间局部性。','LRU思想适配；题目没有逐次hit回调，故不是完整LRU。'],['3 观测热度密度','按(1+衰减热度)/字节保留价值；对下一PROBE施加保护因子。','借鉴LFU/size及LHD单位空间价值[2]；未实现原LHD概率模型。']],[104,204,187])
h('缺口的精确定义')
p('可用空间F=M-U。当前需求d：INSERT溢出时为新增元组字节；PROBE miss时为目标分区全量字节；联合加载规划时为两分区之和。需要释放的缺口D=max(0,d-F)。候选排除当前INSERT目标等不可驱逐项。')
h('ID 1 能证明什么')
p('令候选大小为s_i，选择x_i∈{0,1}，最小化Σs_i·x_i，约束Σs_i·x_i≥D。写带宽W固定且每次落盘按字节收费，因此此目标等价于立即写时间最小。枚举所有可行子集并取最小值，保证这个规划子问题精确。')
p('例如F=8 MiB、待载入20 MiB，D=12 MiB；候选大小13、20、40 MiB，则立即写出最优是13 MiB。如果13 MiB分区马上被访问，未来总代价仍可能更高。公共next_op保护也可能改变最终动作，因此这里没有完整Score最优保证。')

page(3,'候选策略：成本与算子竞争')
table([['ID / 方法','实现','依据与边界'],['4 预计恢复代价密度','按[s/W+q·(s/R+32)]/s排序，低价值优先写出；已知下一PROBE时q=1。','代价感知缓存启发式；q由热度构造，32是固定尺度，均不是题面真实p。'],['5 观测版GreedyDual-Size','维护通胀L与H=L+c/s，驱逐低H；c取读写时间加固定尺度。','Cao、Irani的GDS[3]；只在可观测事件更新，原竞争界不直接适用。'],['6 阶段 + 算子软配额','根据算子阶段和压力分配软配额，BUILD用大小优先，PROBE用配额修正成本密度。','借鉴DuckDB并发算子动态内存管理[4]；未引入题面不允许的压缩或重分区。'],['7 前版自适应控制器','综合观测时间、热度、代价密度，通过ghost反馈切换；保留软配额及保守next_op。','项目此前主方案；反馈思想参考LeCaR[5]，不是原LeCaR实现。']],[104,214,177])
h('next_op与跨算子动作')
p('网络使用题面公开的一步next_op作为特征。专家共用下一目标保护、无额外落盘的预取，以及受限制的两分区联合规划。miss回调最后仍加载当前目标；不能据此访问更长未来。')
h('数学论文的结论必须满足假设')
p('原GDS用H=L+c/s整合访问新近性与取回代价[3]。本题的BUILD会改变分区大小，驱逐也收费，而且没有完整hit事件；这些条件改变了原问题。交付代码因此称“观测版”，不套用原论文竞争比。')
h('切换时的历史处理')
p('8个专家共享实际发生的观测、ghost反馈和GDS状态。运行时没有维护8份独立缓存，也没有先跑完8种策略再投票。选中策略可以直接使用共同历史；这是一套适配后的策略组合，而非8个原算法的独立复制。')

page(4,'分类网络与在线耗时')
p('z=W2·ReLU(W1·x+b1)+b2；输出argmax(z)。部署只做两层矩阵向量乘加、ReLU和最大值比较，省去softmax，不调用Python或机器学习运行时。')
table([['特征范围','内容'],['0..7 容量与请求','已用/需求/缺口/空闲比例；算子数、分区数；BUILD请求与请求算子阶段'],['8..16 驻留结构','驻留比例，最大/最小/平均大小，大小集中度，BUILD/PROBE及请求算子占用'],['17..24 一步信息与I/O','next_op类型、分区大小与驻留、是否同算子、两目标能否共存；读写带宽'],['25..31 自身观测','累计/近期miss压力、目标/整体热度、快速回访压力、上次专家ID、平均分区大小']],[120,375])
p('特征只依赖公开SystemState、一个next_op及自己记录的历史。真实p、总N、周期B、完整未来、文件名、样例种子都不进入模型。输入有部分可观测性：相同特征可能对应不同最优策略，不能期待零分类误差。')
h('何时重新决策')
p('每次溢出和首次miss回调都重新选择专家；周期回调若发现下一INSERT将溢出，也重新选择。无需选盘的空回调及简单可行预取走固定处理路径，避免没有必要的网络运行。当前网络权重离线固定，状态与部分专家反馈在运行中动态更新。')
h('成本不仅是640次乘加')
p('32维特征提取需要扫描候选状态，复杂度O(Q)，Q≤512；后续规划还有遍历、排序或小规模枚举。官方计时还包含状态快照等调用成本。因此评测记录Total_Decision_Time，不能用网络理论运算量代替实际回调延迟。')
h('稳健偏置')
p('在验证集上比较隐藏层8/16、旧策略ID 7输出偏置0/0.5，选中16与0.5。偏置给旧策略略高优先级，减少激进切换；它不是校准过的置信度，也不是最坏情况安全保证。')

page(5,'训练标签、数据划分与第二轮训练')
h('离线反事实标签')
p('在采样决策点复制相同模拟状态，让8个专家分别执行首个动作，然后用共同续行策略推进。比较C_e=ΔIO_e+p·Δmiss_e+Δdecision_e。当前已发生的miss罚分是共同常数，不影响该点的候选比较。')
p('默认向后观察384步；BUILD窗口可延伸至当前算子SWITCH之后128步，但最多2048步。未来仅供离线教师打标签。CPU标签是真实测量，带噪声；有限窗口与续行策略也有偏差，不能称为全局最优oracle。首个选策的共同推理开销未由固定专家标签完整刻画，最终仍须SDK全程评分。')
h('软标签与成本敏感学习')
p('设C*=min C_e，温度τ=max(1,0.02·max(C*,1))；软标签t_e正比于exp(-clip((C_e-C*)/τ,0,20))。近乎平手的专家都获得权重，避免把CPU微小抖动当成绝对正确类别。优化软交叉熵加0.05倍期望截断遗憾项，按工作负载平衡样本权重。')
p('训练为NumPy实现的Adam，160轮；按验证集截断成本遗憾选checkpoint，再用完整SDK Score选择网络大小及偏置。训练随机种子用于复现，不代表测试空间只有这些种子。')
table([['分组','输入数 / 状态数','用途'],['本地 + GitHub train','600+8 / 15,255','交付模型；GitHub贡献196条状态'],['本地验证','150 / 3,889','选checkpoint、隐藏层及偏置；不是最终盲测'],['GitHub eval','8 / 未用于训练','开发回归评分已完成；有历史使用暴露'],['第二轮追加','同一训练输入 / 10,575','网络轨迹重采样；合计25,830条，GitHub合计334条']],[102,184,209])
p('按规范化操作流分组，同一流的不同成本配置不能跨训练与验证。GitHub版本固定为96f3e2da7954756d9346b4c45d375c018792530c。源仓库明确说明16例均参与过历史开发；此处不把eval称为未见数据。')
p('第二轮采用DAgger式数据聚合思路[6]，收集初版网络实际遇到的状态。完整验证Score比值为0.961323、最差1.605629，未优于首轮，因此未采用。最终首轮权重结合O(2^n)枚举复核为0.952349；两轮教师的CPU标签实现版本存在区别。','small')

page(6,'已完成实验：收益与反例')
p('公开参考引擎仅替换调度器，保留执行和计时。按例交替运行顺序，每配置3次；逐例取Score中位数，再计算相对旧版比值的几何均值。此均值是本地指标，不冒充官方跨例汇总公式。')
table([['最终源码测试集','Score比值几何均值','最差比值'],['调参验证150例','0.952349','1.473824'],['冻结后新测试378例','0.975361','2.241042'],['GitHub回归8例','1.056779','1.281646'],['规模诊断6例','1.012914','1.025815']],[229,143,123])
p('新测试含20种基础负载、128个参数角点和专项场景；10个与开发数据操作流重复的模板被剔除后保留378例。其中1例基线Score为0，377例参与比值。新测试在冻结模型后生成，未再调参；它仍来自自建生成器，不能代表官方全部分布。')
table([['同批固定专家4','几何均值','最差比值'],['调参验证150例','0.952598','12.606436'],['新测试377个非零基线例','0.994863','7858.035861'],['GitHub回归8例','0.910727','5.252595'],['规模诊断6例','0.943746','1.070063']],[229,143,123])
p('网络与固定专家4在验证均值上接近，新测试中网络尾部退化较小；GitHub及规模诊断的均值则由固定专家4更好。原始无偏置网络曾退化至38.31倍，已保留实验记录。没有一种方法在所有集合上都优胜。')
table([['回调时间中位数之和 / us','旧版','网络'],['调参验证150例','33,270.01','44,692.34'],['新测试非零基线例','233,970.11','271,365.87'],['规模诊断6例','4,768,257.50','5,615,801.25']],[255,120,120])
p('最终四组测试共6,054条SDK运行记录。CPU是完整回调耗时，包含状态获取、特征汇总、网络与专家规划；不同批次CPU不可直接归因于单项优化。没有官方隐藏成绩或全输入最优保证。','small')

page(7,'本项目的贡献与下一步优先级')
h('1. 面向本题完整Score的专家标签')
p('贡献在于把跨算子落盘、未来恢复、miss罚分与实际CPU成本放进同一个有限窗口比较过程。首个动作由专家决定，后续用共同策略；比仅以当下释放字节标注更贴近本题。成本敏感学习本身是已有方法，本项目贡献是具体的可复现标签协议及部署适配。')
h('2. 部分可见状态下的共享历史选择器')
p('明确区分“观察到的热度”和真实全访问热度，使用合法的next_op；共享反馈历史，保持每次只执行一个专家。不同算子的候选进入同一规划过程，将阶段、内存竞争和选择器状态纳入分类。实现是工程与问题适配贡献，未宣称新通用学习理论。')
h('3. 可证明的局部算法与廉价启发式共存')
p('小候选集保留精确容量覆盖，大候选集使用有界成本启发式；模型学习何时值得支付精确计算成本。即使专家1的子问题精确，神经网络选择和完整Score仍没有同样保证。这一“局部保证 + 实测选策”的边界在实现与说明中保持一致。')
h('4. 用实际运行状态反过来扩充训练集')
p('神经网络动作会改变未来驻留与miss分布，单轮固定教师状态可能失配。第二轮收集模型自己的状态再训练，思想借鉴DAgger[6]；完整评分已完成，本次未改善验证表现，因此保留首轮权重。')
h('下一步按收益优先，而非盲目加深网络')
p('本轮已完成冻结后新样例、强单专家、最大规模与独立动作核算。后续研究可针对高损失误选增加风险权重，并验证便宜门控或特征增量维护是否值得；这些新增改进未包含在当前交付中。')
p('极小网络是合理方向，但决定收益的是专家互补性、标签质量、可观测信息以及总代价。现有证据支持交付可研究的候选，不支持承诺最优或任何分布都下降。')

page(8,'复现入口与参考资料')
h('项目入口')
p('交付：design/MySpillScheduler_neural.cpp。训练与证据：design/neural_selector/。已有旧版推荐仍由CURRENT_SOLUTION.txt指示。全部算法均定义MySpillScheduler，每次只选择一个接入公开框架。')
p('运行：python design/tools/run.py --policy neural --input 输入文件<br/>核对：python design/neural_selector/verify.py<br/>训练：python design/neural_selector/train.py fit<br/>导出：python design/neural_selector/deploy.py model_16.json 0.5','small')
p('离线训练依赖Python与NumPy；正式提交仅依赖C++14标准库。提供冻结的特征标签包、模型JSON、导出模板、离线教师、输入来源哈希和SDK运行记录。原始截图、网页缓存、编译产物和批量输入不纳入此次源码交付。')
h('主要原始资料')
refs=[
('[1] Velox官方文档：Spilling。最大分区选择与分区落盘。','https://facebookincubator.github.io/velox/develop/spilling.html'),
('[2] Beckmann, Chen, Cidon. LHD: Improving Cache Hit Rate by Maximizing Hit Density. NSDI 2018.','https://www.usenix.org/conference/nsdi18/presentation/beckmann'),
('[3] Cao, Irani. Cost-Aware WWW Proxy Caching Algorithms. USITS 1997. GreedyDual-Size算法原文。','https://pages.cs.wisc.edu/~cao/papers/gd-size/node8.html'),
('[4] Kuiper, Groß, Boncz, Mühleisen. Saving Private Hash Join. PVLDB 18(8):2748-2760, 2025.','https://www.vldb.org/pvldb/vol18/p2748-kuiper.pdf'),
('[5] Vietri et al. Driving Cache Replacement with ML-based LeCaR. HotStorage 2018.','https://www.usenix.org/conference/hotstorage18/presentation/vietri'),
('[6] Ross, Gordon, Bagnell. A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning. AISTATS 2011.','https://proceedings.mlr.press/v15/ross11a.html'),
('[7] 项目datasets分支：cyanneko共享数据及其历史开发使用说明。','https://github.com/cyanneko/HuaweiHackathon/tree/96f3e2da7954756d9346b4c45d375c018792530c/datasets/cyanneko'),
]
for text,url in refs:p(escape(text)+f' <link href="{url}" color="#007E87">[原始资料]</link>','small')
p('论文给出的方法与实验结论属于其原始环境。本报告引用其思想和公式，未将原论文收益或理论保证转写成本题保证。未完成的实验均明确标注。','small')

page(9,'完整性核查与最终版本')
h('动作合法性独立核算')
p('最终网络在1,150个输入上通过独立模拟器：608个训练、150个验证、8个GitHub回归、378个新测试与6个规模诊断。核查每步动作的分区编号、INSERT目标排除、LOAD状态及PROBE阶段、miss最后加载当前目标、逐动作容量，以及周期与结束时的内存账目。')
p('其中542个已测SDK输入的I/O、hit、miss与独立核算一致。8个固定专家分别在150个验证输入上通过同样检查；固定专家7的I/O与miss与旧版匹配。公开框架正常退出不单独充当合法性证明。')
h('枚举提速与部署一致性')
p('子集和由逐掩码重扫改为递推，复杂度从O(n·2^n)降为O(2^n)。3,000组随机小实例与完整枚举一致；150个验证输入的动作哈希与首轮源码一致。最终源码已重新全程评分，未把两批CPU差直接当成优化收益。')
p('统一使用deploy.py导出权重。verify.py已确认模型+模板导出与实际评分源码字节一致，核对特征包哈希、分组隔离及6,054条SDK记录的Score算术。新测试可从记录的熵和生成器重建，378个输入哈希已逐一再现。')
h('复现命令')
p('python design/neural_selector/replay_fresh.py<br/>python design/neural_selector/verify.py<br/>python design/neural_selector/benchmark.py --manifest design/neural_selector/fresh_manifest.json --output design/neural_selector/results/replay.json','small')
h('最终提交判断')
p('最终候选仍是32→16→8首轮权重、旧策略偏置0.5，结合等价枚举提速；第二轮模型未采用。神经网络在新测试平均有收益，但回归与规模诊断存在退化，所以CURRENT_SOLUTION继续推荐旧版，神经网络作为明确标注的可用候选。')
p('此结论依据已完成的本地实验；不存在待批准的本轮测试，也不包含官方隐藏测试成绩。源码、训练特征包、证据、PDF与复现入口归入关键项目文件，原始截图和批量输入保留本地。')

def footer(c,doc):
    c.setStrokeColor(colors.HexColor('#D5E0E7'));c.line(50,45,545,45)
    c.setFont('Song',8);c.setFillColor(gray);c.drawString(50,31,'第20题 | 8专家与微型神经网络 | 开发验证候选')
    c.drawRightString(545,31,str(doc.page))
doc=SimpleDocTemplate(str(OUT),pagesize=(595.28,841.89),leftMargin=50,rightMargin=50,topMargin=48,bottomMargin=62,title='第20题：8专家与微型神经网络选择器',author='Hackathon20 项目')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
