import json
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
from pypdf import PdfReader
import pdfplumber
ROOT=Path(__file__).resolve().parent
pdf=ROOT.parent/'topic20_original_contributions_20261026.pdf'
r=PdfReader(pdf);assert len(r.pages)==10
page_text=[p.extract_text() for p in r.pages]
assert all(len(t)>200 for t in page_text)
assert '10059.64' in ''.join(page_text) and '6400' in ''.join(page_text)
assert not any(x in ''.join(page_text) for x in ['turn296','turn656','TODO','PLACEHOLDER'])
with pdfplumber.open(pdf) as doc:
    for p in doc.pages:
        assert all(c['x0']>=35 and c['x1']<=560 and c['top']>=25 and c['bottom']<=820 for c in p.chars),(p.page_number,'bounds')
files=sorted(ROOT.glob('report_page-*.png'));assert len(files)==10
sheet=Image.new('RGB',(860,5*620),'#dce5eb');draw=ImageDraw.Draw(sheet)
for i,path in enumerate(files):
    img=Image.open(path).convert('RGB');img.thumbnail((410,580));x=(i%2)*430+10;y=(i//2)*620+25
    sheet.paste(img,(x,y));draw.text((x,y-18),f'Page {i+1}',fill='#173047')
sheet.save(ROOT/'report_contact.png')
(ROOT/'pdf_checks.json').write_text(json.dumps(dict(pages=10,page_text_lengths=list(map(len,page_text)),all_text_in_page_bounds=True,rendered_pages=10),indent=2))
print('PDF text/bounds/render checks passed; inspect contact sheet and detail pages.')
if __name__=='__main__':pass
