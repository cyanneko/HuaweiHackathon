# BUILD 单轮实验交接

唯一 attempt 已完成，900 秒预算内实际耗时 487.937408039 秒，controller exit0，CPU RELEASED，active_child_processes=0。dyna 36/36 与 stat 30/30 全部有效；没有失败、timeout、重试、调参或晋级。原846格消融保持 HOLD，未运行。

| 数据套 | 官方 Naive 分数 | 最终 Full 分数 | BuildBestFit 分数 | 相对 Full 分差 |
|---|---:|---:|---:|---:|
| dyna1.0 全12 | 0 | 4.455852988527042 | 4.4549088478195955 | -0.0009441407074458619 |
| stat1.0 eval10 | 0 | 3.439749404787465 | 3.445074879979142 | +0.005325475191677187 |

每例均使用同轮 Naive 与原生 stdout `Total_Score` 计算；以上两套分别报告，不合并22点，也不混入旧84点主榜。分数单位沿用每例0–10分后均分。

Build/Full 整程成本比：dyna均1.0001435336684281（3胜9负），P50 1.000099595643751，P90 1.0005258561655797，最差1.0007974089027547；stat均0.9991981309022923（7胜3负），P50 0.999905496410304，P90 1.0001564659910784，最差1.0005616851705617。

物理成本 IO+penalty×Miss 比：dyna均1.0001326029120583（3胜9负）；stat均0.9992134646019035（6胜1平3负）。D总量为dyna Full29,790,738.94us、Build32,355,095.79us；stat Full11,138,208.88us、Build11,209,250.46us。单次计时仅作描述。

全部总成本负例见每例CSV与两套summary：dyna的dev_burst_staggered_09、dev_fast_shared_08、dev_slow_staggered_07、holdout_fast_staggered_11、holdout_slow_shared_10、train_burst_shared_05、train_burst_staggered_06、train_fast_staggered_04、train_slow_staggered_02；stat的eval_00_uniform_static_staggered、eval_01_uniform_fast_staggered、eval_09_mixed_mixed_staggered。

最差总成本增加：dyna holdout_fast_staggered_11 +0.0797408903%；stat eval_09_mixed_mixed_staggered +0.0561685171%。两个数据套方向不一致且幅度小，本轮不支持无条件替换 Full。

仅测得 BUILD 干预的整程总效果。原生输出没有 BUILD/PROBE 分阶段成本，初始驻留变化会影响后续miss、可见信息与决策，不能把整程差量解释为 BUILD 单阶段节省。tiny测试证明固定状态下一次逐出的选择行为及引擎语义；不代表全程收益。

## 证据入口

* `release.preparation.json` SHA78a17cf1ba3cbf30123375270c62dae475e41f5e349ec9d24ace236fe5d28347。
* `publication.json` SHA36ae6b0ffc6e7b875ea9a5f3cdd9176cae09fd017e8a653234bc41ee0985254e，是正式完成与产物hash入口。
* `attempt_completion.json`：实际预算、完整状态及全部进程组清理结果。
* `verification.json`：66份原始输出hash与重新解析、44份同输入Full/Naive历史物理指标严格核对；历史D从未复用。
* `dyna/finalized_summary.json`、`stat/finalized_summary.json`：未截断分数、每例物理/D、全部负例、分组及P50/P90/worst。
* `provisional/per_case.csv`、`provisional/combined_dataset_equal.json`、`provisional/REPORT.md`：文件保持provisional目录与发布前说明；publication已绑定这些确切文件，可作为已验证正式结果引用。
* `effectiveness_red_run/`与`effectiveness_run/`：parent RED按预期exit3，候选GREEN10项通过；正式计时二进制不含测试instrumentation。

最终Full源固定commit3064e270fde0473810cd8c0e57b738ee48356254，SHA2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617，正式ELF与最终版bf1377...一致。候选源SHAb157c93d78928c237ba6050da33e0cd60ea9f58cd1991df7343c9a947851ce96，独立producer与exact patch在tmp/r81_build_candidate_20261031/。

最后只读交接检查已核publication→completion/verification/报告hash、全部66格、44历史控制、实际487.94秒与children0；不重跑policy、不重扫输入。独立复核agent负责另行出具中文REVIEWED_REPORT.md，冻结报告不改。
