"""简历 v6：压回 1 页。

上一版 2 页，超出约 6 行。

取舍：
  · 「大模型应用实践」整节删掉（两个项目已能证明能力，本地部署在技能栏有）
    其中的 MCP 理解 → 并入技能栏「AI 应用」那行
  · 「其他」保持 1 条
  · 字号保持 9.2
"""

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from pathlib import Path

OUT = r"D:\桌面\简历-张圣泽.docx"
PHOTO = r"D:\桌面\_resume_photo.jpg"
FONT = "微软雅黑"
RIGHT_TAB = Cm(18.0)
SZ_BODY, SZ_SMALL, SZ_SEC = 9.2, 8.6, 10.8
LINK = (0x1A, 0x5C, 0xA8)
GRAY = (0x5A, 0x5A, 0x5A)


def style_run(run, size=SZ_BODY, bold=False, color=None, underline=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.underline = underline
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    if color:
        run.font.color.rgb = RGBColor(*color)


def bottom_border(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), "8")
    b.set(qn("w:space"), "1")
    b.set(qn("w:color"), "AAAAAA")
    pBdr.append(b)
    pStyle = pPr.find(qn("w:pStyle"))
    if pStyle is not None:
        pStyle.addnext(pBdr)
    else:
        pPr.insert(0, pBdr)


def para(doc, before=0, after=0.5, indent=0, line=1.0):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = line
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
    return p


def section(doc, title):
    p = para(doc, before=3.5, after=1)
    style_run(p.add_run(title), size=SZ_SEC, bold=True)
    bottom_border(p)


def bullet(doc, text):
    p = para(doc, indent=0.28, after=0.5)
    style_run(p.add_run("· " + text), size=SZ_BODY)


def head_row(doc, left, right, before=2):
    p = para(doc, before=before, after=0)
    style_run(p.add_run(left), size=SZ_BODY + 0.4, bold=True)
    p.add_run("\t")
    style_run(p.add_run(right), size=SZ_SMALL)
    p.paragraph_format.tab_stops.add_tab_stop(RIGHT_TAB, WD_TAB_ALIGNMENT.RIGHT)


doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(1.4)
sec.top_margin = sec.bottom_margin = Cm(0.8)

# ---------- 头部 + 照片 ----------
table = doc.add_table(rows=1, cols=2)
table.autofit = False
table.columns[0].width = Cm(15.6)
table.columns[1].width = Cm(2.8)
left, right = table.cell(0, 0), table.cell(0, 1)

p = left.paragraphs[0]
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(p.add_run("张圣泽"), size=17, bold=True)

for txt in ["13379035775　|　13379035775@163.com",
            "github.com/white20051028",
            "求职意向：AI 应用开发 / Agent 开发　|　可实习 6 个月"]:
    p = left.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    style_run(p.add_run(txt), size=SZ_SMALL)

p = right.paragraphs[0]
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = None
p.paragraph_format.space_after = None
if Path(PHOTO).exists():
    p.add_run().add_picture(PHOTO, width=Cm(2.4))

# ---------- 教育背景 ----------
section(doc, "教育背景")
head_row(doc, "西安科技大学　计算机科学与技术（本科在读）", "2024.09 – 2028.06", before=1)

# ---------- 专业技能 ----------
section(doc, "专业技能")
for k, v in [
    ("AI 应用", "RAG 全流程（加载/切分/向量化/检索/生成）· 提示词工程 · 判断层设计 · "
               "Agent 工具调用与多步循环 · Planner-Critic 双阶段 · 理解 MCP 协议"
               "（transport / capability / tool 声明）"),
    ("框架工具", "LangGraph · LangChain · vLLM · Ollama · Ragas / LangSmith · "
               "FastAPI · Streamlit · 高德开放平台"),
    ("本地部署与数据", "WSL2 + Ubuntu 22.04 + CUDA/cuDNN；vLLM 与 LangChain 两条路径部署 "
                  "Qwen2.5-3B / ChatGLM3-6B；MySQL / Redis（了解原理，无生产实践）"),
    ("AI 编程与评测", "DeepSeek Harness / Claude Code 提需求→AI 实现→自己验收；"
                  "能自标评测集，跑 Recall@5 / MRR / 端到端准确率"),
]:
    p = para(doc, indent=0.28, after=0.5)
    style_run(p.add_run(f"{k}："), size=SZ_BODY, bold=True)
    style_run(p.add_run(v), size=SZ_BODY)

# ---------- 项目经历 ----------
section(doc, "项目经历")

head_row(doc, "教务政策问答系统（Academic-RAG）", "2026.10 – 至今")
p = para(doc, after=0.5)
style_run(p.add_run("个人项目 ｜ Python · FastAPI · Streamlit · BGE-M3 · DeepSeek ｜ "
                    "已上线，十余位同学在用 ｜ "), size=SZ_SMALL, color=GRAY)
style_run(p.add_run("演示 8.137.195.255:8501　代码 github.com/white20051028/Academic-RAG"),
          size=SZ_SMALL, color=LINK, underline=True)
for b in [
    "抓取清洗教务处 147 份公开文件（46.7 万字 / 1119 片段），向量 + BM25 双路检索，"
    "加权 RRF 融合（向量 1.0 / BM25 0.4），书面问法 Recall@5 96.36%",
    "实测发现相似度阈值不可用：该答最低分 0.557、该拒最高分 0.619 分布重叠，"
    "不存在安全分界线 → 改为模型读资料判断，端到端 78.9% → 86.0%，拒答 11/11",
    "判断层从「二分类拦截器」重构为「四档路由器」：A 无关 / B 能答 / C1 资料没有 / "
    "C2 有内容但缺一块；C2 触发 Agent 兜底（读完整文件或换词重搜，最多 3 步）。"
    "实测 C2 仅 5%——数据越全、判断越准，Agent 触发越少",
    "上线后收集 19 条真实反馈，7 条为评测集无法覆盖的场景；最严重一条：用户问"
    "「大三绩点 4.0 能否转专业」被答「能」，定位为「引用了条件、漏了适用范围」并修复",
]:
    bullet(doc, b)

head_row(doc, "城市探索 Agent（City-Agent）", "2026.11 – 至今")
p = para(doc, after=0.5)
style_run(p.add_run("个人项目 ｜ Python · LangGraph · FastAPI · 高德 API · DeepSeek ｜ "),
          size=SZ_SMALL, color=GRAY)
style_run(p.add_run("在线 https://agent-city.site:8443　代码 github.com/white20051028/city-agent"),
          size=SZ_SMALL, color=LINK, underline=True)
for b in [
    "基于 LangGraph 实现 Planner-Critic 双阶段 Agent：Planner 出方案，Critic 用真实"
    "交通耗时/预算复核，不通过打回重排（最多 2 次），能拦住「两小时去三个景点」这类"
    "不可行方案",
    "意图分五类（吃/喝/景点/玩/旅游），检索半径与方式随意图变化：吃饭 1.5km 周边搜索、"
    "景点 8km 按行政区搜索、旅游全城关键字搜索；结果不足自动扩半径，仍不足则放宽时间"
    "限制并标注",
    "数据全部来自高德 API，事实准确率 100%（不会编造不存在的地点）；自标 30 条评测，"
    "调参集 20 条 100%、留出集 10 条 90%（真实水平）；独立完成云服务器部署 + "
    "Let's Encrypt 证书 + PWA + 语音输入",
]:
    bullet(doc, b)

# ---------- 其他 ----------
section(doc, "其他")
bullet(doc, "校软件实验室（2024.09–2025.06）、校流行乐团（2025.09–至今）；"
            "项目仓库含 20+ 篇设计与踩坑文档，GitHub Actions CI（单测 + 假 Key 重跑）")

doc.save(OUT)
print(f"已生成: {OUT}")
