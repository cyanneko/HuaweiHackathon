# Round9 pure 交接（2026-10-30）

## 最新状态（优先于以下历史阶段）

纯dyna阶段最终冻结已完成：`DYNA_FULL12_PURE_FINAL_FREEZE_V1.json`（7个闭合文件）SHA `930a36453625e5b5a1a3259bddb3254e5c307e8f3e9cac29f92ee1678f1bb5e8`。发布清单为该freeze内7文件＋freeze本身＋本HANDOFF快照；coscale准备文件和main60准备文件留下一阶段，不冒称已执行。当前无运行子任务，等待root本轮发布和下一阶段明确启动。

根runner已确认session28924 exit0，dyna12/72/216全部完整。纯全12报告与根SUMMARY现已完成独立372项数值核对（身份/计数精确一致），`DYNA_FULL12_PURE_ROOT_CONSISTENCY_V1.json` passed；无新增solver/输入重放。root最新顺序指令覆盖先前自动续接许可：**先完成本次完整dyna报告/冻结/发布；coscale和主60均暂不执行，等待root随后明确阶段启动**。当前没有本子agent运行命令；cell277已正常结束。下一条动作是交纯报告最终freeze与发布清单，不执行preflight、prepare或runner。

dyna矩阵完整12/12、72审核/216计时，根status complete。`DYNA_FULL12_PURE_REVIEW_V1.json/.md`已生成：pool/flat/global等权物理比0.980570026/0.988519323/1.002342537，分别12好/12好/7好5坏；均分对paired差+0.073689111/+0.046461253/−0.004560869；三BUILD全同，最大wall31.08/25.46/27.77秒，无>60。root SUMMARY尚未落盘时 `verify_dyna_pure_vs_root_v1.py`只做静态准备，待其生成再核对/最终冻结，不能称此一致性已完成。global总模拟I/O减少约1093.56秒但等权指标变差，明确区分总量与等权口径。coscale与主60仍未启动；前者完整报告优先后可按已批preflight执行，后者须root另明确启动。

只读监督cell277已正常结束（monitor_finished=true，completed_cases_seen=11）；没有重启它或任何solver。最后已核对root11/12、68/72审核、198/216计时，进入最后holdout12；后续直接低频读最后status/canonical JSON即可。正式pure报告生成脚本尚未运行，coscale与主60均未启动；主60仍需root内部启动凭证。

dyna已完整9/12、55/72审核、162/216计时，进入holdout10。实时反事实记录（仅描述，不调参）：dev09 global少1,049次Miss，但PROBE写/读各多44,531,820/55,667,821μs，物理比1.000401；pool少1,972次Miss、物理比0.999854，反而费用改善少于flat仅少75次Miss、物理比0.999668。再次说明Miss数量不能替代按对象字节核算的周转成本。九例三风险BUILD分项均同paired；全12汇总仍未生成。

root已静态审过main60 prepare/runner/summary并核对旧reference字段；唯一要求的零值score口径已修成与官方一致（VAL或BASE为0记0），仅py_compile，无执行。现dyna完整7/12、48/72审核、141/216计时（dev08最后一轮）；第7例三风险物理比0.972565/0.988652/0.997945，BUILD仍同，未见>60秒。新增 `write_dyna_full12_pure_review_v1.py` 已写并语法检查，只能在完整review JSON存在后渲染正式报告；目前正式全12报告/结果均未生成。

root确认主60采用5方法同窗口900计时，已授权等待窗口仅实现。`RETURN_RISK_MAIN60_PLAN_V1.json`、prepare/runner/summary三脚本现已写，语法检查通过；prepare和runner均未执行，无新编译/solver。直接绑定现dyna五方法源码/二进制/生成源码SHA与原60顺序/seed，新增180审核+900计时。runner额外要求root在根写启动凭证 `RETURN_RISK_MAIN60_START_AUTHORIZATION_V1.json`，绑定本阶段freeze、已完成dyna结果/最终报告SHA；当前没有该凭证，也没有本阶段execution freeze。不得因dyna自动complete就自行启动主60。

根dyna已完整6/12（六条train全部完成）、39/72审核、108/216计时，现进入dev07。本路线仅核对完成case JSON；前六例三风险版BUILD分项均同paired100，没有>60秒的未插桩运行。未据半面板给总体均值/排名或调参；全12的dev/holdout仅按用户明确授权做这次固定候选描述性终检。`functions.exec` cell277仍显示running，低频监督无solver；coscale仍未执行。

按root新要求已准备 `RETURN_RISK_MAIN60_CLOSED_LOOP_PLAN_V1.md` 一页提案：固定三份现有风险源码、原100-only主60流/顺序/seed，复用180参考审核，建议新增180候选审核与同窗口5方法×3×60=900计时。三候选分别使用mean physical≤.995、worst≤1.02、含决策均分不低于paired三门槛；历史参考计时不足以确认第三门槛。不据dyna选样/改参，无runner/实验启动；执行待本次dyna完整报告后root统一冻结。

续接实查root矩阵已完整4/12、27/72审核、72/216计时，正在train05；本子agent没有solver。唯一global未截顶 `U→gU` 的coscale合同/实现已准备冻结，BUILD_FREEZE SHA `0e2e87d75509cd1cb9dca20675adecd2abe16b1525246a9a82d8b11cfecf6f29`，尚未执行。root补充要求已纳入独立 `preflight_risk_coscale_v1.py`：dyna完整12/72/216后先核对旧scale BUILD_FREEZE SHA及其全部依赖（含metrics）、新freeze全files，落 `RETURN_RISK_COSCALE_PREFLIGHT_V1.json` 再运行原runner。此补证不修改任何冻结件、不重跑旧实验。下一优先事项仍是完整dyna监督与pure正式报告；只有dyna完成后才可逐case公共锁运行原12train纯Python归因，无solver/teacher/新候选。

低频只读监督工具正在运行：`functions.exec` cell277，每45秒只读小status/canonical JSON，不持实验锁、无solver；应使用 `functions.wait(cell_id="277")` 查看续接，不能将其误作根solver句柄。最近完整2/12：train01 pool/flat/scale物理比0.935790/0.960227/1.025068，train02为0.981108/0.986613/0.999793；只个案、不汇总。所有三风险BUILD分项暂同paired，CPU均增加；root元数据已明确全12 rare_hot在train01与holdout12、rare_cold在dev07，profile/period/pressure非正交，不作漂移速度因果归因。

追加静态任务已完成 `RETURN_RISK_UNCERTAINTY_REVIEW_V1.md`：当前只换均值保留U_p是有意单因素隔离，绝非95%保证；分析global条件缩放、比值不确定性、非归一h与类别协方差/选择偏差。补核Howard2021和Chugg/Ramdas2025原文。仅提出原12train共同状态的唯一global风险共缩放归因，未执行、无新候选；当前dyna源码/根freeze不变。

主agent已启动用户要求的 dyna 全12×6正式比较（根runner session28924，execution freeze `7871de549e198358f014fad60bcb5aeabf0f2a0cf5403009df6a0e501972406d`）。纯路线当前只读监督 `level1/build/round9/dyna_full_v1` 已完成case JSON，观察三风险版对paired100的分项与异常；不占实验锁、不重算输入/轨迹、不启动solver、不改候选或根freeze。用户已明确授权本次全12(train6/dev3/holdout3)描述性终检，不能把此前禁止新dev/eval优化的规则误读为阻止本次已冻结比较。仍不得据本次结果调参或重新刷保留集；全部12完成后写 `DYNA_FULL12_PURE_REVIEW_V1.md`。本子agent当前无自有solver进程。

三风险闭环候选部署核查32/32已完成，exec22208 exit0，无运行任务：17同轨迹+15小协议闭环，全部100，参考重跑0/dyna运行0。D/Z在1,115,718次核对差0，pool/flat在183,276pair均值差0且选择全同；C++global与独立Python选择全同，future最大绝对差1.862645149e-9 μs、归一化1.487799343e-12。风险内核固定8,768B。`RETURN_RISK_DEPLOY_REVIEW_V1.md`与静态逆变换审核已完成，三生产源SHA保持freeze原值，可交主agent全12面板；未晋升。限制：15协议闭环均与参考同轨迹，分歧后长期轨迹未由这些小例覆盖，报告已明确；真实after接口确实接收实际选中动作。14文件最终 `RETURN_RISK_DEPLOY_FINAL_FREEZE_V1.json` SHA `f36a53703d2172605f9832c0d6fb53f07f1dd602c6c6d7085e9011d93afb1143` 已完成并交主agent，仅等统一评测，不追加solver/改源。

部署核查freeze已完成，SHA `a032da79d0cbb403795d5da68100e0be1e977f58c9be6d6a87b15534a329c1d6`；实际runner exec22208已启动，公共锁编译并运行32次必要核查。状态文件 `level1/build/round9_pure_return_risk_deploy_v1/status.json`；续接先查现有句柄和状态，不重复运行已完成案例。dyna solver仍由主agent负责，本子任务新增dyna运行0。

当前任务已转为 return-risk 三闭环候选部署核查：用户要求主agent统一全12 dyna测试，纯线只交3个固定100源码和正确性证据，不自行跑dyna。`RETURN_RISK_DEPLOY_CONTRACT_V1.md`已落盘；三候选 pooling/no_pooling/global_scale100_v1 已生成，仅替换原paired两proposal的比较未来均值，原risk/next/BUILD/prefetch不变，after跟随实际动作更新驻留风险账。去logloss/真实等待诊断/输出，保留合法q决定的原稀疏sync以保持浮点顺序。Python语法通过，当前exec55131正在freeze（绑定原12训练+5协议与已完成参考），solver尚未启动、0/32。之后授权运行17同轨迹核查+3候选×5小协议=32次，全100、不复跑参考、不读dyna成绩；完成前不称部署核查通过。

冷 BUILD 单因素60/60完整结束，session34890 exit0；60新audit+180timed全部通过，参考solver新增0。34条R<W完整TRACE全同，26条首次分歧全部同状态q0 overflow。物理比均值1.003365788、最坏1.209434612，含决策均分3.744279205 vs父3.744318216，三个收益门槛全部未过，停止晋升、不进dev、不调规则。正式 `COLD_BUILD_REVIEW_V1.md`、独立 `COLD_BUILD_INDEPENDENT_REVIEW_V1.json` 与17文件 `COLD_BUILD_FINAL_FREEZE_V1.json` 已完成；旧五闭合freeze全保持。当前无运行solver/审核；原已完成candidate/报告冻结，下一条行动为交主agent审阅/统一发布，不自动重跑或继续调gate。

关键反事实：train600初盘81→2、初始驻留431→510、空闲83,956→21,586,052 B，却Miss690→812、物理+20.943%；clipped score两版均0，平均分掩盖尾部。全部流BUILD少写409,122μs，但PROBE写+8,601,133、读+3,791,959、Miss+914,357。不能继续把“最大对象保留更多小分区/空闲”当当前PROBE策略的充分收益机制。只有这项gate被否决，不泛化为所有BUILD增长/保留机制都无效。

冷 BUILD 已冻结并启动：候选 SHA `fa0ce16292ad19afbcd2f0bc7538e46e1a95e0e9061da3d6defaebaedf6887b8`；BUILD_FREEZE SHA `66524a52901c06b67b0e6862828d5c7663ec277a7da42df767c61af5feac027b`。prepare exit0，60成功参考日志/输入/源绑定、旧闭合freezes复核通过；实际exec session34890，命令 `python src/Vanius0525/level1/round9/pure/run_cold_build_v1.py`，逐case公共锁，状态位于 `level1/build/round9_pure_cold_build_v1/status.json`。当前仅启动，尚无完整结果；续接先查该句柄/状态，不重启已完成case。

主agent已进一步授权唯一冷 BUILD after_probe100 实测；早先“暂不新solver”已被本次具体授权取代。`COLD_BUILD_CONTRACT_V1.md` 规定只删除 top4 条件中的 R≥W，使 q=0 回退原有含 next 保护的最大对象顺序；其余源码字节保持。原 root60 train 全部复用 paired100 成功参考，仅新增60候选全动作/字节审核+180未插桩计时，公共锁逐case。34条R<W必须完整TRACE相同；其他首次差异必须起于q0 overflow。晋升到主agent dev审阅须同时满足物理比均值≤0.995、最坏≤1.02、含决策均分不低于paired100；未过停止此候选，不改阈值。合同/脚本已落盘，当前尚未编译或启动solver，下一条执行prepare冻结再run；成功参考train758用attempt1，不复跑旧1/基线/dev/eval。

BUILD只读核查已完成：`BUILD_HISTORY_REVIEW_V1.md`明确Round4 after_probe已做过同类gate，非新机制；未定位当前paired100的同骨架单因素结果。`BUILD_EXISTING_BASELINE_DIAG_V1.json`复核60既有审核：26条R≥W的BUILD写量对Naive为16少/10多，34条R<W全同；AI100全部60相同。paired直接BUILD汇总占0.0491%，不能拿它约束末态驻留对后续PROBE的影响。q0已有PROBE-phase时subset loss包含均匀prior，不能无条件叫纯最小写量。此只读分析公共锁执行exit0，新增solver=0。

缩放归因 12/12 完整结束，session1052 exit0，原三模型/全部 pair 复核、原14文件保持。正式 `RETURN_RISK_SCALE_REVIEW_V1.md` 与 12文件 FINAL_FREEZE 完成。global-scale 流均 log loss −1.3319%，与pool/flat接近，6/12胜pool、7/12胜flat；却仅复现8.76%/8.30%的pool/flat动作改变。尚无稳定逐分区预测优势或动作收益证据，不晋升、不继续加热度模型。所有新solver为0、无运行进程。

主agent已安排AI执行24seed共同状态/两原动作/两teacher及4096/8192续接，故纯线不重复新rollout/集合诊断。下一授权转为只读BUILD研究：核查最大对象/增长份额/最终保留集合是否已有可信同骨架负结果，复用root60成本分项定位机会；比较原BUILD和官方Naive最大对象写法，设计保持PROBE paired100完全不变、只改BUILD的一个最小对照。暂不新solver、dev/eval或训练，不改变已完成冻结件。

唯一 past-only 全局缩放离线归因已获批，`RETURN_RISK_SCALE_CONTRACT_V1.md` 和 6 文件实现冻结，BUILD_FREEZE SHA `bb937a4fa474f4cf2c37db1bfbcdb4c8dd7725a3d945b5d46a052aad60b5ddfe`。原 14 文件全不变，原 12 输入/observer stderr 已绑定。当前命令 `python src/Vanius0525/level1/round9/pure/run_return_risk_scale_v1.py` 已启动，按 case 公共锁纯 Python 重放；新增 solver=0。逐一重新核对原三模型，新增 g=(1+ΣD)/(1+ΣZ) 的事前评分与共同状态交集/受害者数/超额释放。不把离线耗时当独占性能（root提示可能存在 Git maintenance）。

Return-risk 正式报告 `RETURN_RISK_REVIEW_V1.md`、汇总及 14 文件最终冻结均完成，FINAL_FREEZE SHA `4ab35b60c41a798da968491feb9a2997f945b3441b9e274c9274fe76d5a9f5a9`。pooling 10/12 流比 no-pooling 差；改变的 15,151 个影子决定中 10,398 当前更多写，4,753 更少写，不能提前解释为“只是少写”。当前无 solver/审核进程。已提出 `RETURN_RISK_SCALE_PLAN_V1.md`：复用原 12 流完整合法轨迹，新增唯一 past-only 全局 g=(1+ΣD)/(1+ΣZ) 缩放，先审阅再离线复算，不新 solver、不闭环、不扫温度。

Return-risk 100 影子完成，session 37609 exit0：12 train + 5 协议共 22 新 100 solver，复用 12 训练基线，全 TRACE/精确字节/独立两本账/全部 pair 比较/序贯评分通过。train 共 1,477,503 PROBE，307,328 pressure、183,238 不同 pair，pooling 改变影子选择 15,151（8.27% pair / 4.93% pressure）。流均相对 log loss：pooling −1.408%（8好/4坏），no-pooling −1.442%（9好/3坏）；无无限 loss。但 pooling 的 event 分项在 11/12 流更差，改善来自多数 non-event 项，算子池化也未稳定胜过无池化。不能将其叫更好保护热点或闭环收益。正在写正式分解/停止建议，当前无运行 solver。固定对象 20,440 B，总统计 CPU 6.293 秒、wall 8.314 秒；总 h 最大 1.601，明确不是归一化 p。

Return-risk 100 影子已获主agent授权，执行合同 `RETURN_RISK_CONTRACT_V1.md` 和 12 train 选择 `RETURN_RISK_PLAN_V1.json` 已冻结。BUILD_FREEZE_V1 SHA `16b830a0873e040f15386eabd3dc56f7264eb5c44fab076ed65f04e9cf1d0cbd` 绑定 9 文件、12 已完成 paired100 参考和 5 旧协议小例。Python 语法通过。当前执行 `python src/Vanius0525/level1/round9/pure/run_return_risk_v1.py`，session 37609：共享锁编译，接着 5 小例（100参考+observer）与 12 train observer，共 22 新 100 solver；训练基线复用，不改动作。尚无运行结果，不把启动称通过。输出目录 `level1/build/round9_pure_return_risk_v1`。

驱逐重访风险研究已落盘 `EVICTION_RETURN_RISK_DESIGN_V1.md` 与 `EVICTION_RETURN_RISK_RESEARCH_V1.md`，目前仅设计、未执行：分真实等待账/未知请求风险账；已透露 next 位置对所有对象一致排除随机暴露，避免前视选择混杂，B1 回退 next；未返回持续贡献暴露，预取另记已知返回。一个固定 2048 半衰期、伪计数 1 的算子/分区相对 next 校准，先保持 paired100 两 proposal 完全固定。h 不称全局 p、不强行归一化，旧 risk/n_eff 不称新估计置信保证。等待主agent审阅并另冻最小影子合同；没有新 solver 或运行任务。

补充 `EVICTION_RETURN_RISK_BOUNDARIES_V1.md` 已列明未知区间 U 的精确去重式、稀疏回调的指数权重积分、初始在盘/首回调不回填、预取确认与 EOF 边界、触顶 h=1 的无限 log loss必须显式报告。它是静态核对，不是已通过的执行测试。

有界匿名Hit原型已完整收尾：22次官方旧paired影子（session55782 exit0）及无调度器/无penalty的独立最大规模内核（session23961 exit0）均完成，没有运行任务。旧1求解器不再启动；后续统一100必须另冻合同。BOUNDED_HIT_REVIEW_V1记录合法性/数值通过、52,584字节固定状态，以及窗口/刷新差距和CPU风险，未部署、未宣称收益。下一授权仅调研/设计驱逐重访周转风险：保留右删失与预取已知重访，算子/分区收缩，不solver、不扩池、不改BUILD。

## 原始目标与所有权

主agent授权继续有限next共同状态的第一阶段诊断。唯一写入round9/pure及本路线忽略build目录；round8/pure冻结，不读本次final50及fresh逐例调参，不写round9根目录，不commit/push。

## 本阶段范围

预先按训练V2的family/关系/seed选择约8条流，不按旧成绩选择。从冻结paired参考策略获得合法共同状态，记录next驻留且单独覆盖缺口的机会、相对原动作的当前写差、真实下一请求的读/写/Miss、两步终态差。必须对齐原始请求位置并计入真实periodic/预取；先证明observer不改变参考动作。只评估机会和两步非支配性，不宣称整流收益、不叠cross-fitting或其他池扩容。

## 当前状态

已读取Round9根交接、V2数据契约、仓库约定与模拟器协议。原8流PLAN.json/BUILD_FREEZE.json在任何solver运行前冻结；仅Python语法检查已通过。用户随后排除uniform-independent性能探索，因此保留原冻结件，新增PLAN_V2.json/run_diagnostic_v2.py/BUILD_FREEZE_V2.json：只移除原选定的2条uniform，保留6条skew（zipf/hotspot/lognormal各2条，含3条1M与3条250k，共3.75M PROBE），不根据结果重选。每流128个固定RNG reservoir共同状态；完整observer/reference TRACE等价、模拟器reference TRACE等价、真实两请求及periodic的独立Python记账。所有solver/重计算持公共experiment_lock，逐case释放。

## 运行任务

本阶段已完成，exec session 23005正常exit0，无本路线运行命令或服务；从未启动小时服务。完整输出 `RESULTS_V2.json`，正式解释 `REVIEW_V2.md`，机器汇总 `SUMMARY_V2.json`。

## 已验证结果与停止决定

6条skew共3.75M PROBE；12官方运行+6模拟器全流、1536分支独立审计全部通过，observer和simulator参考TRACE全等。全量pressure 782,996，eligible 353,124；每流固定抽128，总768且实际动作都不同。265当前少写中255被下一请求周转反转；只有10例两步便宜，全部hotspot-negative且终态不同。758更贵；557同终态全贵；6流平均差全正。44真实periodic边界样本已计入且两支对应动作相同。详见报告的逐流分母、成本分项与限制。原v1未运行；uniform/dev/fresh/eval访问0。

主agent收到结果后决定停止有限next第一阶段，不进入大续接/新候选。本结果不证明无限保护最优，也不用于选阈值。接下来的授权工作是先给出概率加权冷对象周转预算的一页研究设计，说明与旧core负结果的差别、静态模型及停止条件；不直接扫配置，不重复AI的匿名Hit统计实现，不使用正在更新但未冻结的2.1数据。

## Open Ideas / 值得深挖的问题

2026-10-30：初始周转余量与后续策略可能存在不匹配。单因素cold-BUILD实测train600保留510而非431分区、空闲多21.5MB，却Miss+122、物理+20.943%；这否定“初始多留分区即稳定驻留”的直接推论。下一最小验证应复用AI已经冻结的集合终态/双teacher续接，分清空闲被后续决策消耗还是特定热点被牺牲，不另造重复rollout或由单例调gate。尚无新颖性判断，不称独立论文结论。

2026-10-30：正确评分的总 log loss 改善也可能主要是整体风险尺度校准，而没有更好区分最昂贵的返回对象。触发：return-risk 12train 中 pooling 总 loss 8好/4坏，但真实返回 event 分项 11/12 更差；一条 −5.39% 总误差改善的流原池没有不同 pair。最小后续验证应固定历史/候选，加入单个预定全局尺度对照并分解判别排序与尺度，先不做大闭环或增加层次模型。尚未检查原始文献的新颖性，不宣称独立立项价值。

2026-10-30：带 next 前视的缓存反馈产生“预测目标改变自身观测窗口”的依赖。触发为 paired 对 next 的强保护：即使 IID，被驱逐对象首步也常必然不返回。潜在科研问题是短前视下如何区分直接需求分布与策略条件周转风险；最小验证是已知位置全局排除、B1 零未知暴露、固定动作轨迹上的序贯校准对照。已有 refault/hazard 文献，尚未确认独立新颖性，不宣称顶会价值或已发现收益。

有限next保护的局部机会是否来自真实周转节省，还是截断末尾驻留差制造的表象？触发：Round8静态证明q_next在原1e12保护下恒0，并有合法两步代价反例；尚无一般随机机会频率证据。最小验证即本阶段共同状态、完整两步记账与终态比较（2026-10-30）。

## 计划与实现冻结

原v1未执行，故无uniform实验结果需要停止。v2仅改运行范围与输出文件名；paired源码及C++诊断逻辑不变。下一条命令：`python src/Vanius0525/level1/round9/pure/run_diagnostic_v2.py`。本阶段不实现新候选，不读取fresh/eval，不启动第二阶段。

## 下一条可执行动作

核查旧core配置/负结果及研究原始文献，形成`TURNOVER_BUDGET_DESIGN.md`；主agent审阅后再冻结共同状态小诊断。当前没有新solver启动计划。

## 软核心研究状态（2026-10-30，尚无新实验）

已核查并纠正历史前提：Round7最初无权中位数后来已被core50/core90替换为冷请求概率加权分位数；修正48训练矩阵仍负（0.921009/0.922332 vs linear64 0.917648）。主agent确认撤回“加权预算是新delta”。Round8 paired的refreshCore未调用，不能把死代码当现行核心。

已完成一页 `TURNOVER_BUDGET_DESIGN.md` 与原始文献/静态模型 `TURNOVER_BUDGET_RESEARCH.md`，覆盖2026随机加权强制准入、AdaptSize/LHD、2026变大小策略、DuckDB论文、Velox/Oracle官方经验。当前无新solver或训练；等待主agent审阅机制增量后再冻小诊断。发现一次full-M冷尾分位数经M−b重新装填后不一定覆盖最终冷集合；四对象静态例子使名义50%预算对应最终冷尾96.8%超大质量。此例不代表真实分布收益，也不证明自洽预算更优。

## Open Ideas / 值得深挖的问题（补充）

- 2026-10-30：概率加权周转预算的冷集合是内生的。触发为旧core50源码先定义T0、取分位数、再改变核心，静态四对象例子产生T1≠T0与覆盖失配。最小验证是相同paired热度/状态的影子core50中统计最终冷尾超大质量与真实核心破坏；如果失配少或成本小就停止。已有容量耦合缓存文献，未确认新颖性，不宣称顶会idea。
- 2026-10-30：固定核心＋单冷buffer在IID下的精确费用包含自命中因子1−p_j/Pcold；逐访问p×读写代理忽略这一集合耦合。最小验证是4–6对象可枚举Markov状态、固定p隔离估计误差，检查核心恢复的额外写是否改变旧评分排序。仅受限静态模型，不代表实际策略收益；不与AI匿名Hit估计并行重复实现。

## 新授权：core50影子诊断（2026-10-30）

主agent已审阅一页设计并授权只执行第1项最小影子诊断，以及单buffer静态/小枚举核对；不进入大续接或新候选。`CORE_SHADOW_PLAN_V1.json`在编写实现/运行前冻结：仍为原6 skew、3.75M PROBE；完整paired轨迹、同一合法next热度；q=.5、原门槛及惯性不扫参。每个full-PROBE压力Miss刷新一次独立假想core，统计全分母及实际paired动作对假想core的破坏；这不是真实已保护core，也不是原累计热度core50复跑。随机抽128全部pressure状态做独立重建，不使用旧next-eligible样本。当前新solver未启动。

## Core50影子已验证结果（2026-10-30）

782,996压力Miss中776,058影子激活；名义预算失配360,544，实际装填余量失配61,532，6流等权条件失配率6.33%。真实paired动作spill假想core97,641次，但保留next时容量强迫仅781；其余是价值选择差异，不能叫可省成本。预算失配状态中的core写仅占所有pressure写量约1.29%，不构成未来收益上界，也没有稳定因果关联证据。zipf-negative因共同paired衰减sample_mass与旧64门槛，仅106/6,775激活；不能混为原累计core50行为，不调门槛。

单buffer4个有理数案例精确状态枚举与公式一致，证明受限模型自命中折扣，不证明真实策略收益。建议本次观察阶段停止，不直接修预算/加保护；后续若研究集合周转排名，必须另冻计划。所有原有限next冻结文件待最终hash复核。

最终复核：有限next原15文件与core影子BUILD_FREEZE全部hash一致；新增CORE_SHADOW_FINAL_FREEZE_V1绑定12个完成产物。无未完成运行。

匿名Hit原型首次运行前amendment：加入同256完整区间+live next、同64先验的next-only归因对照；保留next/Miss-only合法来源标签。输出真实PROBE跨度与各类因子数，fresh/fitted时刻分别对齐，避免历史长度或刷新频率混杂。原计划与参数不改，首次solver仍未启动。

匿名Hit实现已冻结BOUNDED_HIT_BUILD_FREEZE_V1。已启动`python src/Vanius0525/level1/round9/pure/run_bounded_hit_v1.py`，exec session55782，公共锁先编译/跑5个官方合法边界输入，再原6 skew，共22基线/影子执行。py_compile通过；状态目录level1/build/round9_pure_bounded_hit_v1。原paired罚值代理仍1，后续用户100决定由主agent单因素处理，不插入本实验。

## 有界匿名Hit最终事实（2026-10-30）

5合法边界+6旧skew、22官方基线/observer运行、3.75M PROBE全部TRACE与字节审核通过。全流观测计数/区间、24数值前缀均独立重建，同窗next-only归因参照保留。真正预取后已知Hit3,135次在完整训练流覆盖。固定状态52,584字节；256区间实际跨度最高34,695 PROBE，不能叫256请求。

4096附近fresh bounded vs full16平均TV .149031、最坏.303998；cached vs fresh平均.214392、最坏.448307。这些是估计间距离，不是预测错误/收益。Zipf负相关1M统计CPU3.501秒，约为旧参考物理时间1.855倍，开销风险不能忽略。独立纯内核近5M请求3重复CPU中位：B1 .397343秒；B17 8.299342秒，无scheduler/penalty、不能继承为100闭环证据。原参数与旧诊断不再改，后续候选需新协议。

有界原型18文件已绑定BOUNDED_HIT_FINAL_FREEZE_V1，先前有限next/core冻结hash及本次两个build freeze全部一致。无运行任务。
