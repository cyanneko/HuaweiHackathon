# Hash Join · 从热度到驻留

本目录是 HuaweiHackathon 的项目展示网站与阅读报告，源码维护在原仓库的 `source/Vanius0525:src/Vanius0525/showcase/`，无需另建 GitHub 源码仓库。

研究快照：2026-10-31。主讲 `R85_fast_prior8`，固定代码提交 `4a259b7b1b4232f521decdb22b826e41d16baf48`。其在 R85 同场 dyna1.0 全12例与 final2.1 全72例、两组各50%的主测中得分4.087790；正式默认仍为R75。AI与我方算法优化均暂停，本任务没有新增算法运行。

## 阅读

- `dist/index.html`：面向访客的项目网站，含成绩切换、参数估值示例及完整阅读路线。
- `dist/HashJoin-Reading-Guide.pdf`：16页A4中文阅读版，字体已嵌入。
- `dist/reading.html`：独立分页的PDF排版源。
- `content.py`：网站与PDF共享正文；`build.py`生成两种HTML。
- `evidence/`：固定版本、汇总来源、代码公式核验稿与展示验证记录。

网站全部静态资源自带，不依赖外部CDN。可部署到GitHub Pages、Sites或其他静态托管服务；托管目录是`dist/`。网站展示与GitHub仓库浏览相互独立，正文及PDF无需登录仓库。

## 本地构建与预览

```bash
python build.py
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

打开 `http://127.0.0.1:8765/`。已有PDF可直接使用。需要重新生成PDF时，在服务器运行期间执行：

```bash
python render_and_check.py
```

渲染依赖Python Playwright、其Chromium浏览器与PyMuPDF；HTML构建仅依赖Python标准库。验证包括桌面/手机横向溢出、15节锚点、成绩切换、公式示例、16页PDF文本与页脚边界；不执行算法测试。

## 公开托管

用户已明确要求公网可访问。此次通过Sites发布，托管工作区的`.openai/hosting.json`绑定站点身份；Sites管理其部署用源码副本，原Hackathon仓库仍是用户侧维护入口。当前Git连接可推送代码，未取得仓库Pages管理API权限，因此没有变更原仓库Pages设置。以后若改用GitHub Pages，部署本目录`dist/`即可，无需改正文。

字体：Droid Sans Fallback，Copyright Google，Apache-2.0；授权原文见`dist/assets/font-LICENSE.txt`。代码原件保持字节与换行，SHA记录在`evidence/VERSION.json`。本站未给原项目算法另设许可证。

## 发布完成

公网网站：https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site

PDF：https://hashjoin-algorithm-atlas.michael-rich577.chatgpt.site/HashJoin-Reading-Guide.pdf

Sites发布状态succeeded，访问模式public。对应托管源码提交为`3ff1c98a3719b8b89d3a27a951abd897496d4e70`。原仓库归档目录为`src/Vanius0525/showcase/`；未修改算法、数据或Pages设置。
