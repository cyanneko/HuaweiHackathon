"""Build the public project narrative and its paginated reading edition."""
from pathlib import Path
import json
from content import pages

ROOT = Path(__file__).parent
D = ROOT / 'dist'
data = json.loads((D/'assets/results.json').read_text())
nav = ''.join(f'<a href="#{p[0]}"><span>{i:02}</span>{p[1]}</a>' for i,p in enumerate(pages,1))
chapters = '\n'.join(f'<section class="chapter" id="{pid}"><div class="chapter-kicker">{i:02} / {label}</div><h2>{title}</h2>{body}</section>' for i,(pid,label,title,body) in enumerate(pages,1))
meta = '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Hash Join 内存调度的协作优化：从数据集设计到 R85 两层热度估计、成本估值与完整算法图解。"><meta name="theme-color" content="#102c32"><link rel="icon" href="assets/mark.svg"><link rel="stylesheet" href="assets/style.css">'
hero = '''<div class="hero-copy"><div class="eyebrow">HUAWEI HACKATHON · RESEARCH ATLAS</div><h1>从热度<br>到<span>驻留</span>。</h1><p class="hero-lead">有限内存，整分区调度。<br>让每一次搬运，都值得。</p><p>一次围绕 Hash Join 的协作探索：从随机与倾斜数据的构造，走向可观察、可估值、可验证的内存决策。</p><div class="hero-actions"><a class="button light" href="#overview">开始阅读 <span>↗</span></a><a class="text-link" href="HashJoin-Reading-Guide.pdf" download>下载阅读 PDF ↓</a></div><div class="hero-meta">Vanius0525 × cyanneko <span>研究快照 · 2026.10.31</span></div></div>
<div class="hero-art" aria-label="热点分区驻留与长尾请求周转的概念示意"><div class="art-tag">MEMORY / 有限容量</div><div class="memory-grid"><div class="partition hot large">A<small>高收益驻留</small></div><div class="partition hot">B<small>复用</small></div><div class="partition warm">C</div><div class="partition cold">D</div><div class="partition ghost">周转空间</div></div><div class="transfer"><span>SPILL ↓</span><span>↑ LOAD</span></div><div class="disk-row"><b>DISK</b><span>E</span><span>F</span><span>G</span><span>…</span></div><div class="art-caption">大小 ≠ 热度<br>Miss 次数 ≠ 搬运成本</div><div class="art-note">问题概念图；R85 并未显式划分热点核心。</div></div>'''
html = f'''<!doctype html><html lang="zh-CN"><head>{meta}<title>Hash Join · 从热度到驻留</title></head><body>
<a class="skip" href="#overview">跳到正文</a><header class="topbar"><a class="brand" href="#top"><img src="assets/mark.svg" alt="">HASH JOIN <span>ATLAS</span></a><nav aria-label="主要导航"><a href="#datasets">数据设计</a><a href="#architecture">算法图解</a><a href="#results">结果</a><a class="download" href="HashJoin-Reading-Guide.pdf">阅读 PDF ↗</a></nav></header>
<main id="top"><section class="hero">{hero}</section><div class="reading-shell"><aside class="toc"><div>阅读路线</div>{nav}<a class="toc-pdf" href="HashJoin-Reading-Guide.pdf" download>保存完整 PDF ↓</a></aside><article>{chapters}</article></div></main>
<footer><span>Hash Join Research Atlas · 2026</span><span>理解机制，保留证据，持续迭代。</span><a href="#top">回到顶部 ↑</a></footer><script src="assets/app.js" defer></script></body></html>'''
(D/'index.html').write_text(html,encoding='utf-8')
cover = f'''<section class="paper cover"><div class="cover-top">HUAWEI HACKATHON <span>项目阅读报告 / 2026.10.31</span></div><div class="cover-title">从热度<br>到<span>驻留</span>。</div><p class="cover-subtitle">Hash Join 内存调度的协作优化</p><div class="cover-rule"></div><div class="cover-description">数据集如何逼近真实问题<br>可见访问如何转化为保留价值<br>R85_fast_prior8 如何作出每一次选择</div><div class="cover-diagram"><b>观测</b><i>→</i><b>估计</b><i>→</i><b>估值</b><i>→</i><b>执行</b></div><div class="cover-bottom"><strong>Vanius0525 × cyanneko</strong><span>基于代码与归档实验的技术叙事<br>正文 15 节 · 含公式、流程与结果</span></div></section>'''
paper = ''.join(f'<section class="paper" data-chapter="{_}"><div class="paper-top">HASH JOIN / RESEARCH ATLAS <span>{label}</span></div><div class="paper-inner"><div class="chapter-kicker">{i:02} / {label}</div><h2>{title}</h2>{body}</div><div class="paper-footer"><span>2026.10.31 · R85_fast_prior8</span><span>{i+1:02} / {len(pages)+1:02}</span></div></section>' for i,(_,label,title,body) in enumerate(pages,1))
(D/'reading.html').write_text(f'<!doctype html><html lang="zh-CN"><head>{meta}<title>Hash Join — 项目阅读报告</title></head><body class="reading-edition">{cover}{paper}<script src="assets/app.js" defer></script></body></html>',encoding='utf-8')
print(f'Built {len(pages)} chapters and {len(pages)+1} PDF pages')
