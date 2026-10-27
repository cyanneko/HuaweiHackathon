const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const ctx=await browser.newContext({locale:'zh-CN'});const page=await ctx.newPage();
 await page.goto('https://www.chaspark.com/#/s/2026Hackathon?multi=zh',{waitUntil:'domcontentloaded',timeout:60000});
 await page.waitForTimeout(3000);
 const endpoint='https://www.chaspark.com/chasiwu/v1/content/page/manual/list?current=1&slotId=1326689542378647554&size=100&isAutoSet=false&minutesType=0&follow=0&channel=0&lang=zh';
 const r=await ctx.request.get(endpoint);const data=await r.json();
 fs.writeFileSync(path.join(__dirname,'all_topics_list.json'),JSON.stringify(data,null,2));
 const rows=data.data.records;console.log('Topics:',rows.length,'Total:',data.data.total);
 console.log(rows.map(x=>({id:x.contentId,title:x.customTitle?.zh||x.title})));
 const req=[],pending=[];
 page.on('response',r=>{if(r.url().includes('/chasiwu/')&&(r.headers()['content-type']||'').includes('json')){
  const i=req.length;req.push({index:i,url:r.url(),status:r.status()});
  pending.push(r.text().then(t=>fs.writeFileSync(path.join(__dirname,`first_${i}.json`),t)).catch(()=>{}));
 }});
 await page.goto(rows[0].detailUrl,{waitUntil:'domcontentloaded',timeout:60000});
 await page.waitForTimeout(6000);
 fs.writeFileSync(path.join(__dirname,'first_topic_body.txt'),await page.locator('body').innerText());
 await Promise.allSettled(pending);fs.writeFileSync(path.join(__dirname,'first_topic_requests.json'),JSON.stringify(req,null,2));
 console.log((await page.locator('body').innerText()).slice(0,14000));
 await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
