"""修两处：
  ① P3 第 3 条 bullet 的中文字体（eastAsia 缺失 → 显示成宋体）
  ② 两个项目的技术栈栏补全（漏了 MCP / 腾讯云 ASR / PWA / BM25 双路 / Ragas）
"""

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

P = Path(r"D:\桌面\简历-张圣泽.docx")
doc = Document(str(P))

# ================================================================
# ① 补齐中文字体
# ================================================================
fixed = 0
for p in doc.paragraphs:
    if not p.text.startswith("· "):
        continue
    for r in p.runs:
        rPr = r._element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            from docx.oxml import OxmlElement
            rFonts = OxmlElement("w:rFonts")
            rPr.insert(0, rFonts)
        if not rFonts.get(qn("w:eastAsia")):
            rFonts.set(qn("w:eastAsia"), "微软雅黑")
            fixed += 1
        if not rFonts.get(qn("w:ascii")):
            rFonts.set(qn("w:ascii"), "微软雅黑")
        if not rFonts.get(qn("w:hAnsi")):
            rFonts.set(qn("w:hAnsi"), "微软雅黑")

print(f"[1] 补齐 {fixed} 处中文字体")

# ================================================================
# ② 技术栈补全
# ================================================================
# 找 P2 和 P3 的 meta 行（以「个人项目 ｜」开头）
REPL = [
    (
        "个人项目 ｜ Python · FastAPI · Streamlit · BGE-M3 · DeepSeek ｜ ",
        "个人项目 ｜ Python · FastAPI · Streamlit · BGE-M3 · DeepSeek · "
        "BM25+向量双路检索 · Ragas ｜ ",
    ),
    (
        "个人项目 ｜ Python · LangGraph · FastAPI · 高德 API · DeepSeek ｜ ",
        "个人项目 ｜ Python · LangGraph · FastAPI · 高德 API · DeepSeek · "
        "MCP · 腾讯云 ASR · PWA ｜ ",
    ),
]

for old, new in REPL:
    done = False
    for p in doc.paragraphs:
        if old in p.text:
            # 找到包含这段文字的 run，替换它
            for r in p.runs:
                if old.split(" ｜ ")[1] in r.text or "LangGraph · FastAPI" in r.text:
                    r.text = r.text.replace(
                        old.split(" ｜ ")[1], new.split(" ｜ ")[1]
                    )
                    r.text = r.text.replace(
                        "Python · FastAPI · Streamlit · BGE-M3 · DeepSeek",
                        "Python · FastAPI · Streamlit · BGE-M3 · DeepSeek · "
                        "BM25+向量双路检索 · Ragas",
                    )
                    r.text = r.text.replace(
                        "Python · LangGraph · FastAPI · 高德 API · DeepSeek",
                        "Python · LangGraph · FastAPI · 高德 API · DeepSeek · "
                        "MCP · 腾讯云 ASR · PWA",
                    )
                    done = True
                    break
            if done:
                break
    print(f"[2] {'✅' if done else '❌'} {old[:40]}…")

doc.save(str(P))
print("已保存")

# 验证
d2 = Document(str(P))
print("\n验证：")
for p in d2.paragraphs:
    if "个人项目 ｜" in p.text:
        print(f"  {p.text[:110]}…")
