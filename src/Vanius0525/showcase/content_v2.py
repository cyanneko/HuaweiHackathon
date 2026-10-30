"""Final R81 narrative; retains the original R85 edition in content.py and Git."""
from pathlib import Path
import json, math
from content import pages as legacy, eq, frac, panel, tl, node, lesson

SNAP='b0beecfee11e4ea4732a52d02c195316909db567'
BASE=f'https://github.com/cyanneko/HuaweiHackathon/blob/{SNAP}/'
CODE='https://github.com/cyanneko/HuaweiHackathon/blob/3064e270fde0473810cd8c0e57b738ee48356254/submission/MySpillScheduler.cpp'
DATA=json.loads((Path(__file__).parent/'dist/assets/results-v2.json').read_text())
OLD={p[0]:p for p in legacy}
def keep(key):
 p=OLD[key]
 return (p[0],p[1],p[2],p[3].replace('R85','R81'))
def figure_curve():
 def line(h):return ' '.join(f'{50+520*t/4096:.1f},{170-140*2**(-t/h):.1f}' for t in range(0,4097,32))
 return f'''<svg class="decay-chart" viewBox="0 0 610 215" role="img" aria-label="观测权重随PROBE间隔指数下降；256快曲线比2048慢曲线衰减更快"><path d="M50 30V170H575" fill="none" stroke="#a6bcb0"/><path d="M50 100H575" stroke="#dce4d7" stroke-dasharray="4 5"/><text x="14" y="35">100%</text><text x="18" y="104">50%</text><text x="24" y="174">0</text><text x="48" y="195">0</text><text x="300" y="195">2048</text><text x="540" y="195">4096</text><text x="215" y="212">距该观测经过的 PROBE 次数</text><polyline points="{line(2048)}" fill="none" stroke="#c3864d" stroke-width="3"/><polyline points="{line(256)}" fill="none" stroke="#087e82" stroke-width="3"/><line id="decay-marker" x1="115" x2="115" y1="28" y2="173" stroke="#718a80" stroke-dasharray="4 4"/></svg>'''

pages=[]
pages.append(('overview','最终方案','面向动态倾斜的分层热度调度',f'''
<p class="lead">热点会迁移，分区大小不一，普通Hit又并非完全可见。我们的目标，是在有限内存里持续做出值得的驻留选择。</p>
<p>当前最终方案是 <strong>R81_op256_cond2048</strong>：以快速变化的算子热度为外层，以较稳定的分区条件分布为内层，再用读写成本把“访问概率”转换成“保留价值”。</p>
<div class="stat-row"><div class="stat"><b>256 / 2048</b><span>算子 / 分区观测的衰减半衰期</span></div><div class="stat"><b>4.084530</b><span>R87同场归档 · R81主测均分</span></div><div class="stat"><b>12 + 72</b><span>动态与静态两套主测 · 各占50%</span></div></div>
<div class="prob-block">全局热度 = 算子活跃度 × 分区条件偏好<small>先估计“谁在变忙”，再判断“忙在哪里”。</small></div>
<h3>我们不是只走过一条路线</h3><p>从直接启发式到学习选择器，从分区重访风险到算子共享，再到双时间尺度估计：有些机制进入最终算法，有些在负结果中帮助我们重新定义问题。数据集也从静态随机，逐步扩展到大规模动态倾斜与更明确的分区偏斜。</p>
<div class="ribbon"><div>问题与成本</div><span>→</span><div>四条探索路线</div><span>→</span><div>数据集演进</div><span>→</span><div>R81机制与证据</div></div>
<p class="small">最终选定R81。R85A在该次主测的数值均分仍略高；本展示解释最终方案与选择过程，不以实验编号代替机制。源码固定于3064e270，报告快照b0beecfe。</p>'''))
pages.append(keep('problem'))

pages.append(('routes','探索全景','四条路径，汇成一个可解释的调度器',f'''
<p class="lead">我们保留的是经过检验的机制和认识，而不是所有尝试的叠加。</p>
<div class="route-map" aria-label="四条探索路径">
<button class="route-card active" data-route="heuristic" aria-pressed="true"><span>01 / 结构与成本</span><strong>启发式与集合规划</strong><small>大小、next保护、有限子集搜索</small></button>
<button class="route-card" data-route="learning" aria-pressed="false"><span>02 / 学习决策</span><strong>专家与小树选择</strong><small>候选动作、续接教师、margin校准</small></button>
<button class="route-card" data-route="risk" aria-pressed="false"><span>03 / 观测修正</span><strong>热度与重访风险</strong><small>分离next样本与驱逐造成的Miss</small></button>
<button class="route-card" data-route="hierarchy" aria-pressed="false"><span>04 / 融合与适应</span><strong>双时间尺度热度</strong><small>快算子 × 慢分区 → 成本规划</small></button>
</div>
<div class="route-detail web-only" id="route-detail" aria-live="polite"><h3>先保证动作合法，再比较集合价值</h3><p>从低成本驱逐与next保护出发，发现单个对象排序不能代替容量约束下的集合选择。最终保留top4子集规划、合法回退和冗余SPILL剪枝。</p><span class="pill">进入最终方案：有限候选与成本规划</span></div>
<table><thead><tr><th>路线</th><th>最重要的认识</th><th>最终去向</th></tr></thead><tbody><tr><td>启发式规划</td><td>单位空间价值与整集合装填都重要</td><td>保留有限规划器</td></tr><tr><td>学习选择</td><td>更多模型容量补不上教师与观测的问题</td><td>AI线暂停，保留负结果</td></tr><tr><td>热度/风险修正</td><td>访问分布与策略导致的周转应分开建模</td><td>next用于主概率，风险保留为回退</td></tr><tr><td>分层热度</td><td>算子变化速度与分区偏好不必相同</td><td>R81主路径</td></tr></tbody></table>
<p class="small">点击网站中的四条路径可查看动机、结果与保留部分。R81没有整体合并我方joint，也没有调用保留在源码中的双方案比较器。</p>'''))

pages.append(('cost-path','路径一 · 规划与成本','从挑一个受害者，到选择一组代价',f'''
<p>最初的直觉很直接：优先写出小分区，保护明确的下一次访问，再用频率与最近性避免驱逐热点。真正的困难在于：<strong>容量按字节约束，动作却只能以整分区为单位</strong>。</p>
<div class="timeline">{tl('局部动作','少写一点，是否一定更便宜','更小的当前写量可能改变最终留在内存的集合，增加之后的读回；需要比较完整执行轨迹。')}{tl('候选与选择','好动作进了候选池，也可能被排错','扩展covering-singleton候选没有稳定晋升。问题不只在搜索范围，也在热度估值是否偏向可见Miss。')}{tl('大小与热度','总价值排序不能直接取代密度排序','R10直接按整对象总价值排序，最坏训练例相对R80成本达23.565倍。后续保留单位空间估值，再在可行子集中比较总损失。')}{tl('驻留与周转','软热点核心是有价值的假设，但这版没有获胜','R12少量保护带来了更少Miss，却可能导致更大分区反复搬运；最终没有引入该核心/尾部折扣。')}</div>
<div class="callout amber"><strong>BUILD也要看后续效果</strong><p>最新独立BuildBestFit对照只改冷启动BUILD的单受害者选择：dyna平均成本比R81高0.01435%，stat低0.08019%，方向相反且幅度很小，最终未采用。</p></div>
<p class="small">BuildBestFit为同学已归档的22例独立对照，不是此次新增实验，也不混入旧84例主榜。它只保证局部可行单对象的写量选择，不保证整个轨迹更优。</p>'''))

pages.append(('learning','路径二 · AI探索','先修正学习问题，再讨论模型大小',f'''
<p class="lead">我们尝试让模型选择专家或动作。但学习器能学到什么，首先取决于观测和教师是否可靠。</p>
<div class="ribbon"><div>合法候选动作</div><span>→</span><div>续接模拟评估</div><span>→</span><div>训练小树</div><span>→</span><div>独立验证</div></div>
<div class="stat-row"><div class="stat"><b>75</b><span>贡献教师状态的请求流</span></div><div class="stat"><b>150</b><span>该轮实际教师状态</span></div><div class="stat"><b>44 / 150</b><span>更换续接策略后动作排名改变</span></div></div>
<h3>瓶颈不只是树的深度</h3><p>同一个局部动作的好坏，会随后续策略改变；按固定回调数量截取续接，又可能覆盖不同长度的真实请求流。这样的标签并非稳定的“动作真值”。增加候选或树深，无法直接消除这些差异。</p>
<table><thead><tr><th>尝试</th><th>实际观察</th><th>由此调整的方向</th></tr></thead><tbody><tr><td>小树与margin校准</td><td>两种校准在同批dev100分别低于强AI参照0.065130、0.083493分</td><td>停止沿相同教师继续加深、扫阈值</td></tr><tr><td>局部候选学习</td><td>续接策略会改变动作排名</td><td>保留分项成本与教师分歧</td></tr><tr><td>参数选择设想</td><td>需要纯配置先表现出稳定互补</td><td>作为后备路线，未并入最终R81</td></tr></tbody></table>
<div class="callout"><strong>最后留下的认识</strong><p>先让合法观测能区分有价值的状态，再判断是否存在值得学习的选择空间。R81最终使用确定性的统计估计与规划，不包含训练模型。</p></div>'''))
pages.append(keep('observations'))
pages.append(keep('datasets'))
d=keep('dynamic-data')
b=d[3].replace('它的成绩单独展示','它的成绩独立归档').replace('补充面板的角色','stat：改变生成假设').replace('balanced24把static12与dyna12配成等权回归；inde提供独立补充族与更长请求。它们帮助定位问题，不自动改写主榜口径。','stat在K×P个分区上分别生成潜在变化，再全局归一化；不预设算子热度层。40例中32例500万操作、8例100万操作。').replace('仍值得补齐的设计','进一步检验泛化').replace('正交改变分区大小与访问概率的正相关、独立、负相关；加入超大冷请求和真实阶段交叠，进一步检验整集合装填。','stat采用全局操作时钟，16条错开阶段案例都存在BUILD/PROBE交叠；24 train、6 dev、10 eval。其均匀对照仅作独立补充，不进入旧主榜。')
pages.append((d[0],d[1],d[2],b))

pages.append(('generation','数据生成策略','把“随机”拆成可控制、可检查的设计',f'''
<p class="lead">生成器的职责是制造有解释力的变化，而不仅是延长操作流。</p>
<div class="generation-flow"><div><b>01</b><strong>物理规格</strong><span>算子/分区数、容量、大小、带宽</span></div><div><b>02</b><strong>BUILD结构</strong><span>增长、最终大小与阶段布局</span></div><div><b>03</b><strong>PROBE分布</strong><span>算子份额、条件热度、热点迁移</span></div><div><b>04</b><strong>验收与固定</strong><span>逐行合法性、实际分布、种子与SHA</span></div></div>
{eq('生成与估计共同面对的分解','p(i,j,t) = π<sub>i</sub>(t) · θ<sub>ij</sub>(t)','算子份额与算子内偏斜是两个维度；全局分布偏斜，并不能保证每个算子内部也有热点。')}
<div class="heat-demo web-only"><div class="score-controls" role="group" aria-label="选择概率结构示意"><button data-heat="operator" aria-pressed="true">只有算子偏斜</button><button data-heat="partition" aria-pressed="false">再加入分区偏斜</button><button data-heat="shift" aria-pressed="false">迁移算子热点</button></div><div id="heat-grid" class="heat-grid" aria-label="四个算子八个分区的联合概率示意"></div><p id="heat-explain" class="small">示意：行的总量不同，但每行内部一样；算子内没有可学习的分区差异。</p><p class="caption">颜色越深表示联合请求概率越大。数值仅演示分解，不是新增生成数据或实测。</p></div>
<div class="print-only callout"><strong>一个关键反例</strong><p>若π=(0.65,0.20,0.10,0.05)，每个算子内部θ都均匀，整体已有明显倾斜，但仍无法区分同算子的分区。final3.0因此进一步要求算子内偏斜；dyna则让π随时间变化。</p></div>
<h3>为什么要分开固定BUILD与PROBE</h3><p>final3.0保留父规格与BUILD种子，重新生成PROBE，便于追问“变化来自热度还是物理结构”。同时记录目标概率与实际采样频率，避免生成配置写着偏斜，落地样本却接近均匀。</p>
<p>stat进一步把潜在随机过程下放到分区，用全局操作时钟每64步更新；大小、BUILD、PROBE使用不同随机流。它没有手工设定算子热度层，因而也能检验分层估计是否依赖生成器的假设；容量与预算仍可能造成耦合。</p>'''))

pages.append(keep('architecture'))
pages.append(('probability','R81公式 · 两层热度','快速响应算子，稳定估计分区',f'''
<p>记K为算子数、P为每算子的分区数。每个去重next样本分别更新快算子质量F<sub>i</sub>与慢分区质量m<sub>ij</sub>，M<sub>i</sub>=Σ<sub>j</sub>m<sub>ij</sub>。</p>
{eq('① 按PROBE间隔衰减','F<sub>i</sub> ← F<sub>i</sub>·2<sup>−Δq/256</sup>，　m<sub>ij</sub> ← m<sub>ij</sub>·2<sup>−Δq/2048</sup>','对应去重next样本加1；其余状态按需衰减到当前概率时钟。')}
{eq('② 算子边际概率',f'π̂<sub>i</sub> = {frac("F<sub>i</sub> + 64/K","∑<sub>k</sub>F<sub>k</sub> + 64")}', '较短窗口帮助算子份额跟随动态热点。')}
{eq('③ 算子内条件概率',f'θ̂<sub>ij</sub> = {frac("(1−α<sub>i</sub>)m<sub>ij</sub> + α<sub>i</sub>M<sub>i</sub>/P + 64/(KP)","M<sub>i</sub> + 64/K")}', '较长窗口减少分区估计抖动；α随分区差异与有效观测量调整。')}
<div class="prob-block">p̂<sub>ij</sub> = π̂<sub>i</sub> · θ̂<sub>ij</sub><small>有相同分区偏好的两个算子，也可以因当前活跃度不同而获得不同驻留价值。</small></div>
<div class="callout"><strong>R81保留的先验</strong><p>快、慢两层的总先验都为64。后来R85A尝试将快先验降为约8.009，R87再尝试快慢专家混合；它们是独立对照，没有进入最终提交。</p></div>
<p class="small">概率不按分区大小分配。大小进入后面的成本与容量规划，避免把“大”直接当成“热”。</p>'''))

pages.append(('recency','R81公式 · 时间信息','访问间隔已经进入热度',f'''
<p class="lead">R81没有丢掉新近性；它把时间间隔编码到整个观测历史，而不是只看最后一次访问。</p>
{eq('一条观测在当前时刻的贡献','w(Δq; H) = 2<sup>−Δq/H</sup>，　H∈&#123;256,2048&#125;','每经过一个半衰期，样本的权重减半。Δq的单位为PROBE次数，不是毫秒。')}
{figure_curve()}<div class="legend"><span>算子：H=256</span><span>分区：H=2048</span></div>
<div class="decay-control web-only"><label class="slider-label" for="decay-age">样本距现在的PROBE间隔 <output id="decay-age-label">512</output></label><input id="decay-age" type="range" min="0" max="4096" step="64" value="512"><div class="sim-result"><div><b id="fast-weight">25.00%</b><span>快算子样本剩余权重</span></div><div><b id="slow-weight">84.09%</b><span>慢分区样本剩余权重</span></div></div></div>
<div class="print-only callout"><strong>经过512次PROBE</strong><p>快算子样本只保留25%权重，慢分区样本仍保留约84.09%。同一个历史事件，对两个时间尺度的影响不同。</p></div>
<h3>显式age项在哪里</h3><p>普通随机PROBE路径将reuse直接设为64p̂，覆盖之前计算的历史age值；这里没有再独立乘一次“距上次访问”的因子。BUILD、扫描等回退路径保留历史最近性，并与重访风险结合。</p>
<p class="small">这是距已观测事件的间隔。普通Hit身份不可见，因此算法不能声称掌握所有分区真实的最后一次访问时间。概率时钟为max(q,last_next_ordinal)，可比已执行PROBE序号提前1。</p>'''))
pages.append(keep('shrinkage'))
planner=keep('planner')
pages.append((planner[0],planner[1],planner[2],planner[3].replace('候选数n≤KP：常见路径约O(n)，多受害者回退O(n+v log n)，最坏O(n log n)；辅助状态O(KP)。','记n=KP。完整回调最坏O(n log(n+1)+C_init)，状态O(n+C_table)；常见单受害者路径近似线性。首次查表初始化共18,436个double项，也计入实际决策耗时。')))
pages.append(keep('callbacks'))

names={'R85_fast_prior8':'R85 · prior8','R81_op256_cond2048':'R81 · 最终方案','R85_hier_anchor':'R85 · anchor','R80_next_hier_fast100':'R80 · hierarchy','Van_latest':'我方 · paired100','R75_dense_switch':'R75 · dense switch','R87_fixedshare_op':'R87 · fixed share'}
ranked=sorted([r for r in DATA['scores'] if r['method']!='Naive'],key=lambda x:x['equal_dataset_score'],reverse=True)
chart='<div class="score-chart" aria-label="R87同场主测成绩">'+''.join(f'<div class="bar-row {"selected" if r["method"]=="R81_op256_cond2048" else ""}" data-method="{r["method"]}"><span class="bar-label">{names[r["method"]]}</span><div class="bar-track"><div class="bar-fill" style="--width:{r["equal_dataset_score"]/5*100:.5f}%"></div></div><span class="bar-value">{r["equal_dataset_score"]:.6f}</span></div>' for r in ranked)+'</div>'
pages.append(('results','同场结果','最终采用R81，收益来自两类场景',f'''
<p>以下为R87归档同批主测：dyna1.0全12例与final2.1全72例，八方法含Naive均新测一次。两套各自逐例均分，再各占50%；不把更多静态样本的数量优势当作更大权重。</p>
{eq('成本归一化分数，越高越好','S<sub>x</sub>=clip(10·(1−C<sub>x</sub>/C<sub>Naive,x</sub>),0,10)<br>S<sub>main</sub>=½mean(S<sub>dyna</sub>)+½mean(S<sub>final</sub>)')}
<div class="score-controls web-only" role="group" aria-label="选择成绩范围"><button data-score="equal_dataset_score" aria-pressed="true">两组等权</button><button data-score="dyna12_score" aria-pressed="false">动态12例</button><button data-score="final72_score" aria-pressed="false">静态72例</button></div>{chart}
<table><thead><tr><th>主线</th><th>dyna12</th><th>final72</th><th>综合</th></tr></thead><tbody><tr><td>原paired100</td><td>4.049627</td><td>3.483592</td><td>3.766610</td></tr><tr><td>R80 hierarchy</td><td>4.306731</td><td>3.709191</td><td>4.007961</td></tr><tr class="highlight"><td>R81</td><td>4.455853</td><td>3.713206</td><td>4.084530</td></tr><tr><td>R85A</td><td>4.482721</td><td>3.692943</td><td>4.087832</td></tr></tbody></table>
<p>R81将两组表现同时推高。R85A相对R81继续改善动态组，却降低静态组，综合差约0.0033分；最终提交选择R81，后续消融用于解释机制。</p>
<p class="small">独立stat10历史评测为两方法各3次、60格有效，R81均分3.439814873；单独报告，不进入旧84例主榜。此处引用已归档结果，本轮未新增算法运行。</p>'''))

abrows=[('UniformOperatorMarginal','算子边际改为均匀'),('UnitMissCost','代价改为单位Miss密度'),('UnifiedSlow2048','快窗口统一为2048'),('FixedShare075','共享固定为0.75'),('NoNextProtection','去next保护'),('NoPeriodicPrefetch','去周期预取'),('NoStructurePolicy','去扫描/循环决策')]
abmap={r['method']:r for r in DATA['ablations']}
abtable=''.join(f'<tr><td>{title}</td><td>{abmap[key]["equal_dataset_score"]:.6f}</td><td>+{abmap[key]["score_gap"]:.6f}</td></tr>' for key,title in abrows)
pages.append(('ablation','机制证据','移除一个机制，实际改变了什么',f'''
<p class="lead">最新消融支持优先讲清：算子热度、异质搬运成本，以及快慢时间尺度。</p>
<p>这一组是独立的R81消融批次，Full主测均分为<strong>4.084508</strong>。每行仅按报告规定改变对应机制，分数差为Full−干预版，正值表示移除后下降。</p>
<table><thead><tr><th>干预内容</th><th>干预版主测均分</th><th>保留机制的分差</th></tr></thead><tbody>{abtable}</tbody></table>
<div class="two-col">{panel('动态算子热度很关键','将算子边际置为均匀，dyna分数下降2.729928，final仅下降0.061736。收益主要发生在动态算子需求变化中。')}{panel('不是每条分支都带来物理收益','去掉扫描/循环决策，94例的IO、Hit、Miss均与Full相同。极小分差来自计时，不能用来说明结构特化创造了增益。')}</div>
<h3>实验也有失败与恢复</h3><p>原94×9运行有1格被局部预算截断。后续按固定规则重测最后一个stat案例的全部9方法，用同批Naive替换该例原结果，最终分析846格。旧dyna/final主测完整保留，stat继续独立。</p>
<p class="small">各行是冻结组合中的条件移除效果，不能相加成独立贡献。共享、统一时间尺度与预取在不同数据集上还出现过方向相反的结果；这里引用上游归档，没有重新执行消融。</p>'''))
pages.append(keep('lessons'))
pages.append(keep('fallback'))

pages.append(('sources','版本与复现','从展示回到可核验的代码与结果',f'''
<div class="version-box"><strong>最终提交：R81_op256_cond2048</strong><br>固定源码：<span class="mono">3064e270fde0473810cd8c0e57b738ee48356254 / submission/MySpillScheduler.cpp</span><br>SHA256：<span class="mono">2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617</span><br><a class="content-link" href="{CODE}">查看最终提交源码 ↗</a></div>
<p>当前提交对历史R81整理排版、注释和宏名称，参数与算法未变。发布记录核对了预处理token与ELF等价；本展示再次核对源文件SHA及实际启用的分支。</p>
<h3>复测时固定什么</h3><p>同一官方框架、CPU、C++14/O2、输入指纹与同批Naive。分别保留IO、Miss、决策耗时与失败。100μs是内部估值代理，真实计分使用输入罚值；D还包含框架状态快照的成本。</p>
<div class="refs">
<div class="ref"><a href="{BASE}docs/FINAL_SUBMISSION_20261031.md">最终R81选择与代码身份</a>；<a href="{BASE}docs/R81_ALGORITHM_COMPLEXITY_20261031.md">完整算法、公式与回调复杂度</a>。</div>
<div class="ref"><a href="{BASE}docs/R87_RESULTS_20261031.md">R87同场八方法主测</a>；<a href="{BASE}docs/R81_ABLATION_20261031.md">R81七项消融与固定恢复</a>。</div>
<div class="ref"><a href="{BASE}docs/R81_BUILD_COMPARISON_20261031.md">BUILD独立对照</a>；<a href="{BASE}docs/R81_STAT_RESULTS_20261031.md">stat独立评测</a>。</div>
<div class="ref"><a href="https://github.com/cyanneko/HuaweiHackathon/blob/388183be301a09157730d3a4b1e966e7d036bf9e/src/reports/r80_20261030/report_zh.md">R80机制迁移</a>：我方paired思路接入同学原规划、共享与风险框架。</div>
<div class="ref"><a href="https://github.com/cyanneko/HuaweiHackathon/tree/c65c7b32b06a5764ce9ad4881133a3c6eb33ed17/final_dataset">final2.1</a>、<a href="https://github.com/cyanneko/HuaweiHackathon/tree/e6613435d59690d6dd768813332387108f7e83c2/final_dataset">final3.0</a>、<a href="https://github.com/cyanneko/HuaweiHackathon/tree/c65c7b32b06a5764ce9ad4881133a3c6eb33ed17/dyna_dataset">dyna</a>与<a href="https://github.com/cyanneko/HuaweiHackathon/tree/e78279e316d578cd1d15cee29f84295d2602b55d/stat_dataset">stat</a>的设计与固定版本。</div>
<div class="ref"><a href="https://github.com/cyanneko/HuaweiHackathon/tree/a00677d59154156ac1da04b236c1bf8d0cff64b1/src/Vanius0525/level1">我方实验归档</a>：联合风险、大小排序、软核心及原完整评测。</div>
</div>
<p class="small">正文与PDF无需访问仓库即可阅读，来源链接遵循原仓库权限。网页演示是公式与概率结构的可视化，不是新实验。上一版R85阅读报告保留于网站归档。</p>
<p class="web-only"><a class="content-link" href="archive/HashJoin-R85-20261031.pdf">阅读上一版R85历史快照 ↗</a></p>'''))
assert len(pages)==20
