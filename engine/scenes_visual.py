"""Picture-first scenes: the script shown as photos, charts, diagrams, icons and maps instead of text.

  photo    one full-screen real photo + short caption                       (image_query / photo)
  gallery  2-4 photo tiles with 1-3 word labels, each appearing as it is said (tiles[{label, image_query, icon, cue}])
  chart    bar | column | line | donut | pie chart that builds as the numbers are spoken (data[{label, value, ...}])
  flow     a process diagram: 3-5 icon nodes joined by arrows, a dot travels between them (nodes[{label, icon, cue}])
  icons    a grid of 3-6 big icons with short labels (items[{label, icon, cue}])
  versus   two sides with photos/icons and short points, "VS" in the middle (left{...}, right{...})
  map      world map that zooms to the countries named, with pins and labels (places[{country, label, cue}])
"""
import json
from html import escape as E

import visuals as V
import motion as MO

SERIES = ["var(--primary)", "var(--alert)", "var(--accent)", "var(--mix2)", "var(--accent-dark)", "var(--dim)", "var(--mix1)"]   # neighbours contrast


def _exit(c, sel):
    return "" if c.last else f'tl.to("{sel}", {{ y: -1500, duration: 0.30, ease: "power4.in", stagger: 0.02 }}, {c.se - 0.28:.3f});\n'


def _cues(c, items, key="cue", fallback_key=None, start=0.08, span=0.85):
    """Time for each item: when its cue word is spoken, otherwise spread across the scene."""
    out, after = [], c.sb
    for k, it in enumerate(items):
        it = it if isinstance(it, dict) else {}
        cue = it.get(key)
        if not cue and fallback_key: cue = (str(it.get(fallback_key, "")).split() or [""])[0]
        t = c.cue(cue or "x", after, frac=start + span * k / max(1, len(items)))
        out.append(t); after = t
    return out


def _fmt(v, unit="", decimals=None):
    try: x = float(v)
    except (TypeError, ValueError): return str(v)
    d = decimals if decimals is not None else (0 if x.is_integer() else 1)
    s = f"{x:,.{d}f}" if abs(x) >= 10000 else f"{x:.{d}f}"
    return s + (unit or "")


def _head(s, c):
    """Kicker + title at the top of a scene (both optional)."""
    h = ""
    if s.get("kicker"): h += f'<div class="ctr k kick">{E(s["kicker"])}</div>'
    if s.get("title"):
        em = f' <em>{E(s["title_em"])}</em>' if s.get("title_em") else ""
        h += f'<div class="ctr sf t fit">{E(s["title"])}{em}</div>'
    return h


def _head_js(S, c):
    return f'tl.fromTo("{S} .kick, {S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap, stagger: 0.06 }}, {c.sb + 0.05:.3f});\n'


def _img_or_icon(it, cls, icon_size=150):
    if it.get("photo_file"): return f'<img class="{cls}" src="media/{E(it["photo_file"])}" alt="" />'
    return f'<div class="{cls} noimg">{V.icon_svg(it.get("icon") or it.get("label") or it.get("text") or "", size=icon_size)}</div>'


# ------------------------------------------------------------------ photo
def photo(s, c):
    """Full-screen photo with a slow push-in and a short caption."""
    S = f"#s{c.i}"
    img = f'<img class="bp" src="media/{E(s["photo_file"])}" alt="" />' if s.get("photo_file") else \
          f'<div class="bp noimg">{V.icon_svg(s.get("icon") or s.get("caption") or "", size=420)}</div>'
    cap_em = f'<br/><em>{E(s["caption_em"])}</em>' if s.get("caption_em") else ""
    pos = "bottom" if s.get("caption_position") == "bottom" else "top"
    html = (f'<div class="full" data-layout-allow-overflow="true">{img}<div class="shade {pos}"></div></div>'
            f'<div class="ctr k kick {pos}">{E(s.get("kicker", ""))}</div><div class="ctr sf cap fit {pos}">{E(s.get("caption", ""))}{cap_em}</div>')
    tc = c.cue(s.get("cue", "x"), c.sb, frac=0.15)
    zoom = (1.22, 1.03) if s.get("motion", "in") == "in" else (1.03, 1.2)
    js = f'''tl.fromTo("{S} .full", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.35 }}, {c.sb});
      tl.fromTo("{S} .full .bp", {{ scale: {zoom[0]}, xPercent: {-2 if c.i % 2 else 2} }}, {{ scale: {zoom[1]}, xPercent: 0, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .kick", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: snap }}, {c.sb + 0.15:.3f});
      tl.fromTo("{S} .cap", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, {max(c.sb + 0.2, tc - 0.25):.3f});
'''
    if not c.last: js += f'      tl.to("{S} .kick, {S} .cap", {{ y: -80, opacity: 0, duration: 0.28, ease: "power3.in" }}, {c.se - 0.3:.3f});\n'
    c.sfx("whoosh", c.sb + 0.05, 0.35)
    return html, js


# ------------------------------------------------------------------ gallery
def gallery(s, c):
    """2-4 photo tiles with short labels; each tile pops in as it is mentioned."""
    S = f"#s{c.i}"
    tiles = [t for t in s.get("tiles", []) if isinstance(t, dict)][:4]
    n = len(tiles)
    top, W = 330 if (s.get("title") or s.get("kicker")) else 220, 920
    H = 1320 - top
    if n <= 2: boxes = [(80, top + k * (H // 2 + 10), W, H // 2 - 10) for k in range(n)]
    elif n == 3: boxes = [(80, top, W, H // 2 - 10), (80, top + H // 2 + 10, W // 2 - 10, H // 2 - 10), (80 + W // 2 + 10, top + H // 2 + 10, W // 2 - 10, H // 2 - 10)]
    else: boxes = [(80 + (k % 2) * (W // 2 + 10), top + (k // 2) * (H // 2 + 10), W // 2 - 10, H // 2 - 10) for k in range(4)]
    html = _head(s, c)
    for k, (t, (x, y, w, h)) in enumerate(zip(tiles, boxes)):
        html += (f'<div class="tile" id="gt{c.i}_{k}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">{_img_or_icon(t, "im", min(w, h) // 3)}'
                 f'<div class="lb">{V.icon_svg(t.get("icon") or t.get("label", ""), size=40) if t.get("icon") else ""}<span class="fit">{E(t.get("label", ""))}</span></div></div>')
    ts = _cues(c, tiles, "cue", "label", 0.05, 0.85)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    for k, t in enumerate(ts):
        js += f'''      tl.fromTo("#gt{c.i}_{k}", {{ scale: 0.7, opacity: 0, rotation: {(-3, 3)[k % 2]} }}, {{ scale: 1, opacity: 1, rotation: 0, duration: 0.38, ease: "back.out(1.5)" }}, {t - 0.25:.3f});
      tl.fromTo("#gt{c.i}_{k} .im", {{ scale: 1.25 }}, {{ scale: 1.05, duration: {max(1.0, c.se - t + 0.25):.3f}, ease: "none" }}, {t - 0.25:.3f});
      tl.fromTo("#gt{c.i}_{k} .lb", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.28, ease: snap }}, {t:.3f});
'''
        c.sfx("pop", t, 0.5, 800 + 120 * k)
    for k, t in enumerate(ts): js += MO.draw(f"#gt{c.i}_{k} .noimg svg", t - 0.2, 0.7)
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .tile")
    return html, js


# ------------------------------------------------------------------ chart
def chart(s, c):
    """bar (horizontal), column, line, donut or pie. Each value appears when it is spoken."""
    S = f"#s{c.i}"
    kind = s.get("kind", "column")
    data = [d for d in s.get("data", []) if isinstance(d, dict)][:10 if kind == "line" else 7]
    vals = []
    for d in data:
        try: vals.append(float(str(d.get("value", 0)).replace(",", "")))
        except ValueError: vals.append(0.0)
    unit, dec = s.get("unit", ""), s.get("decimals")
    disp = [str(d.get("display") or _fmt(v, unit, dec)) for d, v in zip(data, vals)]
    hi = s.get("highlight")   # index or label of the bar to emphasise
    hi_i = hi if isinstance(hi, int) else next((k for k, d in enumerate(data) if str(d.get("label")) == str(hi)), -1)
    html = _head(s, c)
    if s.get("source"): html += f'<div class="ctr src">Source: {E(s["source"])}</div>'
    ts = _cues(c, data, "cue", None, 0.12, 0.75)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    if s.get("source"): js += f'      tl.fromTo("{S} .src", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {c.sb + 0.6:.3f});\n'
    mx = max([abs(v) for v in vals] + [1e-9]); pts = []
    col = lambda k: "var(--alert)" if k == hi_i else ("var(--primary)" if hi_i < 0 or kind in ("donut", "pie") else "var(--mix2)")
    if kind == "bar":
        n = len(data); gap = min(250, 900 // max(1, n)); top = 360 + (900 - n * gap) // 2
        thick = 64 if n <= 3 else 48 if n <= 5 else 34
        for k, (d, v) in enumerate(zip(data, vals)):
            ic = V.icon_svg(d["icon"], size=46) if d.get("icon") else ""
            html += (f'<div class="hb" style="top:{top + k * gap}px"><div class="n">{ic}<span class="fit">{E(d.get("label", ""))}</span><b>{E(disp[k])}</b></div>'
                     f'<div class="tr" style="height:{thick}px;border-radius:{thick // 2}px"><i id="cb{c.i}_{k}" style="width:{max(1.5, abs(v) / mx * 100):.1f}%;border-radius:{thick // 2}px;background:{col(k)}"></i></div></div>')
            js += f'      tl.fromTo("#cb{c.i}_{k}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.6, ease: "power3.out" }}, {ts[k] - 0.2:.3f});\n'
            js += f'      tl.fromTo("{S} .hb:nth-of-type({k + 1}) .n", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.25 }}, {ts[k] - 0.3:.3f});\n'
    elif kind in ("donut", "pie"):
        tot = sum(max(0, v) for v in vals) or 1; R = 230 if kind == "donut" else 125; SW = 90 if kind == "donut" else 250
        C = 2 * 3.14159265 * R; acc = 0.0; segs = ""
        for k, v in enumerate(vals):
            L = max(0, v) / tot * C
            segs += (f'<circle id="dn{c.i}_{k}" cx="300" cy="300" r="{R}" fill="none" stroke="{SERIES[k % len(SERIES)]}" stroke-width="{SW}" '
                     f'stroke-dasharray="0 {C:.1f}" transform="rotate({-90 + acc / C * 360:.2f} 300 300)"/>')
            js += f'      tl.to("#dn{c.i}_{k}", {{ attr: {{ "stroke-dasharray": "{max(0, L - 3):.1f} {C:.1f}" }}, duration: 0.6, ease: "power2.out" }}, {ts[k] - 0.15:.3f});\n'
            acc += L
        center = s.get("center") or (disp[0] if data else "")
        center_lbl = s.get("center_label") or (data[0].get("label", "") if data else "")
        html += f'<svg class="donut" viewBox="0 0 600 600" width="640" height="640">{segs}</svg>'
        if kind == "donut": html += f'<div class="dc"><b class="fit">{E(center)}</b><span>{E(center_lbl)}</span></div>'
        two = len(data) > 4 and max(len(str(d.get("label", ""))) for d in data) <= 12
        html += f'<div class="legend{" two" if two else ""}">' + "".join(
            f'<div id="lg{c.i}_{k}"><i style="background:{SERIES[k % len(SERIES)]}"></i><span>{E(d.get("label", ""))}</span><b>{E(disp[k])}</b></div>'
            for k, d in enumerate(data)) + "</div>"
        for k, t in enumerate(ts): js += f'      tl.fromTo("#lg{c.i}_{k}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.25 }}, {t - 0.1:.3f});\n'
        if kind == "donut": js += f'      tl.fromTo("{S} .dc", {{ scale: 0.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.4, ease: pop }}, {ts[0] + 0.3 if ts else c.sb + 1:.3f});\n'
    elif kind == "line":
        n = len(vals); X0, X1, Y0, Y1 = 60, 820, 40, 560
        lo, hiv = min(vals + [0]), max(vals + [1e-9])
        if min(vals) > 0 and (max(vals) - min(vals)) / max(vals) < 0.35: lo = min(vals) - (max(vals) - min(vals)) * 0.25
        pts = [(X0 + (X1 - X0) * k / max(1, n - 1), Y1 - (v - lo) / max(1e-9, hiv - lo) * (Y1 - Y0)) for k, v in enumerate(vals)]
        dpath = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        area = dpath + f" L{pts[-1][0]:.1f} {Y1} L{pts[0][0]:.1f} {Y1} Z" if pts else ""
        grid = "".join(f'<line x1="{X0}" x2="{X1}" y1="{Y0 + (Y1 - Y0) * g / 4:.0f}" y2="{Y0 + (Y1 - Y0) * g / 4:.0f}" class="gl"/>' for g in range(5))
        dots = "".join(f'<circle id="ld{c.i}_{k}" cx="{x:.1f}" cy="{y:.1f}" r="13" class="dot"/>' for k, (x, y) in enumerate(pts))
        show = range(n) if n <= 6 else sorted({0, n - 1, int(max(range(n), key=lambda k: vals[k])), hi_i if hi_i >= 0 else 0})
        labels = "".join(f'<text id="lv{c.i}_{k}" x="{pts[k][0]:.1f}" y="{pts[k][1] - 30:.1f}" class="vl">{E(disp[k])}</text>' for k in show)
        xl = "".join(f'<text x="{x:.1f}" y="{Y1 + 52}" class="xl">{E(str(data[k].get("label", "")))}</text>' for k, (x, _) in enumerate(pts) if n <= 8 or k % 2 == 0 or k == n - 1)
        html += (f'<svg class="lc" viewBox="0 0 880 640" width="880" height="640">{grid}<path class="ar" d="{area}"/>'
                 f'<path class="ln" d="{dpath}"/>{dots}{labels}{xl}</svg>')
        t0, t1 = (ts[0] - 0.2, ts[-1]) if ts else (c.sb + 0.5, c.se - 1)
        t1 = max(t1, t0 + 0.8)
        js += f'      drawPath(tl, "{S} .ln", {t0:.3f}, {t1 - t0:.3f});\n      tl.fromTo("{S} .ar", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.6 }}, {t1 - 0.3:.3f});\n'
        for k in range(n):
            tk = t0 + (t1 - t0) * k / max(1, n - 1)
            js += f'      tl.fromTo("#ld{c.i}_{k}", {{ scale: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, duration: 0.2, ease: pop }}, {tk:.3f});\n'
            if k in show: js += f'      tl.fromTo("#lv{c.i}_{k}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2 }}, {tk + 0.05:.3f});\n'
    else:   # column
        n = len(data); gap = 26 if n > 4 else 40; w = (860 - gap * (n - 1)) / max(1, n)
        for k, (d, v) in enumerate(zip(data, vals)):
            h = max(6, abs(v) / mx * 640); x = 110 + k * (w + gap)
            ic = V.icon_svg(d["icon"], size=min(64, int(w * 0.5))) if d.get("icon") else ""
            html += (f'<div class="cl" style="left:{x:.0f}px;width:{w:.0f}px"><b style="bottom:{h + 16:.0f}px" id="cv{c.i}_{k}">{E(disp[k])}</b>'
                     f'<i id="cc{c.i}_{k}" style="height:{h:.0f}px;background:{col(k)}"></i><span>{ic}<em class="fit">{E(d.get("label", ""))}</em></span></div>')
            js += f'      tl.fromTo("#cc{c.i}_{k}", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.55, ease: "power3.out" }}, {ts[k] - 0.2:.3f});\n'
            js += f'      tl.fromTo("#cv{c.i}_{k}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.25 }}, {ts[k] + 0.2:.3f});\n'
    for t in ts: c.sfx("pop", t, 0.45, 950)
    for k, t in enumerate(ts): js += MO.draw(f"{S} .cl:nth-of-type({k + 1}) svg, {S} .hb:nth-of-type({k + 1}) svg", t - 0.2, 0.5)
    if ts and kind in ("donut", "pie"):
        bh, bj = MO.burst(c, 540, 680, ts[-1] + 0.5, "var(--primary)"); html += bh; js += bj
    elif ts and kind == "line" and pts:
        bh, bj = MO.burst(c, 100 + pts[-1][0], 420 + pts[-1][1], max(ts[-1], ts[0] + 0.8) + 0.05, "var(--primary)", radius=120); html += bh; js += bj
    elif ts and kind == "column" and data:
        kk = hi_i if 0 <= hi_i < len(data) else max(range(len(vals)), key=lambda q: vals[q])
        n_ = len(data); g_ = 26 if n_ > 4 else 40; w_ = (860 - g_ * (n_ - 1)) / max(1, n_)
        bh, bj = MO.burst(c, 110 + kk * (w_ + g_) + w_ / 2, 1120 - max(6, abs(vals[kk]) / mx * 640) - 40, ts[kk] + 0.35, "var(--alert)" if hi_i >= 0 else "var(--primary)", radius=140)
        html += bh; js += bj
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .src, {S} .hb, {S} .donut, {S} .dc, {S} .legend, {S} .lc, {S} .cl")
    return html, js


# ------------------------------------------------------------------ flow diagram
def flow(s, c):
    """Process diagram: icon nodes top to bottom, arrows drawn between them, a dot travels along."""
    S = f"#s{c.i}"
    nodes = [n for n in s.get("nodes", []) if isinstance(n, dict)][:5]
    n = len(nodes)
    top = 340 if (s.get("title") or s.get("kicker")) else 250
    gap = min(250, (1300 - top) // max(1, n))
    html = _head(s, c)
    cx = 200
    for k, nd in enumerate(nodes):
        y = top + k * gap
        sub = f'<div class="sb">{E(nd["sub"])}</div>' if nd.get("sub") else ""
        html += (f'<div class="nd" id="fn{c.i}_{k}" style="top:{y}px"><div class="cir">{V.icon_svg(nd.get("icon") or nd.get("label", ""), size=84)}</div>'
                 f'<div class="lbx card"><div class="lb fit">{E(nd.get("label", ""))}</div>{sub}</div></div>')
        if k < n - 1:
            html += (f'<svg class="ar" style="top:{y + 150}px;height:{gap - 150}px" width="40" height="{gap - 150}" viewBox="0 0 40 {gap - 150}">'
                     f'<path id="fa{c.i}_{k}" d="M20 4 L20 {gap - 166}" /><path id="fh{c.i}_{k}" class="hd" d="M8 {gap - 176} L20 {gap - 160} L32 {gap - 176}"/></svg>'
                     f'<div class="pk" id="fp{c.i}_{k}" style="left:{cx - 13}px;top:{y + 150}px"></div>')
    ts = _cues(c, nodes, "cue", "label", 0.05, 0.85)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    for k, t in enumerate(ts):
        js += f'''      tl.fromTo("#fn{c.i}_{k} .cir", {{ scale: 0, rotation: -40 }}, {{ scale: 1, rotation: 0, duration: 0.4, ease: "back.out(1.6)" }}, {t - 0.2:.3f});
      tl.fromTo("#fn{c.i}_{k} .lbx", {{ x: 400, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.35, ease: "power4.out" }}, {t - 0.1:.3f});
      tl.to("#fn{c.i}_{k} .cir", {{ backgroundColor: "var(--primary)", color: "var(--on-primary)", duration: 0.2 }}, {t:.3f});
'''
        if k > 0: js += f'      tl.to("#fn{c.i}_{k - 1} .cir", {{ backgroundColor: "var(--surface)", color: "var(--primary)", duration: 0.3 }}, {t:.3f});\n'
        if k < n - 1:
            nxt = ts[k + 1]; a0 = max(t + 0.2, nxt - 0.75); d = max(0.25, nxt - 0.25 - a0)
            js += f'''      drawPath(tl, "#fa{c.i}_{k}", {a0:.3f}, {d:.3f});
      tl.fromTo("#fh{c.i}_{k}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1 }}, {a0 + d:.3f});
      tl.fromTo("#fp{c.i}_{k}", {{ y: 0, opacity: 1, scale: 1 }}, {{ y: {gap - 165}, duration: {d:.3f}, ease: "power1.inOut" }}, {a0:.3f});
      tl.to("#fp{c.i}_{k}", {{ opacity: 0, scale: 0.3, duration: 0.15 }}, {a0 + d:.3f});
'''
            c.sfx("whoosh", a0, 0.2)
        c.sfx("pop", t, 0.5, 850 + 110 * k)
        js += MO.draw(f"#fn{c.i}_{k} .cir svg", t - 0.1, 0.6)
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .nd, {S} .ar")
    return html, js


# ------------------------------------------------------------------ icon grid
def icons(s, c):
    """3-6 big icons with 1-3 word labels."""
    S = f"#s{c.i}"
    items = [it for it in s.get("items", []) if isinstance(it, dict)][:6]
    n = len(items); cols = 2 if n in (2, 4) or n > 4 else 1 if n == 1 else 3 if n == 3 and s.get("row") else 2
    if n == 3 and not s.get("row"): cols = 1
    rows = -(-n // cols); top = 350 if (s.get("title") or s.get("kicker")) else 260
    H = (1320 - top) // max(1, rows); W = 920 // cols
    html = _head(s, c)
    for k, it in enumerate(items):
        x, y = 80 + (k % cols) * W, top + (k // cols) * H
        horiz = cols == 1
        html += (f'<div class="ic{" h" if horiz else ""}" id="ig{c.i}_{k}" style="left:{x + 8}px;top:{y + 8}px;width:{W - 16}px;height:{H - 16}px">'
                 f'<div class="bub">{V.icon_svg(it.get("icon") or it.get("label", ""), size=110 if not horiz else 90)}</div>'
                 f'<div class="lb fit">{E(it.get("label", ""))}</div></div>')
    ts = _cues(c, items, "cue", "label", 0.05, 0.85)
    js = f'tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n      ' + _head_js(S, c)
    for k, t in enumerate(ts):
        js += f'''      tl.fromTo("#ig{c.i}_{k}", {{ y: 60, opacity: 0, scale: 0.8 }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.32, ease: "back.out(1.5)" }}, {t - 0.2:.3f});
      tl.fromTo("#ig{c.i}_{k} .bub svg", {{ scale: 0.3, rotation: -30 }}, {{ scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2)" }}, {t - 0.12:.3f});
      tl.to("#ig{c.i}_{k} .bub", {{ backgroundColor: "var(--primary)", color: "var(--on-primary)", duration: 0.2 }}, {t:.3f});
'''
        c.sfx("pop", t, 0.5, 900 + 100 * k)
        js += MO.draw(f"#ig{c.i}_{k} .bub svg", t - 0.05, 0.6)
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .ic")
    return html, js


# ------------------------------------------------------------------ versus
def versus(s, c):
    """Two sides, each with a photo (or icon), a name and up to 3 short points; "VS" between them."""
    S = f"#s{c.i}"
    L, R = s.get("left") or {}, s.get("right") or {}
    def side(d, cls):
        pts = "".join(f'<li>{V.icon_svg(p.get("icon") if isinstance(p, dict) and p.get("icon") else ("circle-check" if cls == "r" else "circle-minus"), size=36)}'
                      f'<span>{E(p.get("text", "") if isinstance(p, dict) else p)}</span></li>' for p in (d.get("points") or [])[:3])
        return (f'<div class="vs-{cls}">{_img_or_icon(d, "im", 170)}<div class="nm fit">{E(d.get("label", ""))}</div><ul>{pts}</ul></div>')
    html = _head(s, c) + side(L, "l") + side(R, "r") + '<div class="badge">VS</div>'
    tl_ = c.cue(L.get("cue", "x"), c.sb, frac=0.15)
    tr = c.cue(R.get("cue", "x"), tl_, frac=0.55)
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      {_head_js(S, c)}      tl.fromTo("{S} .vs-l", {{ x: -700, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.4, ease: "power4.out" }}, {tl_ - 0.25:.3f});
      tl.fromTo("{S} .vs-l li", {{ opacity: 0, x: -20 }}, {{ opacity: 1, x: 0, duration: 0.22, stagger: 0.18 }}, {tl_ + 0.2:.3f});
      tl.fromTo("{S} .badge", {{ scale: 0, rotation: -90 }}, {{ scale: 1, rotation: 0, duration: 0.35, ease: pop }}, {(tl_ + tr) / 2:.3f});
      tl.fromTo("{S} .vs-r", {{ x: 700, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.4, ease: "power4.out" }}, {tr - 0.25:.3f});
      tl.fromTo("{S} .vs-r li", {{ opacity: 0, x: 20 }}, {{ opacity: 1, x: 0, duration: 0.22, stagger: 0.18 }}, {tr + 0.2:.3f});
'''
    c.sfx("whoosh", tl_ - 0.25, 0.3); c.sfx("thud", (tl_ + tr) / 2, 0.7); c.sfx("whoosh", tr - 0.25, 0.3)
    bh, bj = MO.burst(c, 795, 560, tr + 0.25, "var(--primary)", radius=200); html += bh; js += bj
    js += MO.draw(f"{S} .vs-l li svg", tl_ + 0.2, 0.45, 0.18) + MO.draw(f"{S} .vs-r li svg", tr + 0.2, 0.45, 0.18)
    js += MO.draw(f"{S} .noimg svg", c.sb + 0.2, 0.8)
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .vs-l, {S} .vs-r, {S} .badge")
    return html, js


# ------------------------------------------------------------------ map
MAP_TOP, MAP_W, MAP_H = 330, 1080, 960


def _fit(box, pad=0.35, min_w=110):
    x, y, w, h = box
    w2, h2 = max(w * (1 + 2 * pad), min_w), max(h * (1 + 2 * pad), min_w * MAP_H / MAP_W)
    cx, cy = x + w / 2, y + h / 2
    if w2 / h2 > MAP_W / MAP_H: h2 = w2 * MAP_H / MAP_W
    else: w2 = h2 * MAP_W / MAP_H
    return [cx - w2 / 2, cy - h2 / 2, w2, h2]


def world_map(s, c):
    """World map: zooms to the countries named, colours them and drops labelled pins as they are spoken."""
    S = f"#s{c.i}"
    W = V.world(); C = W["countries"]
    places = []
    for p in (s.get("places") or [])[:6]:
        p = p if isinstance(p, dict) else {"country": p}
        cid = V.country_id(p.get("country") or p.get("label"))
        if cid: places.append({**p, "id": cid})
        else: c.warns.append(f'scene {c.i + 1}: unknown country "{p.get("country")}" on the map')
    ids = {p["id"] for p in places}
    paths = "".join(f'<path id="mp{c.i}_{k}" d="{v["path"]}" class="{"on" if k in ids else ""}"/>' for k, v in C.items())
    if places:
        bx = [C[p["id"]]["box"] for p in places]
        x0, y0 = min(b[0] for b in bx), min(b[1] for b in bx)
        x1, y1 = max(b[0] + b[2] for b in bx), max(b[1] + b[3] for b in bx)
        vb = _fit([x0, y0, x1 - x0, y1 - y0], 0.45 if len(places) == 1 else 0.25)
    else:
        vb = _fit([0, 30, 1010, 600], 0)
    start = _fit([0, 40, 1010, 560], 0)
    html = _head(s, c) + (f'<svg class="wm" viewBox="{" ".join(f"{v:.1f}" for v in start)}" width="{MAP_W}" height="{MAP_H}" '
                          f'preserveAspectRatio="xMidYMid meet" style="top:{MAP_TOP}px">{paths}</svg>')
    ts = _cues(c, places, "cue", "label", 0.15, 0.75)
    tz = max(c.sb + 0.3, (ts[0] - 0.9) if ts else c.sb + 0.4)
    for k, p in enumerate(places):
        b = C[p["id"]]["box"]
        px = (b[0] + b[2] / 2 - vb[0]) * MAP_W / vb[2]
        py = MAP_TOP + (b[1] + b[3] / 2 - vb[1]) * MAP_H / vb[3]
        lbl = p.get("label") or C[p["id"]]["name"]
        val = f'<b>{E(p["value"])}</b>' if p.get("value") else ""
        side = "l" if px > 760 else "r" if px < 320 else "c"
        if k == 0: px0 = (px, py)
        html += f'<div class="pin {side}" id="pn{c.i}_{k}" style="left:{px:.0f}px;top:{py:.0f}px"><i></i><span>{E(lbl)}{val}</span></div>'
    vb_s = " ".join(f"{v:.1f}" for v in vb)
    js = f'''tl.fromTo("{S} .wm", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {c.sb});
      {_head_js(S, c)}      tl.to("{S} .wm", {{ attr: {{ viewBox: "{vb_s}" }}, duration: 1.3, ease: "power3.inOut" }}, {tz:.3f});
'''
    for k, (p, t) in enumerate(zip(places, ts)):
        js += f'''      tl.fromTo("#mp{c.i}_{p["id"]}", {{ fill: "var(--land)" }}, {{ fill: "{p.get("color") or SERIES[k % 2 if k < 2 else k % len(SERIES)]}", duration: 0.35 }}, {max(t - 0.3, tz + 0.6):.3f});
      tl.fromTo("#pn{c.i}_{k}", {{ scale: 0, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "back.out(2)" }}, {max(t - 0.1, tz + 1.3):.3f});
'''
        c.sfx("pop", max(t - 0.1, tz + 1.3), 0.5, 900 + 120 * k)
        if k == 0:
            bh, bj = MO.burst(c, px0[0], px0[1], max(t - 0.1, tz + 1.3), "var(--alert)", radius=110, size=14); html += bh; js += bj
    c.sfx("whoosh", tz, 0.4)
    js += "      " + _exit(c, f"{S} .kick, {S} .t, {S} .wm, {S} .pin")
    return html, js


BUILDERS = {"photo": photo, "gallery": gallery, "chart": chart, "flow": flow, "icons": icons, "versus": versus, "map": world_map}
HIDE_BRAND = {"photo"}
FULL_BLEED = {"photo"}
