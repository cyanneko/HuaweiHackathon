# Team 19 · 面向动态倾斜的分层热度感知优化

当前主页是供演示的精简版，依据用户提供的 `report.pdf`（6页）和 `ppt_team19.pptx`（4页）重组。参考文件身份与口径核对见 `evidence/v3/REFERENCE_NOTES.json`；未上传两份原文件。

- 5部分：问题、探索路线、数据设计、最终算法、结果与消融。
- 主文约2700字；保留关键图解，完整公式与七项消融按需展开。
- 最终算法仍为R81，不运行新训练或算法评测。
- 主结果固定为dyna12/final72各50%，平均相对成本下降40.0362%，本地归一分4.084507912；stat单列。结果来自同批R81消融报告，不混入PPT的三套等权均值或旧stat三重复计时。

## 本地直接打开

双击 `dist/HashJoin-Team19-Demo.html`。这是一个约6.7MiB的独立HTML，字体、样式、交互数据及21页技术PDF均已内嵌，断网也可阅读、切换数据场景、拖动概率、查看消融并导出PDF；页尾GitHub来源链接需要联网。

`dist/index.html`是同内容的多文件版。公网地址：
https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site

## 构建与验证

```bash
python build.py
python check_demo.py
```

构建仅依赖Python标准库：读取`demo.html`模板、`dist/assets/demo-results.json`，生成主页和离线HTML。检查使用Playwright/Chromium，以`file://`和断网模式验证；不启动服务器或执行算法。

- `demo.html`：精简正文与语义结构。
- `dist/assets/demo.css`、`demo.js`：样式及交互。
- `build_offline.py`：单文件打包。
- `check_demo.py`：离线、下载、交互与布局验证。
- `render_and_check.py`：当前检查的兼容入口。

## 完整技术版与历史

原20节内容保留在 `dist/technical.html`，21页PDF仍为 `dist/HashJoin-R81-Reading-Guide.pdf`。`build_v2.py`可重建技术版及其打印源；需要重渲染旧PDF时，按旧流程运行本地8765服务器，再执行`render_and_check_v2.py`。旧R85 PDF保留在`dist/archive/`。

`content.py`、`content_v2.py`及旧证据继续作为历史资料，不用旧数据覆盖当前主指标。`SOURCE_MANIFEST.json`与`SOURCE_MANIFEST_V2.json`分别记录此前发布快照；V3内容与验证见`evidence/v3/`。

## 托管与源码

源码仍在原仓库 `source/Vanius0525:src/Vanius0525/showcase/`，静态发布目录`dist/`。Sites身份记录见`PUBLICATION.json`；GitHub Pages的一次性设置及后续更新见`GITHUB_PAGES.md`与`GITHUB_PAGES_STATUS.json`。无需为本地使用开启任何托管。

字体Droid Sans Fallback（Google，Apache-2.0）内嵌到离线HTML，授权原文见`dist/assets/font-LICENSE.txt`。未为原项目算法另设许可证。
