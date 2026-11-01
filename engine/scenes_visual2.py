"""More picture-first scenes.

  pictogram  "1 in 5" as a grid of people/icons, the share lighting up      (total, highlight, icon, display, label)
  kpis       2-4 key numbers that count up, each with an icon                (items[{value, prefix, suffix, label, icon, cue}])
  bubbles    circles sized by value, to compare sizes at a glance            (items[{label, value, display, icon, cue}])
  gauge      a semicircle meter with a needle: a score, risk or level         (value 0-100, label, zones)
  funnel     stages that narrow down (applicants -> hired, visitors -> buyers) (stages[{label, value/display, icon, cue}])
  cycle      a loop of 3-6 steps around a circle (water cycle, build-learn)  (nodes[{label, icon, cue}], center)
  chat       a phone conversation; bubbles appear as they are spoken         (name, messages[{from: me|them, text, cue}])
  reveal     before/after photos with a sliding wipe                         (before{label, image_query}, after{...})
"""
import math
from html import escape as E

import visuals as V
import motion as MO
from scenes_visual import _head, _head_js, _exit, _cues, _fmt, _img_or_icon, SERIES


def _num(v, d=0.0):
    try: return float(str(v).replace(",", ""))
    except (TypeError, ValueError): return d


def _counter(el_id, val, dec, locale, t0, dur=1.0, plain=False):
    return (f'(function () {{ const o = {{ v: 0 }}, el = document.getElementById("{el_id}");'
            f' const fmt = (v) => {{ try {{ return v.toLocaleString("{locale}", {{ minimumFractionDigits: {dec}, maximumFractionDigits: {dec}, useGrouping: {"false" if plain else "true"} }}); }} catch (e) {{ return v.toFixed({dec}); }} }};'
            f' el.textContent = fmt(0); tl.fromTo(o, {{ v: 0 }}, {{ v: {val}, duration: {dur}, ease: "power2.out", onUpdate: () => {{ el.textContent = fmt(o.v); }} }}, {t0:.3f}); }})();\n')


# ------------------------------------------------------------------ pictogram
def pictogram(s, c):
    S = f"#s{c.i}"
    total = int(_num(s.get("total"), 10)) if int(_num(s.get("total"), 10)) in (5, 10, 20, 50, 100) else 10
    hi = _num(s.get("highlight"), 1)
    if s.get("percent") or (hi > total and hi <= 100): hi = hi * total / 100
    hi = max(0, min(total, int(round(hi))))
    cols = {5: 5, 10: 5, 20: 5, 50: 10, 100: 10}[total]; rows = total // cols
    size = {5: 150, 10: 150, 20: 120, 50: 70, 100: 56}[total]; gap = {5: 26, 10: 30, 20: 26, 50: 12, 100: 9}[total]
    icon = s.get("icon") or "user"
    W = cols * size + (cols - 1) * gap; H = rows * size + (rows - 1) * gap
    x0, y0 = (1080 - W) // 2, 360 + max(0, (640 - H) // 2)
    cells = "".join(f'<div class="pi{" on" if k < hi else ""}" id="pi{c.i}_{k}" style="left:{x0 + (k % cols) * (size + gap)}px;top:{y0 + (k // cols) * (size + gap)}px;width:{size}px;height:{size}px">'
                    f'{V.icon_svg(icon, size=size, stroke=1.6)}</div>' for k in range(total))
    disp = s.get("display") or f"{hi} in {total}"
    lbl_em = f' <em>{E(s["label_em"])}</em>' if s.get("label_em") else ""
    ylab = min(y0 + H + 40, 1070)
    html = (_head(s, c) + cells + f'<div class="ctr big" style="top:{ylab}px">{E(disp)}</div>'
            f'<div class="ctr sf lbl fit" style="top:{ylab + 140}px">{E(s.get("label", ""))}{lbl_em}</div>')
    tc = c.cue(s.get("cue", "x"), c.sb, frac=0.4)
    js = (f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c) +
          f'      tl.fromTo("{S} .pi", {{ scale: 0, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "back.out(2)", stagger: {min(0.06, 0.9 / total):.3f} }}, {c.sb + 0.2:.3f});\n'
          f'      tl.to("{S} .pi.on", {{ color: "var(--alert)", scale: 1.12, duration: 0.25, ease: "back.out(2)", stagger: {min(0.12, 0.8 / max(1, hi)):.3f} }}, {max(c.sb + 0.9, tc - 0.1):.3f});\n'
          f'      tl.to("{S} .pi.on", {{ scale: 1, duration: 0.2 }}, {max(c.sb + 0.9, tc - 0.1) + 0.3 + min(0.12, 0.8 / max(1, hi)) * hi:.3f});\n'
          f'      tl.fromTo("{S} .big", {{ scale: 0.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: pop }}, {max(c.sb + 0.9, tc):.3f});\n'
          f'      tl.fromTo("{S} .lbl", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, ease: snap }}, {max(c.sb + 1.1, tc + 0.25):.3f});\n')
    c.sfx("shimmer", c.sb + 0.2, 0.35); c.sfx("thud", max(c.sb + 0.9, tc), 0.7)
    js += MO.draw(f"{S} .pi svg", c.sb + 0.2, 0.5, min(0.06, 0.9 / total))
    bh, bj = MO.burst(c, 540, ylab + 60, max(c.sb + 0.9, tc) + 0.1, "var(--alert)", radius=210); html += bh; js += bj
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .pi, {S} .big, {S} .lbl")
    return html, js


# ------------------------------------------------------------------ kpis
def kpis(s, c):
    S = f"#s{c.i}"
    items = [x for x in s.get("items", []) if isinstance(x, dict)][:4]
    n = len(items); top = 350 if (s.get("title") or s.get("kicker")) else 260
    if n == 4: boxes = [(80 + (k % 2) * 470, top + (k // 2) * 470, 450, 450) for k in range(4)]
    else:
        h = min(440, (1310 - top - 20 * (n - 1)) // max(1, n)); boxes = [(80, top + k * (h + 20), 920, h) for k in range(n)]
    html = _head(s, c)
    ts = _cues(c, items, "cue", "label", 0.1, 0.8)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    for k, (it, (x, y, w, h)) in enumerate(zip(items, boxes)):
        val = _num(it.get("value")); dec = int(it.get("decimals", 0 if float(val).is_integer() else 1))
        horiz = n < 4
        html += (f'<div class="kp card{" h" if horiz else ""}" id="kp{c.i}_{k}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
                 f'<div class="bub">{V.icon_svg(it.get("icon") or it.get("label", ""), size=84 if horiz else 96)}</div><div class="tx">'
                 f'<div class="v"><span>{E(str(it.get("prefix", "")))}</span><b id="kv{c.i}_{k}">0</b><span>{E(str(it.get("suffix", "")))}</span></div>'
                 f'<div class="lb">{E(it.get("label", ""))}</div></div></div>')
        js += f'      tl.fromTo("#kp{c.i}_{k}", {{ y: 80, opacity: 0, scale: 0.9 }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.35, ease: "back.out(1.5)" }}, {ts[k] - 0.3:.3f});\n'
        js += "      " + _counter(f"kv{c.i}_{k}", val, dec, c.locale, ts[k] - 0.2, 0.9, float(val).is_integer() and 1000 <= val <= 2100)
        js += f'      tl.to("#kp{c.i}_{k} .bub", {{ backgroundColor: "var(--primary)", color: "var(--on-primary)", duration: 0.25 }}, {ts[k]:.3f});\n'
        c.sfx("pop", ts[k], 0.5, 900 + 100 * k)
        js += MO.draw(f"#kp{c.i}_{k} .bub svg", ts[k] - 0.25, 0.6)
    if items:
        x, y, w, h = boxes[len(items) - 1]
        bh, bj = MO.burst(c, x + (330 if n < 4 else w / 2), y + (h / 2 if n < 4 else h * 0.55), ts[-1] + 0.75, "var(--primary)", radius=150); html += bh; js += bj
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .kp")
    return html, js


# ------------------------------------------------------------------ bubbles
def bubbles(s, c):
    S = f"#s{c.i}"
    items = [x for x in s.get("items", []) if isinstance(x, dict)][:5]
    vals = [max(0.0, _num(x.get("value"))) for x in items]; mx = max(vals + [1e-9])
    d = [max(90.0, 620 * math.sqrt(v / mx)) for v in vals]
    gap = 24; scale = min(1.0, (940 - gap * (len(d) - 1)) / max(1, sum(d)))
    d = [x * scale for x in d]
    x = (1080 - sum(d) - gap * (len(d) - 1)) / 2; base = 1060
    html = _head(s, c); ts = _cues(c, items, "cue", "label", 0.1, 0.8)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    for k, (it, dia) in enumerate(zip(items, d)):
        disp = it.get("display") or _fmt(vals[k], s.get("unit", ""))
        inside = dia >= 170
        ic = V.icon_svg(it["icon"], size=int(min(90, dia * 0.3))) if it.get("icon") and dia >= 220 else ""
        col = SERIES[k % len(SERIES)]
        html += (f'<div class="bb" id="bb{c.i}_{k}" style="left:{x:.0f}px;top:{base - dia:.0f}px;width:{dia:.0f}px;height:{dia:.0f}px;background:{col}">'
                 f'{ic}{f"<b>{E(disp)}</b>" if inside else ""}</div>'
                 f'<div class="bl" id="bl{c.i}_{k}" style="left:{x + dia / 2 - 150:.0f}px;top:{base + 22}px">{"" if inside else f"<b>{E(disp)}</b>"}<span>{E(it.get("label", ""))}</span></div>')
        js += f'      tl.fromTo("#bb{c.i}_{k}", {{ scale: 0, transformOrigin: "50% 100%" }}, {{ scale: 1, duration: 0.55, ease: "elastic.out(1, 0.6)" }}, {ts[k] - 0.2:.3f});\n'
        js += f'      tl.fromTo("#bl{c.i}_{k}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.25 }}, {ts[k]:.3f});\n'
        c.sfx("pop", ts[k], 0.5, 700 + 160 * k)
        x += dia + gap
    if items:
        kb = max(range(len(items)), key=lambda q: vals[q]); xb = (1080 - sum(d) - gap * (len(d) - 1)) / 2 + sum(d[:kb]) + gap * kb + d[kb] / 2
        bh, bj = MO.burst(c, xb, base - d[kb] / 2, ts[kb] + 0.3, "var(--alert)", radius=d[kb] / 2 + 60); html += bh; js += bj
        js += MO.draw(f"{S} .bb svg", (ts[0] if ts else c.sb) - 0.1, 0.6, 0.3)
    if s.get("note"): html += f'<div class="ctr note">{E(s["note"])}</div>'; js += f'      tl.fromTo("{S} .note", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {ts[-1] + 0.4 if ts else c.sb + 1:.3f});\n'
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .bb, {S} .bl, {S} .note")
    return html, js


# ------------------------------------------------------------------ gauge
def gauge(s, c):
    S = f"#s{c.i}"
    val = max(0.0, min(100.0, _num(s.get("value"), 50)))
    zones = s.get("zones") or ["Low", "Medium", "High"]
    R, CX, CY = 360, 540, 980
    def arc(a0, a1, r):   # angles in degrees, 180 = left, 0 = right
        p = lambda a: (CX + r * math.cos(math.radians(a)), CY - r * math.sin(math.radians(a)))
        (x0, y0), (x1, y1) = p(a0), p(a1)
        return f"M{x0:.1f} {y0:.1f} A{r} {r} 0 0 1 {x1:.1f} {y1:.1f}"
    lbl_em = f' <em>{E(s["label_em"])}</em>' if s.get("label_em") else ""
    nz = len(zones); cols = ["#1f9d6b", "#e0a23c", "var(--alert)"] if nz == 3 else [SERIES[k % len(SERIES)] for k in range(nz)]
    segs = "".join(f'<path d="{arc(180 - 180 * k / nz - 1, 180 - 180 * (k + 1) / nz + 1, R)}" stroke="{cols[k]}" class="zn"/>' for k in range(nz))
    labels = "".join(f'<text x="{CX + (R + 92) * math.cos(math.radians(180 - 180 * (k + .5) / nz)):.0f}" y="{CY - (R + 92) * math.sin(math.radians(180 - 180 * (k + .5) / nz)):.0f}" class="zl">{E(str(z))}</text>' for k, z in enumerate(zones))
    html = (_head(s, c) + f'<svg class="gg" viewBox="0 0 1080 1120" width="1080" height="1120"><path d="{arc(180, 0, R)}" class="tk"/>{segs}{labels}'
            f'<g id="nd{c.i}"><path d="M{CX - 14} {CY} L{CX} {CY - R + 50} L{CX + 14} {CY} Z" class="ndl"/><circle cx="{CX}" cy="{CY}" r="34" class="hub"/></g></svg>'
            f'<div class="ctr gv"><b id="gv{c.i}">0</b><span>{E(str(s.get("suffix", "")))}</span></div>'
            f'<div class="ctr sf lbl fit">{E(s.get("label", ""))}{lbl_em}</div>')
    tv = c.cue(s.get("cue", "x"), c.sb, frac=0.35)
    t0 = max(c.sb + 0.5, tv - 0.6)
    js = (f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c) +
          f'      tl.fromTo("{S} .gg", {{ opacity: 0, y: 60 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: snap }}, {c.sb + 0.1:.3f});\n'
          f'      tl.fromTo("#nd{c.i}", {{ rotation: -90, svgOrigin: "{CX} {CY}" }}, {{ rotation: {-90 + 180 * val / 100:.1f}, svgOrigin: "{CX} {CY}", duration: 1.3, ease: "elastic.out(1, 0.55)" }}, {t0:.3f});\n'
          + "      " + _counter(f"gv{c.i}", val, 0 if float(val).is_integer() else 1, c.locale, t0, 1.0) +
          f'      tl.fromTo("{S} .lbl", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, ease: snap }}, {t0 + 0.6:.3f});\n')
    c.sfx("whoosh", t0, 0.35); c.sfx("thud", t0 + 0.9, 0.7)
    js += f'      drawPath(tl, "{S} .gg .zn", {c.sb + 0.15:.3f}, 0.8);\n'
    bh, bj = MO.burst(c, 540, 1100, t0 + 0.95, "var(--primary)", radius=200); html += bh; js += bj
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .gg, {S} .gv, {S} .lbl")
    return html, js


# ------------------------------------------------------------------ funnel
def funnel(s, c):
    S = f"#s{c.i}"
    st = [x for x in s.get("stages", []) if isinstance(x, dict)][:5]
    n = len(st); top = 360; H = min(200, 900 // max(1, n)); g = 14
    html = _head(s, c); ts = _cues(c, st, "cue", "label", 0.08, 0.82)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    for k, it in enumerate(st):
        w0 = 940 - (940 - 470) * k / max(1, n); w1 = 940 - (940 - 470) * (k + 1) / max(1, n)
        inset = (w0 - w1) / 2 / w0 * 100
        y = top + k * (H + g)
        disp = it.get("display") or (_fmt(_num(it.get("value")), s.get("unit", "")) if it.get("value") not in (None, "") else "")
        col = SERIES[0] if k == 0 else f"color-mix(in srgb, var(--primary) {100 - 18 * k}%, var(--accent))"
        html += (f'<div class="fs" id="fs{c.i}_{k}" style="left:{(1080 - w0) / 2:.0f}px;top:{y}px;width:{w0:.0f}px;height:{H}px;background:{col};'
                 f'clip-path:polygon(0 0,100% 0,{100 - inset:.2f}% 100%,{inset:.2f}% 100%)">'
                 f'{V.icon_svg(it.get("icon") or it.get("label", ""), size=min(64, H // 2)) if w1 >= 600 else ""}<span class="fit">{E(it.get("label", ""))}</span>{f"<b>{E(disp)}</b>" if disp else ""}</div>')
        js += f'      tl.fromTo("#fs{c.i}_{k}", {{ scaleX: 0.2, opacity: 0 }}, {{ scaleX: 1, opacity: 1, duration: 0.4, ease: "back.out(1.4)" }}, {ts[k] - 0.25:.3f});\n'
        c.sfx("pop", ts[k], 0.5, 1100 - 120 * k)
        js += MO.draw(f"#fs{c.i}_{k} svg", ts[k] - 0.15, 0.5)
    if st:
        bh, bj = MO.burst(c, 540, top + (n - 1) * (H + g) + H / 2, ts[-1] + 0.25, "var(--highlight)", radius=230); html += bh; js += bj
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .fs")
    return html, js


# ------------------------------------------------------------------ cycle
def cycle(s, c):
    S = f"#s{c.i}"
    nodes = [x for x in s.get("nodes", []) if isinstance(x, dict)][:6]
    n = len(nodes); CX, CY, R = 540, 800, 330
    html = _head(s, c)
    ang = [(-90 + 360 * k / max(1, n)) for k in range(n)]
    pos = [(CX + R * math.cos(math.radians(a)), CY + R * math.sin(math.radians(a))) for a in ang]
    arcs = ""
    for k in range(n):
        a0, a1 = math.radians(ang[k] + 17), math.radians(ang[k] + 360 / n - 17)
        x0, y0 = CX + R * math.cos(a0), CY + R * math.sin(a0); x1, y1 = CX + R * math.cos(a1), CY + R * math.sin(a1)
        hx, hy = -math.sin(a1), math.cos(a1)   # arrow head direction (tangent)
        arcs += (f'<path id="ca{c.i}_{k}" d="M{x0:.1f} {y0:.1f} A{R} {R} 0 0 1 {x1:.1f} {y1:.1f}" class="ca"/>'
                 f'<path id="ch{c.i}_{k}" class="ch" d="M{x1 - 16 * hx - 12 * hy:.1f} {y1 - 16 * hy + 12 * hx:.1f} L{x1:.1f} {y1:.1f} L{x1 - 16 * hx + 12 * hy:.1f} {y1 - 16 * hy - 12 * hx:.1f}"/>')
    html += f'<svg class="cy" viewBox="0 0 1080 1920" width="1080" height="1920">{arcs}</svg>'
    if s.get("center"): html += f'<div class="cc fit">{E(s["center"])}</div>'
    for k, (nd, (x, y)) in enumerate(zip(nodes, pos)):
        ca = math.cos(math.radians(ang[k])); sa = math.sin(math.radians(ang[k]))
        side = "l" if ca < -0.45 else "r" if ca > 0.45 else "t" if sa < 0 else "b"
        html += (f'<div class="cn {side}" id="cn{c.i}_{k}" style="left:{x - 95:.0f}px;top:{y - 95:.0f}px"><div class="cir">{V.icon_svg(nd.get("icon") or nd.get("label", ""), size=80)}</div>'
                 f'<div class="lb">{E(nd.get("label", ""))}</div></div>')
    ts = _cues(c, nodes, "cue", "label", 0.06, 0.8)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    js += f'      tl.fromTo("{S} .cc", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.4, ease: pop }}, {c.sb + 0.3:.3f});\n'
    for k, t in enumerate(ts):
        js += f'''      tl.fromTo("#cn{c.i}_{k}", {{ scale: 0, rotation: -60 }}, {{ scale: 1, rotation: 0, duration: 0.42, ease: "back.out(1.7)" }}, {t - 0.2:.3f});
      tl.to("#cn{c.i}_{k} .cir", {{ backgroundColor: "var(--primary)", color: "var(--on-primary)", duration: 0.2 }}, {t:.3f});
'''
        nxt = ts[k + 1] if k + 1 < n else min(c.se - 0.5, t + 0.9)
        d = max(0.25, nxt - t - 0.3)
        js += f'      drawPath(tl, "#ca{c.i}_{k}", {t + 0.1:.3f}, {d:.3f});\n      tl.fromTo("#ch{c.i}_{k}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1 }}, {t + 0.1 + d:.3f});\n'
        c.sfx("pop", t, 0.5, 850 + 100 * k)
        js += MO.draw(f"#cn{c.i}_{k} .cir svg", t - 0.1, 0.6)
    js += f'      tl.to("{S} .cy", {{ rotation: 360, transformOrigin: "{CX}px {CY}px", duration: 14, ease: "none" }}, {ts[-1] + 0.6 if ts else c.sb:.3f});\n' if s.get("spin") else ""
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .cy, {S} .cn, {S} .cc")
    return html, js


# ------------------------------------------------------------------ chat
def chat(s, c):
    S = f"#s{c.i}"
    msgs = [m for m in s.get("messages", []) if isinstance(m, dict) and m.get("text")][:7]
    name = s.get("name") or "Chat"
    html = (_head(s, c) + f'<div class="ph card"><div class="hd"><div class="av">{V.icon_svg(s.get("icon") or "user", size=44)}</div>'
            f'<div><b>{E(name)}</b><span>{E(s.get("status", "online"))}</span></div></div><div class="bd" id="cb{c.i}">')
    y, area = 24, 860
    tops = []
    mine = [str(m.get("from", "them")).lower() in ("me", "you", "user", "right", "customer") for m in msgs]
    for k, m in enumerate(msgs):
        me = mine[k]
        lines = max(1, math.ceil(len(str(m["text"])) / 24)); h = 30 + lines * 50
        tops.append((y, h)); html += f'<div class="msg {"me" if me else "them"}" id="cm{c.i}_{k}" style="top:{y}px">{E(m["text"])}</div>'
        y += h + 22
    html += f'<div class="typing" id="ct{c.i}"><i></i><i></i><i></i></div></div></div>'
    ts = _cues(c, msgs, "cue", "text", 0.03, 0.88)
    js = (f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c) +
          f'      tl.fromTo("{S} .ph", {{ y: 900, rotation: 3 }}, {{ y: 0, rotation: 0, duration: 0.5, ease: "power4.out" }}, {c.sb + 0.05:.3f});\n'
          f'      tl.fromTo("{S} .typing i", {{ y: 0 }}, {{ y: -10, duration: 0.25, yoyo: true, repeat: {int((c.se - c.sb) / 0.25)}, stagger: 0.08, ease: "sine.inOut" }}, {c.sb:.3f});\n')
    for k, (t, (top, h)) in enumerate(zip(ts, tops)):
        me = mine[k]
        js += (f'      tl.set("#ct{c.i}", {{ top: {top}, opacity: {0 if me else 1}, left: {0 if not me else 600} }}, {max(c.sb, t - 0.6):.3f});\n'
               f'      tl.set("#ct{c.i}", {{ opacity: 0 }}, {t - 0.12:.3f});\n'
               f'      tl.fromTo("#cm{c.i}_{k}", {{ scale: 0.3, opacity: 0, transformOrigin: "{"100%" if me else "0%"} 100%" }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "back.out(1.8)" }}, {t - 0.12:.3f});\n')
        if top + h > area:   # scroll the conversation up like a real phone
            js += f'      tl.to("#cb{c.i}", {{ y: {-(top + h - area)}, duration: 0.3, ease: "power2.out" }}, {t - 0.15:.3f});\n'
        c.sfx("pop", t, 0.45, 1300 if me else 900)
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .ph")
    return html, js


# ------------------------------------------------------------------ reveal
def reveal(s, c):
    S = f"#s{c.i}"
    b, a = s.get("before") or {}, s.get("after") or {}
    html = (_head(s, c) + f'<div class="rv"><div class="side bef">{_img_or_icon(b, "im", 280)}<span class="tag">{E(b.get("label", "Before"))}</span></div>'
            f'<div class="side aft" id="ra{c.i}">{_img_or_icon(a, "im", 280)}<span class="tag r">{E(a.get("label", "After"))}</span></div>'
            f'<div class="handle" id="rh{c.i}"><i>{V.icon_svg("chevrons-left-right", size=48)}</i></div></div>')
    if s.get("caption"): html += f'<div class="ctr cap">{E(s["caption"])}</div>'
    tb = c.cue(b.get("cue") or "x", c.sb, frac=0.2)
    ta = c.cue(a.get("cue") or s.get("cue") or "x", tb, frac=0.55)
    t0 = max(tb + 0.5, ta - 0.5)
    js = (f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c) +
          f'      tl.fromTo("{S} .rv", {{ y: 80, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, {c.sb + 0.1:.3f});\n'
          f'      tl.fromTo("#ra{c.i}", {{ clipPath: "inset(0 0 0 100%)" }}, {{ clipPath: "inset(0 0 0 0%)", duration: 1.1, ease: "power2.inOut" }}, {t0:.3f});\n'
          f'      tl.fromTo("#rh{c.i}", {{ left: "100%" }}, {{ left: "0%", duration: 1.1, ease: "power2.inOut" }}, {t0:.3f});\n'
          f'      tl.to("#rh{c.i}", {{ left: "50%", duration: 0.6, ease: "power2.out" }}, {t0 + 1.25:.3f});\n'
          f'      tl.to("#ra{c.i}", {{ clipPath: "inset(0 0 0 50%)", duration: 0.6, ease: "power2.out" }}, {t0 + 1.25:.3f});\n'
          f'      tl.fromTo("{S} .cap", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.3 }}, {t0 + 1.4:.3f});\n')
    c.sfx("whoosh", t0, 0.5); c.sfx("shimmer", t0 + 1.0, 0.4)
    bh, bj = MO.burst(c, 540, 800, t0 + 1.25, "#ffffff", radius=180); html += bh; js += bj
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .rv, {S} .cap")
    return html, js


BUILDERS = {"pictogram": pictogram, "kpis": kpis, "bubbles": bubbles, "gauge": gauge, "funnel": funnel, "cycle": cycle, "chat": chat, "reveal": reveal}


# ------------------------------------------------------------------ spotlight (the original "icon storm", for any topic)
def spotlight(s, c):
    """A big line-drawn hero icon; related icons fly in and orbit it as they are named; then a climax:
    mood "bad" = shake, alert colour, zaps (a problem); "good" = glow, fill, burst, check badge (a win)."""
    S = f"#s{c.i}"
    sats = [x if isinstance(x, dict) else {"icon": x} for x in (s.get("satellites") or [])][:8]
    n = len(sats); mood = s.get("mood", "good")
    has_head = bool(s.get("title") or s.get("kicker"))
    CX, CY, R = 540, (830 if has_head else 780), 330
    html = _head(s, c)
    html += f'<div class="halo" style="left:{CX - 330}px;top:{CY - 330}px"></div>'
    html += (f'<svg class="ring" viewBox="0 0 800 800" width="800" height="800" style="left:{CX - 400}px;top:{CY - 400}px">'
             f'<circle cx="400" cy="400" r="{R}" /></svg>')
    html += f'<div class="hero" style="left:{CX - 190}px;top:{CY - 190}px">{V.icon_svg(s.get("icon") or s.get("title") or "", size=230, stroke=1.6)}</div>'
    html += f'<div class="orb" style="left:{CX}px;top:{CY}px">'
    for k, it in enumerate(sats):
        a = math.radians(-90 + 360 * k / max(1, n) + (0 if n % 2 else 360 / max(1, n) / 2))
        x, y = R * math.cos(a), R * math.sin(a)
        lbl = f'<span>{E(it["label"])}</span>' if it.get("label") else ""
        html += (f'<div class="sat" id="sa{c.i}_{k}" style="left:{x - 72:.0f}px;top:{y - 72:.0f}px" data-x="{x:.0f}" data-y="{y:.0f}">'
                 f'<div class="chip">{V.icon_svg(it.get("icon") or it.get("label") or "", size=74)}</div>{lbl}</div>')
    html += '</div>'
    if mood == "bad":
        html += (f'<div class="zap z1" style="left:{CX - 260}px;top:{CY - 250}px">{V.icon_svg("zap", size=90, stroke=2.2)}</div>'
                 f'<div class="zap z2" style="left:{CX + 170}px;top:{CY - 200}px">{V.icon_svg("zap", size=72, stroke=2.2)}</div>')
    elif mood == "good":
        html += f'<div class="badge-ok" style="left:{CX + 95}px;top:{CY - 195}px">{V.icon_svg("check", size=64, stroke=3)}</div>'
    if s.get("caption"): html += f'<div class="ctr sf cap fit" style="top:{CY + 430}px">{E(s["caption"])}{(" <em>" + E(s["caption_em"]) + "</em>") if s.get("caption_em") else ""}</div>'
    ts = _cues(c, sats, "cue", "label", 0.15, 0.7)
    t_cl = c.cue(s["climax_cue"], (ts[-1] if ts else c.sb) + 0.2, frac=0.85) if s.get("climax_cue") else \
        (ts[-1] if ts else c.sb + 1) + 0.35
    t_cl = max(c.sb + 0.9, min(t_cl, c.se - 1.3))   # leave time to see the climax before the scene changes
    js = (f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.05, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c) +
          f'      tl.fromTo("{S} .halo", {{ scale: 0.3, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.7, ease: "power2.out" }}, {c.sb + 0.1:.3f});\n'
          f'      tl.fromTo("{S} .hero", {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.6)" }}, {c.sb + 0.12:.3f});\n'
          + MO.draw(f"{S} .hero svg", c.sb + 0.2, 0.9) +
          f'      drawPath(tl, "{S} .ring circle", {c.sb + 0.3:.3f}, 1.0);\n'
          f'      tl.fromTo("{S} .orb", {{ rotation: 0 }}, {{ rotation: 38, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb:.3f});\n'
          f'      tl.fromTo("{S} .sat", {{ rotation: 0 }}, {{ rotation: -38, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb:.3f});\n')
    for k, (it, t) in enumerate(zip(sats, ts)):
        a = math.radians(-90 + 360 * k / max(1, n) + (0 if n % 2 else 360 / max(1, n) / 2))
        js += (f'      tl.fromTo("#sa{c.i}_{k} .chip", {{ x: {math.cos(a) * 520:.0f}, y: {math.sin(a) * 520:.0f}, rotation: {(-1) ** k * 120}, scale: 0.4, opacity: 0 }}, '
               f'{{ x: 0, y: 0, rotation: 0, scale: 1, opacity: 1, duration: 0.5, ease: "expo.out" }}, {t - 0.25:.3f});\n'
               f'      tl.fromTo("#sa{c.i}_{k} span", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.25 }}, {t + 0.1:.3f});\n'
               f'      tl.to("{S} .hero", {{ scale: 1.06, duration: 0.08, yoyo: true, repeat: 1 }}, {t + 0.05:.3f});\n')
        js += MO.draw(f"#sa{c.i}_{k} .chip svg", t - 0.15, 0.5)
        c.sfx("pop", t, 0.5, 800 + 110 * k)
    # climax
    js += f'      tl.to("{S} .cam", {{ scale: 1.1, duration: 0.14, ease: "back.out(1.5)" }}, {t_cl:.3f});\n      tl.to("{S} .cam", {{ scale: 1.02, duration: 0.5, ease: "power2.out" }}, {t_cl + 0.14:.3f});\n'
    if mood == "bad":
        js += (f'      tl.to("{S} .hero", {{ borderColor: "var(--alert)", color: "var(--alert)", backgroundColor: "var(--alert-15)", duration: 0.2 }}, {t_cl:.3f});\n'
               f'      tl.to("{S} .halo", {{ background: "radial-gradient(circle, var(--alert-45), transparent 68%)", duration: 0.25 }}, {t_cl:.3f});\n'
               f'      tl.to("{S} .chip", {{ color: "var(--alert)", borderColor: "var(--alert)", duration: 0.2, stagger: 0.03 }}, {t_cl:.3f});\n'
               f'      tl.fromTo("{S} .zap", {{ scale: 0, rotation: -30 }}, {{ scale: 1, rotation: 0, duration: 0.28, ease: pop, stagger: 0.12 }}, {t_cl + 0.05:.3f});\n'
               + MO.shake(f"{S} .hero", t_cl, 16, 7))
        c.sfx("thud", t_cl, 0.9)
    elif mood == "good":
        js += (f'      tl.to("{S} .hero", {{ backgroundColor: "var(--primary)", borderColor: "var(--primary)", color: "var(--on-primary)", duration: 0.25 }}, {t_cl:.3f});\n'
               f'      tl.fromTo("{S} .badge-ok", {{ scale: 0, rotation: -60 }}, {{ scale: 1, rotation: 0, duration: 0.35, ease: "back.out(2.2)" }}, {t_cl + 0.1:.3f});\n'
               f'      tl.to("{S} .chip", {{ backgroundColor: "var(--pale)", duration: 0.2, stagger: 0.03 }}, {t_cl:.3f});\n')
        bh, bj = MO.burst(c, CX, CY, t_cl, "var(--primary)", radius=300, size=22); html += bh; js += bj
        c.sfx("thud", t_cl, 0.8)
    if s.get("caption"): js += f'      tl.fromTo("{S} .cap", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap }}, {t_cl + 0.15:.3f});\n'
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .halo, {S} .ring, {S} .hero, {S} .orb, {S} .zap, {S} .badge-ok, {S} .cap")
    return html, js


BUILDERS["spotlight"] = spotlight
