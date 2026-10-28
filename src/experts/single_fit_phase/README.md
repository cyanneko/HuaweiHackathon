# single_fit_phase · ID103 v1 适配

唯一命名空间 `cyanneko_single_fit_phase_v1`，无状态纯const提案。原R56提交以 [reference.cpp](reference.cpp) 保留原字节；[manifest](manifest.json)记录源与BF依赖SHA。旧R56文件、BF/NG实现和默认101/102组合不改。

缺口存在时，在BUILD/PROBE分别保留最小足够分区代表，并维护排除next的safe代表。有safe单项才优先safe，否则从all选择；PROBE代理系数仍为 `1+W/R`，不是实际未来成本或隐藏miss_penalty。all两个阶段均无单项覆盖时，仅调用已发布无状态BF的 `decide(ctx,out)`，保留完整动态缺口与多victim/tie/最终LOAD。

内部BF是103的算法分支，不新增注册实例、不重复observe/onDispatch、不改变外层selected_id103；与路由非法ID回退101不同。若BF未来变成有状态，必须重新审阅该复用方式。`decide`自行clear；空periodic保持不变，不增加预取或计时器。

`standalone.cpp`仅定义MySpillScheduler外壳，需接官方兼容框架；正式导出仍一个cpp，无main/engine。固定101+103仅有[测试夹具](../tests/fixtures/bf_single_fit_pair.cpp)，不代表三专家路由或训练树。

## 动作与导出验收

```sh
python -B src/experts/tests/run_single_fit_tests.py --out build/single-fit-contracts --max-seconds 30
```

需Python3.10+和同环境g++，输出目录须不存在。直接与展开导出分别通过1039个字面状态、96次短轨迹回调，覆盖独立/固定/交替、safe单项与safe多项之别、BF残余缺口、浮点tie、1×2/8×64/4GiB、零大小、目标排除和内部BF通知计数。参见 [validation.json](validation.json)。这是受控类型夹具和短轨迹，不是完整官方全流动作审计。

先创建目标父目录，再导出到新文件：

```sh
python -B expert_runtime/export.py --entry src/experts/single_fit_phase/standalone.cpp --out build/single_fit_submission.cpp
```

本次没有测量ID103的正式Total_Decision_Time、得分或墙时。R56/R57原直接类的结果不得继承为适配版时延；空钩子和内部委托也不先验称零成本。`performance_validated=false`，后续须在新的独占窗口分别测独立103与固定双专家外壳。
