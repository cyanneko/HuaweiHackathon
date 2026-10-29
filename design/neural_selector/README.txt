第20题：8专家 + 微型神经网络选择器（2026-10-29最终本地验证）

交付与推荐
  ../MySpillScheduler_neural.cpp：32→16→8网络，664个float32参数，2656字节权重。
  默认构造启用网络，每次需选盘时输出专家ID，只执行一个专家；单文件C++14，无外部推理运行时。
  首轮权重 + 旧策略ID7偏置0.5 + O(2^n)等价枚举优化。
  model_dagger_16.json为已完成验证但未采用的第二轮候选。
  综合不同集合表现，旧推荐 ../MySpillScheduler_final.cpp继续作为默认。

使用与复现
  python design/tools/run.py --policy neural --input <输入文件.txt>
  python design/neural_selector/verify.py
  python design/neural_selector/replay_fresh.py
  python design/neural_selector/benchmark.py --manifest design/neural_selector/fresh_manifest.json --output design/neural_selector/results/replay.json
  benchmark.py默认比较网络(-1)、固定专家4、旧版(8)、Naive(9)，每配置3次。
  --split valid可筛选data_manifest.json；原始开发输入未打包，读取位置及哈希见清单。
  新测试可从记录的熵精确重建；已重建核对378个输入哈希。
  正式运行仅需C++14标准库；训练依赖Python3与NumPy。

训练
  python design/neural_selector/train.py fit
  python design/neural_selector/train.py fit dagger
  python design/neural_selector/deploy.py model_16.json 0.5
  train.py export同样调用deploy.py，只有一套导出逻辑；输出本目录generated.cpp。
  训练会覆盖相应model JSON，请自行保留要研究的旧权重；不会自动替换已评分交付源码。
  NumPy/硬件不同可能产生浮点差异；已提供冻结模型、模板与字节一致源码。

数据及标签
  首轮15,255状态，验证3,889状态；第二轮追加10,575，合计25,830。
  原始输入为600本地训练 + GitHub datasets分支8 train；150本地验证；8 GitHub eval。
  首轮GitHub训练状态196，第二轮追加138；eval不进入训练。
  同一规范化操作流不得跨训练/验证，分组与源哈希见data_manifest.json。
  GitHub固定版本96f3e2da7954756d9346b4c45d375c018792530c；8 eval均有历史开发暴露，属于回归集。
  NPZ无pickle：features[32]、costs[8]、输入SHA、source、pos/kind/end、decision_us、misses。
  特征只含可见状态与自身历史；真实p和较长未来仅用于离线教师标签。
  采样点让8专家各执行首个动作，再用共同策略向后推进，比较增量IO + p*miss + 决策CPU。
  默认384步；BUILD可延伸至SWITCH后128步，最多2048步；这是带测量噪声的有限窗口近似。
  第一轮标签的枚举实现O(n*2^n)，第二轮及最终部署O(2^n)，不得把标签当全局最优真值。

最终完整Score测试（比值相对旧版，越低越好）
  调参验证150例：网络几何均值0.952349，最差1.473824；固定4为0.952598/12.606436。
  新测试378例：377例基线Score>0参与比值，网络0.975361，最差2.241042；固定4为0.994863/7858.035861。
  GitHub回归8例：网络1.056779，最差1.281646；固定4为0.910727/5.252595。
  规模诊断6例（含3个500万操作）：网络1.012914，最差1.025815；固定4为0.943746/1.070063。
  每配置3次，逐例取Score中位数，再取相对旧版比值几何均值；不是官方跨样例汇总公式。
  最终四组共6054条SDK记录，计时包含真实状态获取、特征扫描、网络与专家执行。
  新测试在冻结代码后用OS熵生成；10个与历史开发操作流重复的模板被排除；未据此继续调参。
  第二轮验证0.961323、最差1.605629，劣于首轮，未采用。
  原始无偏置网络曾38.31倍退化，历史结果见sweep_summary.json，不隐藏反例。
  CPU中位数之和（us）：验证网络44692.34/旧33270.01，新测试271365.87/旧233970.11；规模5615801.25/旧4768257.50。
  网络并非在所有集合上更优，旧版继续默认；本地自建分布不是官方隐藏分布，没有全输入最优保证。

正确性核查
  action_audit.json：独立模拟器核查1150个网络输入；542例IO/hit/miss与SDK一致。
  8个固定专家各通过150例合法性检查；固定7与旧版IO/miss一致。
  150例优化前后动作哈希一致，3000组小实例的子集和/最优掩码一致。
  verify.py核查导出字节、标签哈希、划分隔离、冻结记录与6054条Score算术。
  独立核查：g++ -std=c++14 -O2 design/neural_selector/audit.cpp -o audit
  ./audit paths.txt audit.jsonl -1（paths.txt每行一个输入绝对路径；0..7检查固定专家）
  离线标注：g++ -std=c++14 -O2 design/neural_selector/teacher.cpp -o teacher
  ./teacher paths.txt labels.jsonl 24 -2 7

文档与证据
  catalog.json：8方法及原始来源、数学保证边界。
  results.json：最终版本、四组评分与第二轮取舍；action_audit.json与verification.json：核查摘要。
  *_final_runs.jsonl及optimized_valid_runs.jsonl：最终SDK记录；同名summary为汇总。
  validation_runs/summary、sweep_summary：优化前历史证据，不混用CPU批次。
  ../topic20_neural_selector_report.pdf：9页中文说明、创新点、完整结果与复现。
  截图、原始批量输入、缓存和编译产物保留本地；关键源码、标签包、来源与证据纳入源码交付。
