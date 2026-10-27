const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const out='C:/Users/liunian/Desktop/Hackathon20/design/website_research';
 const list=JSON.parse(fs.readFileSync(out+'/all_topics.json','utf8')).data.records;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage();await page.goto('https://www.chaspark.com/',{waitUntil:'domcontentloaded'});
 const summary=[];
 for(let i=0;i<list.length;i+=4){
  const batch=list.slice(i,i+4);
  const results=await page.evaluate(async xs=>Promise.all(xs.map(async x=>{
   try{const response=await fetch('/chasiwu/v1/content/races/question/detail/'+x.contentId+'?seat=1&lang=zh');
    const body=await response.json();const d=body.data;if(!d?.content)return {id:x.contentId,title:x.title,error:body.message};
    const doc=new DOMParser().parseFromString(d.content,'text/html');
    doc.querySelectorAll('br').forEach(e=>e.replaceWith('\n'));
    doc.querySelectorAll('p,h1,h2,h3,h4,li,tr,pre').forEach(e=>e.append('\n'));
    const text=doc.body.textContent.replace(/\n[ \t]*\n+/g,'\n\n');
    const images=[...doc.querySelectorAll('img')].map(e=>e.src);
    return {id:x.contentId,title:x.title,url:x.detailUrl,body,text,images};
   }catch(e){return {id:x.contentId,error:e.message}}})),batch);
  for(const r of results){const n=String(list.findIndex(x=>x.contentId===r.id)+1).padStart(2,'0');
   fs.writeFileSync(out+'/topic_'+n+'.json',JSON.stringify(r,null,2));
   if(r.text)fs.writeFileSync(out+'/topic_'+n+'.txt',r.text);
   summary.push({number:Number(n),id:r.id,title:r.title,url:r.url,chars:r.text?.length,images:r.images?.length,error:r.error});
  }
  console.log('Fetched',Math.min(i+4,list.length),'/',list.length);
 }
 fs.writeFileSync(out+'/details_inventory.json',JSON.stringify(summary,null,2));
 console.log('SUMMARY',summary);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
