# 动态倾斜下的分层热度调度 · R81

HuaweiHackathon 的项目展示网站与阅读报告。原仓库维护入口为 `source/Vanius0525:src/Vanius0525/showcase/`，不需要另建 GitHub 源码仓库。

- 公网网站：https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site
- 阅读PDF：https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site/HashJoin-R81-Reading-Guide.pdf
- 研究快照：2026-10-31；最终选定 `R81_op256_cond2048`。同批 R87 归档主测均分 4.084530；R85A 数值均分略高，展示中保留这一区别。
- 最终源文件：`3064e270fde0473810cd8c0e57b738ee48356254:submission/MySpillScheduler.cpp`；SHA256 `2e168451ea28c80250301bc06dffb7497265eb285c490dd57514468259ede617`。

## 内容

20节正文、21页A4阅读版。主线依次为问题与成本、四条探索路径、数据生成策略、R81算法与公式、同场结果与机制消融。

网站可交互查看启发式/AI/风险/分层路线、算子与分区概率结构、256与2048半衰期衰减、概率与大小估值、动态/静态成绩。交互数值是示意，未执行新算法实验。旧R85阅读版保留在 `dist/archive/HashJoin-R85-20261031.pdf`；旧PDF通用URL指向最新R81版。

数据集演进包括final2.0→2.1→3.0、dyna及stat。stat冻结生产划分为24 train/6 dev/10 eval，属于独立补充。当前主榜仍固定dyna1.0全12与final2.1 eval72，两组等权。

## 构建与检查

```bash
python build.py
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

另一终端执行 `python render_and_check_v2.py`（或兼容入口 `python render_and_check.py`）渲染PDF并检查展示。HTML构建仅需Python标准库；渲染需要Python Playwright、Chromium与PyMuPDF。

`content_v2.py`共用网站/PDF正文，复用`content.py`中仍适用的解释与排版函数；旧版内容与结果证据留档。`dist/assets/results-v2.json`绑定R87同场和独立R81消融，不混批计算。`evidence/v2/`固定新源码、上游报告、元数据及展示验证；`research_v2/`保留研究事实审核。

验证覆盖20节锚点、重复ID、JS异常、1440/390宽度、四类交互、21页PDF中文文本与全部可见内容的页脚边界，并目视检查封面、公式、流程、数据和实验页。所有算法优化、训练、评测及数据生成仍暂停。

## 托管与版本

当前沿用既有public Sites站点；发布身份与实际提交见`PUBLICATION.json`。用户源码仍维护在原Hackathon仓库。静态发布目录为`dist/`，可迁移到GitHub Pages等平台，无外部CDN依赖。

`SOURCE_MANIFEST_V2.json`为R81 V2发布时的源文件清单；`SOURCE_MANIFEST.json`保留V1历史身份，不用于校验V2文件。`evidence/v2/SOURCE_IDENTITY.json`独立记录最终算法证据。

字体Droid Sans Fallback（Google，Apache-2.0）自带并嵌入PDF，见`dist/assets/font-LICENSE.txt`。未为原项目算法另设许可证。

## GitHub Pages迁移

已新增同仓库`gh-pages`发布脚本与静态入口，网站页脚可直接进入GitHub源码。一次性启用及后续更新见[GITHUB_PAGES.md](GITHUB_PAGES.md)，实际部署状态见[GITHUB_PAGES_STATUS.json](GITHUB_PAGES_STATUS.json)。源代码继续维护在本分支，发布分支只包含网站静态文件。
