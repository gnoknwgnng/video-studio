"""Scene library. Each scene type turns its JSON block into (html, js) and registers sound cues.

Every builder receives `c`, a SceneContext with:
  c.i, c.sb, c.se       scene index, start time, end time (seconds)
  c.cue(word, after)    time the word is spoken in this scene (searched after `after`; estimated if never heard)
  c.find(word, after)   same, but None when the word is not heard
  c.locale              language for number formatting
  c.sfx(kind, t, *args) add a sound effect at time t
  c.logo(cls)           big logo <div> (image or wordmark)
  c.first, c.last       first / last scene flags
"""
from html import escape as E
import visuals as V
import motion as MO


def _mark(x, fallback, size=60):
    """An item's icon (if it has one) or its number."""
    if isinstance(x, dict) and x.get("icon"): return V.icon_svg(x["icon"], size=size)
    return fallback


def _thumb(x):
    return f'<img class="th" src="media/{E(x["photo_file"])}" alt="" />' if isinstance(x, dict) and x.get("photo_file") else ""

ICONS = {
    "tooth": "M60 20 C30 20 15 45 20 80 C25 115 35 150 50 175 C58 188 70 185 72 170 L80 120 C82 110 98 110 100 120 L108 170 C110 185 122 188 130 175 C145 150 155 115 160 80 C165 45 150 20 120 20 C105 20 98 30 90 30 C82 30 75 20 60 20 Z",
    "document": "M40 18 H112 L148 54 V182 H40 Z",
    "heart": "M90 175 C40 135 15 105 20 70 C25 40 60 25 90 55 C120 25 155 40 160 70 C165 105 140 135 90 175 Z",
    "shield": "M90 20 L155 45 V100 C155 140 125 165 90 182 C55 165 25 140 25 100 V45 Z",
    "building": "M40 182 V40 H120 V80 H150 V182 Z",
    "box": "M30 60 L90 30 L150 60 V150 L90 180 L30 150 Z",
    "chip": "M45 45 H135 V155 H45 Z",
    "phone": "M58 20 H122 Q140 20 140 38 V162 Q140 180 122 180 H58 Q40 180 40 162 V38 Q40 20 58 20 Z",
    "globe": "M90 30 A70 70 0 1 1 89.9 30 Z",
    "rocket": "M90 15 C120 40 130 80 125 128 L148 162 H120 L112 178 H68 L60 162 H32 L55 128 C50 80 60 40 90 15 Z",
    "bulb": "M90 20 C125 20 150 45 150 80 C150 105 135 120 125 135 V165 H55 V135 C45 120 30 105 30 80 C30 45 55 20 90 20 Z",
    "bag": "M40 70 H140 L152 182 H28 Z",
    "user": "M90 25 A36 36 0 1 1 89.9 25 Z M28 182 C28 118 152 118 152 182 Z",
    "briefcase": "M30 72 H150 V178 H30 Z",
    "lock": "M48 95 H132 V182 H48 Z",
    "chart": "M28 182 V120 H64 V182 Z M74 182 V80 H110 V182 Z M120 182 V38 H156 V182 Z",
    "leaf": "M35 172 C35 82 90 30 160 24 C160 110 112 166 35 172 Z",
    "book": "M28 40 H84 Q90 40 90 50 V182 Q90 170 78 170 H28 Z M152 40 H96 Q90 40 90 50 V182 Q90 170 102 170 H152 Z",
    "home": "M90 22 L162 86 H142 V182 H38 V86 H18 Z",
    "cap": "M90 40 L170 76 L90 112 L10 76 Z M45 94 V136 C70 156 110 156 135 136 V94 L90 114 Z",
    "mail": "M25 52 H155 V162 H25 Z",
    "chat": "M28 35 H152 V135 H82 L50 166 V135 H28 Z",
    "bolt": "M102 14 L40 110 H86 L70 188 L142 82 H96 Z",
    "cloud": "M55 152 C24 152 18 110 45 100 C40 70 75 55 96 70 C106 44 152 50 150 86 C176 90 176 152 140 152 Z",
    "cross": "M70 30 H110 V75 H155 V115 H110 V172 H70 V115 H25 V75 H70 Z",
    "coin": "M90 34 A66 66 0 1 1 89.9 34 Z",
}
CRACK = "M88 34 L96 62 L84 86 L100 112 L92 140"
ZAP = '<svg class="zap {cls}" viewBox="0 0 40 60" width="{w}" height="{h}"><path d="M24 2 L6 34 H20 L14 58 L36 22 H22 Z" fill="var(--alert)"/></svg>'
CHECK = '<svg width="32" height="32" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" stroke="var(--on-primary)" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
OKDOT = '<svg width="34" height="34" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#1f9d6b"/><path d="M6.5 12.5l3.5 3.5L17.5 8.5" stroke="#fff" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def exit_up(c, sel):
    """Standard exit: elements fly up just before the scene ends."""
    if c.last: return ""
    return f'tl.to("{sel}", {{ y: -1500, duration: 0.30, ease: "power4.in", stagger: 0.02 }}, {c.se - 0.28:.3f});\n'


def problem(s, c):
    S = f"#s{c.i}"
    alert = (s.get("alert_word") or "").strip()
    words = [(w, False) for w in s.get("title", "").split()] + [(w, True) for w in s.get("title_em", "").split()]
    spans = []
    for w, em in words:
        cls = "w hd" if alert and w == alert else "w"
        spans.append(("<em>" if em else "") + f'<span class="{cls}">{E(w)}</span>' + ("</em>" if em else ""))
    title = " ".join(spans).replace("</em> <em>", " ")
    cards = s.get("cards", [])[:4]
    icon = s.get("icon_path") or ICONS.get(s.get("icon", "tooth"), ICONS["document"])
    minis = "".join(f'<div class="md" id="md{c.i}_{k}"><i></i><i></i><i></i></div>' for k in range(10))
    cards_html = "".join(
        f'<div class="pc card{" bad" if k == len(cards) - 1 else ""}" id="pc{c.i}_{k}"><div class="ic">{_mark(cd, f"{k + 1:02d}", 44)}</div><div class="tx fit">{E(cd["text"])}</div></div>'
        for k, cd in enumerate(cards))
    segs = "".join(f'<i id="m{c.i}_{k}"></i>' for k in range(len(cards)))
    meter = f'<div class="meter"><div class="ml k">{E(s.get("meter_label", "Pain level"))}</div><div class="segs">{segs}</div></div>' if s.get("meter_label", "x") else ""
    html = f'''
        {'<div class="flash"></div>' if c.first else ''}
        <div class="ctr k kick">{E(s.get("kicker", "The problem"))}</div>
        <div class="ctr sf t fit">{title}</div>
        <div class="stage">
          <div class="glow"></div>
          <div class="orbit">{minis}</div>
          <svg class="icon" viewBox="0 0 180 200" width="300" height="333">
            <path class="ifill" d="{icon}" fill="var(--surface)"/>
            <path class="iline" d="{icon}" fill="none" stroke="var(--primary)" stroke-width="6" stroke-linejoin="round"/>
            <path class="crack" d="{CRACK}" fill="none" stroke="var(--alert)" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          {ZAP.format(cls="zap1", w=60, h=90)}{ZAP.format(cls="zap2", w=50, h=75)}
        </div>
        <div class="grid4">{cards_html}</div>
        {meter}'''
    t_alert = c.cue(alert, c.sb, frac=0.35) if alert else c.sb + 2.5
    t_cards, after = [], c.sb + 0.5
    for k, cd in enumerate(cards):
        t = c.cue(cd.get("cue") or cd["text"].split()[-1], after, frac=0.5 + 0.4 * k / max(1, len(cards)))
        t_cards.append(t); after = t + 0.1
    t_first = t_cards[0] if t_cards else c.sb + 3
    t_last = t_cards[-1] if t_cards else c.sb + 5
    js = f'''
      {f'tl.fromTo("{S} .flash", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.35, ease: "power2.out" }}, {c.sb});' if c.first else ''}
      tl.fromTo("{S} .inner", {{ scale: 1.08 }}, {{ scale: 1.0, duration: 0.5, ease: "power4.out" }}, {c.sb});
      tl.to("{S} .inner", {{ scale: 1.04, duration: {max(0.4, t_last - (c.sb + 0.5)):.3f}, ease: "none" }}, {c.sb + 0.5:.3f});
      tl.fromTo("{S} .kick", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.28, ease: snap }}, {c.sb + 0.12:.3f});
      tl.fromTo("{S} .t .w", {{ y: 60, opacity: 0, rotation: 3 }}, {{ y: 0, opacity: 1, rotation: 0, duration: 0.32, ease: snap, stagger: 0.12 }}, {c.sb + 0.18:.3f});
      tl.to("{S} .t .hd", {{ color: "var(--alert)", duration: 0.22 }}, {min(t_alert, t_first - 0.4):.3f});
      drawPath(tl, "{S} .iline", {c.sb + 0.18:.3f}, 0.8);
      tl.fromTo("{S} .ifill", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {c.sb + 0.7:.3f});
      tl.fromTo("{S} .glow", {{ scale: 0.3, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.6, ease: "power2.out" }}, {c.sb + 0.5:.3f});
      prepPath("{S} .crack"); tl.set("{S} .crack", {{ opacity: 0 }}, {c.sb}); tl.set("{S} .crack", {{ opacity: 1 }}, {t_last - 0.01:.3f});
      MD.forEach(([x, y, r], k) => tl.fromTo("#md{c.i}_" + k, {{ x: x * 3.2, y: y * 3.2, rotation: r * 4, opacity: 0 }}, {{ x: x, y: y, rotation: r, opacity: 1, duration: 0.5, ease: "expo.out" }}, {c.sb + 0.7:.3f} + k * 0.10));
      tl.fromTo("{S} .orbit", {{ rotation: 0 }}, {{ rotation: 75, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb + 0.7:.3f});
      tl.fromTo("{S} .meter", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.30, ease: snap }}, {t_first - 0.6:.3f});
      {json_list(t_cards)}.forEach((t, k, a) => {{
        const amp = 4 + 10 * k / Math.max(1, a.length - 1);
        tl.fromTo("#pc{c.i}_" + k, {{ rotationX: -90, y: 60, opacity: 0, transformPerspective: 800 }}, {{ rotationX: 0, y: 0, opacity: 1, duration: 0.32, ease: "back.out(1.4)" }}, t - 0.20);
        tl.to("#pc{c.i}_" + k + " .ic", {{ scale: 1.25, duration: 0.15, yoyo: true, repeat: 1 }}, t + 0.08);
        tl.to("#m{c.i}_" + k, {{ backgroundColor: k < a.length / 2 ? "#e08a3c" : "var(--alert)", scaleY: 1.25, duration: 0.16, ease: pop }}, t);
        tl.to("#m{c.i}_" + k, {{ scaleY: 1, duration: 0.18 }}, t + 0.18);
        tl.to("{S} .icon", {{ x: amp, rotation: amp / 4, duration: 0.05, yoyo: true, repeat: 5, ease: "none" }}, t);
      }});
      tl.fromTo("{S} .zap1", {{ scale: 0, rotation: -30 }}, {{ scale: 1, rotation: 0, duration: 0.28, ease: pop }}, {t_cards[-2] if len(t_cards) > 1 else t_last:.3f});
      tl.fromTo("{S} .zap2", {{ scale: 0, rotation: 30 }}, {{ scale: 1, rotation: 0, duration: 0.28, ease: pop }}, {t_last:.3f});
      tl.to("{S} .crack", {{ strokeDashoffset: 0, duration: 0.25, ease: "power3.out" }}, {t_last:.3f});
      tl.to("{S} .ifill", {{ fill: "var(--alert-15)", duration: 0.2 }}, {t_last:.3f});
      tl.to("{S} .iline", {{ stroke: "var(--alert)", duration: 0.2 }}, {t_last:.3f});
      tl.to("{S} .glow", {{ background: "radial-gradient(circle, var(--alert-45), transparent 70%)", duration: 0.25 }}, {t_last:.3f});
      tl.to("{S} .inner", {{ scale: 1.12, duration: 0.16, ease: "back.out(1.4)", overwrite: "auto" }}, {t_last:.3f});
      tl.to("{S} .inner", {{ scale: 1.05, duration: 0.28, ease: "power2.out" }}, {t_last + 0.16:.3f});
      tl.to("{S} .inner", {{ scale: 1.09, duration: {max(0.2, (c.se - 0.28) - (t_last + 0.44)):.3f}, ease: "none" }}, {t_last + 0.44:.3f});
      {'' if c.last else f'tl.to("{S} .inner", {{ scale: 1.8, opacity: 0, transformOrigin: "50% 36%", duration: 0.30, ease: "power4.in" }}, {c.se - 0.28:.3f});'}
'''
    if c.first: c.sfx("thud", c.sb, 0.9)
    c.sfx("shimmer", c.sb + 0.05, 0.45, 1.0)
    for k, t in enumerate(t_cards):
        c.sfx("thud" if k == len(t_cards) - 1 else "pop", t, 0.8 if k == len(t_cards) - 1 else 0.5, 900)
        js += MO.draw(f"#pc{c.i}_{k} .ic svg", t - 0.15, 0.5)
    return html, js


def stats(s, c):
    S = f"#s{c.i}"
    bars = s.get("bars", [])[:3]
    bh = "".join(
        f'<div class="br{" s" if k % 2 else ""}"><div class="n"><span>{E(b["name"])}</span><span class="{"pri" if k == 0 else ""}">{E(b.get("display", str(b["value"]) + "%"))}</span></div>'
        f'<div class="tr"><div class="fl" id="fl{c.i}_{k}" style="width:{max(0, min(100, float(b["value"])))}%"></div></div></div>' for k, b in enumerate(bars))
    co = s.get("callout")
    ppl_top = 280 + 80 + len(bars) * 130 + 40
    html = f'<div class="bars"><div class="k" style="font-size:24px;color:var(--dim);margin-bottom:18px">{E(s.get("label", ""))}</div>{bh}</div>'
    t = c.cue(bars[0].get("cue", bars[0]["name"]), c.sb, frac=0.15) if bars else c.sb + 0.5
    if co:
        n, empty = int(co.get("people", 5)), int(co.get("empty", 1))
        pv = "".join(
            f'<svg id="pv{c.i}_{k}" width="110" height="150" viewBox="0 0 110 150"><circle cx="55" cy="38" r="28" class="body" fill="var(--primary)" stroke="var(--primary)" stroke-width="5"/>'
            f'<path d="M10 145 C10 95 100 95 100 145 Z" class="body" fill="var(--primary)" stroke="var(--primary)" stroke-width="5"/></svg>' for k in range(n))
        html += f'<div class="ppl card" style="top:{ppl_top}px"><div class="q fit"><em>{E(co.get("em", ""))}</em> {E(co.get("text", ""))}</div><div class="row">{pv}</div></div>'
        tc = c.cue(co.get("cue", "x"), t, frac=0.55)
        te = c.cue(co["empty_cue"], tc, frac=0.8) if co.get("empty_cue") else tc + 1.2
        dur1 = max(0.2, tc - c.sb)
        dur2 = max(0.2, c.se - (tc + 0.44))
        js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {dur1:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .bars", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.08:.3f});
'''
        for k in range(len(bars)):
            js += f'      tl.fromTo("#fl{c.i}_{k}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.55, ease: "power4.out" }}, {t - 0.15 + 0.3 * k:.3f});\n'
        js += f'''      tl.fromTo("{S} .ppl", {{ y: 350, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap }}, {tc - 0.35:.3f});
      tl.fromTo("{S} .ppl .row svg", {{ y: 35, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.25, ease: pop, stagger: 0.06 }}, {tc - 0.15:.3f});
      tl.to("{S} .inner", {{ scale: 1.12, duration: 0.16, ease: "back.out(1.4)" }}, {tc:.3f});
      tl.to("{S} .inner", {{ scale: 1.04, duration: 0.28, ease: "power2.out" }}, {tc + 0.16:.3f});
      tl.to("{S} .inner", {{ scale: 1.08, duration: {dur2:.3f}, ease: "none" }}, {tc + 0.44:.3f});
'''
        for k in range(n - empty, n):
            js += f'      tl.to("#pv{c.i}_{k} .body", {{ fill: "var(--surface)", duration: 0.18 }}, {te - 0.15:.3f}); tl.to("#pv{c.i}_{k}", {{ y: -14, duration: 0.12, yoyo: true, repeat: 3 }}, {te - 0.08:.3f});\n'
        c.sfx("pop", tc, 0.45, 1000)
    else:
        js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.06, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .bars", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.08:.3f});
'''
        for k in range(len(bars)):
            js += f'      tl.fromTo("#fl{c.i}_{k}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.55, ease: "power4.out" }}, {t - 0.15 + 0.3 * k:.3f});\n'
    c.sfx("pop", t, 0.45, 1000)
    js += "      " + exit_up(c, f"{S} .bars, {S} .ppl")
    return html, js


def intro(s, c):
    S = f"#s{c.i}"
    photos = s.get("photos", [])[:2]
    ph = "".join(f'<div class="ph p{k + 1}"><img src="media/{E(p)}" alt="" /></div>' for k, p in enumerate(photos))
    tags = s.get("tags", [])[:4]
    tg = "".join(f'<div id="tg{c.i}_{k}" class="{"on" if t.get("highlight") else ""}">{E(t["text"])}</div>' for k, t in enumerate(tags))
    y = 280 if photos else 440   # centre the scene vertically when there are no photos
    html = f'''{c.logo("biglogo lg", style=f"top:{y}px")}
        <div class="ctr sf tag fit" style="top:{y + 210}px">{E(s.get("tagline", ""))}<br/><em>{E(s.get("tagline_em", ""))}</em></div>
        {ph}
        <div class="tags" style="top:{1200 if photos else y + 430}px">{tg}</div>'''
    tl_ = c.cue(s.get("logo_cue", "x"), c.sb, frac=0.1)
    tt = c.cue(s.get("tagline_cue", "x"), tl_, frac=0.3)
    dur1 = max(0.15, tl_ - c.sb)
    dur2 = max(0.2, c.se - (tl_ + 0.44))
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.02, duration: {dur1:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .lg", {{ scale: 1.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "back.out(1.4)" }}, {tl_ - 0.25:.3f});
      tl.to("{S} .inner", {{ scale: 1.12, duration: 0.16, ease: "back.out(1.4)" }}, {tl_:.3f});
      tl.to("{S} .inner", {{ scale: 1.04, duration: 0.28, ease: "power2.out" }}, {tl_ + 0.16:.3f});
      tl.to("{S} .inner", {{ scale: 1.08, duration: {dur2:.3f}, ease: "none" }}, {tl_ + 0.44:.3f});
      tl.fromTo("{S} .tag", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {tt - 0.15:.3f});
'''
    for k in range(len(photos)):
        js += f'      tl.fromTo("{S} .p{k + 1}", {{ y: 400, rotation: {-6 if k == 0 else 6}, opacity: 0 }}, {{ y: 0, rotation: {-3 if k == 0 else 3}, opacity: 1, duration: 0.40, ease: snap }}, {tt + 0.15 + 0.2 * k:.3f});\n'
    after = tt
    for k, t in enumerate(tags):
        tk = c.cue(t["cue"], after, frac=0.6 + 0.1 * k) if t.get("cue") else after + 0.6
        after = tk
        js += f'      tl.fromTo("#tg{c.i}_{k}", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.28, ease: pop }}, {tk - 0.15:.3f});\n'
        c.sfx("pop", tk, 0.45, 1000)
    js += "      " + exit_up(c, f"{S} .lg, {S} .tag, {S} .ph, {S} .tags")
    c.sfx("thud", tl_, 0.85)
    return html, js


def steps(s, c):
    S = f"#s{c.i}"
    st = s.get("steps", [])[:4]
    gap = min(280, 840 // max(1, len(st)))
    items = "".join(
        f'<div class="st" id="st{c.i}_{k}" style="top:{340 + k * gap}px"><div class="no" id="no{c.i}_{k}">{_mark(x, k + 1, 58)}</div><div class="bd card{" wth" if x.get("photo_file") else ""}">{_thumb(x)}<div class="h">{E(x["title"])}</div>'
        f'<div class="chips">{"".join(f"<span>{E(ch)}</span>" for ch in x.get("chips", [])[:5])}</div></div></div>' for k, x in enumerate(st))
    html = f'<div class="ctr sf t fit">{E(s.get("title", "How it works"))}</div><div class="rail" style="height:{(len(st) - 1) * gap + 150}px"><i></i></div>{items}'
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.06, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.08:.3f});
'''
    after, t0 = c.sb, None
    for k, x in enumerate(st):
        t = c.cue(x.get("cue") or x["title"].split()[0], after, frac=0.05 + 0.9 * k / max(1, len(st)))
        after = t; t0 = t0 or t
        js += f'''      tl.fromTo("#st{c.i}_{k}", {{ x: 750, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.32, ease: "power4.out" }}, {t - 0.22:.3f});
      tl.to("#no{c.i}_{k}", {{ backgroundColor: "var(--primary)", borderColor: "var(--primary)", color: "var(--on-primary)", scale: 1.15, duration: 0.18, ease: pop }}, {t:.3f});
      tl.to("#no{c.i}_{k}", {{ scale: 1, duration: 0.15 }}, {t + 0.18:.3f});
      tl.fromTo("#st{c.i}_{k} .chips span", {{ y: 16, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.20, stagger: 0.12 }}, {t + 0.2:.3f});
'''
        c.sfx("pop", t, 0.45, 1000)
        js += MO.draw(f"#no{c.i}_{k} svg", t - 0.1, 0.55)
    end = c.line_end_last()
    js += f'      tl.fromTo("{S} .rail i", {{ scaleY: 0 }}, {{ scaleY: 1, duration: {max(0.4, end - (t0 or c.sb)):.3f}, ease: "none" }}, {t0 or c.sb:.3f});\n'
    c.sfx("shimmer", end, 0.5)
    js += "      " + exit_up(c, f"{S} .t, {S} .st, {S} .rail")
    return html, js


def _rows(rows, i, side):
    out = ""
    for k, r in enumerate(rows):
        st = r.get("style", "")
        v = E(r.get("v", ""))
        if st == "ok": v = f'<span class="v-ok" id="rv{i}{side}{k}">{OKDOT}{v}</span>'
        else: v = f'<b class="v-{st}" id="rv{i}{side}{k}">{v}</b>'
        out += f'<div class="ln"><span>{E(r.get("k", ""))}</span>{v}</div>'
    return out


def flip(s, c):
    S = f"#s{c.i}"
    f, b = s.get("front", {}), s.get("back", {})
    html = f'''<div class="ctr sf t fit">{E(s.get("title", ""))}<br/><em>{E(s.get("title_em", ""))}</em></div>
        <div class="claim">
          <div class="face card front"><div class="k">{E(f.get("kicker", ""))}</div><div class="nm">{E(f.get("title", ""))}</div>{_rows(f.get("rows", []), c.i, "f")}
            {f'<div class="stamp">{E(f["stamp"])}</div>' if f.get("stamp") else ""}</div>
          <div class="face card back" style="opacity:0"><div class="k">{E(b.get("kicker", ""))}</div><div class="nm">{E(b.get("title", ""))}</div>{_rows(b.get("rows", []), c.i, "b")}</div>
        </div>'''
    ts = c.cue(f.get("cue", "x"), c.sb, frac=0.3)
    back_cues = []
    after = ts
    for k, r in enumerate(b.get("rows", [])):
        if r.get("cue"):
            t = c.cue(r["cue"], after, frac=0.6 + 0.15 * len(back_cues)); after = t; back_cues.append((k, t))
    tflip = (back_cues[0][1] if back_cues else ts + 1.5)
    dur1 = max(0.15, ts - c.sb)
    dur2 = max(0.2, c.se - (ts + 0.44))
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.02, duration: {dur1:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.08:.3f});
      tl.fromTo("{S} .claim", {{ y: 800, rotation: 5 }}, {{ y: 0, rotation: -1, duration: 0.45, ease: snap }}, {c.sb + 0.12:.3f});
      tl.fromTo("{S} .stamp", {{ scale: 2.8, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.20, ease: "power4.in" }}, {ts - 0.12:.3f});
      tl.to("{S} .claim", {{ x: 10, duration: 0.05, yoyo: true, repeat: 3 }}, {ts + 0.06:.3f});
      tl.to("{S} .inner", {{ scale: 1.12, duration: 0.16, ease: "back.out(1.4)" }}, {ts:.3f});
      tl.to("{S} .inner", {{ scale: 1.04, duration: 0.28, ease: "power2.out" }}, {ts + 0.16:.3f});
      tl.to("{S} .inner", {{ scale: 1.08, duration: {dur2:.3f}, ease: "none" }}, {ts + 0.44:.3f});
      tl.to("{S} .front", {{ scaleX: 0, duration: 0.18, ease: "power2.in" }}, {tflip - 0.45:.3f});
      tl.set("{S} .front", {{ opacity: 0 }}, {tflip - 0.27:.3f});
      tl.set("{S} .back", {{ opacity: 1, scaleX: 0 }}, {tflip - 0.27:.3f});
      tl.to("{S} .back", {{ scaleX: 1, duration: 0.20, ease: "back.out(1.4)" }}, {tflip - 0.27:.3f});
'''
    for k, t in back_cues:
        js += f'      tl.fromTo("#rv{c.i}b{k}", {{ scale: 0.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.28, ease: pop }}, {t:.3f});\n'
        c.sfx("shimmer", t, 0.5)
    c.sfx("thud", ts, 0.85)
    js += "      " + exit_up(c, f"{S} .t, {S} .claim")
    return html, js


def question(s, c):
    S = f"#s{c.i}"
    html = f'''<div class="ctr sf q1" style="top:520px">{E(s.get("pre", "So what makes"))}</div>
        <div class="ctr sf q2 fit" style="top:660px"><em>{E(s.get("em", ""))}</em> {E(s.get("post", "different?"))}</div>
        <div class="ctr mk" style="top:920px;font-size:270px">?</div>'''
    te = c.cue(s.get("em_cue", "x"), c.sb, frac=0.4)
    tm = c.cue(s.get("mark_cue", "x"), te, frac=0.8)
    dur1 = max(0.15, tm - c.sb)
    dur2 = max(0.2, c.se - (tm + 0.44))
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {dur1:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .q1", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .q2", {{ scale: 1.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.32, ease: "back.out(1.4)" }}, {te - 0.15:.3f});
      tl.fromTo("{S} .mk", {{ scale: 0, rotation: -60 }}, {{ scale: 1, rotation: 0, duration: 0.35, ease: pop }}, {tm:.3f});
      tl.to("{S} .inner", {{ scale: 1.12, duration: 0.16, ease: "back.out(1.4)" }}, {tm:.3f});
      tl.to("{S} .inner", {{ scale: 1.04, duration: 0.28, ease: "power2.out" }}, {tm + 0.16:.3f});
      tl.to("{S} .inner", {{ scale: 1.08, duration: {dur2:.3f}, ease: "none" }}, {tm + 0.44:.3f});
      ''' + exit_up(c, f"{S} .q1, {S} .q2, {S} .mk")
    c.sfx("thud", tm, 0.85)
    return html, js


def compare(s, c):
    S = f"#s{c.i}"
    rows = s.get("rows", [])[:4]
    rh = "".join(
        f'<div class="row" style="top:{350 + k * 230}px" data-layout-allow-overflow="true"><div class="a" id="ra{c.i}_{k}"><s class="fit" data-box="parent">{E(r["left"])}</s></div>'
        f'<div class="b" id="rb{c.i}_{k}"><span class="ck">{CHECK}</span><span class="fit" data-box="parent">{E(r["right"])}</span></div></div>' for k, r in enumerate(rows))
    html = f'<div class="hd" style="top:230px"><div class="a">{E(s.get("left_label", "Others"))}</div><div class="b">{E(s.get("right_label", ""))}</div></div>{rh}'
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.06, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .hd", {{ y: -50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.05:.3f});
'''
    after = c.sb
    for k, r in enumerate(rows):
        tb = c.cue(r.get("right_cue", "x"), after, frac=0.2 + 0.8 * (k + 0.6) / len(rows))
        ta = c.cue(r["left_cue"], after, frac=0.2 + 0.8 * k / len(rows)) if r.get("left_cue") else tb - 0.5
        ta = min(ta, tb - 0.2); after = tb
        js += f'''      tl.fromTo("#ra{c.i}_{k}", {{ x: -600, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.28, ease: "power4.out" }}, {ta - 0.20:.3f});
      tl.fromTo("#rb{c.i}_{k}", {{ x: 600, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.28, ease: "power4.out" }}, {tb - 0.20:.3f});
      tl.fromTo("#rb{c.i}_{k} .ck", {{ scale: 0 }}, {{ scale: 1, duration: 0.25, ease: pop }}, {tb + 0.05:.3f});
      tl.to("#rb{c.i}_{k}", {{ backgroundColor: "var(--primary)", color: "var(--on-primary)", scale: 1.05, duration: 0.20, ease: "back.out(1.4)" }}, {tb + 0.08:.3f});
      tl.to("#rb{c.i}_{k}", {{ backgroundColor: "var(--surface)", color: "var(--ink)", scale: 1.0, duration: 0.35, ease: "power2.out" }}, {tb + 0.65:.3f});
'''
        c.sfx("tick", ta, 0.6); c.sfx("pop", tb, 0.6, 1300)
    if not c.last:
        js += f'      tl.to("{S} .hd, {S} .row", {{ opacity: 0, y: -40, duration: 0.25, stagger: 0.02 }}, {c.se - 0.28:.3f});\n'
    return html, js


def end(s, c):
    S = f"#s{c.i}"
    ch = s.get("chart")
    html, js = "", ""
    if ch:
        bars = ch.get("bars", [])[:5]
        shades = ["var(--primary)", "var(--mix1)", "var(--mix2)", "var(--accent)", "var(--accent)"]
        html += f'<div class="ctr k ch" style="top:250px">{E(ch.get("label", ""))}</div><div class="chart" style="top:300px;height:360px">' + "".join(
            f'<div class="bar" id="eb{c.i}_{k}" style="height:{max(1, min(100, float(b.get("from", 100))))}%;background:{shades[k]}"></div>' for k, b in enumerate(bars)) + "</div>"
        html += '<div class="albl" style="top:680px">' + "".join(f"<span>{E(b.get('label', ''))}</span>" for b in bars) + "</div>"
        js += f'''tl.fromTo("{S} .ch, {S} .albl", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.28 }}, {c.sb + 0.08:.3f});
      tl.fromTo("{S} .bar", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.42, ease: snap, stagger: 0.06 }}, {c.sb + 0.05:.3f});
'''
        for k, b in enumerate(bars):
            fr, to = float(b.get("from", 100)), float(b.get("to", b.get("from", 100)))
            if fr > 0 and abs(fr - to) > 0.01:
                js += f'      tl.to("#eb{c.i}_{k}", {{ scaleY: {to / fr:.3f}, duration: 0.65, ease: "power2.inOut" }}, {c.sb + 0.65 + 0.08 * k:.3f});\n'
    top = 780 if ch else 520
    html += c.logo("biglogo lg", style=f"top:{top}px") + f'''
        <div class="ctr sf tg fit" style="top:{top + 190}px;font-size:82px">{E(s.get("tagline", ""))}<br/><em>{E(s.get("tagline_em", ""))}</em></div>
        <div class="ctr url" style="top:{top + 400}px">{E(s.get("url") or c.url)}</div>'''
    tlg = c.cue(s.get("logo_cue", "x"), c.sb, frac=0.7)
    ttg = c.cue(s.get("tagline_cue", "x"), c.sb, frac=0.05)
    dur1 = max(0.15, tlg - c.sb)
    dur2 = max(0.2, c.se - (tlg + 0.44))
    js += f'''      tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.03, duration: {dur1:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .lg", {{ scale: 1.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.38, ease: "back.out(1.4)" }}, {tlg - 0.25:.3f});
      tl.to("{S} .inner", {{ scale: 1.12, duration: 0.16, ease: "back.out(1.4)" }}, {tlg:.3f});
      tl.to("{S} .inner", {{ scale: 1.04, duration: 0.28, ease: "power2.out" }}, {tlg + 0.16:.3f});
      tl.to("{S} .inner", {{ scale: 1.08, duration: {dur2:.3f}, ease: "none" }}, {tlg + 0.44:.3f});
      tl.fromTo("{S} .tg", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap }}, {ttg - 0.2:.3f});
      tl.fromTo("{S} .url", {{ opacity: 0, y: 25 }}, {{ opacity: 1, y: 0, duration: 0.32 }}, {tlg + 0.2:.3f});
'''
    c.sfx("thud", tlg, 0.85); c.sfx("shimmer", ttg, 0.5)
    bh, bj = MO.burst(c, 540, top + 100, tlg + 0.05, "var(--primary)", radius=300, size=20); html += bh; js += bj
    return html, js


def website(s, c):
    """The real website scrolling inside a phone frame (screenshot captured by capture_site.cjs)."""
    S = f"#s{c.i}"
    SCREEN_W, VIEW_H = 532, 824                       # screen width and visible height in video pixels
    img_h = round(s.get("shot_px", 2000) * SCREEN_W / 780)
    dist = max(0, img_h - VIEW_H)
    lock = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M7 11V8a5 5 0 0 1 10 0v3" fill="none" stroke="currentColor" stroke-width="2.4"/><rect x="5" y="11" width="14" height="10" rx="2" fill="currentColor"/></svg>'
    html = f'''<div class="ctr k kick" style="top:180px">{E(s.get("kicker", "See it live"))}</div>
        <div class="ctr sf t fit" style="top:220px">{E(s.get("title", ""))}</div>
        <div class="phone"><div class="screen">
          <div class="bar">{lock}<span>{E(s.get("url_label", c.url))}</span></div>
          <div class="view"><img class="shot" src="media/{E(s.get("shot", ""))}" style="height:{img_h}px" alt="" /></div>
        </div></div>'''
    if s.get("mode") == "logo":   # no capture and no share image: logo + address on a clean page
        html = html.replace(f'<div class="view"><img class="shot" src="media/{E(s.get("shot", ""))}" style="height:{img_h}px" alt="" /></div>',
            f'<div class="view logo">{c.logo("biglogo cardlogo")}<div class="site">{E(s.get("url_label", c.url))}</div>'
            f'<div class="visit">Visit website</div></div>')
        js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .kick, {S} .t", {{ y: 35, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap, stagger: 0.06 }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .phone", {{ y: 900, rotation: 3 }}, {{ y: 0, rotation: 0, duration: 0.50, ease: "power4.out" }}, {c.sb + 0.12:.3f});
      tl.fromTo("{S} .cardlogo", {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.4)" }}, {c.sb + 0.65:.3f});
      tl.fromTo("{S} .site, {S} .visit", {{ y: 25, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap, stagger: 0.10 }}, {c.sb + 0.95:.3f});
      tl.to("{S} .visit", {{ scale: 1.06, duration: 0.4, ease: "sine.inOut", yoyo: true, repeat: 3 }}, {c.sb + 1.5:.3f});
'''
        c.sfx("pop", c.sb + 0.25, 0.45, 900); c.sfx("pop", c.sb + 0.7, 0.4, 1200)
        js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .phone")
        return html, js
    if s.get("mode") == "card":   # page couldn't be captured: the site's own share image, slow zoom
        img = E(s.get("shot", ""))
        html = html.replace(f'<div class="view"><img class="shot" src="media/{img}" style="height:{img_h}px" alt="" /></div>',
            f'<div class="view card"><img class="bg" src="media/{img}" alt="" /><img class="cardimg" src="media/{img}" alt="" />'
            f'<div class="site">{E(s.get("url_label", c.url))}</div></div>')
        js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .kick, {S} .t", {{ y: 35, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap, stagger: 0.06 }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .phone", {{ y: 900, rotation: 3 }}, {{ y: 0, rotation: 0, duration: 0.50, ease: "power4.out" }}, {c.sb + 0.12:.3f});
      tl.fromTo("{S} .cardimg", {{ scale: 0.86, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: snap }}, {c.sb + 0.6:.3f});
      tl.fromTo("{S} .bg", {{ scale: 1.15 }}, {{ scale: 1.35, duration: {max(1.0, c.se - c.sb - 0.6):.3f}, ease: "none" }}, {c.sb + 0.12:.3f});
      tl.to("{S} .cardimg", {{ scale: 1.08, duration: {max(1.0, c.se - c.sb - 1.2):.3f}, ease: "sine.inOut" }}, {c.sb + 1.1:.3f});
      tl.fromTo("{S} .site", {{ y: 25, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap }}, {c.sb + 0.9:.3f});
'''
        c.sfx("pop", c.sb + 0.25, 0.45, 900); c.sfx("whoosh", c.sb + 0.6, 0.25)
        js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .phone")
        return html, js
    t0, t1 = c.sb + 1.2, max(c.sb + 2.5, c.se - 0.6)
    seg = (t1 - t0) / 3
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .kick, {S} .t", {{ y: 35, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap, stagger: 0.06 }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .phone", {{ y: 900, rotation: 3 }}, {{ y: 0, rotation: 0, duration: 0.50, ease: "power4.out" }}, {c.sb + 0.12:.3f});
'''
    for k in range(3):   # scroll in three moves with short pauses, like a person reading
        a = t0 + k * seg
        js += f'      tl.to("{S} .shot", {{ y: {-round(dist * (k + 1) / 3)}, duration: {seg * 0.7:.3f}, ease: "power2.inOut" }}, {a:.3f});\n'
        c.sfx("whoosh", a, 0.25)
    c.sfx("pop", c.sb + 0.25, 0.45, 900)
    js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .phone")
    return html, js


# ------------------------------------------------------------------ scenes added in Video Studio 2
def _word_spans(text, em="", hl="", split=str.split):
    """Title words as <span class="w">; the `em` part is italic in the brand colour; `hl` gets a marker highlight."""
    out = []
    for part, is_em in ((text, False), (em, True)):
        for w in split(str(part or "")):
            cls = "w" + (" hl" if hl and (w.strip(".,!?:;") == hl.strip(".,!?:;") or (len(hl) > 1 and hl in w)) else "")
            out.append(("<em>" if is_em else "") + f'<span class="{cls}">{E(w)}</span>' + ("</em>" if is_em else ""))
    j = "" if split is not str.split and getattr(split, "__self__", None) is not None and split.__self__.nospace else " "
    return j.join(out).replace(f"</em>{j}<em>", j)


def _sync_times(c, words, t_from, t_to):
    """Time for each display word: when it is spoken (if it is), otherwise spread evenly in between."""
    ts, after = [], t_from - 0.05
    for w in words:
        t = c.find(w, after)
        if t is not None and t <= t_to + 0.05: ts.append(t); after = t
        else: ts.append(None)
    n = len(ts); i = 0
    while i < n:
        if ts[i] is not None: i += 1; continue
        j = i
        while j < n and ts[j] is None: j += 1
        a = ts[i - 1] if i > 0 else t_from
        b = ts[j] if j < n else max(a + 0.12 * (j - i), min(t_to, a + 0.22 * (j - i)))
        for k in range(i, j): ts[k] = a + (b - a) * (k - i + 1) / (j - i + 1)
        i = j
    return ts


def hook(s, c):
    """A big statement that appears word by word as it is spoken. A strong first scene for any topic."""
    S = f"#s{c.i}"
    title = _word_spans(s.get("text", ""), s.get("em", ""), s.get("highlight", ""), c.split)
    words = c.split(s.get("text", "")) + c.split(s.get("em", ""))
    flash = '<div class="flash"></div>' if c.first else ''
    gap = ' style="gap:0"' if c.nospace else ""
    html = f'{flash}<div class="ctr k kick">{E(s.get("kicker", ""))}</div><div class="ctr sf t fit"{gap}>{title}</div><div class="bar"><i></i></div>'
    t_end = c.marks[c.lines_idx[0]]["end"]
    ts = _sync_times(c, words, c.sb + 0.12, t_end)
    hl = str(s.get("highlight") or "").strip(".,!?:;")
    t_hl = next((t for w, t in zip(words, ts) if hl and (w.strip(".,!?:;") == hl or (len(hl) > 1 and hl in w))), ts[-1] if ts else c.sb + 1)
    js = ""
    if c.first: js += f'tl.fromTo("{S} .flash", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.35, ease: "power2.out" }}, {c.sb});\n      '
    js += f'''tl.fromTo("{S} .inner", {{ scale: 1.06 }}, {{ scale: 1.0, duration: 0.5, ease: "power4.out" }}, {c.sb});
      tl.to("{S} .inner", {{ scale: 1.06, duration: {max(0.5, c.se - c.sb - 0.8):.3f}, ease: "none" }}, {c.sb + 0.5:.3f});
      tl.fromTo("{S} .kick", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.28, ease: snap }}, {c.sb + 0.05:.3f});
      {json_list(ts)}.forEach((t, k) => tl.fromTo(document.querySelectorAll("{S} .t .w")[k], {{ y: 70, opacity: 0, scale: 0.9 }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.26, ease: "back.out(1.6)" }}, Math.max({c.sb:.3f}, t - 0.08)));
      tl.fromTo("{S} .bar i", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {max(0.3, c.se - c.sb - 0.4):.3f}, ease: "none" }}, {c.sb + 0.2:.3f});
'''
    if hl: js += f'      tl.fromTo("{S} .t .hl", {{ backgroundSize: "0% 9%" }}, {{ backgroundSize: "100% 9%", duration: 0.35, ease: "power2.out" }}, {t_hl + 0.1:.3f});\n'
    if not c.last: js += f'      tl.to("{S} .inner", {{ scale: 1.6, opacity: 0, duration: 0.30, ease: "power4.in" }}, {c.se - 0.28:.3f});\n'
    if c.first: c.sfx("thud", c.sb, 0.9)
    for t in ts[::3]: c.sfx("tick", t, 0.35)
    if hl: c.sfx("pop", t_hl + 0.1, 0.5, 1100)
    return html, js


def number(s, c):
    """One giant number that counts up when it is spoken, with a label (e.g. 2,000+ VC firms)."""
    S = f"#s{c.i}"
    try: val = float(str(s.get("value", 0)).replace(",", ""))
    except ValueError: val = 0.0
    dec = int(s.get("decimals", 0 if float(val).is_integer() else 1))
    plain = bool(s.get("plain")) or (float(val).is_integer() and 1000 <= val <= 2100 and not s.get("prefix") and not s.get("suffix"))   # years: no "2,016"
    ring = bool(s.get("percent")) and 0 <= val <= 100
    pre, suf = E(str(s.get("prefix", ""))), E(str(s.get("suffix", "%" if ring else "")))
    if ring:
        deco = ('<svg class="ring" viewBox="0 0 200 200" width="640" height="640"><circle cx="100" cy="100" r="88" fill="none" stroke="var(--pale)" stroke-width="14"/>'
                '<circle class="rg" cx="100" cy="100" r="88" fill="none" stroke="var(--primary)" stroke-width="14" stroke-linecap="round" transform="rotate(-90 100 100)"/></svg>')
    else:
        deco = '<div class="glow"></div>'
    lbl_em = f' <em>{E(s["label_em"])}</em>' if s.get("label_em") else ""
    html = (f'<div class="ctr k kick">{E(s.get("kicker", ""))}</div>{deco}'
            f'<div class="ctr num"><span class="pre">{pre}</span><span class="val" id="nv{c.i}">0</span><span class="suf">{suf}</span></div>'
            f'<div class="ctr sf lbl fit">{E(s.get("label", ""))}{lbl_em}</div><div class="ctr note">{E(s.get("note", ""))}</div>')
    tn = c.cue(s.get("cue", "x"), c.sb, frac=0.25)
    t0 = max(c.sb + 0.15, tn - 0.55)
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.05, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .kick", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.28, ease: snap }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .num", {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "back.out(1.5)" }}, {max(c.sb, t0 - 0.2):.3f});
      (function () {{ const o = {{ v: 0 }}, el = document.getElementById("nv{c.i}");
        const fmt = (v) => {{ try {{ return v.toLocaleString("{c.locale}", {{ minimumFractionDigits: {dec}, maximumFractionDigits: {dec}, useGrouping: {"false" if plain else "true"} }}); }} catch (e) {{ return v.toFixed({dec}); }} }};
        el.textContent = fmt(0);
        tl.fromTo(o, {{ v: 0 }}, {{ v: {val}, duration: 1.1, ease: "power2.out", onUpdate: () => {{ el.textContent = fmt(o.v); }} }}, {t0:.3f}); }})();
      tl.to("{S} .num", {{ scale: 1.1, duration: 0.14, ease: "power2.out", yoyo: true, repeat: 1 }}, {t0 + 1.1:.3f});
      tl.fromTo("{S} .lbl", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {t0 + 0.5:.3f});
      tl.fromTo("{S} .note", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {t0 + 1.0:.3f});
'''
    if ring:
        js += f'''      (function () {{ const r = document.querySelector("{S} .rg"), L = 2 * Math.PI * 88; r.style.strokeDasharray = L; r.style.strokeDashoffset = L;
        tl.fromTo(r, {{ strokeDashoffset: L }}, {{ strokeDashoffset: L * (1 - {val / 100:.4f}), duration: 1.1, ease: "power2.out" }}, {t0:.3f}); }})();
'''
    else:
        js += f'      tl.fromTo("{S} .glow", {{ scale: 0.3, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.8, ease: "power2.out" }}, {max(c.sb, t0 - 0.2):.3f});\n'
    c.sfx("whoosh", t0, 0.3); c.sfx("thud", t0 + 1.1, 0.8)
    bh, bj = MO.burst(c, 540, 690, t0 + 1.1, "var(--primary)", radius=260, size=22); html += bh; js += bj
    js += "      " + exit_up(c, f"{S} .kick, {S} .num, {S} .lbl, {S} .note, {S} .ring, {S} .glow")
    return html, js


def timeline(s, c):
    """Dated events on a vertical line, each lighting up as it is spoken (history, news, a company's story)."""
    S = f"#s{c.i}"
    ev = s.get("events", [])[:5]
    gap = min(230, 900 // max(1, len(ev)))
    rows = "".join(
        f'<div class="ev" id="ev{c.i}_{k}" style="top:{380 + k * gap}px"><div class="dot" id="dt{c.i}_{k}"></div>'
        f'<div class="bd card{" wth" if x.get("photo_file") else ""}">{_thumb(x)}<div class="dt">{E(x.get("date", ""))}</div><div class="tx fit">{E(x.get("text", ""))}</div></div></div>' for k, x in enumerate(ev))
    html = f'<div class="ctr sf t fit">{E(s.get("title", ""))}</div><div class="line" style="height:{max(1, len(ev) - 1) * gap + 40}px"><i></i></div>{rows}'
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.05, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap }}, {c.sb + 0.06:.3f});
'''
    after, t0 = c.sb, None
    for k, x in enumerate(ev):
        cue = x.get("cue") or (str(x.get("date", "")).split() or ["x"])[0]
        t = c.cue(cue, after, frac=0.08 + 0.85 * k / max(1, len(ev))); after = t; t0 = t0 or t
        js += f'''      tl.fromTo("#ev{c.i}_{k} .bd", {{ x: 700, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.34, ease: "power4.out" }}, {t - 0.25:.3f});
      tl.fromTo("#dt{c.i}_{k}", {{ scale: 0 }}, {{ scale: 1, duration: 0.3, ease: pop }}, {t - 0.1:.3f});
      tl.to("#dt{c.i}_{k}", {{ backgroundColor: "var(--primary)", boxShadow: "0 0 0 12px var(--accent-35)", duration: 0.2 }}, {t:.3f});
'''
        c.sfx("pop", t, 0.45, 800 + 120 * k)
    js += f'      tl.fromTo("{S} .line i", {{ scaleY: 0 }}, {{ scaleY: 1, duration: {max(0.4, c.line_end_last() - (t0 or c.sb)):.3f}, ease: "none" }}, {t0 or c.sb:.3f});\n'
    js += "      " + exit_up(c, f"{S} .t, {S} .ev, {S} .line")
    return html, js


def listing(s, c):
    """A numbered or ranked list (top 5, mistakes to avoid, tips). Items drop in as they are named."""
    S = f"#s{c.i}"
    items = s.get("items", [])[:6]
    n = len(items)
    down = bool(s.get("countdown"))
    gap = min(200, 960 // max(1, n))
    rows = ""
    for k, x in enumerate(items):
        note = f'<div class="nt">{E(x.get("note", ""))}</div>' if x.get("note") else ""
        rows += (f'<div class="it card" id="it{c.i}_{k}" style="top:{370 + k * gap}px;height:{gap - 22}px"><div class="no">{_mark(x, (n - k) if down else k + 1, 54)}</div>'
                 f'<div class="bd"><div class="tx fit">{E(x.get("text", ""))}</div>{note}</div>{_thumb(x)}</div>')
    html = f'<div class="ctr k kick">{E(s.get("kicker", ""))}</div><div class="ctr sf t fit">{E(s.get("title", ""))}</div>{rows}'
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.05, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .kick, {S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.32, ease: snap, stagger: 0.06 }}, {c.sb + 0.05:.3f});
'''
    after = c.sb
    for k, x in enumerate(items):
        cue = x.get("cue") or (str(x.get("text", "")).split() or ["x"])[0]
        t = c.cue(cue, after, frac=0.08 + 0.85 * k / max(1, n)); after = t
        js += f'''      tl.fromTo("#it{c.i}_{k}", {{ y: -60, opacity: 0, rotationX: 70, transformPerspective: 900 }}, {{ y: 0, opacity: 1, rotationX: 0, duration: 0.34, ease: "back.out(1.4)" }}, {t - 0.22:.3f});
      tl.fromTo("#it{c.i}_{k} .no", {{ scale: 0.4 }}, {{ scale: 1, duration: 0.3, ease: pop }}, {t - 0.05:.3f});
'''
        c.sfx("pop", t, 0.5, 900 + 90 * k)
        js += MO.draw(f"#it{c.i}_{k} .no svg", t - 0.1, 0.55)
    js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .it")
    return html, js


def quote(s, c):
    """A real quotation with its author (only quotes that were actually said or written)."""
    S = f"#s{c.i}"
    role = f'<span>{E(s["role"])}</span>' if s.get("role") else ""
    html = (f'<div class="mk">“</div><div class="ctr sf q fit">{E(s.get("text", ""))}</div>'
            f'<div class="ctr who"><b>{E(s.get("author", ""))}</b>{role}</div>')
    ta = c.cue(s.get("cue", "x"), c.sb, frac=0.75)
    tw = max(c.sb + 0.8, ta - 0.2)
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.05, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .mk", {{ scale: 0, rotation: -20, opacity: 0 }}, {{ scale: 1, rotation: 0, opacity: 1, duration: 0.4, ease: pop }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .q", {{ y: 50, opacity: 0, filter: "blur(10px)" }}, {{ y: 0, opacity: 1, filter: "blur(0px)", duration: 0.6, ease: "power3.out" }}, {c.sb + 0.25:.3f});
      tl.fromTo("{S} .who", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap }}, {tw:.3f});
'''
    c.sfx("shimmer", c.sb + 0.1, 0.4); c.sfx("pop", tw, 0.4, 900)
    js += "      " + exit_up(c, f"{S} .mk, {S} .q, {S} .who")
    return html, js


def broll(s, c):
    """Full-screen real footage or photo (stock video, a clip or image you provide) with a caption on top."""
    S = f"#s{c.i}"
    media = ""   # a video clip is placed under the scene by make_video.py (it needs its own timeline item)
    if s.get("photo_file") and not s.get("video_file"):
        media = f'<img class="bp" src="media/{E(s["photo_file"])}" alt="" />'
    cap_em = f'<br/><em>{E(s["caption_em"])}</em>' if s.get("caption_em") else ""
    html = (f'<div class="full" data-layout-allow-overflow="true">{media}<div class="shade"></div></div><div class="ctr k kick">{E(s.get("kicker", ""))}</div>'
            f'<div class="ctr sf cap fit">{E(s.get("caption", ""))}{cap_em}</div>')
    tc = c.cue(s.get("cue", "x"), c.sb, frac=0.15)
    js = f'''tl.fromTo("{S} .full", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.35 }}, {c.sb});
      tl.fromTo("{S} .kick", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: snap }}, {c.sb + 0.15:.3f});
      tl.fromTo("{S} .cap", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, {max(c.sb + 0.2, tc - 0.25):.3f});
'''
    if s.get("photo_file"): js += f'      tl.fromTo("{S} .full .bp", {{ scale: 1.22 }}, {{ scale: 1.04, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});\n'
    if not c.last: js += f'      tl.to("{S} .kick, {S} .cap", {{ y: -80, opacity: 0, duration: 0.28, ease: "power3.in" }}, {c.se - 0.3:.3f});\n'
    c.sfx("whoosh", c.sb + 0.05, 0.35)
    return html, js


def presenter(s, c):
    """A person: round photo, name, role and 2-4 points (personal pitches, hiring, speaker intros, profiles)."""
    S = f"#s{c.i}"
    nm = str(s.get("name", ""))
    initials = "".join(w[0] for w in nm.split()[:2]).upper() or "*"
    ph = f'<img src="media/{E(s["photo_file"])}" alt="" />' if s.get("photo_file") else f'<span class="ini">{E(initials)}</span>'
    pts = s.get("points", [])[:4]
    chips = "".join(f'<div id="pt{c.i}_{k}">{E(p.get("text", "") if isinstance(p, dict) else p)}</div>' for k, p in enumerate(pts))
    html = (f'<div class="pf"><svg class="rg" viewBox="0 0 200 200" width="560" height="560"><circle cx="100" cy="100" r="96" fill="none" stroke="var(--primary)" stroke-width="5"/></svg>'
            f'<div class="av">{ph}</div></div><div class="ctr k role">{E(s.get("role", ""))}</div>'
            f'<div class="ctr sf nm fit">{E(nm)}</div><div class="pts">{chips}</div>')
    tn = c.cue(s.get("name_cue") or (nm.split() or ["x"])[0], c.sb, frac=0.15)
    js = f'''tl.fromTo("{S} .inner", {{ scale: 1.0 }}, {{ scale: 1.05, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb});
      tl.fromTo("{S} .av", {{ scale: 0.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.5)" }}, {c.sb + 0.08:.3f});
      drawPath(tl, "{S} .rg circle", {c.sb + 0.2:.3f}, 0.9);
      tl.fromTo("{S} .nm", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: snap }}, {max(c.sb + 0.3, tn - 0.2):.3f});
      tl.fromTo("{S} .role", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.3 }}, {max(c.sb + 0.45, tn):.3f});
'''
    after = max(c.sb + 0.6, tn)
    for k, p in enumerate(pts):
        cue = p.get("cue") if isinstance(p, dict) else None
        t = c.cue(cue, after, frac=0.35 + 0.6 * k / max(1, len(pts))) if cue else after + 0.5
        after = t
        js += f'      tl.fromTo("#pt{c.i}_{k}", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.28, ease: pop }}, {t - 0.12:.3f});\n'
        c.sfx("pop", t, 0.45, 1000 + 100 * k)
    c.sfx("shimmer", c.sb + 0.2, 0.4)
    js += "      " + exit_up(c, f"{S} .pf, {S} .role, {S} .nm, {S} .pts")
    return html, js


def json_list(xs):
    return "[" + ",".join(f"{x:.3f}" for x in xs) + "]"


BUILDERS = {"problem": problem, "stats": stats, "intro": intro, "steps": steps, "flip": flip,
            "question": question, "compare": compare, "end": end, "website": website,
            "hook": hook, "number": number, "timeline": timeline, "list": listing, "quote": quote,
            "broll": broll, "presenter": presenter}
HIDE_BRAND = {"intro", "end", "broll", "presenter"}
FULL_BLEED = {"broll"}          # scenes that draw their own full-screen background



# picture-first scenes (photos, charts, diagrams, icons, maps) live in scenes_visual.py
import scenes_visual as _SV  # noqa: E402
BUILDERS.update(_SV.BUILDERS)
HIDE_BRAND |= _SV.HIDE_BRAND
FULL_BLEED |= _SV.FULL_BLEED
import scenes_visual2 as _SV2  # noqa: E402
BUILDERS.update(_SV2.BUILDERS)
