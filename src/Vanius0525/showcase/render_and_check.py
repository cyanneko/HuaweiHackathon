"""Render the reading PDF and check presentation behavior; never executes an algorithm."""
from pathlib import Path
import json
import pymupdf as fitz
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).parent
OUT=ROOT/'qa';OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    resp=page.goto('http://127.0.0.1:8765/',wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(OUT/'desktop.png'))
    missing_anchors=page.evaluate("[...document.querySelectorAll('a[href^=\"#\"]')].map(x=>x.hash).filter(h=>h && !document.getElementById(h.slice(1)))")
    page.locator('[data-score="dyna12_score"]').click()
    dynamic=page.locator('.bar-row .bar-value').first.inner_text()
    assert dynamic=='4.482767',dynamic
    page.locator('[data-score="final72_score"]').click()
    static=page.locator('.bar-row .bar-value').first.inner_text()
    assert static=='3.692813',static
    page.locator('[data-score="equal_dataset_score"]').click()
    page.locator('#op-prob').fill('50')
    page.locator('#part-prob').fill('20')
    page.locator('#part-size').fill('8')
    example={k:page.locator('#'+k).inner_text() for k in ['joint-value','value-total','value-density']}
    assert example['joint-value']=='10.00%'
    assert example['value-total']=='157.93 ms',example
    desktop_overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.set_viewport_size({'width':390,'height':844})
    page.goto('http://127.0.0.1:8765/',wait_until='networkidle');page.evaluate('document.fonts.ready')
    mobile_overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    page.goto('http://127.0.0.1:8765/reading.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
    page.set_viewport_size({'width':1000,'height':1300})
    page.emulate_media(media='print')
    paper_measurements=page.evaluate("""[...document.querySelectorAll('.paper')].map((p,i)=>{const c=p.querySelector('.paper-inner'),f=p.querySelector('.paper-footer');return {page:i+1,content_bottom:c?c.lastElementChild.getBoundingClientRect().bottom:null,footer_top:f?f.getBoundingClientRect().top:null,overlap:c&&f?c.lastElementChild.getBoundingClientRect().bottom>f.getBoundingClientRect().top-10:false};})""")
    page.pdf(path=str(ROOT/'dist/HashJoin-Reading-Guide.pdf'),prefer_css_page_size=True,print_background=True,display_header_footer=False,tagged=True,outline=True)
    browser.close()
doc=fitz.open(ROOT/'dist/HashJoin-Reading-Guide.pdf')
pdf_text=[page.get_text() for page in doc]
assert len(doc)==16,len(doc)
assert all(len(t)>60 for t in pdf_text)
assert '4.087790' in ''.join(pdf_text)
assert '8.009479828' in ''.join(pdf_text)
for number in [0,4,6,7,8,9,11,12,13,14,15]:
    doc[number].get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(OUT/f'pdf-{number+1:02}.png')
report={'website_status':resp.status,'javascript_errors':errors,'missing_anchors':missing_anchors,'desktop_overflow':desktop_overflow,'mobile_overflow':mobile_overflow,'chart_switches':[dynamic,static],'interactive_example':example,'paper_layout':paper_measurements,'pdf_pages':len(doc),'pdf_chars_per_page':[len(t) for t in pdf_text],'new_solver_runs':0,'new_training_runs':0}
(OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if errors or missing_anchors or desktop_overflow or mobile_overflow or any(x['overlap'] for x in paper_measurements):raise SystemExit('Presentation QA requires correction')
