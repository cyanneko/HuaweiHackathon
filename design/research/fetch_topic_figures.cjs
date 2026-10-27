const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const ctx=await browser.newContext();const page=await ctx.newPage();
 const nums=process.argv.slice(2).map(Number);const jobs=[];
 fs.mkdirSync(path.join(__dirname,'figures'),{recursive:true});
 for(const n of nums){
  const html=fs.readFileSync(path.join(__dirname,`topic_${String(n).padStart(2,'0')}.html`),'utf8');
  // Parse the public content without running any embedded scripts.
  await page.setContent('<!doctype html><body></body>');
  const srcs=await page.evaluate(x=>{const d=new DOMParser().parseFromString(x,'text/html');return [...d.querySelectorAll('img')].map(i=>i.getAttribute('src'));},html);
  srcs.forEach((url,i)=>jobs.push({number:n,index:i+1,url,file:`figures/t${String(n).padStart(2,'0')}_${String(i+1).padStart(2,'0')}.png`}));
 }
 let pos=0;
 async function worker(){while(pos<jobs.length){const j=jobs[pos++];try{
  const r=await ctx.request.get(j.url,{timeout:30000});j.status=r.status();
  if(r.ok()){fs.writeFileSync(path.join(__dirname,j.file),await r.body());j.saved=true;}
 }catch(e){j.error=e.message;}}}
 await Promise.all([worker(),worker(),worker(),worker()]);
 fs.writeFileSync(path.join(__dirname,'figure_index.json'),JSON.stringify(jobs,null,2));
 console.log('Figures saved:',jobs.filter(x=>x.saved).length,'/',jobs.length);
 await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
