from pathlib import Path
from html.parser import HTMLParser
import json,re
class Extract(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ['p','div','tr','li','h1','h2','h3','h4','br','table','pre']:self.parts.append('\n')
        if tag in ['td','th']:self.parts.append(' | ')
        d=dict(attrs)
        if tag=='img':self.parts.append('[图像:'+d.get('alt','')+']')
    def handle_endtag(self,tag):
        if tag in ['p','div','tr','li','h1','h2','h3','h4','table','pre']:self.parts.append('\n')
    def handle_data(self,d):self.parts.append(d)
p=Path(__file__).parent
for f in sorted(p.glob('topic_*.html')):
    ex=Extract();ex.feed(f.read_text(encoding='utf-8'))
    s=re.sub(r'\n[ \t\xa0]*\n(?:[ \t\xa0]*\n)*','\n\n',''.join(ex.parts))
    f.with_suffix('.txt').write_text(s,encoding='utf-8')
    print(f.stem,len(s))
