# R78新scale单fit评估：已完成

当前结果：24/24 完成，独立重解析 PASS，CPU 已释放。详见 REPORT.md、report.json、per_case.csv、independent_checks.json。下面保留执行接口说明；prepared_status.json 是早先未绑定时的准备快照，当前完成状态以 report.json 为准。

runner已参数化，已绑定数据agent的`tmp/r78_scale_data/data_manifest.json`并在Root授权的 fast-ledger 释放后窗口执行。未生成数据、编译或重跑stage0。

两步分别调用：

```text
python tmp/r78_scale_singlefit_eval/runner.py prepare --manifest tmp/r78_scale_data/data_manifest.json
python tmp/r78_scale_singlefit_eval/runner.py run --cpu-window-released
```

第二行仅在Root授权的新窗口执行；开关不替代窗口授权。Windows可完成prepare，Linux运行使用同脚本和相应/mnt/e绝对路径。路径字段支持manifest的Windows/Linux绝对路径转换。

prepare核验8个显式TRAIN、各100000操作、K8/P64/M64MiB/B127、4机制同seed压力3/12配对；输入与metadata SHA实际核验，计数Probe与penalty来自metadata。加载原版R75发布身份与冻结producer两变体，核验原始source/TU/binary SHA；仅在比较framework文本时统一CRLF为LF。prepare不会启动二进制，成功后才写selection.json冻结24格，拒绝覆盖。

run再次核验全部冻结SHA，按case→3方法串行，全部native进程共享60秒deadline；超时停止并保留已完成格、原始stdout/stderr和partial.json，不补跑、不换数据。结束即写cpu_released.json；只有24格全成功、计数账本合法且冻结产物未改变才汇总。

主指标为物理IO+真实penalty×miss相对同轮R75的倍率，保留负改善；无Naive所以不生成归一得分。输出全部逐例、all8及pressure3/12的mean/P50/P90/worst/best、胜负平。D累计值/含D TotalCost/wall仅非正式记录，不视为正式性能计时。

产物：selection.json、logs/、partial.json、report.json、per_case.csv、cpu_released.json，以及独立复核脚本和结果。两个纯函数测试覆盖真实penalty/D分离及分组/负改善；执行后的独立复核也已通过。
