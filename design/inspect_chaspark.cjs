const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const out='C:/Users/liunian/Desktop/Hackathon20/design/website_research';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1400,height:1000}});
 const responses=[];const tasks=[];
 page.on('response',r=>{if(['xhr','fetch'].includes(r.request().resourceType()))tasks.push((async()=>{try{const ct=r.headers()['content-type']||'';if(ct.includes('json'))responses.push({url:r.url(),status:r.status(),body:await r.json()});}catch{}})());});
 await page.goto(process.argv[2]||'https://www.chaspark.com/#/s/2026Hackathon?multi=zh',{waitUntil:'domcontentloaded',timeout:60000});
 await page.waitForTimeout(15000);
 const t=await page.locator('body').innerText();fs.writeFileSync(out+'/directory.txt',t);
 fs.writeFileSync(out+'/links.json',JSON.stringify(await page.locator('a').evaluateAll(as=>as.map(a=>({text:a.innerText,url:a.href}))),null,2));
 await page.screenshot({path:out+'/directory.png',fullPage:true});
 await Promise.allSettled(tasks);fs.writeFileSync(out+'/responses.json',JSON.stringify(responses,null,2));
 console.log(t.slice(0,16000));console.log('JSON responses',responses.length,responses.map(r=>r.url));await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
