"""Shared Chinese editorial content. Formulae are rendered locally, without a CDN."""
import json
from pathlib import Path

SNAP='4a259b7b1b4232f521decdb22b826e41d16baf48'
BASE=f'https://github.com/cyanneko/HuaweiHackathon/blob/{SNAP}/'
SRC=BASE+'src/experiments/r85_math_ablations_20261030/R85_fast_prior8.cpp'
OWN='https://github.com/cyanneko/HuaweiHackathon/blob/a00677d59154156ac1da04b236c1bf8d0cff64b1/src/Vanius0525/level1/'
def frac(a,b): return f'<span class="frac"><span>{a}</span><span>{b}</span></span>'
def eq(label,body,explain=''):
 return f'<div class="eq"><span class="eq-label">{label}</span>{body}'+(f'<span class="explain">{explain}</span>' if explain else '')+'</div>'
def panel(title,body): return f'<div class="panel"><h4>{title}</h4><p>{body}</p></div>'
def tl(tag,title,body):return f'<div class="timeline-item"><div class="date">{tag}</div><h3>{title}</h3><p>{body}</p></div>'
def node(i,title,body,accent=False):return f'<div class="flow-node {"accent" if accent else ""}"><b>{i}</b><div><strong>{title}</strong><p>{body}</p></div></div>'
def lesson(i,title,body):return f'<div class="lesson"><b>{i}</b><div><h3>{title}</h3><p>{body}</p></div></div>'

scores=json.loads((Path(__file__).parent/'dist/assets/results.json').read_text())['scores']
names={'R85_fast_prior8':'R85 · prior8','R81_op256_cond2048':'R81 · 双时间尺度','R85_hier_anchor':'R85 · anchor','R80_next_hier_fast100':'R80 · hierarchy','R80_paired_hier_fast100':'R80 · paired','Van_latest':'我方 · paired100','R75_dense_switch':'R75 · dense switch'}
chart='<div class="score-chart" aria-label="R85归档同场方法成绩">'+''.join(f'<div class="bar-row" data-method="{r["method"]}"><span class="bar-label">{names[r["method"]]}</span><div class="bar-track"><div class="bar-fill" style="--width:{r["equal_dataset_score"]/5*100:.5f}%"></div></div><span class="bar-value">{r["equal_dataset_score"]:.6f}</span></div>' for r in scores if r['method']!='Naive')+'</div>'

pages=[]
pages.append(('overview','阅读起点','把有限内存留给真正有价值的数据',f'''
<p class="lead">我们优化的不是 Hash Join 的连接逻辑，而是它在内存不足时的整分区驻留与搬运决策。</p>
<p>多个算子共享同一块内存。BUILD 持续增加分区体积；PROBE 请求到来时，目标若在磁盘，必须完整读回。每一次选择受害者，都在“现在写出去多少”与“以后还要搬回来多少”之间权衡。</p>
<div class="stat-row"><div class="stat"><b>R85</b><span>本报告主讲版本 · fast_prior8</span></div><div class="stat"><b>4.087790</b><span>当前完整主测最高综合分</span></div><div class="stat"><b>12 + 72</b><span>动态与静态两组 · 各占50%</span></div></div>
<p>截至这份快照，<strong>R85_fast_prior8</strong> 在同学 R85 归档的八方法同场比较中综合分最高。它把算子活跃度与算子内分区偏好分开估计：前者快速跟随热点迁移，后者用更长历史稳定判断。</p>
<div class="two-col">{panel('本报告回答什么','数据为何这样设计？哪些优化改变了决策？当前算法怎样把有限观测变成驱逐集合？哪些负结果改变了我们的判断？')}{panel('如何理解“当前最优”','这里指固定主测上的最高实测均分。R85 比 R81 高 0.003361 分，静态组略退步；仓库正式默认入口仍为 R75。')}</div>
<h3>阅读路线</h3><div class="ribbon"><div>问题与观测</div><span>→</span><div>数据与演进</div><span>→</span><div>公式与执行</div><span>→</span><div>结果与认识</div></div>
<p class="small">本轮只整理代码与已有实验，不新增训练或性能测试。数据快照为 dyna1.0 与 final2.1；final3.0 单独作为敏感性观察。</p>'''))

pages.append(('problem','问题与目标','优化对象是成本，不只是 Miss',f'''
<p class="lead">一次小分区 Miss 和一次大分区 Miss，可能相差几个数量级的搬运费用。</p>
{eq('真实计分成本',f'C = {frac("B<sub>read</sub>","R")} + {frac("B<sub>write</sub>","W")} + λ · N<sub>miss</sub> + D','R、W：读写带宽（字节/μs）；B：实际搬运字节；λ：输入中的真实Miss罚值；D：回调决策时间。')}
<p>降低 Miss 有价值，但要同时看读写字节。我们可以让多个便宜的冷请求 Miss，却避免一个昂贵分区反复被逐出；反过来，盲目保护大分区也可能挤走大量更常用的小分区。</p>
<table><thead><tr><th>三个独立的量</th><th>它决定什么</th><th>策略应该怎样使用</th></tr></thead><tbody><tr><td>分区大小 s</td><td>容量占用、读写成本</td><td>进入搬运成本和装填约束</td></tr><tr><td>PROBE 概率 p</td><td>未来驻留收益</td><td>从合法观测估计，不由大小推断</td></tr><tr><td>BUILD 增长</td><td>后续内存压力</td><td>影响保留机会，不等同于未来热度</td></tr></tbody></table>
<h3>调度器可以改变什么</h3><p>合法动作为整分区 <code>SPILL</code> 与 <code>LOAD</code>。调度器不能拆热点分区、换哈希函数、压缩数据、重排请求或把查询改成批处理。冷请求也不能被拒绝准入。</p>
{eq('线上估值代理','λ̃ = 100 μs','真实λ不在SystemState中；100只用于算法内部估值，评分始终使用各输入自己的真实λ。')}
<div class="callout"><strong>最关键的转向</strong><p>从“哪块数据看起来最冷”，转向“释放足够空间时，牺牲哪个集合的总成本最低”。</p></div>'''))

pages.append(('observations','观测边界','没有被看见，不等于没有被访问',f'''
<p class="lead">普通 Hit 常常不暴露身份；Miss 一定暴露目标。直接累计可见访问，会把调度策略造成的缺页当成真实热度。</p>
<table><thead><tr><th>信息来源</th><th>可获得的信息</th><th>在当前算法中的用途</th></tr></thead><tbody><tr><td>累计 Hit / Miss</td><td>总请求进度，无完整Hit身份</td><td>构造PROBE逻辑时钟 q</td></tr><tr><td>periodic 与 Miss 回调的 next</td><td>下一条请求的算子与分区</td><td>去重采样，更新概率估计</td></tr><tr><td>当前 Miss 与驱逐后重访</td><td>哪个盘上分区被再次需要</td><td>更新重访风险与历史回退</td></tr><tr><td>分区大小、阶段、位置</td><td>当前可合法操作的状态</td><td>成本计算、容量与阶段约束</td></tr></tbody></table>
{eq('时钟与去重','q = Hit + Miss，　next 的序号 = q + 1','同一个next可能在多个回调中出现；只接收序号大于已采样序号的请求。连续两次同key但序号不同，仍是两个样本。')}
<div class="two-col">{panel('为什么不只统计 Miss','驻留成功的热点少产生Miss，反而不再可见。Miss更适合描述“驱逐后损失”，不能直接替代无偏访问频率。')}{panel('为什么保留 next 样本','它在部分Hit之前就暴露请求，能补足只看Miss的偏差。固定独立请求下更易解释；动态相关流仍需衰减与稳健估计。')}</div>
<h3>实现与统计解释分开</h3><p>R85 将 periodic 和 Miss 后暴露的 <code>next</code> 合并去重后采样，没有为两类样本设置独立权重。当前 Miss 不直接再加入这条概率采样流，但会更新重访与历史状态。这个区分避免了简单重复计数，也保留了周转反馈。</p>
<p class="small">256 / 2048按PROBE序号计时。概率状态对齐到t=max(q, last_next_ordinal)，已暴露next时可为q+1；重访风险仍按q。二者都不是墙钟时间。</p>'''))

pages.append(('datasets','数据设计 · 静态','让测试逐渐对准真正的问题',f'''
<p class="lead">数据集不只是更多案例。每次迭代都在修正一种错误的选型信号。</p>
<div class="timeline">{tl('起点 / 综合集 2.0','从少数成员数据，走向统一评测','500 train、50 eval。统一成本与评分口径，减少在各自擅长的数据上分别报优的偏差；其中仍混有均匀独立请求。')}{tl('聚焦 / 综合集 2.1','把规模、容量压力与倾斜放到主线','推荐540 train、72 eval；以hotspot、Zipf和lognormal为主。均匀对照及特殊边界移出主测；我方从推荐训练集固定train432/dev108，并选择60例训练面板。')}{tl('追问 / 综合集 3.0','全局倾斜，是否真的意味着分区热度可学习','保持父规格和BUILD种子，重建全部PROBE。显式保证每个算子内部也有概率差异，防止“只有算子冷热不同，算子内仍接近均匀”。540 train、72 eval。')}</div>
<h3>三种随机偏斜，覆盖不同形状</h3><div class="three-col">{panel('Hotspot','少量热门分区，配合冷长尾。检验热点保留与冷请求周转。')}{panel('Zipf','访问概率按秩衰减。检验多层次热度与容量装填的相互作用。')}{panel('Lognormal','连续、非规则的概率差异。减少策略只适配简单头部结构的机会。')}</div>
{eq('3.0 的偏斜度验收',f'TV(p, uniform) = ½ ∑<sub>j</sub> | p<sub>j</sub> − {frac("1","P")} |','TV为总变差距离，越大越偏离均匀。目标分布要求≥0.20，实际采样频率要求≥0.10；这是数据设计阈值。')}
<p class="small">均匀请求没有可学习的分区概率差异，但大小和搬运成本仍可不同。移出主测是任务聚焦，并不意味着这类调度问题必然简单。</p>'''))

pages.append(('dynamic-data','数据设计 · 动态','稳定倾斜之外，还要追踪热点迁移',f'''
<p class="lead">静态数据回答“能不能识别热点”；动态数据追问“热点变了，多久才能跟上”。</p>
<div class="stat-row"><div class="stat"><b>12</b><span>dyna1.0 完整案例</span></div><div class="stat"><b>500万</b><span>每例操作数</span></div><div class="stat"><b>3 × 2</b><span>迁移速度与阶段布局组合</span></div></div>
<table><thead><tr><th>设计维度</th><th>变化方式</th><th>检验的能力</th></tr></thead><tbody><tr><td>Slow / Fast / Burst</td><td>缓慢变化、快速切换、突发热点</td><td>估计窗口的响应与稳定性</td></tr><tr><td>Shared / Staggered</td><td>阶段同步或错开</td><td>跨算子竞争；错开时可出现BUILD与PROBE共存</td></tr><tr><td>长操作流</td><td>每例500万操作</td><td>累计周转损失与决策开销</td></tr></tbody></table>
<div class="callout"><strong>主测怎样汇总</strong><p>当前主榜分别计算 dyna12 与 final2.1/72 的逐例均分，再各赋50%权重。这样不会仅因静态案例更多，就把动态适应能力稀释掉。</p></div>
<div class="two-col">{panel('补充面板的角色','balanced24把static12与dyna12配成等权回归；inde提供独立补充族与更长请求。它们帮助定位问题，不自动改写主榜口径。')}{panel('仍值得补齐的设计','正交改变分区大小与访问概率的正相关、独立、负相关；加入超大冷请求和真实阶段交叠，进一步检验整集合装填。')}</div>
<h3>固定身份，比记住文件名更可靠</h3><p>新版会重编号，旧案例要按父谱系映射，而非按文件名猜测。我们固定输入指纹、生成种子、数据版本与结果所属批次。3.0已进入R86补充实验；它的成绩单独展示，不与2.1混成一条进步曲线。</p>'''))

pages.append(('evolution','优化路线','从独立尝试，到机制层面的融合',f'''
<p class="lead">有效的进步，逐渐从“加入更多规则”转向“更好地估计，同一套合法动作的价值”。</p>
<div class="timeline">{tl('01 / 我方 paired100','固定动作规划，比较两个方案','把next样本按序号去重，用100μs代理与短窗口未来代价比较驱逐集合。小树、候选池扩展及校准没有形成稳定收益，AI线随后暂停。')}{tl('02 / 双方风险探索','把分区自身与算子共性联系起来','同学R74/R75发展驱逐后的重访风险和算子共享；我方joint另用盘上暴露与意外Miss校准方案比较的未来均值。动态有收益，但没有稳定通过原训练面板。')}{tl('03 / R79 → R80','将next概率估值接入原调度框架','保留同学的合法规划器、重访与扫描分支；吸收我方next去重、64步价值估计、100μs代理及动作差额比较思想，形成hierarchy与paired两个变体。')}{tl('04 / R81','将算子热度与分区偏好分开计时','算子活跃度用256半衰期快速跟踪；算子内条件分布用2048半衰期积累稳定证据。普通随机路径使用两者的乘积。')}{tl('05 / R85_fast_prior8','校准快窗口中的先验强度','缩短窗口也减少了累计样本质量。将快算子先验总量从64降为约8.009，避免快窗口被同样大的均匀先验过度拉平。')}</div>
<div class="callout amber"><strong>融合的准确含义</strong><p>R85继承的是双方若干有效机制。它没有完整合并我方joint校准，也没有实现显式热点核心。其当前配置只生成一个hierarchy方案，保留的双方案比较代码不在这条主路径执行。</p></div>'''))

pages.append(('architecture','算法总览','一条完整的决策链',f'''
<p class="lead">先确认状态，再估计请求价值，最后在有限候选内解决容量约束。</p>
<div class="flow">{node('1','接收回调并更新状态','Overflow / Miss / Periodic；确认上次动作是否生效，维护PROBE序号与去重next。')}<div class="flow-arrow">↓</div>{node('2','识别可用证据与请求形态','维护快算子、慢分区样本；检测已被连续观测支持的扫描或等大小循环。')}<div class="flow-arrow">↓</div>{node('3','普通PROBE：两层热度合成','快速算子边际 × 自适应收缩的慢分区条件概率，得到每个分区的p̂。',True)}<div class="flow-arrow">↓</div>{node('4','计算单位空间保留价值','64p̂ ×（读单位成本＋写单位成本＋100/大小）；对明确next施加强保护。')}<div class="flow-arrow">↓</div>{node('5','选择能覆盖缺口的驱逐集合','最低优先级top4枚举15个非空子集；不够时走线性单受害者或堆回退。')}<div class="flow-arrow">↓</div>{node('6','剪掉冗余SPILL，完成必要LOAD','Miss目标必须加载；周期预取受空闲容量/已确认循环条件限制；记录动作意图。')}</div>
<p class="small">特殊分支：确认的等大小全局循环可直接选择近期对象；全局scan信号会停用hier估值，匹配目标算子才用扫描距离，其余走历史/风险。BUILD也走历史回退。</p>
<div class="callout"><strong>职责分离</strong><p>估计器回答“未来可能用到谁”；规划器回答“要释放这些字节，牺牲哪组对象更合适”。概率再准确，也不能跳过整分区的组合约束。</p></div>'''))

pages.append(('probability','核心公式 · 两层估计','算子跟得快，分区看得稳',f'''
<p>记 <em>K</em> 为算子数，<em>P</em> 为每算子的分区数。对每个去重next样本，分别累计快算子质量 <em>F<sub>i</sub></em> 与慢分区质量 <em>m<sub>ij</sub></em>；<em>M<sub>i</sub>=Σ<sub>j</sub>m<sub>ij</sub></em>。</p>
{eq('① 时间衰减','F<sub>i</sub> ← F<sub>i</sub> · 2<sup>−Δq/256</sup>，　m<sub>ij</sub> ← m<sub>ij</sub> · 2<sup>−Δq/2048</sup>','每个去重next样本对应的算子与分区分别加1。其他状态延迟衰减，访问时再对齐到当前逻辑时钟。')}
{eq('② 快算子边际',f'π̂<sub>i</sub> = {frac("F<sub>i</sub> + β/K","∑<sub>k</sub>F<sub>k</sub> + β")}', '先回答：下一次请求来自哪个算子？')}
{eq('③ 慢分区条件概率',f'θ̂<sub>ij</sub> = {frac("(1−α<sub>i</sub>)m<sub>ij</sub> + α<sub>i</sub>M<sub>i</sub>/P + 64/(KP)","M<sub>i</sub> + 64/K")}', '再回答：在这个算子内部，哪个分区值得保留？α决定向算子内均匀分布收缩多少。')}
<div class="prob-block">p̂<sub>ij</sub> = π̂<sub>i</sub> · θ̂<sub>ij</sub><small>全局访问概率 = 算子活跃度 × 算子内分区偏好</small></div>
{eq('④ R85 的先验校准',f'β = 64 · {frac("1 − 2<sup>−1/2048</sup>","1 − 2<sup>−1/256</sup>")} ≈ 8.009479828','指数累计的稳态质量与1/(1−衰减系数)成正比；快窗口质量更小，因此同步缩小快先验。慢条件先验总量仍为64。')}
<p>这避免了一个隐藏混杂：如果只缩短窗口却保留64的先验，变化的不仅是响应速度，还有先验相对于数据的强度。校准修正这一比例，并不增加新的观测。</p>'''))

pages.append(('shrinkage','核心公式 · 自适应共享','证据不足时共享，差异清晰时分开',f'''
<p class="lead">同一个算子的分区有共性，也可能极不相同。共享强度应该随证据变化。</p>
<div class="compact">
<p>维护算子慢样本总质量 <em>M<sub>i</sub></em>、分区质量平方和 <em>S<sub>i</sub>=Σ<sub>j</sub>m<sub>ij</sub>²</em>，以及样本权重平方和 <em>Q<sub>i</sub>=Σ<sub>e</sub>w<sub>e</sub>²</em>。</p>
{eq('① 有效样本量',f'n<sub>eff,i</sub> = {frac("M<sub>i</sub>²","Q<sub>i</sub>")}', '用于修正加权采样噪声；它不是回调次数，也不是全部真实访问数。')}
{eq('② 扣除有限样本噪声后的差异',f'ν<sub>i</sub> = max(0, {frac("P S<sub>i</sub>/M<sub>i</sub>² − 1 − (P−1)/n<sub>eff,i</sub>","1 − 1/n<sub>eff,i</sub>")})')}
{eq('③ 证据强度与共享比例',f'κ<sub>i</sub> = ν<sub>i</sub> · {frac("M<sub>i</sub>−8","M<sub>i</sub>+P")}，　α<sub>i</sub> = {frac("0.75","1+κ<sub>i</sub>")}')}
<p>当 <em>M<sub>i</sub>≤8</em>、有效样本量≤8，或数值条件不足时，源码使用默认 <em>α=0.75</em>。证据越多且分区差异越大，<em>α</em> 越小，越相信分区自己的质量；近均匀时保留较强共享。</p>
<div class="two-col">{panel('少量观测','一个分区暂时没出现，很可能只是没抽到。收缩可以避免过早把它判为冷。')}{panel('明确倾斜','如果少数分区持续占据大多数样本，过强共享会抹平热点。自适应α让差异逐渐显现。')}</div>
<div class="callout"><strong>共享发生在两个层面</strong><p>π̂跟踪算子之间的资源需求；α控制算子内部的分区平滑。前者解决“哪台算子更忙”，后者解决“忙碌是否集中在少数分区”。</p></div>
</div>'''))

pages.append(('planner','核心公式 · 成本与集合','概率只是起点，还要算每个字节的价值',f'''
<p>对大小为 <em>s<sub>ij</sub></em> 的普通PROBE分区，R85把概率转为未来64次访问的复用质量。它可以超过1，不是单次复用概率。</p>
{eq('① 单位空间保留优先级',f'ρ<sub>ij</sub> = 64p̂<sub>ij</sub> · ( {frac("1","R")} + {frac("1","W")} + {frac("100","s<sub>ij</sub>")} )','先按ρ从小到大找可牺牲对象；同值时优先更大对象。next目标额外加10¹²作为强保护。')}
{eq('② 前四个低优先级对象内枚举集合',f'ℒ(S) = ∑<sub>(i,j)∈S</sub> [ρ<sub>ij</sub>s<sub>ij</sub> + 0.25 · {frac("s<sub>ij</sub>","W")}]','约束Σs ≥ 当前缺口。q>0或R≥W时进入top4，枚举最多15个非空子集。')}
<p>乘回大小后，第一项成为预计读入、再次写出与Miss代理的总损失；第二项加入当前写出的权重。<strong>0.25是当前启发式系数</strong>，不是物理写费只收25%。改为1的既有尝试没有稳定获益。</p>
<div class="two-col">{panel('为什么不只保留大对象','大对象一次搬运贵，也占更多空间。单位空间收益与整个集合的装填必须同时考虑。')}{panel('top4放不下怎么办','已有PROBE时先检查最低优先级单个对象，再用堆取出更多对象；尚无PROBE时全排序贪心。最终剪除冗余SPILL。')}</div>
<div class="simulator web-only"><h3>动手看一次估值</h3><p class="small">公式示例，不是新评测。固定R=1024 B/μs、W=512 B/μs，拖动观察“总价值”与“单位空间价值”的区别。</p><div class="sliders"><label><span class="slider-label">算子概率 π <output id="op-label">40%</output></span><input aria-label="算子访问概率" id="op-prob" type="range" min="1" max="90" value="40"></label><label><span class="slider-label">条件概率 θ <output id="part-label">15%</output></span><input aria-label="分区条件概率" id="part-prob" type="range" min="1" max="90" value="15"></label><label><span class="slider-label">分区大小 <output id="size-label">4 MiB</output></span><input aria-label="分区大小MiB" id="part-size" type="range" min="1" max="64" value="4"></label></div><div class="sim-result"><div><b id="joint-value">6.00%</b><span>全局访问概率 p̂</span></div><div><b id="value-total">47.57 ms</b><span>64步预计总损失</span></div><div><b id="value-density">11.89</b><span>单位空间损失 ms/MiB</span></div></div></div>
<div class="print-only callout"><strong>一个数值例子</strong><p>π=0.4、θ=0.15，则p̂=0.06。若分区4 MiB、R=1024 B/μs、W=512 B/μs，64步搬运与Miss代理约47.57 ms；单位空间约11.89 ms/MiB，另计0.25倍当前写入项。</p></div>
<p class="small">候选数n≤KP：常见路径约O(n)，多受害者回退O(n+v log n)，最坏O(n log n)；辅助状态O(KP)。</p>'''))

pages.append(('callbacks','执行细节','BUILD、Miss 与预取，各有自己的职责',f'''
<div class="compact">
<table><thead><tr><th>回调</th><th>当前行为</th></tr></thead><tbody><tr><td>onMemoryOverflow</td><td>更新证据，排除当前INSERT目标，按缺口选择SPILL并剪除冗余动作。</td></tr><tr><td>onPartitionMiss</td><td>结束目标的盘上重访观察；释放足够空间后，必须LOAD目标整分区。</td></tr><tr><td>onPeriodicAdjust</td><td>首个Overflow/Miss启用调度器后才更新next并考虑预取；此前直接返回。</td></tr></tbody></table>
<h3>预取：明确会用，还要考虑是否额外驱逐</h3><p>若目标已在内存、不是PROBE阶段或大于总内存，就不预取。空闲空间足够时可LOAD；若需要额外驱逐，只有已确认的等大小循环分支会继续。这样保留普通Miss回调带来的后续信息。</p>
<h3>重访风险：为历史与特殊分支保留后备信息</h3>
{eq('盘上暴露与事件衰减','E ← E e<sup>−Δq/τ</sup> + aτ(1−e<sup>−Δq/τ</sup>)，　N ← N e<sup>−Δq/τ</sup><br>μ = (E+64)/(N+1)，　r = 64/(64+μ)','a为正在盘上观察的分区数；确认驱逐后开始观察，Miss计事件，预取读回只结束暴露。分区τ=512、算子τ=128，是时间常数而非半衰期。')}
<p>在历史回退分支，周期覆盖率不足0.75时，可见历史权重为0.25，其余结合分区/算子重访风险；覆盖率≥0.75时权重切为1，完全采用可见历史。普通随机PROBE主路径直接使用层次概率，<strong>并不是把风险分数再叠加一次</strong>。</p>
<h3>BUILD：先后顺序改变机会成本</h3>
{eq('已确定会在BUILD内落盘的分区','首次写出 a + 后续追加 b = 最终分区大小','提前落盘不额外增加这部分累计写字节；改变的是占用内存的时间、挤走谁，以及谁能留到PROBE。')}
<p>当前R85没有新的BUILD增长预测器；BUILD候选沿用历史/风险分支。降低BUILD当前写量也可能增加之后的PROBE周转，因此没有另加“BUILD不罚Miss就优先牺牲”的规则。</p>
</div>'''))

pages.append(('results','实验结果','进步主要来自更好的概率估值',f'''
<p>下图来自<strong>同一R85归档批次</strong>：八方法含Naive、单次CPU评测；dyna1.0/12与final2.1/72分别均分，再各占50%。分数越高，表示相对同批Naive节省的成本越多。</p>
{eq('评分与汇总','score<sub>x</sub> = clamp(10 · (1 − C<sub>x</sub>/C<sub>Naive,x</sub>), 0, 10)<br>综合分 = ½ · mean(score<sub>dyna</sub>) + ½ · mean(score<sub>final</sub>)')}
<div class="score-controls web-only" role="group" aria-label="选择成绩范围"><button data-score="equal_dataset_score" aria-pressed="true">两组等权</button><button data-score="dyna12_score" aria-pressed="false">动态12例</button><button data-score="final72_score" aria-pressed="false">静态72例</button></div>
{chart}
<table><thead><tr><th>主线方法</th><th>dyna12</th><th>final2.1 / 72</th><th>综合</th></tr></thead><tbody><tr><td>我方 paired100</td><td>4.049627</td><td>3.483619</td><td>3.766623</td></tr><tr><td>R80 hierarchy</td><td>4.306697</td><td>3.709196</td><td>4.007946</td></tr><tr><td>R81 双时间尺度</td><td>4.455848</td><td>3.713010</td><td>4.084429</td></tr><tr class="highlight"><td>R85 fast_prior8</td><td>4.482767</td><td>3.692813</td><td>4.087790</td></tr></tbody></table>
<p><strong>读懂增益来源：</strong>R85相对R81，动态组+0.026919，静态组−0.020197，综合仅+0.003361。最终静态组有6例成本高于Naive；平均收益没有消除长尾问题。</p>
<p class="small">final3.0的R86补充中，R85A静态分4.087043，R85 anchor为4.168410，排序发生变化。它们是不同请求版本，不能把新旧分差当作算法提升。</p>'''))

pages.append(('lessons','关键认识','五个真正改变方向的教训',f'''
{lesson('01','候选更丰富，不保证选得更好','covering-singleton和小树扩展没有稳定晋升。好动作进候选池之后，仍可能被有偏估值排错；因此先改善观测与估值，再扩搜索。')}
{lesson('02','减少 Miss，可能付出更大的读写代价','R12的train519比R80少833次Miss，按该例真实罚值只省0.099127秒，却多7.346876秒模拟IO费用，净物理成本增加约12.63%。软核心的直觉需要周转字节验证。')}
{lesson('03','改成总价值排序，会改变整个可行集合','R10 value_rank在固定训练面板最坏单例物理成本约为R80的23.565倍。成本×概率有用，但移除单位空间归一化，会改变候选入口和整分区装填。')}
{lesson('04','一个数据域的优势，不等于普遍优势','我方joint在动态12例物理成本全部改善；原72例均分仅比paired高约0.000085，最坏物理成本增加约5.48%。需要同时看动态适应与静态长尾。')}
{lesson('05','更低的当前写量，不一定是更好的BUILD策略','既有cold-BUILD尝试累计减少约0.409秒BUILD写出，却增加约12.393秒PROBE读写。阶段之间的机会成本，比眼前最小写量更值得关注。')}
<div class="callout"><strong>当前最有用的判断标准</strong><p>总成本是否下降？下降来自读、写、Miss还是决策时间？最坏案例发生了什么？这些问题比“机制听起来是否合理”更能推动优化。</p></div>
<p class="small">本页数字来自各自固定训练/评测报告，用于解释机制；不与上一页的同场主榜合并计分。</p>'''))

pages.append(('fallback','补充公式 · 回退分支','当请求结构比频率更有用',f'''
<p>以下是R85保留的历史、风险与扫描分支。普通随机PROBE使用前述层次概率；当分支条件变化时，仍用同一个成本与容量规划器执行。</p>
<div class="compact">
{eq('① 可见历史：次数与最近性',f'h<sub>j</sub> ← h<sub>j</sub> · {frac("256","256+Δq")} + 1<br>u<sub>j</sub> = {frac("min(1, h<sub>j</sub>/16)","1 + (max(0, q+1−last<sub>j</sub>)+1)/64")}', '历史只从可见当前Miss或next更新；此处是有理式衰减，不是概率层的指数半衰期。')}
{eq('② 周期观测覆盖率',f'G ← G e<sup>−(t−t<sub>G</sub>)/256</sup> + (1−e<sup>−1/256</sup>)<br>c = min(1, {frac("G e<sup>−max(0,q−t<sub>G</sub>)/256</sup>","1−e<sup>−max(1,q)/256</sup>")})', '只有periodic暴露新的PROBE next时，才增加覆盖质量G。t为新next序号；随后令t_G=t。')}
{eq('③ 回退估值的组合','w = 1（c≥0.75），否则 w=0.25<br>reuse = w · u + (1−w)[(1−α)r<sub>partition</sub> + αr<sub>operator</sub>]','仅在有相应重访记录时使用风险项；没有分区记录则回退到u，没有算子记录则只用分区值。')}
<table><thead><tr><th>结构分支</th><th>触发与行为</th></tr></thead><tbody><tr><td>扫描</td><td>连续同算子、相同非零步长至少6次，且可见观察密度超过一半；匹配目标算子时用1−步距/P替换u，再进入风险/覆盖混合。</td></tr><tr><td>等大小全局循环</td><td>所有算子PROBE、所有分区等大且非空；每条后继边置信计数≥3并构成覆盖全分区的单环。扫描近期对象，排除当前目标和next，寻找单个可覆盖缺口的对象。</td></tr></tbody></table>
<p class="small">这些是保留的结构特化，不是本轮主要增益来源。模式证据不足时继续走通用流程，不需要假设请求一定循环或扫描。</p>
</div>'''))

pages.append(('sources','版本与复现','让这份叙事有明确的落点',f'''
<p class="lead">主讲版本固定，数据口径固定。后续同学更新算法时，可以从这个快照继续讲清变化。</p>
<div class="version-box"><strong>R85_fast_prior8 · 纯C++14调度器</strong><br>源码提交：<span class="mono">{SNAP}</span><br>路径：<span class="mono">src/experiments/r85_math_ablations_20261030/R85_fast_prior8.cpp</span><br>SHA256：<span class="mono">a0ebc08399a8cd8c039dae59a779231df0c35306af3ea3269df3067c321779b5</span><br><a class="content-link" href="{SRC}">查看固定版本源码 ↗</a></div>
<h3>在第三方环境重测</h3><p>将仅含 <code>MySpillScheduler</code> 的源码接入同一官方框架，使用C++14与O2编译；保持输入指纹一致，每方法每题一次，Naive同批重测。保存IO、Miss、决策时间与失败，按两套数据各50%汇总。100μs只属于算法估值，不改测试输入的罚值。</p>
<h3>主要阅读依据</h3>
<div class="refs">
<div class="ref"><a href="{BASE}docs/R85_RESULTS_20261030.md">R85 完整结果与数学消融</a>：当前主讲版本、完整两组成绩、先验校准与anchor比较。</div>
<div class="ref"><a href="{SRC}">R85_fast_prior8.cpp</a>：公式与实际控制流的直接依据，尤其MODE=2、top4规划、预取与回退。</div>
<div class="ref"><a href="https://github.com/cyanneko/HuaweiHackathon/blob/2932ce972289b8744f5355c9692fe9cb2c93b5f4/docs/R80_RESULTS_20261030.md">R80 机制迁移报告</a>：我方paired思想与同学原框架的连接。</div>
<div class="ref"><a href="https://github.com/cyanneko/HuaweiHackathon/tree/c65c7b32b06a5764ce9ad4881133a3c6eb33ed17/final_dataset">final2.1</a>、<a href="https://github.com/cyanneko/HuaweiHackathon/tree/e6613435d59690d6dd768813332387108f7e83c2/final_dataset">final3.0</a>与<a href="https://github.com/cyanneko/HuaweiHackathon/tree/c65c7b32b06a5764ce9ad4881133a3c6eb33ed17/dyna_dataset">dyna1.0</a>：数据设计、版本与生成配方。</div>
<div class="ref"><a href="{OWN}round10/REPORT_V1.md">我方Round10</a>、<a href="{OWN}round12/pure/REPORT_V1.md">Round12</a>、<a href="{OWN}round9/eval72/REPORT_V1.md">完整72例</a>：集合排序、软核心与联合校准的正负结果。</div>
<div class="ref"><a href="{BASE}docs/R86_SUPPLEMENT_20261030.md">R86 补充敏感性实验</a>：将新final3.0与旧主测分开理解。</div>
</div>
<p class="small">本报告对源码分支与公式作静态核对，成绩引用固定归档；不是一次新增复测。源码链接是否可打开取决于原仓库访问权限，网站正文和PDF可独立阅读。制作：Vanius0525 × cyanneko 项目资料整理。</p>'''))
