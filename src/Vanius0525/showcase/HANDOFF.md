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

## V2制作启动：最终R81与探索路径

用户明确要求直接生成并优化当前最佳算法的展示，以及算法/数据集生成策略的探索过程。复用原公网Site与现有仓库目录，保留公开访问；将主讲对象从历史最高均分R85A改为最终选定R81。独占编辑网站、PDF、V2证据；代理仅在research_v2/pure_ai整理既有研究，不恢复算法工作。

计划：核固定最终提交源码和R87归档，展开纯算法/AI/观测校正/融合路线；补充数据生成链路与可控变化；用交互解释双时间尺度、最近访问与成本估值。已有R85 PDF另存归档，新PDF与主页同步。只运行展示构建、浏览器与PDF验证，不运行训练/评测或生成算法数据。

## V2 内容核验与展示验证完成

最终选定R81_op256_cond2048，固定源码3064e270fde0473810cd8c0e57b738ee48356254，SHA2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617；上游说明固定b0beecfee11e4ea4732a52d02c195316909db567。两层先验均64，算子/分区半衰期256/2048。普通PROBE显式age被概率覆盖，但历史衰减保留时间信息。

20节、21页；四条探索路径、数据生成矩阵、时间衰减曲线、同批主榜和独立消融。主榜R81为4.084530，R85A为4.087832；保留最终选择与最高均分的区别。stat生产划分24/6/10，独立补充。两位代理仅核查资料，已停止。

展示验证python build.py、python render_and_check_v2.py全部通过：网站200，1440/390无横向溢出，20节锚点、重复ID、JS异常、四类交互、21页PDF文本与页脚边界检查通过。已目视检查关键页面。源文件SHA和旧R85 PDF字节保持核对通过。无新算法编译/训练/评测/数据生成。

当前正在发布既有public Site；发布成功后更新PUBLICATION.json并仅提交showcase改动。预览会话13623待停止。

## V2 已上线

Sites version2发布succeeded，public访问保持；URL https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site 。新PDF为/HashJoin-R81-Reading-Guide.pdf，旧通用PDF地址也指向新版，原R85另有归档。托管源码0f7023f941caa1c7f2dcee0df752cd3b0524037c，部署appgdep_6ae4fd8973708191a3399c8a3736b0c9。身份与匿名HTTP核验见PUBLICATION.json。

预览会话13623已Ctrl-C停止；无本轮后台任务。旧持续目标经get_goal确认仍paused。正在对仅showcase文件的暂存内容做最后身份核对，再提交并推送source/Vanius0525；其余旧修改和草稿不加入。

## GitHub Pages迁移

用户要求改为GitHub有源码、可公网访问的版本。源码1161fa3a已在source/Vanius0525。此次独占showcase，准备同仓库gh-pages静态发布分支，不更改原Sites站点或他人成果。当前SSH推送可用；未配置gh、GH_TOKEN/GITHUB_TOKEN或credential helper。匿名仓库/Pages API和预期Pages域名均404，不能据此确认仓库可见性、套餐或Pages设置。

已准备publish_github_pages.py：只从已提交的dist生成发布树，绑定source commit，保留既有gh-pages历史，不切共享工作树分支，不force push；检测未知分支或删除时停止。接下来检查GitHub子路径下资源/交互，提交源码、推送部署分支，再确认网址与剩余启用条件。

GitHub子路径验证通过：在/HuaweiHackathon/下主页200、四类交互正常、字体/PDF200、手机无横向溢出、无JS异常或资源404。PDF字节保持原V2。验证服务器已停止。初始远端没有gh-pages分支；下步提交展示专属改动并以正常非强推发布静态分支。Pages是否启用及仓库套餐仍无法通过当前凭据确认。

## GitHub发布分支已推送，等待首次Pages启用

源码84063070ac06d2497acbb4e7c69cb7b995e55f1f已推送source/Vanius0525；静态发布b96462e7fe87fbef57fe50aaeb1c7ce2daf5c1a6已推送同仓库gh-pages。15项网站文件Git对象身份与source/dist完全一致，另加pages-deployment.json绑定源码提交；不含其他实验资料。

GitHub预期网址https://cyanneko.github.io/HuaweiHackathon/再次核验404，不能称为上线。当前无Pages管理API登录，已请用户/仓库管理员在Settings→Pages选择Deploy from a branch、gh-pages、/(root)并Save。下一步：收到设置完成反馈后，检查GitHub页面、PDF、子路径资源和公布的部署身份，再更新GITHUB_PAGES_STATUS.json。不需重跑算法或重建PDF。

本轮可独立完成的源码适配、验证和Git分支发布均完成；原Sites继续可用。没有本轮后台任务，旧优化仍暂停；其他任务文件未纳入提交。

## V3 精简演示与本地单文件

用户提供report.pdf（6页）及ppt_team19.pptx（4页），要求言简意赅且重点完整，继续交付可双击的本地HTML。已阅读PDF全文和PPT文字/内嵌路线图、流程图。主线压缩为问题、双线探索、数据设计、最终算法、结果与消融，复杂公式按需展开。

核查：report主榜dyna/final各50%，S=4.084507912、未截断U=4.003620157（平均相对成本下降40.0362%）；PPT三组均分3.8696是另一口径，不能混用。PPT额外固定reuse=1消融未出现在report七项对照中，暂不并入主表；stat描述改为分区潜在过程分别演化，避免将归一化访问概率称为相互独立。

只编辑展示和打包，不恢复算法实验。原6页PDF/PPT保持不变；参考内容按SHA与页码记录，不上传本机路径。V2长版保留为补充，生成自包含本地HTML并核验file://离线交互，再同步GitHub展示源码。

## V3 本地文件与验证完成

五部分主文约2700字，离线HTML约6.66MiB；保留双线探索、三套数据、四步流程、分层概率/集合示例及完整消融。旧20节内容保留technical.html，21页PDF原字节未变。单文件内嵌字体、交互数据和PDF；已另存用户桌面HashJoin_Team19_演示.html（本机交付路径不写入仓库）。

python build.py及python check_demo.py均通过：file://+offline，0HTTP、0JS异常、5节锚点/所有交互/内嵌PDF下载通过；桌面和手机无横向溢出。断网下载PDF与原件SHA一致。证据与截图位于evidence/v3。两份参考文件仅记录名称/SHA，原件未修改、未上传。

展示源码已同步；正在发布既有public Site，随后提交source/Vanius0525并更新gh-pages部署分支。无算法实验，无运行中的预览服务。

## V3 源码与公网交付完成

展示源码efc03098已推送source/Vanius0525，仅27个本轮展示文件，16项暂存源码/产物SHA一致。Sites version3发布succeeded，托管源码84747b4e0dae7655b4db1a3bd325f4c5b3502349，部署appgdep_6ae506d7ce78819187402346ced2ba8b。匿名主页已核验新内容；离线HTML地址经规范重定向后下载成功，SHA与桌面文件完全一致。首次curl未跟随重定向取得空响应，已用-L完成验证，没有更改产物。

当前仅补记发布状态并更新同仓库gh-pages副本。用户可直接使用桌面单文件，无需GitHub Pages设置。旧优化仍暂停，资料代理已结束，无本轮后台进程。
