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


# 意图词：出现这些词说明新问题自带意图，不需要靠历史补全
INTENT_WORDS = (
    "吃", "饭", "餐厅", "美食", "小吃",
    "喝", "奶茶", "咖啡", "饮料",
    "景点", "玩", "逛", "看看", "旅游", "古迹",
    "住", "酒店", "宾馆", "住宿",
    "娱乐", "电影", "唱歌", "ktv", "KTV",
)

# 补充型短语：出现这些说明是在延续上一轮
FOLLOWUP_WORDS = ("再来", "换一个", "另一个", "还有", "呢？", "呢", "那个", "这个",
                  "是的", "对", "好的", "安静点", "便宜点", "贵一点", "近一点")


def is_self_contained(question: str) -> bool:
    """判断这个问题是不是「自带完整意图」。

    自带完整意图 → 不拼历史（避免上一轮的意图污染这一轮）

    规则（按优先级）：
      ① 有「补充型修饰词」（安静点/便宜点/再来一个/那个）→ 补充，要拼
         即使是「安静点的餐厅」——它是在上一轮基础上加条件
      ② 没有补充词但有意图词（吃/玩/景点）→ 独立，不拼
      ③ 都没有（「安静点的」这种短句）→ 补充，要拼

    实测教训：
      第 1 轮「附近有什么好吃的」+ 第 2 轮「附近能去哪玩」
      如果总拼，模型会把第 2 轮判成 eat，继续返回餐厅
    """
    q = question.strip()
    if len(q) < 5:
        return False

    # ① 补充词优先级最高
    if any(w in q for w in FOLLOWUP_WORDS):
        return False

    # ② 有意图词 → 独立
    return any(w in q for w in INTENT_WORDS)


def build_effective_query(question: str, history: list[dict] | None,
                           max_turns: int = 1) -> str:
    """把多轮历史拼成一句完整意图。**只对补充型问题拼。**

    **为什么不总是拼**：实测踩过坑——
      第 1 轮「附近有什么好吃的」→ 第 2 轮「附近能去哪玩」
      拼成「附近有什么好吃的；附近能去哪玩」
      模型看到「好吃的」在前面，判成 eat，第 2 轮还是返回餐厅

    所以：新问题自带意图词（吃/玩/景点）→ 当新话题，**不拼**
          新问题是「安静点的」「那个呢」这种 → 补充，**拼**

    **max_turns 默认 1**（只延续最近一轮）。实测踩过：
      ① 「附近能去哪玩」    → play
      ② 「附近有什么好吃的」 → eat
      ③ 「便宜点」          → 拼 3 轮后变成
                             「附近能去哪玩；附近有什么好吃的；便宜点」
                             → 模型看到「玩」在前，判成 play，给了公园
      修成只拼最近 1 轮 → 拼成「附近有什么好吃的；便宜点」→ 正确判成 eat
    """
    if not history:
        return question

    # 自带完整意图 → 新话题，不拼历史
    if is_self_contained(question):
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
