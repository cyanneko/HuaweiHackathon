const fs=require('fs');
const path=require('path');
const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=__dirname;
(async()=>{
 const exe=['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,...(exe?{executablePath:exe}:{})});
 const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
 const page=await ctx.newPage();const requests=[];const pending=[];
 page.on('response',r=>{
  const ct=r.headers()['content-type']||'';
  if(ct.includes('json') && r.url().includes('chaspark')){
   const n=requests.length;requests.push({index:n,url:r.url(),status:r.status()});
   pending.push(r.text().then(x=>fs.writeFileSync(path.join(root,`response_${n}.json`),x)).catch(()=>{}));
  }
 });
 await page.goto('https://www.chaspark.com/#/s/2026Hackathon?multi=zh',{waitUntil:'domcontentloaded',timeout:60000});
 await page.waitForTimeout(10000);
 fs.writeFileSync(path.join(root,'event_body.txt'),await page.locator('body').innerText());
 fs.writeFileSync(path.join(root,'event_html.html'),await page.content());
 fs.writeFileSync(path.join(root,'event_links.json'),JSON.stringify(await page.locator('a').evaluateAll(as=>as.map(a=>({text:a.innerText,href:a.href}))),null,2));
 await page.screenshot({path:path.join(root,'event.png'),fullPage:true});
 await Promise.allSettled(pending);
 fs.writeFileSync(path.join(root,'network_index.json'),JSON.stringify(requests,null,2));
 console.log((await page.locator('body').innerText()).slice(0,14000));
 console.log('Public JSON responses saved:',requests.length);
 await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
