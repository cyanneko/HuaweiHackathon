from pathlib import Path
from PIL import Image,ImageDraw
from pypdf import PdfReader
import pdfplumber,json
ROOT=Path(__file__).resolve().parent
pdf=ROOT.parent/'topic20_holistic_iteration_report.pdf'
reader=PdfReader(pdf);assert len(reader.pages)==13
checks=[]
with pdfplumber.open(pdf) as doc:
    for i,page in enumerate(doc.pages,1):
        txt=page.extract_text();assert txt and '\ufffd' not in txt
        body=[c for c in page.chars if c['top']<790]
        assert all(c['x0']>=44 and c['x1']<=552 and c['top']>=35 and c['bottom']<=782 for c in body),(i,[(c['text'],c['x0'],c['top']) for c in body if c['x0']<44 or c['x1']>552 or c['bottom']>782][:4])
        checks.append(dict(page=i,chars=len(page.chars),last_body_bottom=max(c['bottom'] for c in body)))
thumbs=[]
for i,p in enumerate(sorted(ROOT.glob('report-page-*.png')),1):
    im=Image.open(p).convert('RGB');im.thumbnail((259,367));tile=Image.new('RGB',(279,397),'#dce5e9');tile.paste(im,((279-im.width)//2,10));ImageDraw.Draw(tile).text((12,379),f'Page {i}',fill='black');thumbs.append(tile)
sheet=Image.new('RGB',(279*4,397*4),'white')
for i,im in enumerate(thumbs):sheet.paste(im,((i%4)*279,(i//4)*397))
sheet.save(ROOT/'report-contact.png')
(ROOT/'report_qa.json').write_text(json.dumps(dict(pages=13,bounds_checked=True,checks=checks),indent=2))
print('13 pages, text and bounds passed; contact sheet ready.')
