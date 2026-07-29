from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "SSP_Tulu四阶段实验方案_组会讨论稿.md"
OUTPUT = ROOT / "SSP_Tulu四阶段实验方案_组会讨论稿.docx"

# Named academic-report override: STSong is present in both the local Word
# environment and the headless LibreOffice QA environment, including CJK glyphs.
LATIN_FONT = "STSong"
CJK_FONT = "STSong"
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
INK = "1F2937"
MUTED = "667085"
LIGHT_GRAY = "F2F4F7"
CALLOUT = "F4F6F9"
BORDER = "C9CED6"
WHITE = "FFFFFF"

CONTENT_WIDTH_DXA = 9360
TABLE_INDENT_DXA = 120


def set_font(run, size=None, bold=None, italic=None, color=INK, font=LATIN_FONT):
    run.font.name = font
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), font)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), font)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), CJK_FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:cs"), CJK_FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_paragraph_border(paragraph, side, color, size=8, space=4):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    edge = p_bdr.find(qn(f"w:{side}"))
    if edge is None:
        edge = OxmlElement(f"w:{side}")
        p_bdr.append(edge)
    edge.set(qn("w:val"), "single")
    edge.set(qn("w:sz"), str(size))
    edge.set(qn("w:space"), str(space))
    edge.set(qn("w:color"), color)


def shade_paragraph(paragraph, fill):
    p_pr = paragraph._p.get_or_add_pPr()
    shd = p_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        p_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def add_page_field(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("第 ")
    set_font(run, size=9, color=MUTED)
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)
    tail = paragraph.add_run(" 页")
    set_font(tail, size=9, color=MUTED)


def add_hyperlink(paragraph, text, url, size=11, color=BLUE, bold=False):
    part = paragraph.part
    rel_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    r_fonts = OxmlElement("w:rFonts")
    r_fonts.set(qn("w:ascii"), LATIN_FONT)
    r_fonts.set(qn("w:hAnsi"), LATIN_FONT)
    r_fonts.set(qn("w:eastAsia"), CJK_FONT)
    r_fonts.set(qn("w:cs"), CJK_FONT)
    r_pr.append(r_fonts)
    color_el = OxmlElement("w:color")
    color_el.set(qn("w:val"), color)
    r_pr.append(color_el)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    r_pr.append(underline)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    r_pr.append(sz)
    if bold:
        r_pr.append(OxmlElement("w:b"))
    new_run.append(r_pr)
    text_el = OxmlElement("w:t")
    text_el.text = text
    new_run.append(text_el)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


INLINE_RE = re.compile(
    r"(\*\*.+?\*\*|`.+?`|\[[^\]]+\]\(https?://[^)]+\)|https?://[^\s，。；：）]+)"
)


def add_inline(paragraph, text, size=11, color=INK, bold=False):
    pos = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos : match.start()])
            set_font(run, size=size, bold=bold, color=color)
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_font(run, size=size, bold=True, color=color)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_font(run, size=max(size - 0.5, 8), color=DARK_BLUE, font=LATIN_FONT)
        elif token.startswith("["):
            label, url = re.match(r"\[([^\]]+)\]\((https?://[^)]+)\)", token).groups()
            add_hyperlink(paragraph, label, url, size=size)
        else:
            add_hyperlink(paragraph, token, token, size=size)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_font(run, size=size, bold=bold, color=color)


def configure_style(style, size, color, before, after, line=1.1, bold=False):
    style.font.name = LATIN_FONT
    style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), LATIN_FONT)
    style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), LATIN_FONT)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), CJK_FONT)
    style._element.get_or_add_rPr().rFonts.set(qn("w:cs"), CJK_FONT)
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor.from_string(color)
    fmt = style.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line
    fmt.keep_with_next = style.name.startswith("Heading")


def set_outline_level(style, level):
    p_pr = style._element.get_or_add_pPr()
    outline = p_pr.find(qn("w:outlineLvl"))
    if outline is None:
        outline = OxmlElement("w:outlineLvl")
        p_pr.append(outline)
    outline.set(qn("w:val"), str(level))


def add_numbering(doc, marker_type):
    numbering = doc.part.numbering_part.element
    abstract_ids = [
        int(el.get(qn("w:abstractNumId")))
        for el in numbering.findall(qn("w:abstractNum"))
    ]
    num_ids = [int(el.get(qn("w:numId"))) for el in numbering.findall(qn("w:num"))]
    abstract_id = max(abstract_ids, default=0) + 1
    num_id = max(num_ids, default=0) + 1

    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "singleLevel")
    abstract.append(multi)
    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    lvl.append(start)
    num_fmt = OxmlElement("w:numFmt")
    num_fmt.set(qn("w:val"), "bullet" if marker_type == "bullet" else "decimal")
    lvl.append(num_fmt)
    lvl_text = OxmlElement("w:lvlText")
    lvl_text.set(qn("w:val"), "•" if marker_type == "bullet" else "%1.")
    lvl.append(lvl_text)
    suff = OxmlElement("w:suff")
    suff.set(qn("w:val"), "tab")
    lvl.append(suff)
    p_pr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "num")
    tab.set(qn("w:pos"), "720")
    tabs.append(tab)
    p_pr.append(tabs)
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    ind.set(qn("w:hanging"), "360")
    p_pr.append(ind)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), "160")
    spacing.set(qn("w:line"), "280")
    spacing.set(qn("w:lineRule"), "auto")
    p_pr.append(spacing)
    lvl.append(p_pr)
    r_pr = OxmlElement("w:rPr")
    r_fonts = OxmlElement("w:rFonts")
    r_fonts.set(qn("w:ascii"), LATIN_FONT)
    r_fonts.set(qn("w:hAnsi"), LATIN_FONT)
    r_fonts.set(qn("w:eastAsia"), CJK_FONT)
    r_fonts.set(qn("w:cs"), CJK_FONT)
    r_pr.append(r_fonts)
    lvl.append(r_pr)
    abstract.append(lvl)
    numbering.append(abstract)

    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abs_id = OxmlElement("w:abstractNumId")
    abs_id.set(qn("w:val"), str(abstract_id))
    num.append(abs_id)
    numbering.append(num)
    return num_id


def apply_numbering(paragraph, num_id):
    p_pr = paragraph._p.get_or_add_pPr()
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num_pr.append(ilvl)
    num_id_el = OxmlElement("w:numId")
    num_id_el.set(qn("w:val"), str(num_id))
    num_pr.append(num_id_el)
    p_pr.append(num_pr)


def column_widths(headers):
    n = len(headers)
    joined = "|".join(headers)
    if headers[:2] == ["条件", "NTP"] and n == 5:
        return [900, 800, 800, 2100, 4760]
    if headers[:2] == ["条件", "MSE@1"] and n == 4:
        return [1500, 1600, 1600, 4660]
    if headers and headers[0] == "维度" and n == 4:
        return [1250, 2050, 2300, 3760]
    if headers and headers[0] == "条件" and "seed 42" in joined and n == 5:
        return [1500, 1700, 1900, 1900, 2360]
    if headers and headers[0] == "子研究" and n == 4:
        return [1900, 2200, 2400, 2860]
    if headers and headers[0] == "结果模式" and n == 3:
        return [2100, 3550, 3710]
    if headers and headers[0] == "风险" and n == 4:
        return [1700, 2100, 2850, 2710]
    if headers and headers[0] == "优先级" and n == 4:
        return [850, 3000, 2700, 2810]
    if headers and headers[0] == "阶段" and n == 3:
        return [2650, 2100, 4610]
    if n == 5:
        return [1400, 1400, 1400, 2200, 2960]
    if n == 4:
        return [1800, 2200, 2400, 2960]
    if n == 3:
        return [2200, 3200, 3960]
    total = CONTENT_WIDTH_DXA
    base = total // n
    widths = [base] * n
    widths[-1] += total - sum(widths)
    return widths


def set_table_geometry(table, widths):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(TABLE_INDENT_DXA))
    tbl_ind.set(qn("w:type"), "dxa")
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(width))
        grid.append(grid_col)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths[idx]))
            tc_w.set(qn("w:type"), "dxa")
            tc_mar = tc_pr.find(qn("w:tcMar"))
            if tc_mar is None:
                tc_mar = OxmlElement("w:tcMar")
                tc_pr.append(tc_mar)
            for side, value in [("top", 100), ("bottom", 100), ("start", 120), ("end", 120)]:
                el = tc_mar.find(qn(f"w:{side}"))
                if el is None:
                    el = OxmlElement(f"w:{side}")
                    tc_mar.append(el)
                el.set(qn("w:w"), str(value))
                el.set(qn("w:type"), "dxa")
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        tag = borders.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            borders.append(tag)
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), "4")
        tag.set(qn("w:space"), "0")
        tag.set(qn("w:color"), BORDER)


def repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_table(doc, rows):
    headers = rows[0]
    table = doc.add_table(rows=len(rows), cols=len(headers))
    widths = column_widths(headers)
    set_table_geometry(table, widths)
    set_table_borders(table)
    repeat_header(table.rows[0])

    for row_idx, row_data in enumerate(rows):
        for col_idx, value in enumerate(row_data):
            cell = table.cell(row_idx, col_idx)
            cell.text = ""
            if row_idx == 0:
                set_cell_shading(cell, LIGHT_GRAY)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            p.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER
                if row_idx == 0 or (len(value) <= 10 and col_idx > 0)
                else WD_ALIGN_PARAGRAPH.LEFT
            )
            add_inline(
                p,
                value,
                size=8.6 if len(headers) >= 4 else 9.2,
                color=DARK_BLUE if row_idx == 0 else INK,
                bold=row_idx == 0,
            )
    after = doc.add_paragraph()
    after.paragraph_format.space_before = Pt(0)
    after.paragraph_format.space_after = Pt(2)
    after.paragraph_format.line_spacing = 1
    return table


def configure_document():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    normal = doc.styles["Normal"]
    configure_style(normal, 11, INK, 0, 6, line=1.1)
    normal.paragraph_format.widow_control = True

    heading1 = doc.styles["Heading 1"]
    configure_style(heading1, 16, BLUE, 16, 8, line=1.05, bold=True)
    set_outline_level(heading1, 0)

    heading2 = doc.styles["Heading 2"]
    configure_style(heading2, 13, BLUE, 12, 6, line=1.05, bold=True)
    set_outline_level(heading2, 1)

    heading3 = doc.styles["Heading 3"]
    configure_style(heading3, 12, DARK_BLUE, 8, 4, line=1.05, bold=True)
    set_outline_level(heading3, 2)

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.space_after = Pt(0)
    hr = hp.add_run("组会讨论稿  |  SSP × Tulu-3 四阶段轨迹几何")
    set_font(hr, size=9, color=MUTED)

    footer = section.footer
    fp = footer.paragraphs[0]
    add_page_field(fp)

    props = doc.core_properties
    props.title = "基于语义步骤预测的 Tulu-3-8B 四阶段推理轨迹几何重组研究"
    props.subject = "SSP 复现与扩展实验方案（组会讨论稿）"
    props.author = "研究项目组"
    props.keywords = "SSP; STP; Tulu-3; RLVR; DPO; reasoning geometry"
    return doc


def add_opening(doc, lines):
    title = lines[0][2:].strip()
    subtitle = lines[2][3:].strip()

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(title)
    set_font(run, size=23, bold=True, color="17365D")

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run(subtitle)
    set_font(run, size=14, bold=True, color=BLUE)

    metadata = []
    callout = None
    for line in lines[3:]:
        line = line.strip()
        if line.startswith("**") and "：**" in line:
            label, value = line.split("：**", 1)
            metadata.append((label.replace("**", ""), value.strip()))
        elif line.startswith(">"):
            callout = line[1:].strip()

    for label, value in metadata:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(label + "：")
        set_font(r, size=10.5, bold=True, color=DARK_BLUE)
        add_inline(p, value, size=10.5)

    rule = doc.add_paragraph()
    rule.paragraph_format.space_before = Pt(8)
    rule.paragraph_format.space_after = Pt(12)
    set_paragraph_border(rule, "bottom", BLUE, size=10, space=2)

    if callout:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.16)
        p.paragraph_format.right_indent = Inches(0.1)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(12)
        p.paragraph_format.line_spacing = 1.15
        shade_paragraph(p, CALLOUT)
        set_paragraph_border(p, "left", BLUE, size=18, space=6)
        add_inline(p, callout, size=11, color=DARK_BLUE)


PAGE_BREAK_BEFORE = {
    "7. 风险、缓解措施与剩余不确定性",
    "9. 待导师讨论的问题",
    "11. 资料来源",
}


def build():
    raw_lines = SOURCE.read_text(encoding="utf-8").splitlines()
    split_idx = raw_lines.index("---")
    opening = raw_lines[:split_idx]
    body = raw_lines[split_idx + 1 :]

    doc = configure_document()
    add_opening(doc, opening)
    bullet_num_id = add_numbering(doc, "bullet")
    decimal_num_id = None
    in_numbered_block = False

    idx = 0
    while idx < len(body):
        line = body[idx].rstrip()
        stripped = line.strip()
        if not stripped or stripped == "---":
            in_numbered_block = False
            idx += 1
            continue

        if stripped.startswith("|") and idx + 1 < len(body):
            next_line = body[idx + 1].strip()
            if next_line.startswith("|") and re.match(r"^\|?[\s:|-]+\|?$", next_line):
                table_lines = [stripped]
                idx += 2
                while idx < len(body) and body[idx].strip().startswith("|"):
                    table_lines.append(body[idx].strip())
                    idx += 1
                rows = []
                for table_line in table_lines:
                    cells = [c.strip() for c in table_line.strip("|").split("|")]
                    rows.append(cells)
                add_table(doc, rows)
                in_numbered_block = False
                continue

        if stripped.startswith("# "):
            in_numbered_block = False
            title = stripped[2:].strip()
            if title in PAGE_BREAK_BEFORE:
                doc.add_page_break()
            p = doc.add_paragraph(style="Heading 1")
            add_inline(p, title, size=16, color=BLUE, bold=True)
        elif stripped.startswith("## "):
            in_numbered_block = False
            p = doc.add_paragraph(style="Heading 2")
            add_inline(p, stripped[3:].strip(), size=13, color=BLUE, bold=True)
        elif stripped.startswith("### "):
            in_numbered_block = False
            p = doc.add_paragraph(style="Heading 3")
            add_inline(p, stripped[4:].strip(), size=12, color=DARK_BLUE, bold=True)
        elif stripped.startswith(">"):
            in_numbered_block = False
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.16)
            p.paragraph_format.right_indent = Inches(0.1)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(10)
            p.paragraph_format.line_spacing = 1.15
            shade_paragraph(p, CALLOUT)
            set_paragraph_border(p, "left", BLUE, size=18, space=6)
            add_inline(p, stripped[1:].strip(), size=11, color=DARK_BLUE)
        elif re.match(r"^- ", stripped):
            in_numbered_block = False
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.167
            apply_numbering(p, bullet_num_id)
            add_inline(p, stripped[2:].strip())
        elif re.match(r"^\d+\. ", stripped):
            if not in_numbered_block:
                decimal_num_id = add_numbering(doc, "decimal")
                in_numbered_block = True
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.167
            apply_numbering(p, decimal_num_id)
            add_inline(p, re.sub(r"^\d+\. ", "", stripped))
        else:
            in_numbered_block = False
            paragraph_lines = [stripped]
            idx += 1
            while idx < len(body):
                candidate = body[idx].strip()
                if (
                    not candidate
                    or candidate == "---"
                    or candidate.startswith("#")
                    or candidate.startswith("|")
                    or candidate.startswith(">")
                    or re.match(r"^- ", candidate)
                    or re.match(r"^\d+\. ", candidate)
                ):
                    break
                paragraph_lines.append(candidate)
                idx += 1
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.1
            add_inline(p, " ".join(paragraph_lines))
            continue
        idx += 1

    # Keep headings with following content and avoid orphan table headers.
    for paragraph in doc.paragraphs:
        if paragraph.style.name.startswith("Heading"):
            paragraph.paragraph_format.keep_with_next = True
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
