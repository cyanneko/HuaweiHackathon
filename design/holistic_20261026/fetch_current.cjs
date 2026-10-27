const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const dir=__dirname;const url='https://www.chaspark.com/#/races/competitions/1326693349800046592';
 const api='https://www.chaspark.com/chasiwu/v1/content/races/question/detail/1326693349800046592?seat=1&lang=zh';
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const ctx=await browser.newContext({locale:'zh-CN'});const page=await ctx.newPage();
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
  const r=await ctx.request.get(api,{timeout:60000});const data=await r.json();
  if(!data.data?.content)throw new Error('No public problem content: '+JSON.stringify({status:r.status(),code:data.code}));
  fs.writeFileSync(path.join(dir,'topic_20_current.json'),JSON.stringify(data,null,2));
  fs.writeFileSync(path.join(dir,'topic_20_current.html'),data.data.content);
  const text=await page.evaluate(html=>{const d=document.createElement('div');d.innerHTML=html.replace(/<\/(p|div|tr|li|h[1-6]|pre)>/gi,'</$1>\n').replace(/<br\s*\/?\s*>/gi,'\n');return d.textContent;},data.data.content);
  fs.writeFileSync(path.join(dir,'topic_20_current.txt'),text);
  fs.writeFileSync(path.join(dir,'fetch_provenance.json'),JSON.stringify({url,api,public_unauthenticated:true,fetched_at:new Date().toISOString(),http_status:r.status(),code:data.code,title:data.data.title,content_sha256:crypto.createHash('sha256').update(data.data.content).digest('hex'),metadata_keys:Object.keys(data.data),attachments:data.data.attachments||[]},null,2));
  console.log(JSON.stringify({status:r.status(),title:data.data.title,content_chars:data.data.content.length,metadata_keys:Object.keys(data.data),attachments:data.data.attachments||[]},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
