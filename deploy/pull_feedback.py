"""把服务器上的反馈拉下来看。

用法：
    python deploy/pull_feedback.py          # 拉取并打印
    python deploy/pull_feedback.py --save   # 同时存到本地 data/feedback_local.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"
ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict:
    cfg = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def main() -> None:
    cfg = load_env()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["HOST"], username=cfg["USER"], password=cfg["PASS"], timeout=20)

    _, out, _ = client.exec_command(
        "cat ~/city-agent/data/feedback.jsonl 2>/dev/null || echo ''", timeout=60
    )
    raw = out.read().decode("utf-8", "replace").strip()
    client.close()

    if not raw:
        print("还没有反馈")
        return

    lines = [x for x in raw.splitlines() if x.strip()]
    print(f"共 {len(lines)} 条反馈\n")

    for i, line in enumerate(lines, 1):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue

        print("=" * 64)
        print(f"#{i}  {d.get('time', '?')}  v{d.get('version', '?')}")
        print("=" * 64)
        print(f"  用户说：{d.get('comment', '（空）')}")
        print(f"  问的是：{d.get('question', '（空）')[:80]}")
        print(f"  答的是：{d.get('answer', '（空）')[:120]}")
        print(f"  意图：{d.get('intent') or '-'}  "
              f"调用链：{len(d.get('tool_log') or [])} 步  "
              f"历史：{len(d.get('history') or [])} 条")
        if d.get("tool_log"):
            print("  工具链：")
            for t in d["tool_log"][:6]:
                print(f"    · {t}")
        print()

    if "--save" in sys.argv:
        dst = ROOT / "data" / "feedback_local.jsonl"
        dst.write_text(raw + "\n", encoding="utf-8")
        print(f"已保存到 {dst}")


if __name__ == "__main__":
    main()
