"""Render the companion Markdown using markdown-it-py and ReportLab; no network access."""
from pathlib import Path
from html import escape
import re
from markdown_it import MarkdownIt
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent
pdfmetrics.registerFont(TTFont('CJK', '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'))
pdfmetrics.registerFont(TTFont('Mono', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'))
styles = {
    'body': ParagraphStyle('body', fontName='CJK', fontSize=9, leading=14, spaceAfter=6, wordWrap='CJK'),
    'quote': ParagraphStyle('quote', fontName='CJK', fontSize=8.5, leading=13, leftIndent=10, borderPadding=6, backColor=colors.HexColor('#edf4fa'), spaceAfter=8, wordWrap='CJK'),
    'code': ParagraphStyle('code', fontName='CJK', fontSize=6.5, leading=9, spaceAfter=0, wordWrap='CJK'),
    'cell': ParagraphStyle('cell', fontName='CJK', fontSize=7.5, leading=11, wordWrap='CJK'),
}
for level in range(1, 5):
    styles[f'h{level}'] = ParagraphStyle(f'h{level}', fontName='CJK', fontSize={1:18,2:14,3:11,4:10}[level], leading=22 if level==1 else 18, spaceBefore=12, spaceAfter=8, keepWithNext=True, wordWrap='CJK')

def fontify(text):
    runs=[]
    for char in text:
        font = 'CJK' if ord(char)>127 and ord(char) in pdfmetrics.getFont('CJK').face.charToGlyph else 'Mono'
        if runs and runs[-1][0]==font:
            runs[-1]=(font,runs[-1][1]+char)
        else:
            runs.append((font,char))
    return ''.join('<font name="'+font+'">'+escape(value)+'</font>' for font,value in runs)


def inline(token):
    # Text stays selectable; code identifiers use the same font to retain Chinese comments.
    result=[]
    for child in token.children or []:
        if child.type in ('text','code_inline'): result.append(fontify(child.content))
        elif child.type=='softbreak': result.append('<br/>')
        elif child.type=='hardbreak': result.append('<br/>')
        # Link text remains visible; do not emit nested HTML or source-page artifacts.
    return ''.join(result)

tokens=MarkdownIt('commonmark').enable('table').parse((ROOT/'STATEMENT_ENHANCED.md').read_text())
story=[]; quote=0; heading=None; table=None; row=None; i=0
for token in tokens:
    typ=token.type
    if typ=='blockquote_open': quote+=1
    elif typ=='blockquote_close': quote-=1
    elif typ=='heading_open': heading=token.tag
    elif typ=='heading_close': heading=None
    elif typ=='table_open': table=[]
    elif typ=='tr_open': row=[]
    elif typ=='tr_close': table.append(row); row=None
    elif typ=='table_close':
        width=A4[0]-80
        t=Table(table, colWidths=[width/len(table[0])]*len(table[0]), repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4ebf1')),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#bac5cf')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
        story.extend([t,Spacer(1,8)]);table=None
    elif typ=='inline':
        if table is not None: row.append(Paragraph(inline(token),styles['cell']))
        else: story.append(Paragraph(inline(token),styles[heading or ('quote' if quote else 'body')]))
    elif typ=='fence':
        story.append(Spacer(1,6))
        for line in token.content.splitlines():
            # Keep indentation and wrap long C++ lines rather than clip them at the page edge.
            n=len(line)-len(line.lstrip(' '))
            content='&#160;'*n+fontify(line[n:])
            story.append(Paragraph(content or '&#160;', styles['code']))
        story.append(Spacer(1,8))

def page(canvas, doc):
    canvas.saveState();canvas.setFont('CJK',7)
    canvas.drawString(40,22,'题面个人补充版')
    canvas.setFont('Mono',7)
    canvas.drawRightString(A4[0]-40,22,str(doc.page));canvas.restoreState()

SimpleDocTemplate(str(ROOT/'STATEMENT_ENHANCED.pdf'), pagesize=A4, rightMargin=40,leftMargin=40,topMargin=35,bottomMargin=35,title='Hash Join Spill-to-Disk 题面个人补充版',author='Vanius0525').build(story,onFirstPage=page,onLaterPages=page)
