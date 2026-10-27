import json
from pathlib import Path
from PIL import Image,ImageDraw
from pypdf import PdfReader
import pdfplumber
ROOT=Path(__file__).resolve().parent
pdf=ROOT.parent/'topic20_decision_cpu_report.pdf'
r=PdfReader(pdf);assert len(r.pages)==7
texts=[p.extract_text() for p in r.pages];assert all(len(t)>200 for t in texts)
assert '1.58%' in ''.join(texts)
with pdfplumber.open(pdf) as d:
    for p in d.pages:
        assert all(c['x0']>=35 and c['x1']<=560 and c['top']>=25 and c['bottom']<=820 for c in p.chars),p.page_number
files=sorted(ROOT.glob('report_page-*.png'));assert len(files)==7
im=Image.new('RGB',(860,4*620),'#dce5eb');draw=ImageDraw.Draw(im)
for i,f in enumerate(files):
    p=Image.open(f).convert('RGB');p.thumbnail((410,580));x=i%2*430+10;y=i//2*620+25
    im.paste(p,(x,y));draw.text((x,y-18),str(i+1),fill='#183149')
im.save(ROOT/'report_contact.png')
(ROOT/'pdf_checks.json').write_text(json.dumps(dict(pages=7,text_bounds_ok=True,rendered_pages=7,page_text_lengths=list(map(len,texts))),indent=2))
print('PDF text/render/bounds checks passed.')
