"""体验优化：加载状态、结果卡片、快捷追问、错误细化。

注意：JS 字符串里的换行用模板字符串（反引号）或 '\\n' 字面量，
**不能用真实换行**（之前踩过：整个 script 块 SyntaxError，页面空白）。
"""

from pathlib import Path

P = Path(__file__).resolve().parent.parent / "static" / "index.html"
t = P.read_text(encoding="utf-8")

# ================================================================
# ① CSS：卡片 + 追问按钮 + 加载态
# ================================================================
old_css = """  .poi-line { font-size: 13px; padding: 3px 0; }
  .poi-line .n { color: var(--accent); font-weight: 700; margin-right: 4px; }"""

new_css = """  /* 结果卡片（替代纯文本行） */
  .poi-card {
    display: flex; gap: 10px; padding: 10px 12px;
    background: var(--card-2); border-radius: 10px; margin-bottom: 8px;
    cursor: pointer; transition: background .15s;
  }
  .poi-card:active { background: #334155; }
  .poi-rank {
    width: 26px; height: 26px; border-radius: 50%;
    background: var(--accent); color: #0b1220;
    font-weight: 700; text-align: center; line-height: 26px;
    flex-shrink: 0; font-size: 13px;
  }
  .poi-body { flex: 1; min-width: 0; }
  .poi-title { font-weight: 600; font-size: 14px; }
  .poi-tags { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .poi-row { font-size: 12px; margin-top: 3px; }
  .poi-row .rate { color: #fbbf24; }
  .poi-row .near { color: var(--ok); }
  .poi-sub { color: #64748b; font-size: 11px; margin-top: 2px; }

  /* 快捷追问 */
  .followups { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .followup {
    padding: 5px 11px; border-radius: 999px; font-size: 12.5px;
    background: rgba(56, 189, 248, .12); color: var(--accent);
    border: 1px solid rgba(56, 189, 248, .35); cursor: pointer;
  }
  .followup:active { background: rgba(56, 189, 248, .25); }

  /* 加载态：带进度点 */
  .spinner {
    display: none; color: var(--muted); font-size: 13px;
    padding: 10px 0; align-items: center; gap: 8px;
  }
  .spinner.on { display: flex; }
  .spinner .dot {
    width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    animation: blink 1.2s infinite;
  }
  .spinner .dot:nth-child(2) { animation-delay: .2s; }
  .spinner .dot:nth-child(3) { animation-delay: .4s; }
  @keyframes blink { 0%,100% { opacity: .25 } 50% { opacity: 1 } }"""

if old_css not in t:
    print("  [1] CSS 锚点没找到")
else:
    t = t.replace(old_css, new_css, 1)
    print("  [1] CSS：卡片 + 追问 + 加载态")

# ================================================================
# ② HTML：spinner 结构
# ================================================================
old_sp = '  <div id="spinner" class="spinner">Agent 正在思考…</div>'
new_sp = '''  <div id="spinner" class="spinner">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    <span id="spinnerText">正在理解你的需求…</span>
  </div>'''
if old_sp not in t:
    print("  [2] spinner 锚点没找到")
else:
    t = t.replace(old_sp, new_sp, 1)
    print("  [2] HTML：spinner 带进度点")

# ================================================================
# ③ JS：加载状态轮播
# ================================================================
old_vars = "let lastPois = [], lastCenter = null;"
new_vars = """let lastPois = [], lastCenter = null;
let loadTimer = null;

// 加载时的文案轮播（后端是同步返回的，所以这是「假进度」，
// 但比一个静止的转圈好——用户能感知到有事情在发生）
const LOADING_STEPS = [
  '正在理解你的需求…',
  '正在搜索附近的地方…',
  '正在按评分和预算排序…',
  '正在复核时间够不够…',
];
function startLoading() {
  let i = 0;
  const el = document.getElementById('spinnerText');
  el.textContent = LOADING_STEPS[0];
  $spinner.classList.add('on');
  clearInterval(loadTimer);
  loadTimer = setInterval(() => {
    i = (i + 1) % LOADING_STEPS.length;
    el.textContent = LOADING_STEPS[i];
  }, 2200);
}
function stopLoading() {
  clearInterval(loadTimer);
  $spinner.classList.remove('on');
}"""
if old_vars not in t:
    print("  [3] 变量锚点没找到")
else:
    t = t.replace(old_vars, new_vars, 1)
    print("  [3] JS：加载文案轮播")

# ================================================================
# ④ JS：render 里用卡片 + 快捷追问
# ================================================================
old_render = """  if (pois.length) {
    html += '<div class="card">';
    pois.forEach(function (p, i) {
      const meta = [];
      if (p.type) meta.push(p.type);
      if (p.distance != null) meta.push(p.distance + 'm');
      if (p.rating != null) meta.push('⭐' + p.rating);
      if (p.cost != null) meta.push('人均' + Math.round(p.cost));
      if (myLoc && p.location) {
        const xy2 = p.location.split(',').map(Number);
        meta.push('<span style="color:#22c55e">距你' +
                  fmtDist(haversine(myLoc, xy2)) + '</span>');
      }
      html += '<div class="poi-item" data-idx="' + i + '">' +
        '<div class="poi-name">' + (i + 1) + '. ' + p.name + '</div>' +
        '<div class="poi-meta">' + meta.join(' · ') + '</div></div>';
    });
    html += '</div>';
  }"""

new_render = """  if (pois.length) {
    html += '<div class="card">';
    pois.forEach(function (p, i) {
      const tags = [];
      if (p.type) tags.push(p.type);
      if (p.distance != null) tags.push(p.distance + 'm');

      const rows = [];
      if (p.rating != null) rows.push('<span class="rate">⭐ ' + p.rating + '</span>');
      if (p.cost != null) rows.push('人均 ' + Math.round(p.cost));
      if (myLoc && p.location) {
        const xy2 = p.location.split(',').map(Number);
        rows.push('<span class="near">距你 ' + fmtDist(haversine(myLoc, xy2)) + '</span>');
      }
      if (p.travel) rows.push('🚶 ' + (p.travel.walk || '?') + ' 分钟');

      html += '<div class="poi-card" data-idx="' + i + '">' +
        '<div class="poi-rank">' + (i + 1) + '</div>' +
        '<div class="poi-body">' +
          '<div class="poi-title">' + p.name + '</div>' +
          '<div class="poi-tags">' + tags.join(' · ') + '</div>' +
          (rows.length ? '<div class="poi-row">' + rows.join(' · ') + '</div>' : '') +
          (p.address ? '<div class="poi-sub">' + p.address + '</div>' : '') +
        '</div></div>';
    });
    html += '</div>';

    // 快捷追问：只在有结果时给，点一下就等于重新问
    html += '<div class="followups">' +
      ['换一批', '便宜点', '近一点', '还有别的吗'].map(function (x) {
        return '<span class="followup" data-q="' + x + '">' + x + '</span>';
      }).join('') + '</div>';
  }"""

if old_render not in t:
    print("  [4] render 锚点没找到")
else:
    t = t.replace(old_render, new_render, 1)
    print("  [4] JS：卡片渲染 + 快捷追问")

# ================================================================
# ⑤ JS：点击绑定的类名改了
# ================================================================
t = t.replace(
    "document.querySelectorAll('.poi-item').forEach(function (el) {",
    "document.querySelectorAll('.poi-card').forEach(function (el) {"
)
t = t.replace(
    "document.querySelectorAll('.poi-item').forEach(el => {\n    el.addEventListener('click', function () {",
    "document.querySelectorAll('.poi-card').forEach(el => {\n    el.addEventListener('click', function () {"
)

# ================================================================
# ⑥ JS：追问按钮事件（放在 chip 事件旁边）
# ================================================================
old_chip = """document.querySelectorAll('.chip').forEach(c => {
  c.addEventListener('click', () => ask(c.dataset.q));
});"""
new_chip = """document.querySelectorAll('.chip').forEach(c => {
  c.addEventListener('click', () => ask(c.dataset.q));
});
// 快捷追问：动态生成的，用事件委托
$chat.addEventListener('click', function (e) {
  const f = e.target.closest('.followup');
  if (f && f.dataset.q) ask(f.dataset.q);
});"""
if old_chip not in t:
    print("  [6] chip 锚点没找到")
else:
    t = t.replace(old_chip, new_chip, 1)
    print("  [6] JS：追问按钮事件委托")

# ================================================================
# ⑦ 加载/停止：换成新函数
# ================================================================
t = t.replace("  $spinner.classList.add('on');\n", "  startLoading();\n")
t = t.replace("    $spinner.classList.remove('on');\n", "    stopLoading();\n")

# ================================================================
# ⑧ 错误细化
# ================================================================
old_err = """  } catch (e) {
    messages.push({ role: 'assistant', content: '请求失败：' + e.message });
    renderChat();
  } finally {"""
new_err = """  } catch (e) {
    let msg;
    if (e.message.indexOf('500') >= 0) {
      msg = '服务端出错了。可能是高德接口临时超时，**再点一次**通常就好了。\\n\\n' +
            '（如果连续几次都这样，告诉我，我去看服务器日志）';
    } else if (e.message.indexOf('Failed to fetch') >= 0 ||
               e.message.indexOf('NetworkError') >= 0) {
      msg = '网络断了。\\n\\n检查一下手机网络，或者刷新页面重试。';
    } else {
      msg = '请求失败：' + e.message + '\\n\\n重试一次试试。';
    }
    messages.push({ role: 'assistant', content: msg });
    renderChat();
  } finally {"""
if old_err not in t:
    print("  [8] 错误处理锚点没找到")
else:
    t = t.replace(old_err, new_err, 1)
    print("  [8] JS：错误提示细化")

P.write_text(t, encoding="utf-8")
print(f"\n写入完成（{len(t)} 字符）")
