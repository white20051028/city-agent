"""意图识别：把用户的一句话拆成结构化约束。

这是整条链路的第一个 LLM 调用，也是最容易被问的地方：
「你怎么知道用户想吃饭还是想看景点？」
→ 用模型判断，不是关键词匹配。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

INTENT_PROMPT = """你是需求解析器。把用户的话拆成 JSON，只输出 JSON，不要解释。

字段：
- intent: 只能是 eat（吃饭）/ sight（看景点）/ fun（娱乐）/ stay（住宿）/ travel（旅游）
- location_name: 用户提到的地方名（原样输出，没有就空字符串）
- city: 城市名（能从地点名推断就填，如「榆林老街」→「榆林」）
- budget: 人均预算（整数，元）；没提到填 null
- duration_min: 可用时长（分钟，整数）；没提到填 null
- need_clarify: 如果连「想干什么」都判断不了，填 true，否则 false
- clarify_question: need_clarify 为 true 时，向用户提问的一句话（一句话问完，不要多轮）

判断 intent 的规则：
- 「吃/饭/餐厅/小吃/美食」→ eat（**正餐，不含奶茶咖啡**）
- 「喝/奶茶/咖啡/饮料/喝的」→ drink
- 「有什么景点/景点推荐/哪好玩/古迹」→ sight（**明确要景点**）
- 「能去哪玩/有什么好玩的/闲逛/逛逛」→ play（**开放式，什么都算**）
- 「唱歌/电影/娱乐」→ fun
- 「住/酒店/宾馆」→ stay

**play 和 sight 的区别（关键）**：
- 「附近有啥景点」→ sight：用户明确要景点，商场不算
- 「附近能去哪玩」→ play：用户没限定类型，商圈、商场、KTV、公园都算
  （「奥莱」「华阳城」这种在「去哪玩」语境下是合理答案）

**travel 和 sight 怎么区分（重要）**：
- 提到整个城市（「榆林有什么景点」「去西安玩」）→ travel（全城搜索）
- 提到具体位置附近（「骊山校区附近」「我旁边」）→ sight（周边搜索）
- 判断依据：有没有「附近 / 周边 / 这边 / 旁边」这类词
  有 → sight，没有且提到城市 → travel

**关于询问位置**：
- 如果用户消息里带【当前位置】，说明系统已经知道位置，**不要再问「在哪个位置附近」**
- 没有【当前位置】且用户也没提地点时，才问位置

时长换算：
- 「两小时」→ 120，「半天」→ 240，「一天」→ 480，「一会儿」→ 60

示例：
输入：我在西安科技大学骊山校区附近，想吃点东西，人均50
输出：{"intent":"eat","location_name":"西安科技大学骊山校区","city":"西安","budget":50,"duration_min":null,"need_clarify":false,"clarify_question":""}
"""


def _client() -> OpenAI:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    if not key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请写进 .env")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")


def build_effective_query(question: str, history: list[dict] | None,
                           max_turns: int = 3) -> str:
    """把多轮历史拼成一句完整意图。

    **为什么拼而不是保留 state**：反问后用户只说「安静点的餐厅」，
    单独理解不了。拼上前面的话「纪念日，人均150，安静点」就清楚了。
    拼接比重放整条图简单，而且每轮都是完整理解，不会带偏。

    max_turns 限制：只取最近 3 条用户消息，太长会把旧话题带进来。
    """
    if not history:
        return question

    users = [h.get("content", "") for h in history if h.get("role") == "user"]
    users = [u for u in users if u.strip()][-max_turns:]
    if not users:
        return question
    return "；".join(users + [question])


def parse_intent(user_input: str, model: str = "deepseek-chat",
                 history: list[dict] | None = None,
                 current_place: str | None = None) -> dict:
    """返回 {intent, location_name, city, budget, duration_min, need_clarify, clarify_question}。

    解析失败时返回一个兜底的 dict（intent=sight，need_clarify=True），
    不让整条链路崩掉。
    """
    query = build_effective_query(user_input, history)
    # 把已知位置注入，模型就不会再问「你在哪」
    if current_place:
        query = f"【当前位置】{current_place}\n用户：{query}"
    try:
        resp = _client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 解析失败不崩，给兜底
        return {
            "intent": "play",
            "location_name": "",
            "city": "",
            "budget": None,
            "duration_min": None,
            "need_clarify": True,
            "clarify_question": "想找什么地方？吃饭、看景点，还是别的？",
        }

    # 字段校验：模型偶尔会漏字段或给错类型
    allowed = {"eat", "sight", "play", "fun", "stay", "travel", "drink"}
    if data.get("intent") not in allowed:
        data["intent"] = "play"
    for k in ("budget", "duration_min"):
        v = data.get(k)
        if not isinstance(v, int):
            data[k] = None
    data.setdefault("location_name", "")
    data.setdefault("city", "")
    data.setdefault("need_clarify", False)
    data.setdefault("clarify_question", "")
    return data
