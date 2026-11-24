"""七个节点函数。

每个节点签名是 `def node(state: AgentState) -> dict`，
返回**要更新的字段**（LangGraph 会合并进 state，没返回的字段保持原值）。

节点之间只通过 state 通信，不共享全局变量——这样每个节点都能单独测。
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import amap

from .intent import parse_intent
from .state import AgentState

# play（开放式「能去哪玩」）：景点 + 娱乐 + 特色商业街一起搜
# **故意不含 0601xx 购物中心**——那是纯商场，用 keywords 搜不到好结果，
# 而「大唐不夜城」这类地标商圈属于 0610xx 特色商业街，包含在内。
PLAY_TYPES: tuple[str, ...] = ("110000", "080000", "061000")

# 饮品 / 非正餐分类码：eat 要排除，drink 只留这些
# 0505 咖啡厅 · 0506 茶艺馆 · 0507 冷饮店 · 0508 糕饼店 · 0509 甜品店
DRINK_TYPECODES = ("0505", "0506", "0507", "0508", "0509")

# play 的半径：开放场景放宽一点（商圈往往比景点更远）
PLAY_RADIUS = (3000, 8000)

# 意图 → (初始半径, 上限)；travel 用关键字搜索不设半径
# 意图 → (初始半径, 上限)，单位米
# sight 初始 8km：骊山校区 5km 内只有遗址碑这种小点，
# 华清宫主体 2km、兵马俑 8.6km——5km 会把真正想去的地方漏掉。
RADIUS: dict[str, tuple[int, int]] = {
    "eat": (1500, 3000),      # 正餐
    "sight": (8000, 15000),
    "fun": (3000, 5000),
    "stay": (2000, 5000),
    "play": PLAY_RADIUS,
    "drink": (1000, 2000),
}

# 意图 → 高德 POI 类型码
TYPE_CODE = {
    "eat": "050000",
    "drink": "050000",     # 饮品也搜餐饮大类，filter 里再筛出咖啡/奶茶
    "sight": "110000",     # 明确要景点时，只搜风景名胜
    "fun": "080000",
    "stay": "100000",
}

# 意图 → 距离惩罚权重（越大越在意近）
DIST_PENALTY = {"eat": 0.30, "sight": 0.10, "fun": 0.20, "stay": 0.20}

MIN_RESULTS = 3
TARGET_RESULTS = 5


# ---------------------------------------------------------------- ① 意图

def intake(state: AgentState) -> dict:
    """解析用户输入，提取意图和约束。"""
    # 有起点时告诉模型「位置已知」，它就不会问「你在哪」了
    place_hint = state.get("origin_name") or ""
    if not place_hint and state.get("origin_lat") is not None:
        place_hint = "用户已定位的位置"
    parsed = parse_intent(state["user_input"], history=state.get("history"),
                          current_place=place_hint or None)
    log = state.get("tool_log", []) + [
        f"意图解析：{parsed['intent']}，地点「{parsed.get('location_name') or '未提'}」，"
        f"预算 {parsed.get('budget') or '不限'}"
        + (f"（已结合前 {len(state['history'])} 轮）" if state.get("history") else "")
    ]
    # **有起点坐标时不该反问地点**：用户已经定位了，
    # 再问「你在哪」是多余的（实测踩过）。
    has_origin = (isinstance(state.get("origin_lat"), (int, float))
                  and isinstance(state.get("origin_lon"), (int, float)))
    need_clarify = bool(parsed.get("need_clarify"))
    clarify_q = parsed.get("clarify_question", "")

    # 模型已经知道位置（prompt 里注入了【当前位置】），不该再问位置。
    # 万一分. 还是问了，就整条不追问——比砍出病句强。
    if has_origin and need_clarify:
        if "位置" in clarify_q or "哪个城市" in clarify_q:
            need_clarify = False

    return {
        "intent": parsed["intent"],
        "location_name": parsed.get("location_name", ""),
        "city": parsed.get("city", ""),
        "budget": parsed.get("budget"),
        "duration_min": parsed.get("duration_min"),
        "retry_count": 0,
        "excluded_ids": [],
        "now_hour": datetime.now().hour,
        "tool_log": log,
        "answer": clarify_q if need_clarify else "",
    }


# ---------------------------------------------------------------- ② 定位

def resolve(state: AgentState) -> dict:
    """地点名 → 坐标。地名缺失或查不到时，用城市名兜底。"""
    name = state.get("location_name") or state.get("city") or ""
    log = state.get("tool_log", [])

    # **起点优先级最高**：用户手动拖过地图或输入了地名，直接用，不再地理编码。
    lat, lon = state.get("origin_lat"), state.get("origin_lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        origin = f"{lon:.6f},{lat:.6f}"
        label = state.get("origin_name") or "手动设定的起点"
        # 起点还兼当城市区域：反查行政区，sight 场景要用
        # **必须用 regeo**：geocode 传坐标会当成地址字符串，实测匹配到江苏张家港
        adcode, district, cityname = "", "", ""
        try:
            rev = amap.regeo(origin)
            if rev:
                adcode = rev.get("adcode") or ""
                district = rev.get("district") or ""
                cityname = rev.get("city") or ""
        except Exception:  # noqa: BLE001 反查失败不影响主流程
            pass
        return {
            "location": origin,
            "adcode": adcode,
            "district": district,
            "city": cityname or state.get("city") or "",
            "tool_log": log + [f"起点：{label} ({origin})"
                               + (f" · {district}" if district else "")],
        }

    if not name:
        return {"location": None, "tool_log": log + ["定位：没有地点信息"]}

    # 城市约束优先级：用户选的 > 意图解析出的 > 空
    # **必须有城市**：实测「骊山校区」不带城市会匹配到乌鲁木齐的「骊山」。
    city = state.get("user_city") or state.get("city") or ""
    place = amap.geocode(name, city=city or None)

    # 兜底：用地点名 + 城市再试一次
    if not place and city:
        place = amap.geocode(f"{city}{name}", city=None)

    # 再兜底：用城市中心
    if not place and city:
        place = amap.geocode(city)

    if not place:
        return {"location": None, "tool_log": log + [f"定位失败：{name}"]}

    return {
        "location": place["location"],
        "adcode": place.get("adcode"),
        "district": place.get("district"),
        "tool_log": log + [f"定位：{place['address']} ({place['location']})"],
    }


# ---------------------------------------------------------------- ③ 搜索

def _with_distance(p: dict, origin: str) -> dict:
    """给 POI 算到起点的距离（米）。

    关键字搜索（place/text）不返回 distance，要用坐标自己算。
    用简化公式：1 度纬度 ≈ 111km，1 度经度 ≈ 111km × cos(纬度)。
    """
    import math

    loc = p.get("location")
    if not loc or not origin or "," not in loc or "," not in origin:
        return p
    try:
        lon1, lat1 = map(float, loc.split(","))
        lon0, lat0 = map(float, origin.split(","))
    except ValueError:
        return p

    dlat = math.radians(lat1 - lat0)
    dlon = math.radians(lon1 - lon0)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat0)) * math.cos(math.radians(lat1))
         * math.sin(dlon / 2) ** 2)
    dist = round(2 * 6371000 * math.asin(math.sqrt(a)))

    out = dict(p)
    out["distance"] = dist
    return out


def search(state: AgentState) -> dict:
    """按意图和半径搜索 POI。结果不足时自动扩半径。"""
    intent = state.get("intent", "sight")
    log = state.get("tool_log", [])

    # travel：整城关键字搜索，不用半径
    if intent == "travel":
        city = state.get("city") or state.get("location_name") or ""
        if not city:
            return {"pois": [], "tool_log": log + ["搜索：缺少城市名"]}
        pois = amap.search_text("景点", city=city, poi_type=TYPE_CODE["sight"])
        return {"pois": pois, "tool_log": log + [f"全城搜索「{city}」景点：{len(pois)} 条"]}

    loc = state.get("location")
    if not loc:
        return {"pois": [], "tool_log": log + ["搜索：没有坐标"]}

    radius, cap = RADIUS.get(intent, (3000, 5000))

    # sight：**按行政区关键字搜，不用周边搜索**
    # 周边搜索按距离排，返回的全是 200–900m 的小遗址、教堂；
    # 真正的 5A 景区（华清宫 1.7km、兵马俑 6.3km）排不进前 25。
    # 用 adcode 搜「景点」，华清宫 4.7、兵马俑 4.7 都能出来。
    if intent == "sight" and (state.get("adcode") or state.get("district")):
        area = state.get("adcode") or state.get("district")
        max_dist = RADIUS["sight"][1]
        raw = []
        for page in (1, 2):
            chunk = amap.search_text("景点", city=str(area),
                                     poi_type=TYPE_CODE["sight"], page=page)
            raw.extend(chunk)
            if len(chunk) < 25:
                break
        # 按距离过滤（高德不给 distance，用坐标自己算）
        kept = [_with_distance(p, loc) for p in raw]
        kept = [p for p in kept if p.get("distance") is not None
                and p["distance"] <= max_dist]
        return {
            "pois": kept,
            "radius_used": max_dist,
            "tool_log": log + [
                f"按区搜索「{state.get('district') or area}」景点："
                f"{len(raw)} 条，{max_dist}m 内 {len(kept)} 条"
            ],
        }

    # play：三类各搜一次再合并（一次查多类型会被餐饮/景点挤占，实测过）
    if intent == "play":
        pois = []
        for tp in PLAY_TYPES:
            pois.extend(amap.search_around(loc, tp, radius=radius))
        return {
            "pois": pois,
            "radius_used": radius,
            "tool_log": log + [f"开放式搜索：{radius}m 内景点+娱乐+商圈共 {len(pois)} 条"],
        }

    pois = amap.search_around(loc, TYPE_CODE[intent], radius=radius)

    # 结果太少 → 扩半径（最多 2 次）
    tries = 0
    while len(pois) < MIN_RESULTS and radius < cap and tries < 2:
        radius = min(int(radius * 1.5), cap)
        pois = amap.search_around(loc, TYPE_CODE[intent], radius=radius)
        tries += 1

    return {
        "pois": pois,
        "radius_used": radius,
        "tool_log": log + [f"周边搜索：{radius}m 内 {len(pois)} 条"],
    }


# ---------------------------------------------------------------- ④ 筛选排序

def _rating_score(p: dict) -> float:
    """评分归一化到 0–1。没评分给 0.5（不奖不罚）。"""
    r = p.get("rating")
    return r / 5.0 if isinstance(r, (int, float)) and r > 0 else 0.5


def _budget_fit(p: dict, budget: int | None) -> float:
    """预算匹配度：人均越接近预算越高。预算为 None 时看「是否便宜实惠」。"""
    cost = p.get("cost")
    if not isinstance(cost, (int, float)) or cost <= 0:
        return 0.5
    if budget is None:
        return 0.7 if cost <= 100 else 0.4
    diff = abs(cost - budget) / max(budget, 1)
    return max(0.0, 1.0 - diff)


# ---------------------------------------------------------------- 地标 / 商场加权

# 商场关键词：命中就降权。
# 注意「奥莱钟楼广场」这种名字里带地标的，要先判商场（优先级高）。
MALL_KEYWORDS: tuple[str, ...] = (
    "奥莱", "奥特莱斯", "购物中心", "超市", "商场", "百货",
    "MALL", "Mall", "mall", "More", "砂之船", "华阳城", "赛特",
    "购物广场", "商业广场", "国际购物",
)

# 地标关键词：命中就加分。
# 这些是用户会专门跑一趟的地方，哪怕它在高德里只是一个「广场 POI」。
LANDMARK_KEYWORDS: tuple[str, ...] = (
    "钟楼", "不夜城", "世博园", "老街", "古城", "遗址", "博物",
    "公园", "塔", "寺", "宫", "陵", "祠", "庙", "关", "楼",
)


def landmark_bonus(p: dict, intent: str = "sight") -> float:
    """算出该 POI 的「地标 / 商场」加权分。正数是加分，负数是降权。

    **权重随意图变**（这是用户指出的关键）：
      sight（「有什么景点」）→ 商场降权，用户明确要景点
      play （「能去哪玩」）  → 商场**不降权**，奥莱/华阳城也是能逛的地方
      eat  （「吃什么」）    → 商场不降权（商场里全是的餐厅）

    **优先级**：商场关键词 > typecode > 地标关键词。
    因为「临潼奥莱钟楼广场」名字里同时有「奥莱」和「钟楼」，
    如果先判地标会把它当成景点——这是实测踩到的 bug。
    """
    name = p.get("name") or ""
    code = (p.get("typecode") or "")[:4]

    # play / eat：商场不惩罚（只给地标加分）
    mall_penalty = 0.0 if intent in ("play", "eat") else -0.30
    code_penalty = 0.0 if intent in ("play", "eat") else -0.25

    # ① 商场关键词：最高优先级
    if any(k in name for k in MALL_KEYWORDS):
        return mall_penalty

    # ② 高德码是购物中心 / 超市
    if code in ("0601", "0604", "0602"):
        return code_penalty

    # ③ 地标关键词加分
    if any(k in name for k in LANDMARK_KEYWORDS):
        return 0.15

    return 0.0


def time_bonus(p: dict, now_hour: int) -> float:
    """按当前时间给 POI 加权。

    **为什么需要**：用户晚上 8 点问「附近能去哪玩」，
    推「骊山」「百神庙」这种白天景点是没用的——人家早关门了。

    **注意**：这是基于类型的粗判，不是查真实营业时间。
    POI 的 open_time 字段覆盖率不高（很多景点没有），
    所以这里只按「类型 + 时间段」给个粗略权重，界面上会标注。
    """
    name = p.get("name") or ""
    typ = p.get("type") or ""

    # 晚上 19:00 – 次日 6:00
    if now_hour >= 19 or now_hour < 6:
        # 白天型：景区、公园、寺庙、遗址
        if any(k in typ for k in ("风景名胜", "公园", "寺庙", "遗址", "广场")):
            return -0.40
        # 夜间型：娱乐、商业街、夜市、KTV、酒吧
        if any(k in typ for k in ("娱乐", "商业街", "影剧院", "歌舞厅")):
            return 0.20
        if any(k in name for k in ("KTV", "ktv", "酒吧", "夜市", "烧烤", "夜宵")):
            return 0.20
        return 0.0

    # 白天：逆命题，公园景区加分（本来就是白天去）
    if any(k in typ for k in ("风景名胜", "公园", "博物馆", "遗址")):
        return 0.10
    return 0.0


def rank_score(p: dict, intent: str, budget: int | None, radius: int,
               now_hour: int = 12) -> float:
    """评分排序（**不叫质量排序**）：只按可量化维度加权。

    评分高 ≠ 质量好，只是「用户打分高」。
    """
    s = 0.5 * _rating_score(p)
    s += 0.3 * _budget_fit(p, budget)
    s += 0.2 * 1.0  # 类型已经在搜索时限定，这里给满
    s += landmark_bonus(p, intent)  # 地标加分 / 商场降权（权重随意图变）
    s += time_bonus(p, now_hour)    # 时间加权：晚上不推白天景点

    dist = p.get("distance")
    if isinstance(dist, (int, float)) and radius > 0:
        s -= DIST_PENALTY.get(intent, 0.15) * min(dist / radius, 1.0)
    return s


# ---------------------------------------------------------------- 按主景区去重

# 名称分隔符： "华清宫-杨妃池" / "华清宫·杨妃池"
SUB_SEP = ("-", "－", "·", "•")


def main_spot_name(name: str) -> str:
    """把「华清宫-杨妃池」拆成「华清宫」。没有分隔符就原样返回。"""
    for sep in SUB_SEP:
        if sep in name:
            head = name.split(sep)[0].strip()
            if len(head) >= 2:   # 防止「A-B」里的 A 只有一个字时误拆
                return head
    return name


MAX_PREFIX_DIFF = 6   # 前缀归并允许的最大长度差（字）


def _find_parent(main: str, existing: list[str]) -> str | None:
    """在已有主名里找当前名字的「父级」：互为前缀且长度差 <= 6。

    「秦始皇帝陵博物院丽山园」-> 找到「秦始皇帝陵博物院」（它是前缀）
    「秦始皇帝陵」            -> 找到「秦始皇帝陵博物院」（它是前缀）
    「西安博物馆」vs「西安博物院」-> 不互为前缀，不合并
    """
    for e in existing:
        short, long_ = (e, main) if len(e) <= len(main) else (main, e)
        if long_.startswith(short) and len(long_) - len(short) <= MAX_PREFIX_DIFF:
            # **必须返回 existing 里的那个 e**，不能返回 short——
            # short 可能是当前名字（如「秦始皇帝陵」），它不在 seen 里，会 KeyError。
            return e
    return None


def dedupe_by_main_spot(pois: list[dict]) -> list[dict]:
    """同一主景区只留评分最高的一个，子景点挂在 sub_spots 上。

    **两层归并**：
      ① 有分隔符的（「华清宫-杨妃池」）-> 拆出主名
      ② 没分隔符但是前缀关系的（「秦始皇帝陵」/「秦始皇帝陵博物院丽山园」）
         -> 归并到较短的那个

    输入按评分从高到低排好（调用方保证），所以第一次遇到的就是最好的。
    """
    seen: dict[str, dict] = {}
    for p in pois:
        name = p.get("name") or ""
        main = main_spot_name(name)

        # ② 前缀归并：看看能不能并到已有的某个主名下面
        parent = _find_parent(main, list(seen.keys()))
        if parent:
            item = seen[parent]
            sub = name.replace(parent, "").lstrip("".join(SUB_SEP)).strip()
            if sub and sub not in item["sub_spots"]:
                item["sub_spots"].append(sub)
            continue

        if main not in seen:
            item = dict(p)
            item["main_name"] = main
            item["sub_spots"] = []
            seen[main] = item
        else:
            sub = name.replace(main, "").lstrip("".join(SUB_SEP)).strip()
            if sub and sub not in seen[main]["sub_spots"]:
                seen[main]["sub_spots"].append(sub)
    return list(seen.values())


def filter_pois(state: AgentState) -> dict:
    """按评分排序，取前 5 个。

    **被 Critic 打回时换策略**：否则确定性排序会产出同样的结果，死循环。
    打回后的策略：
      · 数量从 5 减到 3（时间不够就少去几个）
      · 剔除步行超过 15 分钟的（距离太远）
      · 有预算问题时只留人均不超预算的
    """
    intent = state.get("intent", "sight")
    budget = state.get("budget")
    radius = state.get("radius_used", 3000)
    pois = state.get("pois", [])
    feedback = state.get("critic_feedback") or ""
    log = state.get("tool_log", [])

    now_hour = state.get("now_hour", 12)

    # **饮品和正餐分开**（用户要求）：
    #   eat   → 排除咖啡厅/冷饮/糕饼/甜品，只留正餐
    #   drink → 只留这些
    if intent == "eat":
        filtered = [p for p in pois
                    if (p.get("typecode") or "")[:4] not in DRINK_TYPECODES]
        if filtered:          # 全被滤掉就保留原列表，别给空
            pois = filtered
    elif intent == "drink":
        filtered = [p for p in pois
                    if (p.get("typecode") or "")[:4] in DRINK_TYPECODES]
        if filtered:
            pois = filtered

    scored = sorted(pois, key=lambda p: rank_score(p, intent, budget, radius, now_hour),
                    reverse=True)

    # 按主景区去重：华清宫-杨妃池 / 华清宫-五间厅 归到「华清宫」一个条目
    if intent in ("sight", "play", "travel"):
        scored = dedupe_by_main_spot(scored)

    if not feedback:
        top = scored[:5]
        return {"filtered": top,
                "tool_log": log + [f"评分排序：取前 {len(top)} 个"]}

    # ---- 打回模式：按 Critic 给的排除名单重筛 ----
    # **为什么用排除名单而不是让 filter 自己判断「太远」**：
    # filter 只有直线距离（distance），Critic 有实际步行时间（walk_min），
    # 两者不一致会让过滤永远失效（806m 直线 = 步行 20 分钟）。
    excluded = set(state.get("excluded_ids") or [])
    pool = [p for p in scored if p.get("id") not in excluded]
    # Critic 算出的「最多能去几个」优先；没有就取目标数量（5）
    # **不能先取 3 再靠「不足就放宽」补到 5**——那等于每次都在放宽，
    # 而且放宽会加「可能闭店」的提示，正常情况不该出现。
    max_points = state.get("max_points")
    limit = max_points if isinstance(max_points, int) and max_points > 0 else TARGET_RESULTS
    top = pool[:limit]

    # ---- 不足 5 个时放宽时间限制 ----
    # 用户要的是「给我 5 个选择」，不是「只给 1 个还理直气壮」。
    # 放宽顺序：距离（search 已扩过半径）→ 时间（这里）。
    relaxed = False
    if len(top) < TARGET_RESULTS and (now_hour >= 19 or now_hour < 6):
        if len(top) < TARGET_RESULTS:
            # 用白天的权重重排（不加夜间惩罚）
            scored2 = sorted(pois, key=lambda p: rank_score(p, intent, budget, radius, 12),
                             reverse=True)
            if intent in ("sight", "play", "travel"):
                scored2 = dedupe_by_main_spot(scored2)
            if len(scored2) > len(top):
                top = scored2[:TARGET_RESULTS]
                relaxed = True
    return {
        "filtered": top,
        "critic_feedback": "",   # 清空，避免重复触发
        "max_points": None,
        "relaxed_time": relaxed,
        "tool_log": log + [f"按 Critic 意见重筛：{len(top)} 个"],
    }


# ---------------------------------------------------------------- ⑤ 路线

# ---------------------------------------------------------------- 交通方式推算

# 速度与固定耗时（分钟）
SPEED_FACTORS = {
    "bike": (0.33, 0),      # 骑行 15 km/h，无固定耗时
    "transit": (0.33, 8),   # 公交 15 km/h，含等车 8 分钟
    "drive": (0.20, 5),     # 驾车 25 km/h，含找车位 5 分钟
}


def estimate_travel(walk_min: int | None, walk_m: int | None) -> dict[str, int]:
    """用步行时间推算其他出行方式。

    短距离不推荐不合理的选项：
      < 800m   → 只给步行（开车找车位比走路还慢）
      800m–2km → 步行 + 骑行
      > 2km    → 步行 + 骑行 + 公交 + 驾车
    """
    if not walk_min or walk_min <= 0:
        return {}

    dist = walk_m or walk_min * 80  # 没给距离就按 80m/分钟估
    out: dict[str, int] = {"walk": walk_min}

    if dist >= 800:
        out["bike"] = max(1, round(walk_min * SPEED_FACTORS["bike"][0]))

    if dist >= 2000:
        out["transit"] = max(2, round(walk_min * SPEED_FACTORS["transit"][0]
                                      + SPEED_FACTORS["transit"][1]))
        out["drive"] = max(2, round(walk_min * SPEED_FACTORS["drive"][0]
                                    + SPEED_FACTORS["drive"][1]))
    return out


def best_travel_min(p: dict) -> int | None:
    """取这个 POI 最快的出行时间（步行/骑行/公交/驾车里最小的）。

    **为什么需要**：说「去景点」的人会坐地铁/打车，不是走路。
    用步行时间当上限，会把所有坐车能到的地方都排除掉。
    """
    travel = p.get("travel") or {}
    if travel:
        return min(travel.values())
    return p.get("walk_min")


def fmt_travel(t: dict[str, int]) -> str:
    """把交通选项格式化成一行。"""
    icons = {"walk": "🚶", "bike": "🚲", "transit": "🚌", "drive": "🚗"}
    names = {"walk": "步行", "bike": "骑行", "transit": "公交", "drive": "驾车"}
    parts = [f"{icons.get(k, '')}{names.get(k, k)} {v} 分钟" for k, v in t.items()]
    return " · ".join(parts)


def route(state: AgentState) -> dict:
    """给筛出来的 POI 算「从起点到第一个」的步行时间。

    多点的串联顺序留到 compose 里按距离就近排，避免一次调太多次 API。
    """
    loc = state.get("location")
    items = state.get("filtered", [])
    log = state.get("tool_log", [])

    # travel 是全城范围，算「步行到每个景点」既慢又没意义（用户会打车/开车）
    if state.get("intent") == "travel":
        return {"itinerary": items,
                "tool_log": log + ["全城场景：跳过步行路线计算"]}

    if not loc or not items:
        return {"itinerary": items, "tool_log": log}

    itin = []
    for p in items:
        item = dict(p)
        if p.get("location"):
            r = amap.get_route(loc, p["location"], mode="walking")
            if r:
                item["walk_min"] = round(r["duration"] / 60)
                item["walk_m"] = r["distance"]
                item["travel"] = estimate_travel(item["walk_min"], item["walk_m"])
        itin.append(item)

    return {"itinerary": itin, "tool_log": log + ["路线：已算起点到各点的步行时间"]}


# ---------------------------------------------------------------- ⑥ 组织答案

def compose(state: AgentState) -> dict:
    """把行程组织成 Markdown 回答。"""
    # 反问场景：intake 已经把问题写进 answer，且没有 itinerary，直接返回
    # **不能写成「有 answer 就跳过」**——Critic 打回后重跑时 answer 还在，
    # 会导致答案不更新（bug：重筛成 3 个，答案还说 5 个）。
    if state.get("answer") and not state.get("itinerary"):
        return {}

    itin = state.get("itinerary", [])
    intent = state.get("intent", "sight")
    place = state.get("location_name") or state.get("city") or ""

    if not itin:
        if intent == "travel":
            return {"answer": f"没搜到「{place}」的景点，可以换个城市名试试。"}
        return {"answer": "附近没搜到符合条件的地方，可以试试换个位置或放宽条件。"}

    # travel 和 eat/sight/play 是两种任务，话术分开写
    if intent == "travel":
        base = _compose_travel(itin, place)
    else:
        base = _compose_nearby(itin, intent, place, state.get("now_hour", 12))

    # 放宽过时间限制：必须告诉用户「有些地方晚上可能关门了」
    if state.get("relaxed_time"):
        base += (
            "\n\n> ⚠️ 符合条件的地方不足 5 个，上面放宽了时间限制——"
            "部分地点现在可能已经关门，去之前建议先打电话确认。"
        )
    return {"answer": base}


def _compose_nearby(itin: list[dict], intent: str, place: str,
                    now_hour: int = 12) -> str:
    """附近场景：突出距离和步行时间，快速决策用。"""
    label = {"eat": "吃的地方", "sight": "景点", "play": "能去的地方",
             "fun": "娱乐场所", "stay": "住宿", "drink": "喝东西的地方"}.get(intent, "地方")

    night = now_hour >= 19 or now_hour < 6
    head = f"**「{place}」附近 {len(itin)} 个{label}：**"
    if night:
        head += f"（现在是 {now_hour} 点，已按夜间可去排序）"
    lines = [head, ""]
    for i, p in enumerate(itin, 1):
        meta = []
        if p.get("type"):
            meta.append(p["type"])
        if p.get("distance") is not None:
            meta.append(f"{p['distance']}m")
        if p.get("travel"):
            meta.append(fmt_travel(p["travel"]))
        elif p.get("walk_min") is not None:
            meta.append(f"步行约 {p['walk_min']} 分钟")
        if p.get("rating") is not None:
            meta.append(f"评分 {p['rating']}")
        if p.get("cost") is not None:
            meta.append(f"人均 {int(p['cost'])}")
        lines.append(f"**{i}. {p['name']}**　" + " · ".join(meta))
        if p.get("sub_spots"):
            lines.append(f"　　🏛 含：{'、'.join(p['sub_spots'][:5])}")
        if p.get("address"):
            lines.append(f"　　{p['address']}")
    lines.append("")
    lines.append("_评分来自高德用户打分；步行时间由高德路径规划计算，"
                 "骑行/公交/驾车为按平均速度推算的估算值，实际以导航为准。_")
    return "\n".join(lines)


def _compose_travel(itin: list[dict], place: str) -> str:
    """旅游场景：不提「附近」和步行分钟数，突出评分和类型。

    travel 是「做功课」，用户会专门跑一趟，
    所以距离和步行时间不是重点，值得不值得去才是。
    """
    lines = [f"**{place}值得去的地方（按高德评分排）：**", ""]
    for i, p in enumerate(itin, 1):
        meta = []
        if p.get("type"):
            meta.append(p["type"])
        if p.get("rating") is not None:
            meta.append(f"⭐ {p['rating']}")
        if p.get("business_area"):
            meta.append(p["business_area"])
        lines.append(f"**{i}. {p['name']}**　" + " · ".join(meta))
        if p.get("sub_spots"):
            lines.append(f"　　🏛 含：{'、'.join(p['sub_spots'][:5])}")
        if p.get("address"):
            lines.append(f"　　📍 {p['address']}")
    lines.append("")
    lines.append("_以上按高德用户评分排序，评分仅供参考；具体开放时间建议出行前确认。_")
    return "\n".join(lines)
