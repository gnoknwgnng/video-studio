"""Scene library. Each scene type turns its JSON block into (html, js) and registers sound cues.

Every builder receives `c`, a SceneContext with:
  c.i, c.sb, c.se       scene index, start time, end time (seconds)
  c.cue(word, after)    time the word is spoken in this scene (searched after `after`)
  c.sfx(kind, t, *args) add a sound effect at time t
  c.logo(cls)           big logo <div> (image or wordmark)
  c.first, c.last       first / last scene flags
"""
from html import escape as E

ICONS = {
    "tooth": "M60 20 C30 20 15 45 20 80 C25 115 35 150 50 175 C58 188 70 185 72 170 L80 120 C82 110 98 110 100 120 L108 170 C110 185 122 188 130 175 C145 150 155 115 160 80 C165 45 150 20 120 20 C105 20 98 30 90 30 C82 30 75 20 60 20 Z",
    "document": "M40 18 H112 L148 54 V182 H40 Z",
    "heart": "M90 175 C40 135 15 105 20 70 C25 40 60 25 90 55 C120 25 155 40 160 70 C165 105 140 135 90 175 Z",
    "shield": "M90 20 L155 45 V100 C155 140 125 165 90 182 C55 165 25 140 25 100 V45 Z",
    "building": "M40 182 V40 H120 V80 H150 V182 Z",
    "box": "M30 60 L90 30 L150 60 V150 L90 180 L30 150 Z",
    "chip": "M45 45 H135 V155 H45 Z",
}
CRACK = "M88 34 L96 62 L84 86 L100 112 L92 140"
ZAP = '<svg class="zap {cls}" viewBox="0 0 40 60" width="{w}" height="{h}"><path d="M24 2 L6 34 H20 L14 58 L36 22 H22 Z" fill="var(--alert)"/></svg>'
CHECK = '<svg width="32" height="32" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" stroke="#fff" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
OKDOT = '<svg width="34" height="34" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#1f9d6b"/><path d="M6.5 12.5l3.5 3.5L17.5 8.5" stroke="#fff" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def exit_up(c, sel):
    """Standard exit: elements fly up just before the scene ends."""
    if c.last: return ""
    return f'tl.to("{sel}", {{ y: -1500, duration: 0.42, ease: "power3.in", stagger: 0.03 }}, {c.se - 0.45:.3f});\n'


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
        f'<div class="pc card{" bad" if k == len(cards) - 1 else ""}" id="pc{c.i}_{k}"><div class="ic">{k + 1:02d}</div><div class="tx fit">{E(cd["text"])}</div></div>'
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
            <path class="ifill" d="{icon}" fill="#ffffff"/>
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
      {f'tl.fromTo("{S} .flash", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.4, ease: "power2.out" }}, {c.sb});' if c.first else ''}
      tl.fromTo("{S} .inner", {{ scale: 1.1 }}, {{ scale: 1, duration: 1.4, ease: "power3.out" }}, {c.sb});
      tl.fromTo("{S} .kick", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: snap }}, {c.sb + 0.15:.3f});
      tl.fromTo("{S} .t .w", {{ y: 70, opacity: 0, rotation: 4 }}, {{ y: 0, opacity: 1, rotation: 0, duration: 0.45, ease: snap, stagger: 0.16 }}, {c.sb + 0.25:.3f});
      tl.to("{S} .t .hd", {{ color: "var(--alert)", duration: 0.25 }}, {min(t_alert, t_first - 0.5):.3f});
      drawPath(tl, "{S} .iline", {c.sb + 0.2:.3f}, 1.0);
      tl.fromTo("{S} .ifill", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {c.sb + 0.9:.3f});
      tl.fromTo("{S} .glow", {{ scale: 0.3, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.8, ease: "power2.out" }}, {c.sb + 0.6:.3f});
      prepPath("{S} .crack"); tl.set("{S} .crack", {{ opacity: 0 }}, {c.sb}); tl.set("{S} .crack", {{ opacity: 1 }}, {t_last - 0.01:.3f});
      MD.forEach(([x, y, r], k) => tl.fromTo("#md{c.i}_" + k, {{ x: x * 3.2, y: y * 3.2, rotation: r * 4, opacity: 0 }}, {{ x: x, y: y, rotation: r, opacity: 1, duration: 0.7, ease: "expo.out" }}, {c.sb + 0.9:.3f} + k * 0.12));
      tl.fromTo("{S} .orbit", {{ rotation: 0 }}, {{ rotation: 75, duration: {c.se - c.sb:.3f}, ease: "none" }}, {c.sb + 0.9:.3f});
      tl.fromTo("{S} .meter", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: snap }}, {t_first - 0.8:.3f});
      {json_list(t_cards)}.forEach((t, k, a) => {{
        const amp = 4 + 10 * k / Math.max(1, a.length - 1);
        tl.fromTo("#pc{c.i}_" + k, {{ rotationX: -90, y: 60, opacity: 0, transformPerspective: 800 }}, {{ rotationX: 0, y: 0, opacity: 1, duration: 0.45, ease: "back.out(1.6)" }}, t - 0.25);
        tl.to("#pc{c.i}_" + k + " .ic", {{ scale: 1.25, duration: 0.15, yoyo: true, repeat: 1 }}, t + 0.1);
        tl.to("#m{c.i}_" + k, {{ backgroundColor: k < a.length / 2 ? "#e08a3c" : "var(--alert)", scaleY: 1.25, duration: 0.18, ease: pop }}, t);
        tl.to("#m{c.i}_" + k, {{ scaleY: 1, duration: 0.2 }}, t + 0.2);
        tl.to("{S} .icon", {{ x: amp, rotation: amp / 4, duration: 0.05, yoyo: true, repeat: 5, ease: "none" }}, t);
      }});
      tl.fromTo("{S} .zap1", {{ scale: 0, rotation: -30 }}, {{ scale: 1, rotation: 0, duration: 0.3, ease: pop }}, {t_cards[-2] if len(t_cards) > 1 else t_last:.3f});
      tl.fromTo("{S} .zap2", {{ scale: 0, rotation: 30 }}, {{ scale: 1, rotation: 0, duration: 0.3, ease: pop }}, {t_last:.3f});
      tl.to("{S} .crack", {{ strokeDashoffset: 0, duration: 0.3, ease: "power3.out" }}, {t_last:.3f});
      tl.to("{S} .ifill", {{ fill: "var(--alert-15)", duration: 0.2 }}, {t_last:.3f});
      tl.to("{S} .iline", {{ stroke: "var(--alert)", duration: 0.2 }}, {t_last:.3f});
      tl.to("{S} .glow", {{ background: "radial-gradient(circle, var(--alert-45), transparent 70%)", duration: 0.3 }}, {t_last:.3f});
      {'' if c.last else f'tl.to("{S} .inner", {{ scale: 2.4, opacity: 0, transformOrigin: "50% 36%", duration: 0.45, ease: "power3.in" }}, {c.se - 0.45:.3f});'}
'''
    if c.first: c.sfx("thud", c.sb, 0.9)
    c.sfx("shimmer", c.sb + 0.05, 0.45, 1.0)
    for k, t in enumerate(t_cards):
        c.sfx("thud" if k == len(t_cards) - 1 else "pop", t, 0.8 if k == len(t_cards) - 1 else 0.5, 900)
    return html, js


def stats(s, c):
    S = f"#s{c.i}"
    bars = s.get("bars", [])[:3]
    bh = "".join(
        f'<div class="br{" s" if k % 2 else ""}"><div class="n"><span>{E(b["name"])}</span><span class="{"pri" if k == 0 else ""}">{E(b.get("display", str(b["value"]) + "%"))}</span></div>'
        f'<div class="tr"><div class="fl" id="fl{c.i}_{k}" style="width:{max(0, min(100, float(b["value"])))}%"></div></div></div>' for k, b in enumerate(bars))
    co = s.get("callout")
    ppl_top = 320 + 110 + len(bars) * 150 + 90
    html = f'<div class="bars"><div class="k" style="font-size:24px;color:var(--dim);margin-bottom:18px">{E(s.get("label", ""))}</div>{bh}</div>'
    js = f'tl.fromTo("{S} .bars", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, {c.sb + 0.1:.3f});\n'
    t = c.cue(bars[0].get("cue", bars[0]["name"]), c.sb, frac=0.15) if bars else c.sb + 0.5
    for k in range(len(bars)):
        js += f'      tl.fromTo("#fl{c.i}_{k}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.7, ease: "power3.out" }}, {t - 0.2 + 0.4 * k:.3f});\n'
    c.sfx("pop", t, 0.45, 1000)
    if co:
        n, empty = int(co.get("people", 5)), int(co.get("empty", 1))
        pv = "".join(
            f'<svg id="pv{c.i}_{k}" width="110" height="150" viewBox="0 0 110 150"><circle cx="55" cy="38" r="28" class="body" fill="var(--primary)" stroke="var(--primary)" stroke-width="5"/>'
            f'<path d="M10 145 C10 95 100 95 100 145 Z" class="body" fill="var(--primary)" stroke="var(--primary)" stroke-width="5"/></svg>' for k in range(n))
        html += f'<div class="ppl card" style="top:{ppl_top}px"><div class="q fit"><em>{E(co.get("em", ""))}</em> {E(co.get("text", ""))}</div><div class="row">{pv}</div></div>'
        tc = c.cue(co.get("cue", "x"), t, frac=0.55)
        te = c.cue(co["empty_cue"], tc, frac=0.8) if co.get("empty_cue") else tc + 1.2
        js += f'''      tl.fromTo("{S} .ppl", {{ y: 400, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: snap }}, {tc - 0.5:.3f});
      tl.fromTo("{S} .ppl .row svg", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, ease: pop, stagger: 0.08 }}, {tc - 0.2:.3f});
'''
        for k in range(n - empty, n):
            js += f'      tl.to("#pv{c.i}_{k} .body", {{ fill: "#ffffff", duration: 0.2 }}, {te - 0.2:.3f}); tl.to("#pv{c.i}_{k}", {{ y: -14, duration: 0.15, yoyo: true, repeat: 3 }}, {te - 0.1:.3f});\n'
        c.sfx("pop", tc, 0.45, 1000)
    js += "      " + exit_up(c, f"{S} .bars, {S} .ppl")
    return html, js


def intro(s, c):
    S = f"#s{c.i}"
    photos = s.get("photos", [])[:2]
    ph = "".join(f'<div class="ph p{k + 1}"><img src="media/{E(p)}" alt="" /></div>' for k, p in enumerate(photos))
    tags = s.get("tags", [])[:4]
    tg = "".join(f'<div id="tg{c.i}_{k}" class="{"on" if t.get("highlight") else ""}">{E(t["text"])}</div>' for k, t in enumerate(tags))
    y = 300 if photos else 470   # centre the scene vertically when there are no photos
    html = f'''{c.logo("biglogo lg", style=f"top:{y}px")}
        <div class="ctr sf tag fit" style="top:{y + 220}px">{E(s.get("tagline", ""))}<br/><em>{E(s.get("tagline_em", ""))}</em></div>
        {ph}
        <div class="tags" style="top:{1240 if photos else y + 450}px">{tg}</div>'''
    tl_ = c.cue(s.get("logo_cue", "x"), c.sb, frac=0.1)
    tt = c.cue(s.get("tagline_cue", "x"), tl_, frac=0.3)
    js = f'''tl.fromTo("{S} .lg", {{ scale: 1.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "power4.out" }}, {tl_ - 0.4:.3f});
      tl.fromTo("{S} .tag", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap }}, {tt - 0.2:.3f});
'''
    for k in range(len(photos)):
        js += f'      tl.fromTo("{S} .p{k + 1}", {{ y: 500, rotation: {-6 if k == 0 else 6}, opacity: 0 }}, {{ y: 0, rotation: {-3 if k == 0 else 3}, opacity: 1, duration: 0.55, ease: snap }}, {tt + 0.2 + 0.25 * k:.3f});\n'
    after = tt
    for k, t in enumerate(tags):
        tk = c.cue(t["cue"], after, frac=0.6 + 0.1 * k) if t.get("cue") else after + 0.6
        after = tk
        js += f'      tl.fromTo("#tg{c.i}_{k}", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: pop }}, {tk - 0.2:.3f});\n'
        c.sfx("pop", tk, 0.45, 1000)
    js += "      " + exit_up(c, f"{S} .lg, {S} .tag, {S} .ph, {S} .tags")
    c.sfx("thud", tl_, 0.85)
    return html, js


def steps(s, c):
    S = f"#s{c.i}"
    st = s.get("steps", [])[:4]
    gap = min(370, 1110 // max(1, len(st)))
    items = "".join(
        f'<div class="st" id="st{c.i}_{k}" style="top:{390 + k * gap}px"><div class="no" id="no{c.i}_{k}">{k + 1}</div><div class="bd card"><div class="h">{E(x["title"])}</div>'
        f'<div class="chips">{"".join(f"<span>{E(ch)}</span>" for ch in x.get("chips", [])[:5])}</div></div></div>' for k, x in enumerate(st))
    html = f'<div class="ctr sf t fit">{E(s.get("title", "How it works"))}</div><div class="rail" style="height:{(len(st) - 1) * gap + 150}px"><i></i></div>{items}'
    js = f'tl.fromTo("{S} .t", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap }}, {c.sb + 0.1:.3f});\n'
    after, t0 = c.sb, None
    for k, x in enumerate(st):
        t = c.cue(x.get("cue") or x["title"].split()[0], after, frac=0.05 + 0.9 * k / max(1, len(st)))
        after = t; t0 = t0 or t
        js += f'''      tl.fromTo("#st{c.i}_{k}", {{ x: 900, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.45, ease: snap }}, {t - 0.35:.3f});
      tl.to("#no{c.i}_{k}", {{ backgroundColor: "var(--primary)", borderColor: "var(--primary)", color: "#ffffff", scale: 1.1, duration: 0.25, ease: pop }}, {t:.3f});
      tl.to("#no{c.i}_{k}", {{ scale: 1, duration: 0.2 }}, {t + 0.25:.3f});
      tl.fromTo("#st{c.i}_{k} .chips span", {{ y: 20, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.25, stagger: 0.18 }}, {t + 0.3:.3f});
'''
        c.sfx("pop", t, 0.45, 1000)
    end = c.line_end_last()
    js += f'      tl.fromTo("{S} .rail i", {{ scaleY: 0 }}, {{ scaleY: 1, duration: {max(0.5, end - (t0 or c.sb)):.3f}, ease: "none" }}, {t0 or c.sb:.3f});\n'
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
    js = f'''tl.fromTo("{S} .t", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap }}, {c.sb + 0.1:.3f});
      tl.fromTo("{S} .claim", {{ y: 900, rotation: 6 }}, {{ y: 0, rotation: -1, duration: 0.55, ease: snap }}, {c.sb + 0.15:.3f});
      tl.fromTo("{S} .stamp", {{ scale: 3, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.22, ease: "power4.in" }}, {ts - 0.15:.3f});
      tl.to("{S} .claim", {{ x: 10, duration: 0.05, yoyo: true, repeat: 3 }}, {ts + 0.08:.3f});
      tl.to("{S} .front", {{ scaleX: 0, duration: 0.25, ease: "power2.in" }}, {tflip - 0.6:.3f});
      tl.set("{S} .front", {{ opacity: 0 }}, {tflip - 0.35:.3f});
      tl.set("{S} .back", {{ opacity: 1, scaleX: 0 }}, {tflip - 0.35:.3f});
      tl.to("{S} .back", {{ scaleX: 1, duration: 0.25, ease: "power2.out" }}, {tflip - 0.35:.3f});
'''
    for k, t in back_cues:
        js += f'      tl.fromTo("#rv{c.i}b{k}", {{ scale: 0.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: pop }}, {t:.3f});\n'
        c.sfx("shimmer", t, 0.5)
    c.sfx("thud", ts, 0.85)
    js += "      " + exit_up(c, f"{S} .t, {S} .claim")
    return html, js


def question(s, c):
    S = f"#s{c.i}"
    html = f'''<div class="ctr sf q1">{E(s.get("pre", "So what makes"))}</div>
        <div class="ctr sf q2 fit"><em>{E(s.get("em", ""))}</em> {E(s.get("post", "different?"))}</div>
        <div class="ctr mk">?</div>'''
    te = c.cue(s.get("em_cue", "x"), c.sb, frac=0.4)
    tm = c.cue(s.get("mark_cue", "x"), te, frac=0.8)
    js = f'''tl.fromTo("{S} .q1", {{ y: 60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .q2", {{ scale: 1.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.4, ease: "power4.out" }}, {te - 0.15:.3f});
      tl.fromTo("{S} .mk", {{ scale: 0, rotation: -60 }}, {{ scale: 1, rotation: 0, duration: 0.5, ease: pop }}, {tm:.3f});
      ''' + exit_up(c, f"{S} .q1, {S} .q2, {S} .mk")
    c.sfx("thud", tm, 0.85)
    return html, js


def compare(s, c):
    S = f"#s{c.i}"
    rows = s.get("rows", [])[:4]
    rh = "".join(
        f'<div class="row" style="top:{380 + k * 270}px"><div class="a" id="ra{c.i}_{k}"><s class="fit" data-box="parent">{E(r["left"])}</s></div>'
        f'<div class="b" id="rb{c.i}_{k}"><span class="ck">{CHECK}</span><span class="fit" data-box="parent">{E(r["right"])}</span></div></div>' for k, r in enumerate(rows))
    html = f'<div class="hd"><div class="a">{E(s.get("left_label", "Others"))}</div><div class="b">{E(s.get("right_label", ""))}</div></div>{rh}'
    js = f'tl.fromTo("{S} .hd", {{ y: -60, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, {c.sb + 0.05:.3f});\n'
    after = c.sb
    for k, r in enumerate(rows):
        tb = c.cue(r.get("right_cue", "x"), after, frac=0.2 + 0.8 * (k + 0.6) / len(rows))
        ta = c.cue(r["left_cue"], after, frac=0.2 + 0.8 * k / len(rows)) if r.get("left_cue") else tb - 0.5
        ta = min(ta, tb - 0.2); after = tb
        js += f'''      tl.fromTo("#ra{c.i}_{k}", {{ x: -600, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.35, ease: snap }}, {ta - 0.25:.3f});
      tl.fromTo("#rb{c.i}_{k}", {{ x: 600, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.35, ease: snap }}, {tb - 0.25:.3f});
      tl.fromTo("#rb{c.i}_{k} .ck", {{ scale: 0 }}, {{ scale: 1, duration: 0.3, ease: pop }}, {tb + 0.05:.3f});
      tl.to("#rb{c.i}_{k}", {{ backgroundColor: "var(--primary)", color: "#ffffff", duration: 0.25 }}, {tb + 0.1:.3f});
      tl.to("#rb{c.i}_{k}", {{ backgroundColor: "#ffffff", color: "var(--ink)", duration: 0.5 }}, {tb + 0.9:.3f});
'''
        c.sfx("tick", ta, 0.6); c.sfx("pop", tb, 0.6, 1300)
    if not c.last:
        js += f'      tl.to("{S} .hd, {S} .row", {{ opacity: 0, y: -50, duration: 0.3, stagger: 0.02 }}, {c.se - 0.35:.3f});\n'
    return html, js


def end(s, c):
    S = f"#s{c.i}"
    ch = s.get("chart")
    html, js = "", ""
    if ch:
        bars = ch.get("bars", [])[:5]
        shades = ["var(--primary)", "var(--mix1)", "var(--mix2)", "var(--accent)", "var(--accent)"]
        html += f'<div class="ctr k ch">{E(ch.get("label", ""))}</div><div class="chart">' + "".join(
            f'<div class="bar" id="eb{c.i}_{k}" style="height:{max(1, min(100, float(b.get("from", 100))))}%;background:{shades[k]}"></div>' for k, b in enumerate(bars)) + "</div>"
        html += '<div class="albl">' + "".join(f"<span>{E(b.get('label', ''))}</span>" for b in bars) + "</div>"
        js += f'''tl.fromTo("{S} .ch, {S} .albl", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {c.sb + 0.1:.3f});
      tl.fromTo("{S} .bar", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.5, ease: snap, stagger: 0.08 }}, {c.sb + 0.05:.3f});
'''
        for k, b in enumerate(bars):
            fr, to = float(b.get("from", 100)), float(b.get("to", b.get("from", 100)))
            if fr > 0 and abs(fr - to) > 0.01:
                js += f'      tl.to("#eb{c.i}_{k}", {{ scaleY: {to / fr:.3f}, duration: 0.8, ease: "power2.inOut" }}, {c.sb + 0.8 + 0.1 * k:.3f});\n'
    top = 900 if ch else 600
    html += c.logo("biglogo lg", style=f"top:{top}px") + f'''
        <div class="ctr sf tg fit" style="top:{top + 210}px">{E(s.get("tagline", ""))}<br/><em>{E(s.get("tagline_em", ""))}</em></div>
        <div class="ctr url" style="top:{top + 460}px">{E(s.get("url") or c.url)}</div>'''
    tlg = c.cue(s.get("logo_cue", "x"), c.sb, frac=0.7)
    ttg = c.cue(s.get("tagline_cue", "x"), c.sb, frac=0.05)
    js += f'''      tl.fromTo("{S} .lg", {{ scale: 1.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "power4.out" }}, {tlg - 0.4:.3f});
      tl.fromTo("{S} .tg", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap }}, {ttg - 0.3:.3f});
      tl.fromTo("{S} .url", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.4 }}, {tlg + 0.3:.3f});
'''
    c.sfx("thud", tlg, 0.85); c.sfx("shimmer", ttg, 0.5)
    return html, js


def website(s, c):
    """The real website scrolling inside a phone frame (screenshot captured by capture_site.cjs)."""
    S = f"#s{c.i}"
    SCREEN_W, VIEW_H = 568, 1032                       # screen width and visible height in video pixels
    img_h = round(s.get("shot_px", 2000) * SCREEN_W / 780)
    dist = max(0, img_h - VIEW_H)
    lock = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M7 11V8a5 5 0 0 1 10 0v3" fill="none" stroke="currentColor" stroke-width="2.4"/><rect x="5" y="11" width="14" height="10" rx="2" fill="currentColor"/></svg>'
    html = f'''<div class="ctr k kick">{E(s.get("kicker", "See it live"))}</div>
        <div class="ctr sf t fit">{E(s.get("title", ""))}</div>
        <div class="phone"><div class="screen">
          <div class="bar">{lock}<span>{E(s.get("url_label", c.url))}</span></div>
          <div class="view"><img class="shot" src="media/{E(s.get("shot", ""))}" style="height:{img_h}px" alt="" /></div>
        </div></div>'''
    if s.get("mode") == "logo":   # no capture and no share image: logo + address on a clean page
        html = html.replace(f'<div class="view"><img class="shot" src="media/{E(s.get("shot", ""))}" style="height:{img_h}px" alt="" /></div>',
            f'<div class="view logo">{c.logo("biglogo cardlogo")}<div class="site">{E(s.get("url_label", c.url))}</div>'
            f'<div class="visit">Visit website</div></div>')
        js = f'''tl.fromTo("{S} .kick, {S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap, stagger: 0.08 }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .phone", {{ y: 1100, rotation: 4 }}, {{ y: 0, rotation: 0, duration: 0.7, ease: "power3.out" }}, {c.sb + 0.15:.3f});
      tl.fromTo("{S} .cardlogo", {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.6, ease: "back.out(1.7)" }}, {c.sb + 0.75:.3f});
      tl.fromTo("{S} .site, {S} .visit", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap, stagger: 0.12 }}, {c.sb + 1.1:.3f});
      tl.to("{S} .visit", {{ scale: 1.06, duration: 0.5, ease: "sine.inOut", yoyo: true, repeat: 3 }}, {c.sb + 1.8:.3f});
'''
        c.sfx("pop", c.sb + 0.3, 0.45, 900); c.sfx("pop", c.sb + 0.8, 0.4, 1200)
        js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .phone")
        return html, js
    if s.get("mode") == "card":   # page couldn't be captured: the site's own share image, slow zoom
        img = E(s.get("shot", ""))
        html = html.replace(f'<div class="view"><img class="shot" src="media/{img}" style="height:{img_h}px" alt="" /></div>',
            f'<div class="view card"><img class="bg" src="media/{img}" alt="" /><img class="cardimg" src="media/{img}" alt="" />'
            f'<div class="site">{E(s.get("url_label", c.url))}</div></div>')
        js = f'''tl.fromTo("{S} .kick, {S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap, stagger: 0.08 }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .phone", {{ y: 1100, rotation: 4 }}, {{ y: 0, rotation: 0, duration: 0.7, ease: "power3.out" }}, {c.sb + 0.15:.3f});
      tl.fromTo("{S} .cardimg", {{ scale: 0.86, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.6, ease: snap }}, {c.sb + 0.7:.3f});
      tl.fromTo("{S} .bg", {{ scale: 1.15 }}, {{ scale: 1.35, duration: {max(1.0, c.se - c.sb - 0.8):.3f}, ease: "none" }}, {c.sb + 0.15:.3f});
      tl.to("{S} .cardimg", {{ scale: 1.08, duration: {max(1.0, c.se - c.sb - 1.6):.3f}, ease: "sine.inOut" }}, {c.sb + 1.3:.3f});
      tl.fromTo("{S} .site", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap }}, {c.sb + 1.1:.3f});
'''
        c.sfx("pop", c.sb + 0.3, 0.45, 900); c.sfx("whoosh", c.sb + 0.7, 0.25)
        js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .phone")
        return html, js
    t0, t1 = c.sb + 1.4, max(c.sb + 3, c.se - 0.8)
    seg = (t1 - t0) / 3
    js = f'''tl.fromTo("{S} .kick, {S} .t", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: snap, stagger: 0.08 }}, {c.sb + 0.05:.3f});
      tl.fromTo("{S} .phone", {{ y: 1100, rotation: 4 }}, {{ y: 0, rotation: 0, duration: 0.7, ease: "power3.out" }}, {c.sb + 0.15:.3f});
'''
    for k in range(3):   # scroll in three moves with short pauses, like a person reading
        a = t0 + k * seg
        js += f'      tl.to("{S} .shot", {{ y: {-round(dist * (k + 1) / 3)}, duration: {seg * 0.7:.3f}, ease: "power2.inOut" }}, {a:.3f});\n'
        c.sfx("whoosh", a, 0.25)
    c.sfx("pop", c.sb + 0.3, 0.45, 900)
    js += "      " + exit_up(c, f"{S} .kick, {S} .t, {S} .phone")
    return html, js


def json_list(xs):
    return "[" + ",".join(f"{x:.3f}" for x in xs) + "]"


BUILDERS = {"problem": problem, "stats": stats, "intro": intro, "steps": steps, "flip": flip,
            "question": question, "compare": compare, "end": end, "website": website}
HIDE_BRAND = {"intro", "end"}
