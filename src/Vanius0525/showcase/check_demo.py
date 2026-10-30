"""Check local-file/offline behavior and the concise site's layout. No algorithm runs."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib,json
ROOT=Path(__file__).parent
OUT=ROOT/'qa/v3';OUT.mkdir(parents=True,exist_ok=True)
file=ROOT/'dist/HashJoin-Team19-Demo.html'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 context=browser.new_context(offline=True,accept_downloads=True,viewport={'width':1440,'height':1000})
 page=context.new_page();errors=[];network=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:network.append(r.url) if r.url.startswith(('https://','http://')) else None)
 page.goto(file.as_uri(),wait_until='load');page.evaluate('document.fonts.ready')
 page.screenshot(path=str(OUT/'demo-desktop.png'))
 assert page.locator('main section[id]').count()==5
 missing=page.evaluate("[...document.querySelectorAll('a[href^=\"#\"]')].map(a=>a.hash).filter(h=>h&&!document.getElementById(h.slice(1)))")
 assert not missing,missing
 assert page.locator('.heat-cell').count()==24
 before=page.locator('.heat-cell').all_text_contents()
 page.locator('#change-time').click();assert page.locator('.heat-cell').all_text_contents()!=before
 page.locator('[data-dataset="final"]').click();before=page.locator('.heat-cell').all_text_contents()
 page.locator('#change-time').click();assert page.locator('.heat-cell').all_text_contents()==before
 page.locator('[data-dataset="stat"]').click();before=page.locator('.heat-cell').all_text_contents()
 page.locator('#change-time').click();assert page.locator('.heat-cell').all_text_contents()!=before
 page.locator('#operator-prob').fill('50');assert page.locator('#joint-answer').inner_text()=='15%'
 page.locator('[data-metric="score"]').click();assert page.locator('.result-value').all_text_contents()==['4.4558','3.7132','3.4398']
 page.locator('[data-metric="cost"]').click();assert page.locator('.result-value').all_text_contents()==['44.56%','35.51%','34.40%']
 for item in page.locator('details').all():
  item.locator('summary').click();assert item.get_attribute('open') is not None
  item.locator('summary').click();assert item.get_attribute('open') is None
 desktop_overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
 with page.expect_download() as event:page.locator('[data-reference-pdf]').click()
 download=event.value;download.save_as(OUT/'offline-reading.pdf')
 assert hashlib.sha256((OUT/'offline-reading.pdf').read_bytes()).hexdigest()==hashlib.sha256((ROOT/'dist/HashJoin-R81-Reading-Guide.pdf').read_bytes()).hexdigest()
 for key in ['journey','datasets','method','evidence']:page.locator('#'+key).screenshot(path=str(OUT/f'demo-{key}.png'))
 length=page.locator('main').inner_text();collapsed_chars=len(length)
 page.set_viewport_size({'width':390,'height':844});page.goto(file.as_uri(),wait_until='load');page.evaluate('document.fonts.ready')
 mobile_overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
 page.screenshot(path=str(OUT/'demo-mobile.png'))
 page.locator('#method').screenshot(path=str(OUT/'demo-mobile-method.png'))
 page.locator('#evidence').screenshot(path=str(OUT/'demo-mobile-evidence.png'))
 # Also validate the ordinary multi-file build from file://, without a server.
 page.goto((ROOT/'dist/index.html').as_uri(),wait_until='load');page.evaluate('document.fonts.ready')
 page.locator('[data-metric="score"]').click();assert page.locator('.result-value').first.inner_text()=='4.4558'
 browser.close()
report={'standalone_file':'dist/HashJoin-Team19-Demo.html','bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'browser_mode':'file:// with network offline','sections':5,'visible_main_chars':collapsed_chars,'js_errors':errors,'http_requests':network,'missing_anchors':missing,'desktop_overflow':desktop_overflow,'mobile_overflow':mobile_overflow,'dataset_time_switches':'passed; final distribution remains fixed','probability_slider':'50% × 30% = 15%','metric_switch':'passed','detail_expansion':'passed','embedded_pdf_download':'passed, byte-identical to original','multi_file_version':'passed offline','new_algorithm_runs':0}
(OUT/'demo-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
assert not errors and not network and not desktop_overflow and not mobile_overflow,report
