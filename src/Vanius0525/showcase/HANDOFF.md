# 项目网站与PDF交付

2026-10-31，用户要求停止我方优化，改为基于同学当前最佳方法制作可读PDF与项目展示网站。随后用户明确网站公网公开，源码放原Hackathon仓库，不另建用户GitHub源码仓库。

## 完成内容
15节正文、16页A4阅读PDF、响应式静态网站、成绩范围切换、概率/大小估值示例。主讲固定4a259b7下R85_fast_prior8；旧dyna12+final2.1/72同场等权4.087790，正式默认R75。真实分支与公式独立核对并修正时钟、dense权重、active启用及无PROBE回退描述。

## 验证
python build.py；本地静态服务器配合python render_and_check.py。16页中文文本和公式可提取，无页脚覆盖；桌面1440与手机390无横向溢出，无JS错误/失效锚点，成绩切换与数值示例通过。封面、流程、公式、教训页目视检查。记录见evidence/VALIDATION.json。0算法运行、0编译、0训练。

## 发布
原仓库独占路径src/Vanius0525/showcase，目标source/Vanius0525。Sites托管步骤进行中，完成后在PUBLICATION.json记录实际状态与URL；不把预期URL当作已上线。没有取得GitHub Pages管理接口权限，没有改变原仓库Pages设置。

## 旧任务状态
我方纯算法和AI优化均暂停；两个周期监测agent已结束循环，只完成本轮只读资料核验。旧R13数据再生V1失败已留档，V2未运行。

## Open Ideas / 值得深挖的问题
本次只整理已有研究，无新算法主张。后续更新时固定新版本、实际执行分支及同口径结果，再更新网站和PDF。

## 发布完成

公网网站：https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site

PDF：https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site/HashJoin-Reading-Guide.pdf

Sites发布状态succeeded，访问模式public。对应托管源码提交为`3ff1c98a3719b8b89d3a27a951abd897496d4e70`。原仓库归档目录为`src/Vanius0525/showcase/`；未修改算法、数据或Pages设置。

## 2026-10-31：最终版本更新与汇报标题

用户询问当前是否采用R81及其访问间隔处理，并要求以热度和动态倾斜为关键词的PPT短标题。本轮只做一次远端只读核验；source/cyanneko已到5f4f55c3b0d3477de6df492cd210f047ac18a4cc，FINAL_SUBMISSION_20261031.md和最新AGENTS明确最终选定R81_op256_cond2048，submission/MySpillScheduler.cpp为排版注释整理版（公布源SHA ef1c26e81013dced4dbf100206ead5666368e2e957996cffdf2258297cb8ef65）。R87未采用。该信息更新了此前R75默认的状态；R85仍保持最新R87同场数值均分略高（4.087832 vs R81 4.084530），不能将最终选定与均分最高混为一谈。

已重新读取原R81代码：普通PROBE的reuse被64×hier_probability覆盖，显式age不再独立参与该路径；但next历史质量按分区2048、算子256的半衰期衰减，故新近性通过概率间接进入排序。历史/风险回退路径保留age项。普通Hit身份不可见，不能声称掌握每分区真实最后访问时间。

本轮没有恢复训练/评测或更改网站/PDF；既有公开成品仍明确绑定4a259b7时点的R85A最高均分说明。后续若改为最终提交版展示，应更新为R81并将快先验从约8.009改回64，同时保留原版快照。标题建议突出“动态倾斜＋分层热度＋Hash Join调度”，避免用版本号替代方法概括。
