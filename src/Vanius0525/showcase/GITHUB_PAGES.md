# GitHub Pages 发布

网站源码继续位于 `source/Vanius0525:src/Vanius0525/showcase/`。
同一仓库的 `gh-pages` 分支仅存放可公开的网站静态文件；首页、交互、字体和PDF均自带，不依赖Sites服务。

## 一次性启用

由具有仓库管理或维护权限的成员打开：

[HuaweiHackathon → Settings → Pages](https://github.com/cyanneko/HuaweiHackathon/settings/pages)

在 **Build and deployment** 中选择：

- **Source**：Deploy from a branch
- **Branch**：gh-pages
- **Folder**：/ (root)
- 点击 **Save**，等待 GitHub 的 Pages 构建和部署完成。

默认预期网址为 `https://cyanneko.github.io/HuaweiHackathon/`；只有GitHub部署完成并核验后才能称为已上线。最终以Settings显示的网址为准。若页面没有Pages选项或提示套餐限制，需要仓库管理员处理；不要为此直接改变整个算法仓库的可见性。

GitHub Free支持公开仓库的Pages；私有仓库是否可启用取决于账号套餐。仓库源码的访问权限与已公开网站的访问权限分别由GitHub控制。本文没有将仓库改成公开。

## 后续更新

在 `source/Vanius0525` 分支修改和构建网站，检查后提交、推送展示源码，再执行：

```bash
python src/Vanius0525/showcase/publish_github_pages.py --push
```

脚本从当前提交中的 `dist/` 生成部署树，因此未提交文件和其他实验材料不会混入网站。发布提交的 `pages-deployment.json` 记录对应源码SHA、路径和固定链接。`.nojekyll`关闭Jekyll处理，保留现有静态资源。启用Pages后，后续更新`gh-pages`会由GitHub自动部署。

脚本不切换共享工作树分支、不强推、不变更Pages设置；遇到未知部署分支、远端并发冲突或文件删除会停止。省略`--push`可准备并查看部署身份而不推送远端。

此前Sites网址保留为已验证的在线版本；迁移状态见`GITHUB_PAGES_STATUS.json`，既有发布记录`PUBLICATION.json`不改写成未经验证的GitHub部署。

依据：[GitHub Pages发布源配置](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。
