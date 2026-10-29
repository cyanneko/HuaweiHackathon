# naive_unique_max_fused · 可选ID104静态适配草稿

唯一namespace为cyanneko_naive_unique_max_fused_v1；reset/observe/onDispatch为空，decide const，不读取next_op、callback年龄或额外未来信息。原R59 header按原字节保存为reference.hpp。三个回调算法体只改签名为私有const helper，tuple布局、候选枚举顺序、size-only比较器、唯一性重置、正缺口/恰足够判断和回退循环保持原样；decide将原返回vector移动给调用者拥有的out。

已完成动作/导出验收：直接版与导出版各278个字面状态（含256随机）及92次短typed回调通过，2export/2build/2unit全部成功、无超时。manifest/validation记录实际范围；仍未运行完整官方引擎或接口计时。独立standalone仅定义MySpillScheduler，需接官方兼容类型/框架，无main/engine。

**104只作为可选候选，不能替换official_naive评分基线。** 动作等价不保证D相等；D计入Score，改快基线会改变参照分。原Naive基线、已发布101/102默认pair和103均不改。固定101+104只在隔离测试夹具中，不构成默认组合、真实tree或NN。

R59原直接类只在4个开发案例上实测，共12次配对运行，并非完整公共集或接口时延验收。接口版的SDK派发、钩子、out移动和组合开销均未测；不能继承直接R59的D或成绩，performance_validated=false。

窗口明确释放后，在同一Linux/WSL Python与g++环境运行src/experts/tests/run_naive_unique_max_tests.py，--out指向不存在的新目录，--max-seconds 55。计划2次C++14/O2编译、2次typed-unit、2次export，申请总窗口不超过60秒；这不运行官方solver、评分、训练或性能实验。

边界包括[5,5,7]/[7,7,5]、先并列后更大、目标op+pid排除/跨op同pid、零大小及非驻留、无缺口、精确缺口、多victim、4GiB、8x64、256固定种子状态；另验证纯const/out.clear、独立/固定/交替、selected104保持、非法selector回退101及短typed动作容量。直接和展开导出都逐动作比较同一冻结R59，不重做其未规定的跨实现tie顺序保证。上述动作/导出结论仅适用于本次同环境typed验收，不代替完整官方流动作重放或接口性能结果。
