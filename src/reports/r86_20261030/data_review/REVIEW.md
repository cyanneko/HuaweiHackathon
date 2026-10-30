# final_dataset 3.0.0：独立 eval72 缓存与离线审计

**PASS，72/72 完整输入通过；CPU 已释放，active0。** 唯一授权的 export+audit 窗口用时 25.623649 秒，预算120秒，无失败、超时或重跑。没有运行调度器、编译、生成器或训练，也没有修改Git分支/工作树、tmp/d70或R84/R85产物。

固定数据提交：`e6613435d59690d6dd768813332387108f7e83c2`；final_dataset tree：`35d4f98b7464e62a9a89b606e41d192380788e76`。新缓存为 `tmp/r86_final3_cache/final_dataset`，通过只读 `git archive` 流式导出，未生成约500MB的tar副本。拒绝软链接、路径穿越、意外文件和覆盖写入；161个文件逐项验证Git blob SHA、字节数及SHA256。原发布manifest/recipe保留全部612项，**没有修改成72项伪装完整发布包**。

缓存范围：72个eval输入、72个sidecar、eval/VERSION，根README/VERSION/manifest/recipe/.gitattributes，6个tools、2个provenance及3个stored reports。总计161文件、479,972,156字节；其中输入474,874,682字节、22,528,629操作。家族为hotspot28、zipf28、lognormal16。没有train540输入或sidecar。

## 本次实际核验

发布版 `tools/verify.py` 没有eval-only CLI，完整audit入口硬要求612。本次wrapper导入**未修改且SHA固定**的 `verify_case`，逐一重新读取全部72输入；这是一轮独立执行与绑定检查，核心流解析/概率校验算法复用发布版，不冒称独立重写验证器。

- 逐字节input、sidecar、操作流和分区语义流SHA；头部N/K/P/M/W/R/罚值/period、实际INSERT/PROBE计数和每op计数一致。实际probe总量独立于N，N包含INSERT与SWITCH。
- 每算子阶段合法、恰好一次SWITCH；key/tuple范围合法，所有完整分区BUILD字节为正且不超过M，存在真实大小差异。
- 233个算子的目标联合/条件概率为正、归一且满足互异规则；算子质量至少0.5/K、目标TV至少0.20、冷热比至少2。逐流实际PROBE的条件TV至少0.10、至少访问2个分区；不要求有限样本计数互异或每分区都被访问。
- recipe中的spec/build_seed/probe_seed、生成工具SHA和sidecar来源绑定；从固定父提交只读取72个小sidecar，实核旧、新partition_sizes逐项相等及compact-JSON布局SHA、INSERT数。未读旧大输入，未重生成BUILD。
- 本次72条真实流的三类SHA，与发布manifest全部612项及父manifest843项声明SHA做去重比较。train540和父843的大输入没有本地重扫；不能把声明哈希比较写成这些输入的逐流重验。

本地eval72最小值：目标条件TV **0.215000000218**，实际条件TV **0.218517296341**，目标冷热比 **6.829790105484**，实际被访问分区数 **8**，BUILD最大/最小正字节比 **1.748106307589**。这些是eval72的最小值，不混用发布者全612最小值。

原 `reports/validation.json` 的612/612 PASS、SHA与本轮manifest/recipe/verifier一致；本轮72条记录的输入/sidecar身份及基础统计也一致。该stored report只作为**发布者既有全包证据**，本地结论严格为eval72审计通过。

## 交接与边界

评测接口为 `tmp/r86_final3_cache/data_manifest.json`，包含新case_id、Windows/Linux输入与metadata路径、SHA、parameters、真实operations/build_count/probe_count/penalty，以及父case映射与布局SHA。新命名如`eval_0000_random_hotspot`，不能把新旧case编号直接当作同一输入。

算法仍为Root冻结的R85八方法；本轮不实施任何快慢混合数学gate。3.0更改PROBE分布，不能把它与2.1的均分差直接称为算法提升。父BUILD规格已有开发曝光，新版本也不是独立盲测。概率证书、未来counts和完整统计仅供离线audit/evaluator，不能传给在线调度类。

关键身份：

| 产物 | SHA256 |
|---|---|
| 发布manifest | `e52f3d88d8d13d20a8f049cc16f477bc7d09c5a6b778aace756b07505c1b4aa6` |
| 发布recipe | `2581e0ea892d125aeabd85ff798eca82dc28cc9b069bbeda759b3d19de7b3ba6` |
| 原verify.py | `07cac57fc204f9de38395789475cc15a1a4544adfa51bd31fb599fb1295542db` |
| 新评测data_manifest | `937e92a0415eac56c799aec4c0d5fff9729417f6d608503ffd344101584484d1` |
| 本地eval_audit | `8f669d0caf3d93b4ce9adccf079866c78b405d2fa6597422332b2c68f23d5f57` |
| parent_layout_review | `eb9f35f28308f7478e99467525710a62a4821983b0ffd720ae8e41519bdfb3b7` |
| export_identity | `8b5392da2dd7542d547130ed3f41296aa7023c2aadca152c0b9886150d1f3483` |
| release | `da83eb14cfa52b039700e5ef74d12161ae4ecc3207a85938c069d6e11c9f5afc` |

最终文件清单与补充审查身份见 `review.json`、`artifacts.json`。已释放数据窗口；正式scheduler计时仍由Root另行授权。
