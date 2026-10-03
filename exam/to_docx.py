"""Export the editable course handbook from exam/content.json.

Each chapter starts a new A4 page. Word remains the editable source;
from_docx.py imports subsequent edits into the printable HTML handbook.
"""
from pathlib import Path
import json
import re

from docx import Document
from docx.shared import Pt, Mm, RGBColor
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_DIRECTION, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
COURSE = REPO.parent
DATA = json.loads((HERE/'content.json').read_text(encoding='utf-8'))
RICH = re.compile(r'(\*\*.+?\*\*|__.+?__|«.+?»|⟨.+?⟩)')
LTR = re.compile(r'\d+[−\-][A-Za-z]+|[A-Za-z][A-Za-z0-9 .,&=−–\-]*(?:[A-Za-z0-9])|[A-Za-z]|\d+(?:[.,−–\-=]\d+)*')

def rtl(par):
    pr = par._p.get_or_add_pPr()
    if pr.find(qn('w:bidi')) is None:
        pr.append(OxmlElement('w:bidi'))
    par.alignment = WD_ALIGN_PARAGRAPH.RIGHT

def add_piece(par, text, size, bold, left=False):
    if not text: return
    run = par.add_run(('\u200e'+text+'\u200e') if left else text)
    run.bold = bold
    run.font.name = 'Arial'
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    run.font.rtl = not left
    run._r.get_or_add_rPr().rFonts.set(qn('w:cs'), 'Arial')
    complex_size = OxmlElement('w:szCs')
    complex_size.set(qn('w:val'), str(int(size*2)))
    run._r.rPr.append(complex_size)

def rich(par, text, size=11, force_bold=False):
    text = re.sub(r'\s*⟦[^⟧]*⟧', '', str(text))
    text = text.replace('\u200e', '').replace('\u200f', '')
    for token in RICH.split(text):
        if not token: continue
        bold = force_bold
        if token.startswith('**') or token.startswith('__'):
            token, bold = token[2:-2], True
        elif token.startswith('«'):
            token = '"'+token[1:-1]+'"'
        elif token.startswith('⟨'):
            add_piece(par, token[1:-1], size, bold, True)
            continue
        pos = 0
        for match in LTR.finditer(token):
            add_piece(par, token[pos:match.start()], size, bold)
            add_piece(par, match.group(), size, bold, True)
            pos = match.end()
        add_piece(par, token[pos:], size, bold)

def configure(sec):
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.top_margin, sec.bottom_margin = Mm(14), Mm(13)
    sec.left_margin, sec.right_margin = Mm(11), Mm(11)
    sec.header_distance, sec.footer_distance = Mm(5), Mm(5)
    cols = sec._sectPr.find(qn('w:cols'))
    cols.set(qn('w:num'), '2')
    cols.set(qn('w:space'), '340')
    if sec._sectPr.find(qn('w:bidi')) is None:
        sec._sectPr.append(OxmlElement('w:bidi'))

def fill(cell, shade):
    pr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement('w:shd'); sh.set(qn('w:fill'), shade); pr.append(sh)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    margins = OxmlElement('w:tcMar')
    for key, value in [('top',45),('bottom',45),('left',65),('right',65)]:
        e = OxmlElement('w:'+key); e.set(qn('w:w'),str(value)); e.set(qn('w:type'),'dxa'); margins.append(e)
    pr.append(margins)

doc = Document()
for style in doc.styles:
    for border in style._element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
normal = doc.styles['Normal']
normal.font.name = 'Arial'; normal.font.size = Pt(11)
normal._element.get_or_add_rPr().rFonts.set(qn('w:cs'), 'Arial')
normal.paragraph_format.space_after = Pt(3)
normal.paragraph_format.line_spacing = 1.04
for name in ['Title', 'Heading 1', 'Heading 2']:
    doc.styles[name].font.name = 'Arial'
    doc.styles[name].font.color.rgb = RGBColor(0,0,0)
doc.core_properties.title = 'חומר פתוח למבחן במנהיגות בניהול אנשים'
doc.core_properties.author = 'Codex'
doc.core_properties.subject = 'מצגות ושאלוני קורס 111762 בבר אילן'

for i, section in enumerate(DATA['sections']):
    sec = doc.sections[0] if i == 0 else doc.add_section(WD_SECTION.CONTINUOUS)
    if i:
        doc.add_page_break()
    configure(sec)
    sec.header.is_linked_to_previous = False
    header = sec.header.paragraphs[0]; rtl(header)
    rich(header, 'מנהיגות בניהול אנשים   '+section['name'], 8.5)
    sec.footer.is_linked_to_previous = False
    footer = sec.footer.paragraphs[0]; rtl(footer)
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rich(footer, 'עמוד ', 8.5)
    field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
    rich(footer, ' מתוך ', 8.5)
    field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'NUMPAGES'); footer._p.append(field)
    if i == 0:
        title = doc.add_paragraph(style='Title'); rtl(title)
        rich(title, 'חומר פתוח למבחן במנהיגות בניהול אנשים', 14, True)
        sub = doc.add_paragraph(); rtl(sub)
        rich(sub, 'בר אילן   עדכון '+DATA.get('updated','1.10.2026')+'   5 דפים דו־צדדיים', 8.5)
    heading = doc.add_paragraph(style='Heading 1'); rtl(heading)
    rich(heading, section['name'], 12.5, True)
    heading.paragraph_format.space_before = Pt(2)
    heading.paragraph_format.space_after = Pt(5)
    for block in section['blocks']:
        if 'h2' in block and 'חמשת הגורמים ושאלון' in block['h2']:
            from docx.enum.text import WD_BREAK
            doc.add_paragraph().add_run().add_break(WD_BREAK.COLUMN)
        if 'tbl' in block:
            spec = block['tbl']; n = len(spec['head'])
            tab = doc.add_table(rows=0, cols=n)
            tab.autofit = False; tab.table_direction = WD_TABLE_DIRECTION.RTL
            pr = tab._tbl.tblPr
            width = pr.find(qn('w:tblW')); width.set(qn('w:w'),'5160'); width.set(qn('w:type'),'dxa')
            proportions = {2:[.30,.70],3:[.22,.39,.39],4:[.17,.25,.29,.29],5:[.16,.21,.21,.21,.21]}.get(n,[1/n]*n)
            for col, proportion in zip(tab.columns, proportions): col.width = Mm(91*proportion)
            borders = OxmlElement('w:tblBorders')
            for edge in ['top','left','bottom','right','insideH','insideV']:
                e = OxmlElement('w:'+edge); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
            pr.append(borders)
            for row_index, values in enumerate([spec['head']]+spec['rows']):
                row = tab.add_row()
                trpr = row._tr.get_or_add_trPr(); trpr.append(OxmlElement('w:cantSplit'))
                if row_index == 0: trpr.append(OxmlElement('w:tblHeader'))
                for cell, value, proportion in zip(row.cells, values, proportions):
                    cell.width = Mm(91*proportion)
                    fill(cell, 'E8EDF1' if row_index == 0 else ('F6F8FA' if row_index%2==0 else 'FFFFFF'))
                    cp = cell.paragraphs[0]; rtl(cp)
                    cp.paragraph_format.space_after = Pt(0)
                    rich(cp, value, 9.5, row_index==0)
            after = doc.add_paragraph(); after.paragraph_format.space_after = Pt(0)
        elif 'h2' in block or 'h3' in block:
            par = doc.add_paragraph(style='Heading 2'); rtl(par)
            rich(par, block.get('h2') or block['h3'], 10.5, True)
            par.paragraph_format.space_before = Pt(5); par.paragraph_format.space_after = Pt(3)
        elif 'items' in block:
            for entry in block['items']:
                head, sep, body = entry.partition(' :: ')
                par = doc.add_paragraph(); rtl(par)
                rich(par, '▪ '+head, 11, True)
                if sep: rich(par, ' — '+body, 11)
        else:
            par = doc.add_paragraph(); rtl(par)
            rich(par, block.get('p') or block.get('warn',''), 11)

# End the final chapter with a continuous break to balance its two columns.
doc.add_section(WD_SECTION.CONTINUOUS)
from navigation import apply_navigation
apply_navigation(doc, DATA)
for path in [REPO/'חומר פתוח - מנהיגות בניהול.docx', COURSE/'חומר פתוח - מנהיגות בניהול.docx']:
    doc.save(path)
    print('נכתב:', path)
