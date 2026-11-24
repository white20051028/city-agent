"""用 MCP 官方 client 连上我们的 server，验证 5 个工具能调。

跑法（在 D:\\桌面\\city-agent 下）：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\test_mcp_client.py

期望：列出 5 个工具，并真正调用其中 2 个拿到数据。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PY = sys.executable
SERVER = Path(__file__).resolve().parent.parent / "tools" / "mcp_server.py"

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command=PY, args=["-X", "utf8", str(SERVER)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ① 列出工具
            tools = await session.list_tools()
            print("=" * 60)
            print(f"① 工具列表（{len(tools.tools)} 个）")
            print("=" * 60)
            for t in tools.tools:
                print(f"  · {t.name}")
                desc = (t.description or "").split("\n")[0]
                print(f"    {desc[:60]}")

            # ② 调 resolve_location
            print()
            print("=" * 60)
            print("② 调用 resolve_location")
            print("=" * 60)
            r = await session.call_tool("resolve_location",
                                        {"name": "西安科技大学骊山校区", "city": "西安"})
            print("  ", r.content[0].text[:200] if r.content else "（空）")

            # ③ 调 search_pois
            print()
            print("=" * 60)
            print("③ 调用 search_pois（2km 餐饮）")
            print("=" * 60)
            r2 = await session.call_tool("search_pois", {
                "location": "109.215724,34.372332",
                "poi_type": "050000",
                "radius": 2000,
            })
            text = r2.content[0].text if r2.content else "（空）"
            print(f"  返回 {len(text)} 字符，前 300：")
            print("  ", text[:300].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
