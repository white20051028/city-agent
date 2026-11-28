"""清掉上一步重复加的技术栈。"""

from pathlib import Path

from docx import Document

P = Path(r"D:\桌面\简历-张圣泽.docx")
doc = Document(str(P))

FIXES = [
    (
        "Python · FastAPI · Streamlit · BGE-M3 · DeepSeek · BM25+向量双路检索 · Ragas"
        " · BM25+向量双路检索 · Ragas",
        "Python · FastAPI · Streamlit · BGE-M3 · DeepSeek · BM25+向量双路检索 · Ragas",
    ),
    (
        "Python · LangGraph · FastAPI · 高德 API · DeepSeek · MCP · 腾讯云 ASR · PWA"
        " · MCP · 腾讯云 ASR · PWA",
        "Python · LangGraph · FastAPI · 高德 API · DeepSeek · MCP · 腾讯云 ASR · PWA",
    ),
]

for p in doc.paragraphs:
    if "个人项目 ｜" not in p.text:
        continue
    for r in p.runs:
        for old, new in FIXES:
            if old in r.text:
                r.text = r.text.replace(old, new)
                print(f"✅ 清理重复")

doc.save(str(P))

# 验证
d2 = Document(str(P))
print("\n验证：")
for p in d2.paragraphs:
    if "个人项目 ｜" in p.text:
        print(f"  {p.text[:115]}…")
