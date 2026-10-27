import hashlib,json,re
from pathlib import Path
from PIL import Image,ImageDraw
from pypdf import PdfReader
import pdfplumber
ROOT=Path(__file__).resolve().parent
pub=json.loads((ROOT/'published_sources.json').read_text());freeze=json.loads((ROOT/'refined_freeze.json').read_text())['sources']
assert hashlib.sha256((ROOT.parent/pub['primary']).read_bytes()).hexdigest()==freeze['MySpillScheduler_gated.cpp']
assert hashlib.sha256((ROOT.parent/pub['alternate']).read_bytes()).hexdigest()==freeze['SafeBase.cpp']
assert (ROOT.parent/pub['primary']).read_bytes()==(ROOT/'MySpillScheduler_gated.cpp').read_bytes()
assert (ROOT.parent/pub['alternate']).read_bytes()==(ROOT/'SafeBase.cpp').read_bytes()
pdf=ROOT.parent/'topic20_joint_iteration_report.pdf';r=PdfReader(pdf);assert len(r.pages)==9
text=[x.extract_text() for x in r.pages];assert all(len(x)>200 for x in text)
assert '5.41%' in ''.join(text) and '7.88%' in ''.join(text)
assert not any(x in ''.join(text) for x in ['TODO','PLACEHOLDER','turn656','turn296'])
with pdfplumber.open(pdf) as d:
    for page in d.pages:
        assert all(c['x0']>=35 and c['x1']<=560 and c['top']>=25 and c['bottom']<=820 for c in page.chars),page.page_number
paths=sorted(ROOT.glob('report_page-*.png'));assert len(paths)==9
im=Image.new('RGB',(860,5*620),'#dce5eb');draw=ImageDraw.Draw(im)
for i,f in enumerate(paths):
    p=Image.open(f).convert('RGB');p.thumbnail((410,580));x=i%2*430+10;y=i//2*620+25;im.paste(p,(x,y));draw.text((x,y-18),str(i+1),fill='#183149')
im.save(ROOT/'report_contact.png')
out=dict(primary=pub['primary'],primary_sha256=pub['source_sha256'],alternate=pub['alternate'],frozen_sources_match_delivery=True,
 pdf_pages=9,page_bounds_ok=True,rendered_pages=9,page_text_lengths=list(map(len,text)))
(ROOT/'output_checks.json').write_text(json.dumps(out,indent=2));print(out)
