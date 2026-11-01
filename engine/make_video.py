"""Video Studio engine: video.json -> vertical video (1080x1920 MP4) + subtitles (.srt) + thumbnail (.jpg).

  python engine/make_video.py videos/docsdocs                 # full run
  python engine/make_video.py videos/docsdocs --no-render     # build index.html + audio only (fast check)
  python engine/make_video.py videos/docsdocs --voice edge:en-IN-PrabhatNeural --subtitles karaoke --theme dark

Pipeline: voice (Kokoro / Edge / Piper / Chatterbox, cached in <video>/.voice/) -> join lines -> word timing
-> scenes synced to the words -> fonts for the language -> sound design + music -> HyperFrames render.
Output: <video>/out/<name>.mp4, <name>.srt, <name>.jpg
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys
import numpy as np, soundfile as sf

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
sys.path.insert(0, ENGINE)
import scenes as SC      # noqa: E402
import sfx as FX         # noqa: E402
import media as MEDIA    # noqa: E402
import voices as VO      # noqa: E402
import timing as TM      # noqa: E402
import languages as LANG  # noqa: E402
import audio as AU       # noqa: E402
import fonts as FONTS    # noqa: E402
import motion as MO      # noqa: E402
NPX = shutil.which("npx") or "npx"

# pauses (seconds): before the first line, after the last, between lines of a scene, between scenes, after scene 1
PACE = {"fast": (0.2, 1.0, 0.2, 0.22, 0.2), "normal": (0.35, 1.6, 0.3, 0.55, 0.7), "relaxed": (0.5, 2.2, 0.42, 0.8, 1.0)}
SUB_STYLES = ("kinetic", "bold", "karaoke", "classic", "none")
OWN_CAMERA = {"problem", "stats", "intro", "flip", "question", "end", "photo", "broll", "website", "spotlight"}   # scenes with their own punch-ins
THEMES = ("light", "dark")


def log(*a): print("[video]", *a, flush=True)


# ---------------------------------------------------------------- colours
def hex_rgb(h):
    h = h.lstrip("#"); h = "".join(c * 2 for c in h) if len(h) == 3 else h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgba(h, a): r, g, b = hex_rgb(h); return f"rgba({r},{g},{b},{a})"


def mix(h1, h2, t):
    a, b = hex_rgb(h1), hex_rgb(h2)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def lum(h):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h); return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = lum(a), lum(b); return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def readable(c, bg, need, toward="#000000"):
    """Move colour `c` toward `toward` step by step (keeping its hue) until it reaches `need` contrast on `bg`."""
    t = 0.0
    while contrast(mix(c, toward, t), bg) < need and t < 0.95: t += 0.05
    return mix(c, toward, t)


def palette(col, theme="light"):
    good = lambda v: isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", v)
    g = lambda k, d: col.get(k) if good(col.get(k)) else d
    p = {"primary": g("primary", "#024c87"), "accent": g("accent", "#85bbe0"), "alert": g("alert", "#d64545"),
         "ink": g("ink", "#0d2440"), "bg": g("background", "#f3f6fb")}
    hl = g("highlight", "#FFE600")
    if theme == "dark":
        p["bg"] = p["bg"] if lum(p["bg"]) < 0.03 else mix("#0a0d14", p["primary"], 0.10)
        p["ink"] = "#f2f4f8"
        p["primary"] = readable(p["primary"], p["bg"], 4.6, "#ffffff")
        p["alert"] = readable(p["alert"], p["bg"], 4.2, "#ffffff")
        accent_dark = readable(mix(p["accent"], p["primary"], 0.3), p["bg"], 3.2, "#ffffff")
        surface = mix(p["bg"], "#ffffff", 0.08)
        p.update({"dim": readable(mix(p["ink"], p["bg"], 0.35), p["bg"], 4.6, "#ffffff"), "pale": mix(p["primary"], p["bg"], 0.72),
                  "surface": surface, "muted-bg": mix(p["bg"], "#ffffff", 0.14), "muted-ink": mix(p["ink"], p["bg"], 0.42),
                  "ink-10": "rgba(255,255,255,0.08)", "ink-12": "rgba(255,255,255,0.12)", "ink-16": "rgba(0,0,0,0.45)",
                  "ink-18": "rgba(0,0,0,0.55)", "ink-86": "rgba(0,0,0,0.80)", "alert-15": mix(p["alert"], p["bg"], 0.78),
                  "land": mix(p["bg"], "#ffffff", 0.16)})
    else:
        # keep any brand palette readable: light background, dark text, colours darkened only as much as needed
        if lum(p["bg"]) < 0.80: p["bg"] = mix(p["bg"], "#ffffff", 0.85)
        p["ink"] = readable(p["ink"], p["bg"], 10)
        p["primary"] = readable(p["primary"], p["bg"], 4.6)
        p["alert"] = readable(p["alert"], p["bg"], 4.0)
        accent_dark = readable(mix(p["accent"], p["primary"], 0.45), p["bg"], 3.2)
        t = 0.35
        while contrast(mix(p["ink"], "#ffffff", t), "#ffffff") < 4.6 and t > 0: t -= 0.05
        p.update({"dim": mix(p["ink"], "#ffffff", t), "pale": mix(p["primary"], "#ffffff", 0.88), "surface": "#ffffff",
                  "muted-bg": "#eceff3", "muted-ink": "#5b6779", "ink-10": rgba(p["ink"], 0.10), "ink-12": rgba(p["ink"], 0.12),
                  "ink-16": rgba(p["ink"], 0.16), "ink-18": rgba(p["ink"], 0.18), "ink-86": rgba(p["ink"], 0.86),
                  "alert-15": mix(p["alert"], "#ffffff", 0.85), "land": mix("#cfd6e0", p["primary"], 0.08)})
    p.update({"accent-dark": accent_dark, "mix1": mix(p["primary"], p["accent"], 0.33), "mix2": mix(p["primary"], p["accent"], 0.66),
              "accent-35": rgba(p["accent"], 0.35), "accent-60": rgba(p["accent"], 0.6), "primary-08": rgba(p["primary"], 0.08),
              "primary-12": rgba(p["primary"], 0.12), "alert-45": rgba(p["alert"], 0.45),
              "on-primary": "#ffffff" if contrast(p["primary"], "#ffffff") >= 4.5 else "#0b1020",
              "highlight": hl, "accent-hl": hl, "accent-hl-green": "#22C55E"})
    return p


# ---------------------------------------------------------------- audio assembly
def trim(x, sr, db=-40, pad=0.04):
    """Cut leading/trailing silence. Returns (audio, seconds removed at the start)."""
    env = np.abs(x); thr = 10 ** (db / 20) * max(env.max(), 1e-9)
    idx = np.where(env > thr)[0]
    if len(idx) == 0: return x, 0.0
    a = max(0, idx[0] - int(pad * sr))
    return x[a: min(len(x), idx[-1] + int(pad * sr))], a / sr


def assemble(paths, scene_of_line, out_wav, pace, pauses):
    LEAD, TAIL, GAP_IN, GAP_SCENE, GAP_FIRST = PACE.get(pace, PACE["fast"])
    clips, sr, cut = [], None, []
    for p in paths:
        x, s = sf.read(p, dtype="float32")
        if x.ndim > 1: x = x.mean(axis=1)
        if sr and s != sr:   # engines can differ in sample rate (several speakers): resample to the first one
            x = np.interp(np.linspace(0, len(x), int(len(x) * sr / s), endpoint=False), np.arange(len(x)), x).astype("float32")
        sr = sr or s
        y, c0 = trim(x, sr); clips.append(y); cut.append(c0)
    gaps = []
    for k in range(len(clips) - 1):
        change = scene_of_line[k + 1] != scene_of_line[k]
        g = GAP_FIRST if change and scene_of_line[k] == 0 else GAP_SCENE if change else GAP_IN
        if pauses[k] is not None: g = float(pauses[k])        # "pause_after": seconds, set per line
        gaps.append(g)
    total = LEAD + sum(len(c) / sr for c in clips) + sum(gaps) + TAIL
    out = np.zeros(int(total * sr) + 1, dtype="float32"); marks, t = [], LEAD
    for k, c in enumerate(clips):
        st = int(t * sr); out[st:st + len(c)] = c
        marks.append({"start": round(t, 3), "end": round(t + len(c) / sr, 3), "trim": round(cut[k], 3)})
        t += len(c) / sr + (gaps[k] if k < len(gaps) else 0)
    sf.write(out_wav, out, sr)
    return marks, round(total, 2), out, sr


# ---------------------------------------------------------------- cues
class SceneContext:
    def __init__(self, i, n, sb, se, lines_idx, marks, words, url, logo_html, warns, events, locale="en"):
        self.i, self.first, self.last, self.sb, self.se = i, i == 0, i == n - 1, sb, se
        self.lines_idx, self.marks, self.words, self.url = lines_idx, marks, words, url
        self._logo, self.warns, self.events, self.locale = logo_html, warns, events, locale
        self.lang, self.nospace = "en", False
        lo, hi = lines_idx[0], lines_idx[-1]
        self.scene_words = [w for w in words if lo <= w["line"] <= hi]

    def line_end_last(self): return self.marks[self.lines_idx[-1]]["end"]

    def find(self, word, after):
        """Time `word` is spoken in this scene at or after `after`, or None. Works in any script."""
        key = TM.norm(word)
        if not key: return None
        ws = [w for w in self.scene_words if w["t"] >= after - 0.05]
        for w in ws:
            if key in TM.norm(w["text"]): return round(w["t"], 3)
        s, owner = "", []      # across word boundaries (languages without spaces, split names)
        for w in ws:
            k = TM.norm(w["text"]); s += k; owner += [w] * len(k)
        i = s.find(key)
        return round(owner[i]["t"], 3) if i >= 0 else None

    def cue(self, word, after, frac=0.5):
        """When `word` is spoken in this scene, searching from time `after` (estimated if never heard)."""
        t = self.find(word, after) if word and word != "x" else None
        if t is not None: return t
        st, en = self.marks[self.lines_idx[0]]["start"], self.marks[self.lines_idx[-1]]["end"]
        t = round(max(after + 0.4, st + (en - st) * frac), 3)
        if word and word != "x":
            self.warns.append(f'scene {self.i + 1}: did not hear "{word}", using {t:.2f}s (check the cue word or the pronunciation)')
        return t

    def split(self, text):
        """Display words of `text`; languages without spaces are cut at the spoken word boundaries."""
        text = str(text or "")
        if not LANG.no_spaces(self.lang) or len(text.split()) > 2: return text.split()
        seg = TM.segment_like(text, [w for w in self.scene_words if TM.norm(w["text"]) and TM.norm(w["text"]) in TM.norm(text)])
        return seg or TM.tokens(text, self.lang)

    def sfx(self, kind, t, gain, *args): self.events.append((kind, t, gain, args))

    def logo(self, cls, style=""): return self._logo(cls, style)


# ---------------------------------------------------------------- subtitles
def _clean(w): return TM.strip_punct(w) or w


def _bursts(sub_words, lang, max_words=3, max_chars=14):
    out = []
    for k, line_w in enumerate(sub_words):
        cur = []
        for w in line_w:
            if not str(w["text"]).strip(): continue
            cur.append(w)
            punc = str(w["text"]).endswith(TM.PUNCT_END)
            chars = sum(len(x["text"]) for x in cur)
            if len(cur) >= max_words or punc or (len(cur) >= 2 and chars >= max_chars):
                out.append((k, cur)); cur = []
        if cur: out.append((k, cur))
    return out


def _chunks(sub_words, max_chars):
    out = []
    for k, line_w in enumerate(sub_words):
        cur = []
        for w in line_w:
            cur.append(w)
            n = sum(len(x["text"]) + 1 for x in cur)
            if n > max_chars * 0.75 and str(w["text"]).endswith(TM.PUNCT_END) or n > max_chars:
                out.append((k, cur)); cur = []
        if cur:
            n = sum(len(x["text"]) + 1 for x in cur)
            if out and out[-1][0] == k and n < 12 and sum(len(x["text"]) + 1 for x in out[-1][1]) + n <= max_chars * 1.35:
                out[-1] = (k, out[-1][1] + cur)          # no orphan word on its own at the end of a line
            else:
                out.append((k, cur))
    return out


def build_subtitles(sub_words, marks, style, lang, case):
    """HTML + GSAP for the subtitles. sub_words[line] = [{text, start, end}]."""
    if style == "none": return [], ""
    joiner = "" if LANG.no_spaces(lang) else " "
    groups = _bursts(sub_words, lang, 3, 14) if style in ("kinetic", "bold") else _chunks(sub_words, 38 if style == "karaoke" else 64)
    html, js = [], []
    for n, (li, g) in enumerate(groups, 1):
        b_start = g[0]["start"]
        if n < len(groups):
            nxt = groups[n][1][0]["start"]
            b_end = nxt if groups[n][0] == li and nxt - g[-1]["end"] < 0.35 else min(g[-1]["end"] + 0.25, nxt - 0.01)
        else:
            b_end = max(g[-1]["end"] + 0.25, marks[li]["end"] + 0.15)
        dur = round(max(0.12, b_end - b_start), 3)
        spans = []
        for wi, w in enumerate(g):
            txt = _clean(w["text"]) if style in ("kinetic", "bold") else w["text"]
            spans.append(f'<span class="w" id="w{n}_{wi}">{SC.E(txt)}</span>')
        html.append(f'<div id="sub{n}" class="sub clip" data-start="{b_start}" data-duration="{dur}" data-track-index="3">'
                    f'<div class="burst">{joiner.join(spans)}</div></div>')
        if style in ("kinetic", "bold"):
            js.append(f'      tl.fromTo("#sub{n}", {{ opacity: 0, scale: 0.94 }}, {{ opacity: 1, scale: 1, duration: 0.10, ease: "power2.out" }}, {b_start});')
            if dur > 0.16: js.append(f'      tl.to("#sub{n}", {{ opacity: 0, duration: 0.08, ease: "power1.in" }}, {round(b_start + dur - 0.08, 3)});')
            for wi, w in enumerate(g):
                js.append(f'      tl.fromTo("#w{n}_{wi}", {{ color: "#ffffff", scale: {1.22 if style == "bold" else 1.15} }}, '
                          f'{{ color: "var(--highlight)", scale: 1.0, duration: 0.12, ease: "back.out(2)", immediateRender: false }}, {w["start"]});')
                if wi + 1 < len(g) and g[wi + 1]["start"] > w["start"]:
                    js.append(f'      tl.to("#w{n}_{wi}", {{ color: "#ffffff", duration: 0.08 }}, {g[wi + 1]["start"]});')
        elif style == "karaoke":
            js.append(f'      tl.fromTo("#sub{n}", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.14, ease: "power2.out" }}, {b_start});')
            for wi, w in enumerate(g):
                js.append(f'      tl.to("#w{n}_{wi}", {{ color: "var(--highlight)", duration: 0.06 }}, {w["start"]});')
                js.append(f'      tl.to("#w{n}_{wi}", {{ color: "#ffffff", duration: 0.12 }}, {w["end"]});')
        else:
            js.append(f'      tl.fromTo("#sub{n}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12 }}, {b_start});')
    return html, "\n".join(js)


def srt_text(sub_words, lang):
    """Standard .srt captions (for YouTube, Instagram, LinkedIn uploads)."""
    joiner = "" if LANG.no_spaces(lang) else " "
    fmt = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round((t - int(t)) * 1000)) % 1000:03d}"
    out, groups = [], _chunks(sub_words, 42)
    for n, (_, g) in enumerate(groups, 1):
        end = g[-1]["end"] + 0.2
        if n < len(groups): end = min(end, groups[n][1][0]["start"] - 0.02)
        out.append(f"{n}\n{fmt(g[0]['start'])} --> {fmt(max(end, g[0]['start'] + 0.3))}\n{joiner.join(w['text'] for w in g)}\n")
    return "\n".join(out)


# ---------------------------------------------------------------- website capture
def capture_website(url, media_dir):
    """Phone-size full-page screenshot of `url` (engine/capture_site.cjs).
    Returns {"mode": "scroll", "shot", "shot_px"}, or {"mode": "card", ...} with the site's own
    share image when the page can't be captured, or {"mode": "logo"} (logo + address) as the last resort."""
    if not url: return None
    url = url if url.startswith("http") else "https://" + url
    png = os.path.join(media_dir, "site_full.png")
    if os.environ.get("SITE_FALLBACK_TEST") in ("card", "logo"):   # local testing of the fallbacks
        info = {"ok": False, "error": "forced by SITE_FALLBACK_TEST"}
        if os.environ["SITE_FALLBACK_TEST"] == "logo": return {"mode": "logo"}
    else:
        info = None
    try:
        if info: raise RuntimeError(info["error"])
        args = ["node", os.path.join(ENGINE, "capture_site.cjs"), url, png]
        if os.environ.get("HYPERFRAMES_BROWSER_PATH"): args.append(os.environ["HYPERFRAMES_BROWSER_PATH"])
        r = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=REPO)
        info = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    except Exception as e:
        info = {"ok": False, "error": str(e)}
    if info.get("ok"):
        from PIL import Image
        im = Image.open(png).convert("RGB"); jpg = "site_scroll.jpg"
        im.save(os.path.join(media_dir, jpg), quality=86); os.remove(png)
        log(f"captured {url} ({im.height}px tall)")
        return {"mode": "scroll", "shot": jpg, "shot_px": im.height}
    log(f"could not capture {url} ({info.get('error', 'unknown error')}); trying the site's share image")
    try:
        card = MEDIA.share_card(url, media_dir)
    except Exception as e:
        card = None; log(f"share image failed: {e}")
    if card:
        log(f"website scene uses the share image of {url} ({card[1]}x{card[2]})")
        return {"mode": "card", "shot": card[0], "card_w": card[1], "card_h": card[2]}
    log(f"no share image for {url}; website scene shows the logo and address instead")
    return {"mode": "logo"}


# ---------------------------------------------------------------- helpers
def flat_lines(scenes):
    lines, scene_of_line = [], []
    for i, s in enumerate(scenes):
        for ln in s["lines"]:
            lines.append(ln); scene_of_line.append(i)
    return lines, scene_of_line


def on_screen_text(scenes, cfg):
    """All text that can appear on screen (used to fetch fonts for the right characters)."""
    out = [str(cfg.get("company", "")), str(cfg.get("url", ""))]
    def walk(v):
        if isinstance(v, str): out.append(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ("lines", "image_query", "image_queries", "video_query", "photo", "photos", "video", "type", "url") and not k.endswith("cue"): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
    for s in scenes: walk(s)
    return " ".join(out)


def option(a_val, cfg, key, default, allowed=None):
    v = a_val if a_val not in (None, "") else cfg.get(key, default)
    if allowed and v not in allowed:
        log(f'WARN "{key}": "{v}" is not one of {", ".join(allowed)}; using "{default}"'); v = default
    return v


# ---------------------------------------------------------------- covers + other formats
def cover_text(cfg, scenes):
    """(kicker, title, em) for the cover: the creator's "cover" settings, else the opening scene's big line."""
    cv = cfg.get("cover") if isinstance(cfg.get("cover"), dict) else {}
    if cv.get("title"): return cv.get("kicker", ""), cv["title"], cv.get("em", "")
    for s in scenes[:3]:
        t = s["type"]
        if t == "hook": return s.get("kicker", ""), s.get("text", ""), s.get("em", "")
        if t in ("photo", "broll"): return s.get("kicker", ""), s.get("caption", ""), s.get("caption_em", "")
        if t == "problem": return s.get("kicker", ""), s.get("title", ""), s.get("title_em", "")
        if s.get("title"): return s.get("kicker", ""), s["title"], s.get("title_em", "")
    end = next((s for s in scenes if s["type"] == "end"), {})
    return "", cfg.get("company", ""), end.get("tagline_em", "")


def cover_photo(cfg, scenes):
    cv = cfg.get("cover") if isinstance(cfg.get("cover"), dict) else {}
    if cv.get("photo_file"): return cv["photo_file"]
    for s in scenes:
        for f in (s.get("photo_file"), s.get("photo")):
            if f: return f
        for key in ("tiles", "items", "steps", "events"):
            for it in s.get(key) or []:
                if isinstance(it, dict) and it.get("photo_file"): return it["photo_file"]
        for side in ("left", "right", "after", "before"):
            d = s.get(side)
            if isinstance(d, dict) and d.get("photo_file"): return d["photo_file"]
    return None


def make_covers(build, outdir, name, cfg, scenes, head_css, logo_html):
    """Designed cover images: <name>.jpg (9:16, Reels/Shorts cover) and <name>-youtube.jpg (16:9 thumbnail)."""
    kick, title, em = cover_text(cfg, scenes)
    photo = cover_photo(cfg, scenes)
    bg = f'<img class="bg" src="media/{SC.E(photo)}" alt="" />' if photo else '<div class="bg grad"></div>'
    cx = " cx" if re.search(r"[^\x00-\u024F\u2000-\u206F\u20A0-\u20CF]", f"{kick}{title}{em}") else ""   # Indic, Arabic, CJK...
    made = []
    for orient, (w, h), out in (("tall", (1080, 1920), f"{name}.jpg"), ("wide", (1280, 720), f"{name}-youtube.jpg")):
        page = f'''<!doctype html><html><head><meta charset="UTF-8"/><style>{head_css}
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#000}}
.cv{{position:relative;width:{w}px;height:{h}px;overflow:hidden;font-family:var(--font-sans)}}
.bg{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.bg.grad{{background:radial-gradient(1200px 900px at 80% 10%,var(--accent),transparent 60%),linear-gradient(160deg,var(--primary),#0b0f1a)}}
.shade{{position:absolute;inset:0}}
.tall .shade{{background:linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,0) 22%,rgba(0,0,0,0) 40%,rgba(0,0,0,.88) 72%,rgba(0,0,0,.92) 100%)}}
.wide .shade{{background:linear-gradient(90deg,rgba(0,0,0,.9) 0%,rgba(0,0,0,.75) 45%,rgba(0,0,0,0) 80%)}}
.brand{{position:absolute;display:flex;align-items:center;padding:14px 26px;border-radius:999px;background:rgba(255,255,255,.94)}}
.brand img{{height:100%;max-width:100%;object-fit:contain}} .brand .wm{{font-weight:900;color:var(--primary);white-space:nowrap;font-size:1em}}
.brand .lockup{{display:inline-flex;align-items:center;gap:.35em;height:100%}} .brand .lockup .ico{{height:1em}}
.tall .brand{{left:50%;transform:translateX(-50%);top:110px;height:64px;font-size:44px}}
.wide .brand{{left:56px;top:48px;height:46px;font-size:32px}}
.kick{{position:absolute;color:var(--highlight);font-weight:800;letter-spacing:.14em;text-transform:uppercase}}
.ttl{{position:absolute;color:#fff;font-weight:900;line-height:1.02;letter-spacing:-.02em;text-shadow:0 6px 30px rgba(0,0,0,.5)}}
.ttl em{{font-style:normal;color:var(--highlight)}} .cx .kick{{letter-spacing:0}} .cx .ttl{{line-height:1.22}}
.tall .kick{{left:80px;right:80px;top:1080px;font-size:34px;text-align:center}}
.tall .ttl{{left:60px;right:60px;top:1140px;height:560px;font-size:156px;text-align:center;display:flex;align-items:flex-start;justify-content:center}}
.wide .kick{{left:56px;width:62%;top:200px;font-size:26px}}
.wide .ttl{{left:56px;width:64%;top:244px;height:420px;font-size:108px}}
.bar{{position:absolute;background:var(--highlight)}} .tall .bar{{left:470px;width:140px;height:10px;top:1740px;border-radius:5px}} .wide .bar{{left:56px;width:120px;height:9px;top:170px;border-radius:5px}}
</style></head><body><div class="cv {orient}{cx}">{bg}<div class="shade"></div><div class="bar"></div>
<div class="brand">{logo_html("x").split(">", 1)[1].rsplit("</div>", 1)[0]}</div>
<div class="kick">{SC.E(kick)}</div><div class="ttl fit"><span>{SC.E(title)}{(" <em>" + SC.E(em) + "</em>") if em else ""}</span></div></div>
<script>window.fitAll=function(){{document.querySelectorAll(".fit").forEach(el=>{{let fs=parseFloat(getComputedStyle(el).fontSize),n=0;
while((el.scrollHeight>el.clientHeight+2||el.scrollWidth>el.clientWidth+2)&&fs>24&&n<80){{fs-=3;el.style.fontSize=fs+"px";n++}}}})}};fitAll();</script></body></html>'''
        hp = os.path.join(build, f"cover_{orient}.html")
        open(hp, "w", encoding="utf-8").write(page)
        try:
            args = ["node", os.path.join(ENGINE, "cover.cjs"), hp, os.path.join(outdir, out), str(w), str(h)]
            r = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=REPO)
            if r.returncode == 0: made.append(out)
            else: log(f"WARN cover {orient} failed: {(r.stdout + r.stderr)[-200:]}")
        except Exception as e:
            log(f"WARN cover {orient} failed: {e}")
    if made: log("covers: " + ", ".join(made))
    return made


def other_formats(mp4, formats):
    """16:9 and 1:1 versions of the vertical video: the video in the middle, a blurred copy filling the sides."""
    sizes = {"16:9": (1920, 1080, "16x9"), "1:1": (1080, 1080, "1x1"), "4:5": (1080, 1350, "4x5")}
    out = []
    for f in formats:
        if f not in sizes: log(f'WARN unknown format "{f}" (use 16:9, 1:1 or 4:5)'); continue
        W, H, tag = sizes[f]
        dst = mp4[:-4] + f"-{tag}.mp4"
        flt = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:4,eq=brightness=-0.12[bg];"
               f"[0:v]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-filter_complex", flt, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                            "-c:a", "copy", "-movflags", "+faststart", dst])
        if r.returncode == 0: out.append(os.path.basename(dst))
    if out: log("other formats: " + ", ".join(out))
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir", help="folder containing video.json, e.g. videos/docsdocs")
    ap.add_argument("--skip-voice", action="store_true", help="fail instead of generating missing voice lines")
    ap.add_argument("--no-render", action="store_true", help="stop after building index.html and the audio")
    ap.add_argument("--voice", help='override the narrator voice, e.g. "am_michael" or "edge:hi-IN-MadhurNeural"')
    ap.add_argument("--lang", help="language code (default: video.json \"language\", else detected from the text)")
    ap.add_argument("--subtitles", help="kinetic | bold | karaoke | classic | none")
    ap.add_argument("--theme", help="light | dark")
    ap.add_argument("--music", help="upbeat | calm | dramatic | tech | news | none | a file next to video.json")
    ap.add_argument("--pace", help="fast | normal | relaxed")
    ap.add_argument("--fps", default=os.environ.get("RENDER_FPS", "30"))
    ap.add_argument("--formats", default=os.environ.get("VIDEO_FORMATS", ""), help='extra versions, e.g. "16:9,1:1" (also "formats" in video.json)')
    a = ap.parse_args()

    vdir = os.path.abspath(a.video_dir)
    cfg = json.load(open(os.path.join(vdir, "video.json"), encoding="utf-8"))
    cfg["url"] = re.sub(r"^(https?://)?(www\.)?", "", str(cfg.get("url", ""))).rstrip("/")   # show "amazon.com"
    name = os.path.basename(vdir.rstrip("/"))
    scenes = cfg["scenes"]
    for s in scenes:
        if s.get("type") not in SC.BUILDERS: sys.exit(f'unknown scene type "{s.get("type")}". Use one of: {", ".join(SC.BUILDERS)}')
        if not s.get("lines"): sys.exit(f'scene "{s["type"]}" needs at least one voice line')
    lines, scene_of_line = flat_lines(scenes)
    if cfg.get("voice_quality") in ("fast", "natural"): os.environ["VOICE_QUALITY"] = cfg["voice_quality"]
    lang = LANG.norm_code(a.lang or cfg.get("language") or LANG.looks_like(" ".join(l["say"] for l in lines)))
    theme = option(a.theme, cfg, "theme", "light", THEMES)
    sub_style = option(a.subtitles, cfg, "subtitles", "kinetic", SUB_STYLES)
    pace = option(a.pace, cfg, "pace", "fast", tuple(PACE))
    music = a.music or cfg.get("music", "upbeat")
    log(f"{name}: {len(scenes)} scenes, {len(lines)} voice lines, language {LANG.name(lang)}, theme {theme}, subtitles {sub_style}")

    build = os.path.join(vdir, "out", "build"); shutil.rmtree(build, ignore_errors=True)
    os.makedirs(os.path.join(build, "audio")); os.makedirs(os.path.join(build, "media"))
    shutil.copytree(os.path.join(REPO, "assets"), os.path.join(build, "assets"))
    shutil.copy(os.path.join(REPO, "hyperframes.json"), build)
    json.dump({"id": name, "name": cfg.get("company", name)}, open(os.path.join(build, "meta.json"), "w"))
    for f in os.listdir(vdir):  # logo + photos + clips stored next to video.json
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")): shutil.copy(os.path.join(vdir, f), os.path.join(build, "media", f))
    media_dir = os.path.join(build, "media")

    used_media = set()

    def media(ref, aspect="tall"):
        """Local file name, an http(s) URL, or a photo search. Returns a file name in media/ or None."""
        ref = str(ref or "").strip()
        if not ref: return None
        if ref.startswith(("http://", "https://")):
            import urllib.request
            ext = os.path.splitext(ref.split("?")[0])[1].lower()
            fn = "dl_" + hashlib.sha1(ref.encode()).hexdigest()[:10] + (ext if ext in (".png", ".jpg", ".jpeg", ".webp", ".svg") else ".png")
            dst = os.path.join(media_dir, fn)
            if os.path.exists(dst): return fn
            try:
                req = urllib.request.Request(ref, headers={"User-Agent": "Mozilla/5.0 video-studio"})
                with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f: f.write(r.read())
                log("downloaded", ref); return fn
            except Exception as e:
                log(f"WARN download failed for '{ref}': {e}"); return None
        if os.path.exists(os.path.join(media_dir, ref)): return ref
        log(f"'{ref}' is not a file next to video.json; searching for a photo of it")
        try:
            found = MEDIA.find_photo(ref, media_dir, used_media, credits, aspect)
            if found: return found
        except Exception as e:
            log(f"photo search failed for '{ref}': {e}")
        log(f"WARN: media '{ref}' not found; continuing without it"); return None

    def video_media(ref, query, dur):
        """A clip for a scene: a file next to video.json, an https URL, or a stock-footage search."""
        ref = str(ref or "").strip()
        if ref:
            src = None
            if ref.startswith(("http://", "https://")):
                import urllib.request
                src = os.path.join(media_dir, "dl_" + hashlib.sha1(ref.encode()).hexdigest()[:10] + "_src")
                try:
                    with urllib.request.urlopen(urllib.request.Request(ref, headers={"User-Agent": "video-studio"}), timeout=90) as r, open(src, "wb") as f:
                        shutil.copyfileobj(r, f)
                except Exception as e:
                    log(f"WARN video download failed for '{ref}': {e}"); src = None
            elif os.path.exists(os.path.join(vdir, ref)):
                src = os.path.join(vdir, ref)
            if src:
                fn = "clip_" + hashlib.sha1(ref.encode()).hexdigest()[:10] + ".mp4"
                try:
                    MEDIA.prepare_video(src, os.path.join(media_dir, fn), dur); return fn
                except Exception as e:
                    log(f"WARN could not prepare video '{ref}': {e}")
        if query:
            try: return MEDIA.find_video(query, media_dir, used_media, credits, dur)
            except Exception as e: log(f"stock video search failed for '{query}': {e}")
        return None

    credits = MEDIA.enrich(cfg, media_dir)   # free real photos + logo
    os.makedirs(os.path.join(vdir, "out"), exist_ok=True)
    cfg["logo"] = media(cfg.get("logo"))
    # every picture the scenes ask for, fetched in parallel: scene photos, tiles, list/step/timeline items, comparison sides
    jobs = []   # (dict to fill, key to set, reference, aspect)
    for s in scenes:
        t = s["type"]
        if t == "presenter": jobs.append((s, "photo_file", s.pop("photo", None) or s.get("image_query"), "tall"))
        elif t == "photo": jobs.append((s, "photo_file", s.get("photo") or s.get("image_query") or s.get("caption"), "tall"))
        elif s.get("photo"): jobs.append((s, "photo", s["photo"], "tall"))
        if s.get("photos"):
            for k, ref in enumerate(list(s["photos"])): jobs.append((s["photos"], k, ref, "wide"))
        for key in ("tiles", "items", "steps", "events"):
            for it in s.get(key) or []:
                if isinstance(it, dict) and (it.get("photo") or it.get("image_query")):
                    jobs.append((it, "photo_file", it.get("photo") or it.get("image_query"), "tall" if t == "gallery" else "wide"))
        for side in ("left", "right", "before", "after"):
            d = s.get(side)
            if t in ("versus", "reveal") and isinstance(d, dict) and (d.get("photo") or d.get("image_query")):
                jobs.append((d, "photo_file", d.get("photo") or d.get("image_query"), "wide"))
    if jobs:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=int(os.environ.get("PHOTO_WORKERS", 6))) as ex:
            found = list(ex.map(lambda j: media(j[2], j[3]), jobs))
        for (target, key, _, _), fn in zip(jobs, found):
            target[key] = fn
        for s in scenes:
            if s.get("photos"): s["photos"] = [p for p in s["photos"] if p]
        log(f"pictures: {sum(1 for f in found if f)} of {len(jobs)} found")
    # 2.5D: full-screen photos get a subject (or near) layer that moves faster than the background
    if cfg.get("depth", True) and not os.environ.get("NO_25D"):
        import depth as DEPTH
        for s in [s for s in scenes if s["type"] == "photo" and s.get("photo_file")][:4]:
            r = DEPTH.layers(os.path.join(media_dir, s["photo_file"]))
            if r: s["layers"] = {"fg": os.path.basename(r["fg"]), "bg": os.path.basename(r["bg"]), "mode": r["mode"]}
    if any(s["type"] == "map" for s in scenes):
        credits.append("- World map: svg-maps/world by VictorCazanave (CC BY 4.0), https://github.com/VictorCazanave/svg-maps")

    # website scroll scenes: capture the real site now; drop the scene if it can't be captured
    keep = []
    for s in scenes:
        if s["type"] == "website":
            shot = capture_website(s.get("url") or (cfg.get("images") or {}).get("logo_domain") or cfg.get("url"), media_dir)
            if not shot: continue
            s.update(shot)
            s["url_label"] = re.sub(r"^(https?://)?(www\.)?", "", s.get("url") or cfg.get("url", "")).rstrip("/")
        keep.append(s)
    if len(keep) != len(scenes):
        scenes[:] = keep; lines, scene_of_line = flat_lines(scenes)

    # 1. voices: narrator ("voice"), named speakers ("voices"), per-line "voice"
    named = cfg.get("voices") or {}
    narrator = a.voice or cfg.get("voice")
    specs = []
    for ln in lines:
        v = ln.get("voice") or narrator
        spec = VO.parse_spec(v, lang, named)
        specs.append(spec)
    out_voice, specs = VO.make_voice(vdir, lines, specs, a.skip_voice)
    log("voices: " + ", ".join(sorted({VO.voice_label(s) for s in specs})))

    # 2. join the lines
    pauses = [ln.get("pause_after") for ln in lines]
    marks, total, vo, sr = assemble([p for p, _ in out_voice], scene_of_line, os.path.join(build, "audio", "vo_raw.wav"), pace, pauses)
    log(f"voiceover {total}s")

    # 3. word timing
    words, srcs = TM.word_times(lines, marks, [w for _, w in out_voice], os.path.join(build, "audio", "vo_raw.wav"), lang)
    log(f"word timing: {', '.join(srcs)} ({len(words)} words)")
    sub_words = TM.subtitle_words(lines, words, lang)

    # 4. scenes
    first_line = [scene_of_line.index(i) for i in range(len(scenes))]
    B = [0.0]
    for i in range(1, len(scenes)):
        prev_end = marks[first_line[i] - 1]["end"]; curr_start = marks[first_line[i]]["start"]
        B.append(round(min(curr_start - 0.08, max(B[-1] + 0.1, (prev_end + curr_start) / 2)), 3))
    B.append(total)

    # footage: b-roll scenes and optional background clips (need the scene lengths, so done after timing)
    for i, s in enumerate(scenes):
        dur = B[i + 1] - B[i]
        if s["type"] == "broll":
            s["video_file"] = video_media(s.get("video"), s.get("video_query"), dur)
            if not s.get("video_file"):
                s["photo_file"] = media(s.get("photo") or s.get("image_query") or s.get("video_query") or s.get("caption"), "tall")
            if not s.get("video_file") and not s.get("photo_file"):   # nothing to show: a big statement instead
                log(f"scene {i + 1}: no footage found; showing the caption as a statement")
                s.update({"type": "hook", "text": s.get("caption", ""), "em": s.get("caption_em", "")})
        elif s.get("video") or s.get("video_query"):
            s["bg_video"] = video_media(s.get("video"), s.get("video_query"), dur)
    open(os.path.join(vdir, "out", "credits.md"), "w", encoding="utf-8").write(
        ("Image credits:\n" + "\n".join(credits) + "\n") if credits else "")

    pal = palette(cfg.get("colors", {}), theme)
    logo_file = cfg.get("logo")
    company = cfg.get("company", name)
    locale = {"hi": "en-IN", "hinglish": "en-IN", "en-in": "en-IN"}.get(lang, lang)

    def logo_html(cls, style=""):
        if logo_file and cfg.get("logo_kind") == "icon":
            inner = f'<span class="lockup fit" data-box="parent"><img class="ico" src="media/{SC.E(logo_file)}" alt="" /><span class="wm">{SC.E(company)}</span></span>'
        elif logo_file:
            inner = f'<img src="media/{SC.E(logo_file)}" alt="{SC.E(company)}" />'
        else:
            inner = f'<span class="wm fit" data-box="parent">{SC.E(company)}</span>'
        return f'<div class="{cls}" style="{style}">{inner}</div>'

    warns, events, body, js_all, under = [], [], [], [], []
    for i, s in enumerate(scenes):
        lidx = [k for k, sc in enumerate(scene_of_line) if sc == i]
        c = SceneContext(i, len(scenes), B[i], B[i + 1], lidx, marks, words, cfg.get("url", ""), logo_html, warns, events, locale)
        c.lang = lang; c.nospace = LANG.no_spaces(lang)
        if i > 0: c.sfx("whoosh", B[i] - 0.12, 0.55)
        ev0 = len(events)
        h, j = SC.BUILDERS[s["type"]](s, c)
        # camera energy: punch in (and shake on big hits) at the scene's key moments, like the original scenes do
        if s["type"] not in OWN_CAMERA and cfg.get("camera", True):
            hits = sorted(((t, 2 if k == "thud" else 1) for k, t, g, _ in events[ev0:] if k in ("thud", "pop", "shimmer") and B[i] + 0.35 < t < B[i + 1] - 0.55),
                          key=lambda x: x[0])
            strong = [h_ for h_ in hits if h_[1] == 2]
            picks = strong[:3] or ([hits[len(hits) // 2], hits[-1]] if len(hits) > 2 else hits[-1:])
            last = -9
            for t, kind in sorted(set(picks)):
                if t - last < 1.0: continue
                amp = 1.075 if kind == 2 else 1.045
                j += (f'\n      tl.to("#s{i} .cam", {{ scale: {amp}, duration: 0.12, ease: "power2.out" }}, {t - 0.02:.3f});'
                      f'\n      tl.to("#s{i} .cam", {{ scale: 1, duration: 0.45, ease: "power3.inOut" }}, {t + 0.1:.3f});\n')
                if kind == 2: j += MO.shake(f"#s{i} .cam", t, 9)
                last = t
        # retention: the first second hits hard (fast zoom-in + impact), and no stretch goes ~2.5 s without a visual change
        if cfg.get("pacing", True):
            if i == 0:
                j += (f'\n      tl.fromTo("#s0 .pace", {{ scale: 1.14 }}, {{ scale: 1, duration: 0.55, ease: "power4.out" }}, 0);\n')
                c.sfx("thud", 0.03, 0.8)
            marks_t = sorted({round(t, 2) for k, t, g, _ in events[ev0:] if B[i] < t < B[i + 1]} | {B[i], B[i + 1]})
            k = 0
            for a_, b_ in zip(marks_t, marks_t[1:]):
                if b_ - a_ < 2.8: continue
                for n_ in range(1, int((b_ - a_) / 2.4) + 1):
                    t = a_ + (b_ - a_) * n_ / (int((b_ - a_) / 2.4) + 1)
                    if t > B[i + 1] - 0.6: continue
                    if k % 2 == 0:   # a quick punch-in that settles back
                        j += (f'\n      tl.to("#s{i} .pace", {{ scale: 1.045, duration: 0.18, ease: "power2.out" }}, {t:.3f});'
                              f'\n      tl.to("#s{i} .pace", {{ scale: 1, duration: 0.7, ease: "power2.inOut" }}, {t + 0.18:.3f});\n')
                    else:            # a small sideways drift
                        dx = 1.6 if (i + k) % 4 < 2 else -1.6
                        j += (f'\n      tl.to("#s{i} .pace", {{ xPercent: {dx}, scale: 1.03, duration: 0.5, ease: "power2.inOut" }}, {t:.3f});'
                              f'\n      tl.to("#s{i} .pace", {{ xPercent: 0, scale: 1, duration: 0.8, ease: "power2.inOut" }}, {t + 0.55:.3f});\n')
                    k += 1
        dur = round(B[i + 1] - B[i], 3)
        vid = s.get("video_file") if s["type"] == "broll" else s.get("bg_video")
        if vid:   # clips sit under the scenes, as their own timeline items
            cls = "bgv full" if s["type"] == "broll" else "bgv dim"
            under.append(f'<video id="v{i}" class="clip {cls}" src="media/{SC.E(vid)}" data-start="{B[i]}" data-duration="{dur}" data-track-index="0" muted playsinline></video>')
            j += f'\n      tl.fromTo("#v{i}", {{ opacity: 0 }}, {{ opacity: {1 if s["type"] == "broll" else 0.22}, duration: 0.4 }}, {B[i]});\n'
            if s["type"] != "broll": h = '<div class="bgshade"></div>' + h
        elif s.get("photo") and s["type"] not in SC.FULL_BLEED:
            h = f'<div class="bgphoto"><img src="media/{SC.E(s["photo"])}" alt="" /></div>' + h
            j += f'\n      tl.fromTo("#s{i} .bgphoto img", {{ scale: 1.18 }}, {{ scale: 1.02, duration: {dur}, ease: "none" }}, {B[i]});\n'
            j += f'      tl.fromTo("#s{i} .bgphoto", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.6 }}, {B[i]});\n'
        body.append(f'<div id="s{i}" class="clip sc-{s["type"]}" data-start="{B[i]}" data-duration="{dur}" data-track-index="1"><div class="inner"><div class="pace"><div class="cam">{h}</div></div></div></div>')
        js_all.append(f"      // scene {i + 1}: {s['type']}\n      " + j)
        if s["type"] in SC.HIDE_BRAND:
            js_all.append(f'      tl.to("#brand", {{ opacity: 0, duration: 0.2 }}, {max(0, B[i] - 0.2):.3f});\n')
            if i < len(scenes) - 1: js_all.append(f'      tl.to("#brand", {{ opacity: 1, duration: 0.3 }}, {B[i + 1] + 0.1:.3f});\n')

    # polish: transitions between scenes, a progress bar, a slowly moving background
    overlay = []
    trans = str(cfg.get("transition", "wipe")).lower()
    if trans in ("wipe", "flash"):
        for i in range(1, len(scenes)):
            b, k = B[i], len(overlay)
            if b < 0.4: continue
            overlay.append(f'<div id="tr{i}" class="clip tr-{trans}{" v" if i % 2 == 0 else ""}" data-start="{round(b - 0.34, 3)}" data-duration="0.66" data-track-index="4"></div>')
            if trans == "wipe":
                ax = "yPercent" if i % 2 == 0 else "xPercent"
                js_all.append(f'      tl.fromTo("#tr{i}", {{ {ax}: -101 }}, {{ {ax}: 0, duration: 0.27, ease: "power3.in" }}, {b - 0.32:.3f});\n'
                              f'      tl.to("#tr{i}", {{ {ax}: 101, duration: 0.32, ease: "power3.out" }}, {b - 0.04:.3f});\n')
            else:
                js_all.append(f'      tl.fromTo("#tr{i}", {{ opacity: 0 }}, {{ opacity: 0.9, duration: 0.16 }}, {b - 0.16:.3f});\n'
                              f'      tl.to("#tr{i}", {{ opacity: 0, duration: 0.3 }}, {b + 0.02:.3f});\n')
    if cfg.get("progress_bar", True):
        overlay.append(f'<div id="prog" class="clip" data-start="0" data-duration="{total}" data-track-index="6"><i></i></div>')
        js_all.append(f'      tl.fromTo("#prog i", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {total}, ease: "none" }}, 0);\n')
    blobs = ""
    if cfg.get("background_motion", True):
        blobs = '<div class="blob b1"></div><div class="blob b2"></div>'
        js_all.append(f'      tl.fromTo(".blob.b1", {{ x: -120, y: -60 }}, {{ x: 160, y: 220, duration: {total}, ease: "sine.inOut" }}, 0);\n'
                      f'      tl.fromTo(".blob.b2", {{ x: 120, y: 80 }}, {{ x: -180, y: -240, duration: {total}, ease: "sine.inOut" }}, 0);\n')

    sub_case = cfg.get("subtitle_case") or ("uppercase" if sub_style in ("kinetic", "bold") and not LANG.no_spaces(lang) else "none")
    subs, subs_js = build_subtitles(sub_words, marks, sub_style, lang, sub_case)

    # stickers: a small icon pops up beside the subtitles when a clear key word is spoken ("money", "phone", "rain")
    sticker_ok = {"hook", "problem", "stats", "number", "intro", "steps", "timeline", "list", "flip", "compare", "question", "quote", "broll", "photo", "end"}
    if cfg.get("stickers", LANG.base(lang) == "en" or lang == "hinglish") and sub_style != "none":
        import visuals as VIS
        last_t, last_icon, n_st, side = -9.0, None, 0, 0
        for w in words:
            sc_i = scene_of_line[w["line"]]
            if scenes[sc_i]["type"] not in sticker_ok or w["t"] - last_t < 3.0 or w["t"] > B[sc_i + 1] - 1.0 or w["t"] < B[sc_i] + 0.3: continue
            ic = VIS.sticker_for(w["text"])
            if not ic or ic == last_icon: continue
            beside = sub_style in ("kinetic", "bold")       # short subtitles leave room at the sides; long ones: sit above
            x = (906 if side == 0 else 30) if beside else (820 if side == 0 else 120); side ^= 1; n_st += 1
            subs.append(f'<div id="stk{n_st}" class="clip stk{" beside" if beside else ""}" data-start="{w["t"] - 0.05:.3f}" data-duration="1.45" data-track-index="5" style="left:{x}px">'
                        f'{VIS.icon_svg(ic, size=70)}</div>')
            subs_js += (f'\n      tl.fromTo("#stk{n_st}", {{ scale: 0, rotation: {-25 if side else 25} }}, {{ scale: 1, rotation: {-8 if side else 8}, duration: 0.35, ease: "back.out(2.4)" }}, {w["t"] - 0.05:.3f});'
                        f'\n      tl.to("#stk{n_st}", {{ y: -14, duration: 0.5, yoyo: true, repeat: 1, ease: "sine.inOut" }}, {w["t"] + 0.3:.3f});'
                        f'\n      tl.to("#stk{n_st}", {{ scale: 0, opacity: 0, duration: 0.2, ease: "power2.in" }}, {w["t"] + 1.2:.3f});')
            events.append(("pop", w["t"], 0.35, (1500,)))
            last_t, last_icon = w["t"], ic
        if n_st: log(f"stickers: {n_st}")
    js_all.append(f"      // subtitles ({sub_style})\n" + subs_js)

    # 5. fonts for the language
    text_all = on_screen_text(scenes, cfg) + " " + " ".join(w["text"] for g in sub_words for w in g)
    font_css, sans_extra, serif_extra = FONTS.build(text_all, os.path.join(build, "assets", "fonts", "extra"), lang)
    complex_script = any(f[0] != "Inter" for f in FONTS.needed(text_all, lang))   # Indic, Arabic, CJK...: no letter-spacing
    sans = ", ".join(x for x in ("'Inter'", sans_extra, "'Noto Sans'", "sans-serif") if x)
    serif = ", ".join(x for x in ("'ISerif'", serif_extra, sans_extra, "'Noto Serif'", "serif") if x)
    sub_top = {"lower": 1360, "bottom": 1560, "middle": 1180}.get(str(cfg.get("subtitle_position", "lower")), 1360)
    root_vars = ";".join(f"--{k}:{v}" for k, v in pal.items()) + f";--font-sans:{sans};--font-serif:{serif};--sub-top:{sub_top}px;--sub-case:{sub_case}"
    if LANG.no_spaces(lang): root_vars += ";--sub-gap:0px"

    MD = [[round(math.cos(math.radians(k * 36 + 12)) * (230 + (k % 3) * 30)), round(math.sin(math.radians(k * 36 + 12)) * (230 + (k % 3) * 30) * 0.72), (k * 17) % 40 - 20] for k in range(10)]
    js = "\n".join(js_all)
    for k, v in sorted(pal.items(), key=lambda kv: -len(kv[0])):  # GSAP needs literal colours
        js = js.replace(f"var(--{k})", v)
    head_css = (open(os.path.join(REPO, "assets", "fonts", "fonts.css"), encoding="utf-8").read().replace("url('", "url('assets/fonts/")
                + font_css + ":root{" + root_vars + "}")
    html_lang = {"hinglish": "hi-Latn"}.get(lang, lang)
    direction = "rtl" if LANG.is_rtl(lang) else "ltr"
    extra_css = MO.CSS + """
.bgv { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; z-index: 0; }
.bgv.dim { opacity: 0.22; filter: saturate(0.8); }
.bgshade { position: absolute; inset: 0; background: linear-gradient(180deg, var(--bg) 0%, transparent 28%, transparent 62%, var(--bg) 100%); opacity: 0.85; }
.sc-broll .full { background: transparent !important; }
.sub .burst { column-gap: var(--sub-gap, 14px); }
.stk { position: absolute; top: calc(var(--sub-top, 1360px) - 150px); width: 136px; height: 136px; border-radius: 50%; z-index: 51;
  display: flex; align-items: center; justify-content: center; background: var(--highlight); color: #111; box-shadow: 0 14px 34px rgba(0,0,0,0.35), 0 0 0 6px rgba(255,255,255,0.9); }
.stk.beside { top: calc(var(--sub-top, 1360px) - 18px); width: 124px; height: 124px; }
.blob { position: absolute; width: 900px; height: 900px; border-radius: 50%; pointer-events: none; }
.blob.b1 { left: -200px; top: 200px; background: radial-gradient(circle, var(--accent-35), transparent 65%); }
.blob.b2 { right: -260px; top: 1000px; background: radial-gradient(circle, var(--primary-12), transparent 65%); }
.tr-wipe { position: absolute; inset: 0; z-index: 45; background: linear-gradient(100deg, var(--primary) 0 72%, var(--accent) 72% 100%); }
.tr-wipe.v { background: linear-gradient(190deg, var(--primary) 0 72%, var(--accent) 72% 100%); }
.tr-flash { position: absolute; inset: 0; z-index: 45; background: #fff; opacity: 0; }
#prog { position: absolute; left: 0; right: 0; top: 0; height: 9px; background: var(--ink-10); z-index: 60; }
#prog i { position: absolute; inset: 0; background: var(--primary); transform-origin: left center; display: block; }
.script-complex .k, .script-complex .sub .w, .script-complex .sc-compare .hd div { letter-spacing: 0 !important; }
.script-complex .sf { line-height: 1.25; }
"""
    html = f'''<!doctype html>
<html lang="{html_lang}" dir="{direction}" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
    <title>{SC.E(company)}</title>
    <script src="assets/vendor/gsap.min.js"></script>
    <style>{open(os.path.join(REPO, "assets", "fonts", "fonts.css"), encoding="utf-8").read().replace("url('", "url('assets/fonts/")}</style>
    <style>{font_css}</style>
    <style>:root{{{root_vars}}}\n{open(os.path.join(ENGINE, "style.css"), encoding="utf-8").read()}{extra_css}</style>
  </head>
  <body>
    <div id="root" class="theme-{theme} subs-{sub_style}{' script-complex' if complex_script else ''}" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
      <div class="dots"></div>{blobs}
      <audio id="mix" src="audio/final.wav" data-start="0" data-duration="{total}" data-track-index="10" data-volume="1"></audio>
{chr(10).join("      " + u for u in under)}
      <div id="brand" class="clip" data-start="0" data-duration="{total}" data-track-index="2" style="inset:auto;top:100px;left:0;right:0;height:60px">{logo_html("brandin").replace('class="brandin" style=""', 'style="display:contents"')}</div>
{chr(10).join("      " + b for b in body)}
{chr(10).join("      " + o for o in overlay)}
{chr(10).join("      " + s for s in subs)}
    </div>
    <script>
      const MD = {json.dumps(MD)};
      function prepPath(sel) {{ document.querySelectorAll(sel).forEach(p => {{ const L = p.getTotalLength(); p.style.strokeDasharray = L; p.style.strokeDashoffset = L; }}); }}
{MO.JS}
      function drawPath(tl, sel, at, dur) {{ document.querySelectorAll(sel).forEach(p => {{ const L = p.getTotalLength(); p.style.strokeDasharray = L; tl.fromTo(p, {{ strokeDashoffset: L }}, {{ strokeDashoffset: 0, duration: dur, ease: "power2.inOut" }}, at); }}); }}
      // Shrink text that would overflow its box. Measures an un-animated clone so GSAP's
      // start positions (which change scroll sizes) never affect the result.
      function fitAll() {{
        document.querySelectorAll(".fit").forEach(el => {{
          const target = el.dataset.box === "parent" ? el.parentElement : el;
          const W = target.offsetWidth, H = target.offsetHeight;
          if (!W || !H) return;
          const clone = target.cloneNode(true);
          [clone, ...clone.querySelectorAll("*")].forEach(n => {{ n.style.transform = "none"; n.style.opacity = "1"; }});
          Object.assign(clone.style, {{ visibility: "hidden", position: "absolute", left: "0px", top: "0px", width: W + "px", height: H + "px", margin: "0" }});
          target.parentElement.appendChild(clone);
          const txt = target === el ? clone : clone.querySelector(".fit");
          let fs = parseFloat(getComputedStyle(el).fontSize), n = 0;
          const over = () => clone.scrollHeight - clone.clientHeight > fs * 0.3 || clone.scrollWidth - clone.clientWidth > 4;
          while (over() && fs > 16 && n < 80) {{ fs -= 2; txt.style.fontSize = fs + "px"; n++; }}
          if (n) el.style.fontSize = fs + "px";
          clone.remove();
        }});
      }}
      fitAll(); if (document.fonts) document.fonts.ready.then(fitAll);
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      const pop = "back.out(1.4)", snap = "power4.out";
      tl.fromTo("#brand", {{ y: -50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, ease: snap }}, 0.05);
{js}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
'''
    open(os.path.join(build, "index.html"), "w", encoding="utf-8").write(html)
    for w in warns: log("WARN", w)
    log("built index.html")
    srt = os.path.join(vdir, "out", f"{name}.srt")
    open(srt, "w", encoding="utf-8").write(srt_text(sub_words, lang))

    # 6. sound design + music: a polished voice on top, real music well underneath (cut to the beat), effects
    mv = os.environ.get("MUSIC_VOLUME", "").strip().lower()   # the workflow's "background music" choice
    if mv in ("off", "none"): music = "none"
    elif mv: cfg["music_volume"] = {"soft": "low", "loud": "high"}.get(mv, mv)
    level = AU.music_level(cfg.get("music_volume"))
    if str(music).lower() in ("none", "off", "no"): level = None
    mood = music if music in FX.MOODS and music != "none" else cfg.get("music_mood", "upbeat")
    vo_mix = AU.polish_voice(vo, sr, room=cfg.get("room_tone", True)) if cfg.get("voice_polish", True) else vo
    fx = FX.render_fx(len(vo_mix), sr, events) * 0.22 * float(cfg.get("sfx_volume", 1.0))
    bed, minfo = None, {}
    if level is not None:
        path, minfo = AU.find_music(vdir, {**cfg, "music": music}, mood, total + 3, build)
        if path:
            try:
                start, bpm, hits = AU.align_start(AU.decode(path, sr), sr, B[1:-1], total)
                bed = AU.prepare_track(path, sr, len(vo_mix), start)
                minfo.update({"start": round(start, 2), "bpm": round(bpm), "cuts_on_beat": f"{hits}/{len(B) - 2}"})
                log(f"music: {minfo.get('title') or minfo.get('file')} ({minfo.get('source')}), {bpm:.0f} BPM, "
                    f"{hits}/{len(B) - 2} scene cuts on the beat, level {cfg.get('music_volume') or 'low'}")
            except Exception as e:
                log(f"WARN could not use the music track ({str(e)[:120]}); using the built-in bed"); bed, minfo = None, {}
        if bed is None:
            bed = np.pad(FX.music_bed(sr, len(vo_mix) / sr, mood), (0, len(vo_mix)))[:len(vo_mix)].astype("float32")
            minfo = {"source": "built-in", "mood": mood}
    mixed = AU.mix(vo_mix, fx, bed, sr, level)
    sf.write(os.path.join(build, "audio", "mix_raw.wav"), mixed, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "audio/mix_raw.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "audio/final.wav"], cwd=build, check=True)
    log(f"mixed {len(events)} sound effects, music: {minfo.get('source', 'off')}")
    if minfo.get("credit"):   # CC BY music must be credited: added to credits.md (also printed in the Release notes)
        cp = os.path.join(vdir, "out", "credits.md")
        prev = open(cp, encoding="utf-8").read() if os.path.exists(cp) else ""
        open(cp, "w", encoding="utf-8").write(prev + ("\n" if prev else "") + minfo["credit"] + "\n")
    json.dump({"duration": total, "language": lang, "voices": sorted({VO.voice_label(s) for s in specs}), "timing": srcs,
               "scenes": [s["type"] for s in scenes], "music": minfo, "warnings": warns}, open(os.path.join(vdir, "out", "info.json"), "w"), indent=2)
    covers = []
    if cfg.get("covers", True) and not os.environ.get("NO_COVERS"):
        covers = make_covers(build, os.path.join(vdir, "out"), name, cfg, scenes, head_css, logo_html)
    if a.no_render: return

    # 7. render
    if subprocess.run([NPX, "hyperframes", "check"], cwd=build).returncode != 0:
        log("WARN quality check reported issues (see above); rendering anyway")
        gs = os.environ.get("GITHUB_STEP_SUMMARY")
        if gs: open(gs, "a").write("\n> ⚠️ The layout/contrast check reported issues; the video was rendered anyway. Watch it before sharing.\n")
    out = os.path.join(vdir, "out", f"{name}.mp4")
    subprocess.run([NPX, "hyperframes", "render", "-o", out, "--fps", str(a.fps)], cwd=build, check=True)
    if f"{name}.jpg" not in covers:   # no designed cover: use a frame of the first scene
        thumb_t = max(0.5, min(B[1] - 0.35 if len(B) > 2 else total / 2, total - 0.5))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{thumb_t:.2f}", "-i", out, "-frames:v", "1", "-q:v", "3",
                        os.path.join(vdir, "out", f"{name}.jpg")], check=False)
    fm = cfg.get("formats") or [x.strip() for x in str(a.formats or "").split(",") if x.strip()]
    if isinstance(fm, str): fm = [x.strip() for x in fm.split(",") if x.strip()]
    if fm: other_formats(out, fm)
    log("done ->", os.path.relpath(out, REPO))


if __name__ == "__main__":
    main()
