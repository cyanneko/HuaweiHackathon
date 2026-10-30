"""Bundle the demonstration, Chinese font, interaction data and reading PDF in one HTML."""
from pathlib import Path
import base64,re,json,zipfile
ROOT=Path(__file__).parent
D=ROOT/'dist'
def uri(path,mime):return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()
def build_offline():
 html=(D/'index.html').read_text()
 css=(D/'assets/demo.css').read_text().replace('url(Chinese.ttf)', 'url('+uri(D/'assets/Chinese.ttf','font/ttf')+')')
 html=html.replace('<link rel="stylesheet" href="assets/demo.css">','<style>'+css+'</style>')
 html=html.replace('assets/mark.svg',uri(D/'assets/mark.svg','image/svg+xml'))
 js=(D/'assets/demo.js').read_text()
 html=html.replace('<script src="assets/demo.js" defer></script>','<script>'+js+'</script>')
 html=re.sub(r'<a class="offline-link" data-offline-download[^>]*>.*?</a>','<span class="offline-link">离线演示 · 可直接分享</span>',html)
 html=re.sub(r'<a class="quiet-link"[^>]*data-technical-link>.*?</a>','<span class="quiet-link">正文与交互均可离线使用</span>',html)
 pdf=base64.b64encode((D/'HashJoin-R81-Reading-Guide.pdf').read_bytes()).decode()
 loader='''<script id="offline-pdf" type="application/octet-stream">'''+pdf+'''</script><script>
const bytes=Uint8Array.from(atob(document.getElementById('offline-pdf').textContent.trim()),c=>c.charCodeAt(0));
const pdfURL=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'}));
document.querySelectorAll('[data-reference-pdf]').forEach(a=>{a.href=pdfURL;a.download='HashJoin-R81-Reading-Guide.pdf';});
</script>'''
 html=html.replace('</body>',loader+'</body>')
 license=(D/'assets/font-LICENSE.txt').read_text().replace('--','—')
 html=html.replace('</head>','<!-- Embedded font license: '+license+' -->\n</head>')
 out=D/'HashJoin-Team19-Demo.html';out.write_text(html,encoding='utf-8')
 with zipfile.ZipFile(D/'HashJoin-Team19-Demo.zip','w') as z:
  entry=zipfile.ZipInfo(out.name,date_time=(2026,10,31,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(entry,out.read_bytes())
 return out
if __name__=='__main__':print(build_offline())
