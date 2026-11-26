"""把《项目设计方案》从 Markdown 转成 Word。

排版：
  · A4，边距 2.5cm
  · 标题：微软雅黑 18pt 加粗居中
  · 一级标题：16pt 加粗，带底部横线
  · 二级标题：13pt 加粗
  · 三级标题：11pt 加粗
  · 正文：宋体 10.5pt，行距 1.5
  · 代码块：Consolas 9pt，灰底
  · 表格：带边框，表头加粗
"""

from pathlib import Path
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

SRC = Path(r"D:\桌面\城市探索Agent-项目设计方案.md")
OUT = Path(r"D:\桌面\城市探索Agent-项目设计方案.docx")

FONT_CN = "微软雅黑"
FONT_BODY = "宋体"
FONT_CODE = "Consolas"


def style_run(run, size=10.5, bold=False, font=FONT_BODY, color=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if color:
        run.font.color.rgb = RGBColor(*color)


def shade(paragraph, color="F2F2F2"):
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    pPr.append(shd)


def bottom_border(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), "8")
    b.set(qn("w:space"), "2")
    b.set(qn("w:color"), "666666")
    pBdr.append(b)
    pStyle = pPr.find(qn("w:pStyle"))
    if pStyle is not None:
        pStyle.addnext(pBdr)
    else:
        pPr.insert(0, pBdr)


def add_para(doc, text, size=10.5, bold=False, indent=0, before=0, after=4,
             line=1.5, font=FONT_BODY, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = line
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
    # 处理行内 **粗体** 和 `代码`
    parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            style_run(p.add_run(part[2:-2]), size=size, bold=True, font=font, color=color)
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(part[1:-1])
            style_run(r, size=size - 0.5, font=FONT_CODE, color=(0xC7, 0x25, 0x4E))
        else:
            style_run(p.add_run(part), size=size, bold=bold, font=font, color=color)
    return p


def add_code_block(doc, lines):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.left_indent = Cm(0.5)
    shade(p)
    style_run(p.add_run("\n".join(lines)), size=8.5, font=FONT_CODE)


def add_table(doc, rows):
    """rows[0] 是表头。"""
    ncol = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, row in enumerate(rows):
        for j in range(ncol):
            cell = table.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            text = row[j] if j < len(row) else ""
            # 表格里也可能有 **粗体**，要解析
            parts = re.split(r'(\*\*[^*]+\*\*)', text)
            for part in parts:
                if not part:
                    continue
                if part.startswith('**') and part.endswith('**'):
                    style_run(p.add_run(part[2:-2]), size=9.5, bold=True)
                else:
                    style_run(p.add_run(part), size=9.5, bold=(i == 0))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    lines = md.splitlines()

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.5)
    sec.top_margin = sec.bottom_margin = Cm(2.5)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 代码块
        if stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            add_code_block(doc, block)
            i += 1
            continue

        # 表格（连续的 | 开头行）
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                # 跳过 |---|---| 分隔行
                if not all(set(c) <= set("-: ") for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                add_table(doc, rows)
            continue

        # 标题
        if stripped.startswith("# "):
            p = add_para(doc, stripped[2:], size=18, bold=True, before=0, after=10, font=FONT_CN)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif stripped.startswith("## "):
            p = add_para(doc, stripped[3:], size=15, bold=True, before=14, after=6, font=FONT_CN)
            bottom_border(p)
        elif stripped.startswith("### "):
            add_para(doc, stripped[4:], size=12.5, bold=True, before=10, after=4, font=FONT_CN)
        elif stripped.startswith("#### "):
            add_para(doc, stripped[5:], size=11, bold=True, before=8, after=3, font=FONT_CN)
        # 分隔线
        elif stripped in ("---", "***"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
        # 引用
        elif stripped.startswith(">"):
            add_para(doc, stripped[1:].strip(), size=10, indent=0.5, color=(0x55, 0x55, 0x55))
        # 列表
        elif stripped.startswith("- "):
            add_para(doc, "· " + stripped[2:], size=10.5, indent=0.5, after=2)
        elif re.match(r"^\d+\.\s", stripped):
            add_para(doc, stripped, size=10.5, indent=0.5, after=2)
        # 空行
        elif not stripped:
            pass
        # 正文
        else:
            add_para(doc, stripped, size=10.5)

        i += 1

    doc.save(OUT)
    print(f"已生成: {OUT}")

    # 统计
    import win32com.client as win32
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    d = word.Documents.Open(str(OUT))
    print(f"页数: {d.ComputeStatistics(2)}  字数: {d.ComputeStatistics(0)}")
    d.Close()
    word.Quit()


if __name__ == "__main__":
    main()
