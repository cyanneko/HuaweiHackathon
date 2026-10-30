"""Render and validate the R81 presentation. No scheduler or training is executed."""
from pathlib import Path
import hashlib, json
import pymupdf as fitz
from playwright.sync_api import sync_playwright
from content_v2 import pages

ROOT=Path(__file__).parent
OUT=ROOT/'qa'/'v2';OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    resp=page.goto('http://127.0.0.1:8765/',wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(OUT/'desktop.png'))
    missing_anchors=page.evaluate("[...document.querySelectorAll('a[href^=\"#\"]')].map(x=>x.hash).filter(h=>h && !document.getElementById(h.slice(1)))")
    duplicate_ids=page.evaluate("[...document.querySelectorAll('[id]')].map(x=>x.id).filter((x,i,a)=>a.indexOf(x)!==i)")
    page.locator('[data-score="dyna12_score"]').click()
    dynamic=page.locator('.bar-row.selected .bar-value').inner_text()
    assert dynamic=='4.455853',dynamic
    page.locator('[data-score="final72_score"]').click()
    static=page.locator('.bar-row.selected .bar-value').inner_text()
    assert static=='3.713206',static
    page.locator('[data-score="equal_dataset_score"]').click()
    page.locator('[data-route="learning"]').click()
    assert '150' in page.locator('#route-detail').inner_text()
    page.locator('[data-route="hierarchy"]').click()
    assert '2048' in page.locator('#route-detail').inner_text()
    assert page.locator('.heat-cell').count()==32
    initial_heat=page.locator('.heat-cell').all_text_contents()
    page.locator('[data-heat="partition"]').click()
    partition_heat=page.locator('.heat-cell').all_text_contents()
    assert initial_heat!=partition_heat
    page.locator('[data-heat="shift"]').click()
    shift_heat=page.locator('.heat-cell').all_text_contents()
    assert partition_heat!=shift_heat and '迁移到3' in page.locator('#heat-explain').inner_text()
    assert page.locator('#fast-weight').inner_text()=='25.00%'
    assert page.locator('#slow-weight').inner_text()=='84.09%'
    page.locator('#decay-age').fill('2048')
    assert page.locator('#fast-weight').inner_text()=='0.39%'
    assert page.locator('#slow-weight').inner_text()=='50.00%'
    page.locator('#op-prob').fill('50')
    page.locator('#part-prob').fill('20')
    page.locator('#part-size').fill('8')
    example={k:page.locator('#'+k).inner_text() for k in ['joint-value','value-total','value-density']}
    assert example['joint-value']=='10.00%' and example['value-total']=='157.93 ms',example
    desktop_overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
    for key in ['routes','generation','recency','results']:
        page.locator('#'+key).screenshot(path=str(OUT/f'web-{key}.png'))
    page.set_viewport_size({'width':390,'height':844})
    page.goto('http://127.0.0.1:8765/',wait_until='networkidle');page.evaluate('document.fonts.ready')
    mobile_overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.screenshot(path=str(OUT/'mobile.png'))
    for key in ['generation','probability','results']:
        page.locator('#'+key).screenshot(path=str(OUT/f'mobile-{key}.png'))
    page.goto('http://127.0.0.1:8765/reading.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
    page.set_viewport_size({'width':1000,'height':1300})
    page.emulate_media(media='print')
    paper_measurements=page.evaluate("""[...document.querySelectorAll('.paper')].map((p,i)=>{const c=p.querySelector('.paper-inner'),f=p.querySelector('.paper-footer');return {page:i+1,chapter:p.dataset.chapter||'cover',content_bottom:c?Math.max(...[...c.children].filter(e=>getComputedStyle(e).display!=='none').map(e=>e.getBoundingClientRect().bottom)):null,footer_top:f?f.getBoundingClientRect().top:null,overlap:c&&f?Math.max(...[...c.children].filter(e=>getComputedStyle(e).display!=='none').map(e=>e.getBoundingClientRect().bottom))>f.getBoundingClientRect().top-10:false};})""")
    page.pdf(path=str(ROOT/'dist/HashJoin-R81-Reading-Guide.pdf'),prefer_css_page_size=True,print_background=True,display_header_footer=False,tagged=True,outline=True)
    browser.close()
pdf=ROOT/'dist/HashJoin-R81-Reading-Guide.pdf'
doc=fitz.open(pdf);pdf_text=[page.get_text() for page in doc];all_text=''.join(pdf_text)
assert len(doc)==len(pages)+1,len(doc)
assert all(len(t)>60 for t in pdf_text)
assert '4.084530' in all_text and '2e168451ea28c802' in all_text
assert '正式默认仍为R75' not in all_text
for number in [0,3,4,5,7,8,9,10,11,12,14,16,17,20]:
    doc[number].get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(OUT/f'pdf-{number+1:02}.png')
report={'website_status':resp.status,'javascript_errors':errors,'missing_anchors':missing_anchors,'duplicate_ids':duplicate_ids,'desktop_overflow':desktop_overflow,'mobile_overflow':mobile_overflow,'chart_switches_R81':[dynamic,static],'routes_passed':True,'probability_heatmap_passed':True,'recency_slider_passed':True,'interactive_example':example,'paper_layout':paper_measurements,'pdf_pages':len(doc),'pdf_chars_per_page':[len(t) for t in pdf_text],'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'new_solver_runs':0,'new_training_runs':0}
(OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if errors or missing_anchors or duplicate_ids or desktop_overflow or mobile_overflow or any(x['overlap'] for x in paper_measurements):raise SystemExit('Presentation QA requires correction')
