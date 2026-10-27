const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/liunian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const ctx=await browser.newContext({locale:'zh-CN'});
 const list=JSON.parse(fs.readFileSync(path.join(__dirname,'all_topics_list.json'),'utf8')).data.records;
 let pos=0;const index=[];
 async function worker(){
  while(pos<list.length){
   const i=pos++,row=list[i],n=String(i+1).padStart(2,'0');
   const url=`https://www.chaspark.com/chasiwu/v1/content/races/question/detail/${row.contentId}?seat=1&lang=zh`;
   const r=await ctx.request.get(url,{timeout:60000});const data=await r.json();
   fs.writeFileSync(path.join(__dirname,`topic_${n}.json`),JSON.stringify(data,null,2));
   fs.writeFileSync(path.join(__dirname,`topic_${n}.html`),data.data?.content||'');
   index.push({number:i+1,id:row.contentId,title:data.data?.title,url:row.detailUrl,api:url,status:r.status(),code:data.code,attachments:data.data?.attachments||[]});
   console.log(n,row.customTitle?.zh,'characters',data.data?.content?.length||0);
  }
 }
 await Promise.all([worker(),worker(),worker(),worker()]);
 fs.writeFileSync(path.join(__dirname,'topic_index.json'),JSON.stringify(index.sort((a,b)=>a.number-b.number),null,2));
 await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
