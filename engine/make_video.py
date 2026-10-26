"""Video Studio engine: video.json -> vertical explainer MP4.

  python engine/make_video.py videos/docsdocs            # full run
  python engine/make_video.py videos/docsdocs --no-render  # build index.html only (fast check)

Pipeline: Chatterbox voice (cached in <video>/.voice/) -> join lines -> Whisper word timestamps
-> scenes synced to words -> synthesised sound design -> HyperFrames render (headless Chrome).
Output: <video>/out/<name>.mp4
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys
import numpy as np, soundfile as sf

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
sys.path.insert(0, ENGINE)
import scenes as SC  # noqa: E402
import sfx as FX     # noqa: E402
import media as MEDIA  # noqa: E402

norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
LEAD, TAIL, GAP_IN, GAP_SCENE, GAP_FIRST = 0.35, 2.2, 0.32, 0.7, 1.0


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
    """Darken colour `c` step by step (keeping its hue) until it reaches `need` contrast on `bg`."""
    t = 0.0
    while contrast(mix(c, toward, t), bg) < need and t < 0.95: t += 0.05
    return mix(c, toward, t)


def palette(col):
    p = {"primary": col.get("primary", "#024c87"), "accent": col.get("accent", "#85bbe0"), "alert": col.get("alert", "#d64545"),
         "ink": col.get("ink", "#0d2440"), "bg": col.get("background", "#f3f6fb")}
    # keep any brand palette readable: light background, dark text, colours darkened only as much as needed
    if lum(p["bg"]) < 0.80: p["bg"] = mix(p["bg"], "#ffffff", 0.85)
    p["ink"] = readable(p["ink"], p["bg"], 10)
    p["primary"] = readable(p["primary"], p["bg"], 4.6)
    p["alert"] = readable(p["alert"], p["bg"], 4.0)
    accent_dark = readable(mix(p["accent"], p["primary"], 0.45), p["bg"], 3.2)
    t = 0.35
    while contrast(mix(p["ink"], "#ffffff", t), "#ffffff") < 4.6 and t > 0: t -= 0.05
    p.update({"dim": mix(p["ink"], "#ffffff", t), "pale": mix(p["primary"], "#ffffff", 0.88), "accent-dark": accent_dark,
              "mix1": mix(p["primary"], p["accent"], 0.33), "mix2": mix(p["primary"], p["accent"], 0.66),
              "accent-35": rgba(p["accent"], 0.35), "accent-60": rgba(p["accent"], 0.6), "primary-08": rgba(p["primary"], 0.08),
              "primary-12": rgba(p["primary"], 0.12), "ink-10": rgba(p["ink"], 0.10), "ink-12": rgba(p["ink"], 0.12),
              "ink-16": rgba(p["ink"], 0.16), "ink-18": rgba(p["ink"], 0.18), "ink-86": rgba(p["ink"], 0.86),
              "alert-15": mix(p["alert"], "#ffffff", 0.85), "alert-45": rgba(p["alert"], 0.45)})
    return p


# ---------------------------------------------------------------- voice
def line_key(ln, v):
    return hashlib.sha1(f'{ln["say"]}|{ln.get("seed", 42)}|{v.get("exaggeration", 0.6)}|{v.get("cfg_weight", 0.45)}'.encode()).hexdigest()[:16]


def make_voice(vdir, lines, vcfg, skip_voice):
    cache = os.path.join(vdir, ".voice"); os.makedirs(cache, exist_ok=True)
    paths, todo = [], []
    for ln in lines:
        p = os.path.join(cache, line_key(ln, vcfg) + ".wav"); paths.append(p)
        if not os.path.exists(p): todo.append((ln, p))
    if todo and skip_voice:
        sys.exit(f"{len(todo)} voice line(s) missing from {cache} and --skip-voice was given")
    if todo:
        import torch
        from chatterbox.tts import ChatterboxTTS
        dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        log(f"generating {len(todo)} voice line(s) on {dev} (cached lines reused: {len(lines) - len(todo)})")
        model = ChatterboxTTS.from_pretrained(device=dev)
        for k, (ln, p) in enumerate(todo, 1):
            torch.manual_seed(int(ln.get("seed", 42)))
            wav = model.generate(ln["say"], exaggeration=vcfg.get("exaggeration", 0.6), cfg_weight=vcfg.get("cfg_weight", 0.45))
            sf.write(p, wav.squeeze(0).cpu().numpy(), model.sr)
            log(f"  voice {k}/{len(todo)}: {ln['say'][:60]}")
        del model
        import gc; gc.collect()
    # drop cache files no longer used by any line
    keep = {os.path.basename(p) for p in paths}
    for f in os.listdir(cache):
        if f.endswith(".wav") and f not in keep: os.remove(os.path.join(cache, f))
    return paths


def trim(x, sr, db=-40, pad=0.04):
    env = np.abs(x); thr = 10 ** (db / 20) * max(env.max(), 1e-9)
    idx = np.where(env > thr)[0]
    if len(idx) == 0: return x
    return x[max(0, idx[0] - int(pad * sr)): min(len(x), idx[-1] + int(pad * sr))]


def assemble(paths, scene_of_line, out_wav):
    clips, sr = [], None
    for p in paths:
        x, s = sf.read(p, dtype="float32")
        if x.ndim > 1: x = x.mean(axis=1)
        sr = sr or s; clips.append(trim(x, sr))
    gaps = []
    for k in range(len(clips) - 1):
        change = scene_of_line[k + 1] != scene_of_line[k]
        gaps.append(GAP_FIRST if change and scene_of_line[k] == 0 else GAP_SCENE if change else GAP_IN)
    total = LEAD + sum(len(c) / sr for c in clips) + sum(gaps) + TAIL
    out = np.zeros(int(total * sr) + 1, dtype="float32"); marks, t = [], LEAD
    for k, c in enumerate(clips):
        st = int(t * sr); out[st:st + len(c)] = c
        marks.append({"start": round(t, 3), "end": round(t + len(c) / sr, 3)})
        t += len(c) / sr + (gaps[k] if k < len(gaps) else 0)
    sf.write(out_wav, out, sr)
    return marks, round(total, 2), out, sr


# ---------------------------------------------------------------- cues
class SceneContext:
    def __init__(self, i, n, sb, se, lines_idx, marks, words, url, logo_html, warns, events):
        self.i, self.first, self.last, self.sb, self.se = i, i == 0, i == n - 1, sb, se
        self.lines_idx, self.marks, self.words, self.url = lines_idx, marks, words, url
        self._logo, self.warns, self.events = logo_html, warns, events

    def line_end_last(self): return self.marks[self.lines_idx[-1]]["end"]

    def cue(self, word, after, frac=0.5):
        """When `word` is spoken in this scene, searching from time `after`."""
        lo_line, hi_line = self.lines_idx[0], self.lines_idx[-1]
        for w in self.words:
            if w["line"] < lo_line or w["line"] > hi_line: continue
            if w["t"] >= after - 0.05 and norm(word) and norm(word) in norm(w["text"]):
                return round(w["t"], 3)
        st, en = self.marks[lo_line]["start"], self.marks[hi_line]["end"]
        t = round(max(after + 0.4, st + (en - st) * frac), 3)
        self.warns.append(f'scene {self.i + 1}: did not hear "{word}", using {t:.2f}s (check the cue word or the pronunciation)')
        return t

    def sfx(self, kind, t, gain, *args): self.events.append((kind, t, gain, args))

    def logo(self, cls, style=""): return self._logo(cls, style)


def word_lines(words, marks, lines):
    """Assign each Whisper word to its voice line by aligning Whisper's text to the script text
    character by character (robust to timing drift and small mishearings), then clamp its time
    into that line."""
    import bisect, difflib
    script, bounds = "", []
    for ln in lines:
        script += norm(ln["say"]); bounds.append(len(script))
    hyp, starts = "", []
    for w in words:
        starts.append(len(hyp)); hyp += norm(w["text"])
    hmap = [None] * len(hyp)
    for blk in difflib.SequenceMatcher(None, hyp, script, autojunk=False).get_matching_blocks():
        for k in range(blk.size): hmap[blk.a + k] = blk.b + k
    out, prev = [], 0
    for i, w in enumerate(words):
        a, b = starts[i], starts[i + 1] if i + 1 < len(words) else len(hyp)
        pos = next((hmap[k] for k in range(a, b) if hmap[k] is not None), None)
        li = prev if pos is None else min(bisect.bisect_right(bounds, pos), len(lines) - 1)
        li = max(li, prev); prev = li
        m = marks[li]
        out.append({"text": w["text"], "t": min(max(w["start"], m["start"]), m["end"]), "line": li})
    return out


def transcribe_groq(wav_path, key):
    """Word timestamps from Groq's hosted Whisper (about 2 seconds)."""
    import urllib.request, uuid
    mp3 = wav_path[:-4] + "_16k.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-ac", "1", "-ar", "16000", "-b:a", "48k", mp3], check=True)
    bnd = uuid.uuid4().hex
    fields = {"model": os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"), "response_format": "verbose_json",
              "timestamp_granularities[]": "word", "language": "en", "temperature": "0"}
    body = b"".join(f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    body += f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="vo.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode()
    body += open(mp3, "rb").read() + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={bnd}", "User-Agent": "video-studio"})
    import time, urllib.error
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
            return [{"text": w["word"], "start": float(w["start"]), "end": float(w["end"])} for w in d.get("words", [])]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4: time.sleep(8 * (attempt + 1)); continue
            raise


def transcribe(build_dir, wav_rel):
    key = os.environ.get("GROQ_API_KEY")
    if key:
        try:
            W = transcribe_groq(os.path.join(build_dir, wav_rel), key)
            if W: log(f"word timing: Groq Whisper ({len(W)} words)"); return W
        except Exception as e:
            log(f"Groq Whisper failed ({e}); falling back to local Whisper")
    for p in ("transcript.json", os.path.join("audio", "transcript.json")):
        if os.path.exists(os.path.join(build_dir, p)): os.remove(os.path.join(build_dir, p))
    subprocess.run(["npx", "hyperframes", "transcribe", wav_rel], cwd=build_dir, check=True, stdout=subprocess.DEVNULL)
    for p in ("transcript.json", os.path.join("audio", "transcript.json")):
        f = os.path.join(build_dir, p)
        if os.path.exists(f):
            W = json.load(open(f, encoding="utf-8"))
            log("word timing: local Whisper")
            return W.get("words", W) if isinstance(W, dict) else W
    sys.exit("transcription produced no transcript.json")


# ---------------------------------------------------------------- subtitles
def split_sub(text, st, en):
    out, cur = [], []
    for w in text.split():
        cur.append(w)
        if len(" ".join(cur)) > 58 and (w.endswith((",", ".", "?", ":", "…", "!")) or len(" ".join(cur)) > 76):
            out.append(" ".join(cur)); cur = []
    if cur: out.append(" ".join(cur))
    tot = sum(len(c) for c in out) or 1; r, t = [], st
    for c in out:
        d = (en - st) * len(c) / tot; r.append((round(t, 3), round(d, 3), c)); t += d
    return r


# ---------------------------------------------------------------- main
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
        r = subprocess.run(["node", os.path.join(ENGINE, "capture_site.cjs"), url, png], capture_output=True, text=True, timeout=120, cwd=REPO)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_dir", help="folder containing video.json, e.g. videos/docsdocs")
    ap.add_argument("--skip-voice", action="store_true", help="fail instead of generating missing voice lines")
    ap.add_argument("--no-render", action="store_true", help="stop after building index.html")
    a = ap.parse_args()

    vdir = os.path.abspath(a.video_dir)
    cfg = json.load(open(os.path.join(vdir, "video.json"), encoding="utf-8"))
    cfg["url"] = re.sub(r"^(https?://)?(www\.)?", "", str(cfg.get("url", ""))).rstrip("/")   # show "amazon.com"
    name = os.path.basename(vdir.rstrip("/"))
    scenes = cfg["scenes"]
    for s in scenes:
        if s.get("type") not in SC.BUILDERS: sys.exit(f'unknown scene type "{s.get("type")}". Use one of: {", ".join(SC.BUILDERS)}')
        if not s.get("lines"): sys.exit(f'scene "{s["type"]}" needs at least one voice line')
    lines, scene_of_line = [], []
    for i, s in enumerate(scenes):
        for ln in s["lines"]:
            lines.append(ln); scene_of_line.append(i)
    log(f"{name}: {len(scenes)} scenes, {len(lines)} voice lines")

    build = os.path.join(vdir, "out", "build"); shutil.rmtree(build, ignore_errors=True)
    os.makedirs(os.path.join(build, "audio")); os.makedirs(os.path.join(build, "media"))
    shutil.copytree(os.path.join(REPO, "assets"), os.path.join(build, "assets"))
    for f in ("hyperframes.json",):
        shutil.copy(os.path.join(REPO, f), build)
    json.dump({"id": name, "name": cfg.get("company", name)}, open(os.path.join(build, "meta.json"), "w"))
    for f in os.listdir(vdir):  # logo + photos stored next to video.json
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")): shutil.copy(os.path.join(vdir, f), os.path.join(build, "media", f))

    used_media = set()

    def media(ref, aspect="tall"):
        """Local file name, download an http(s) URL, or search online for a photo query. Returns file name or None."""
        if not ref:
            return None
        ref = str(ref).strip()
        if not ref:
            return None
        if ref.startswith(("http://", "https://")):
            import urllib.request
            ext = os.path.splitext(ref.split("?")[0])[1].lower()
            fn = "dl_" + hashlib.sha1(ref.encode()).hexdigest()[:10] + (ext if ext in (".png", ".jpg", ".jpeg", ".webp", ".svg") else ".png")
            dst = os.path.join(build, "media", fn)
            if os.path.exists(dst):
                return fn
            try:
                req = urllib.request.Request(ref, headers={"User-Agent": "Mozilla/5.0 video-studio"})
                with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
                    f.write(r.read())
                log("downloaded", ref)
                return fn
            except Exception as e:
                log(f"WARN download failed for '{ref}': {e}")
                return None

        if os.path.exists(os.path.join(build, "media", ref)):
            return ref

        log(f"'{ref}' not found next to video.json; attempting online photo search...")
        try:
            found = MEDIA.find_photo(ref, os.path.join(build, "media"), used_media, credits, aspect)
            if found:
                return found
        except Exception as e:
            log(f"photo fallback search failed for '{ref}': {e}")

        log(f"WARN: media '{ref}' not found; proceeding without it")
        return None

    credits = MEDIA.enrich(cfg, os.path.join(build, "media"))   # free real photos + logo (no keys)
    os.makedirs(os.path.join(vdir, "out"), exist_ok=True)
    cfg["logo"] = media(cfg.get("logo"))
    for s in scenes:
        if s.get("photos"):
            s["photos"] = [p for p in (media(p, "wide") for p in s["photos"]) if p]
        if s.get("photo"):
            s["photo"] = media(s["photo"], "tall")
    open(os.path.join(vdir, "out", "credits.md"), "w", encoding="utf-8").write(
        ("Image credits:\n" + "\n".join(credits) + "\n") if credits else "")

    # website scroll scenes: capture the real site now; drop the scene if it can't be captured
    keep = []
    for s in scenes:
        if s["type"] == "website":
            shot = capture_website(s.get("url") or (cfg.get("images") or {}).get("logo_domain") or cfg.get("url"), os.path.join(build, "media"))
            if not shot: continue
            s.update(shot)
            s["url_label"] = re.sub(r"^(https?://)?(www\.)?", "", s.get("url") or cfg.get("url", "")).rstrip("/")
        keep.append(s)
    if len(keep) != len(scenes):
        scenes[:] = keep
        lines, scene_of_line = [], []
        for i, s in enumerate(scenes):
            for ln in s["lines"]:
                lines.append(ln); scene_of_line.append(i)

    # 1-2. voice + assembly
    paths = make_voice(vdir, lines, cfg.get("voice", {}), a.skip_voice)
    marks, total, vo, sr = assemble(paths, scene_of_line, os.path.join(build, "audio", "vo_raw.wav"))
    log(f"voiceover {total}s")

    # 3. word timestamps
    words = word_lines(transcribe(build, "audio/vo_raw.wav"), marks, lines)

    # 4. scenes
    first_line = [scene_of_line.index(i) for i in range(len(scenes))]
    B = [0.0] + [round(marks[first_line[i]]["start"] - 0.25, 3) for i in range(1, len(scenes))] + [total]
    pal = palette(cfg.get("colors", {}))
    logo_file = cfg.get("logo")
    company = cfg.get("company", name)

    def logo_html(cls, style=""):
        if logo_file and cfg.get("logo_kind") == "icon":
            inner = f'<span class="lockup fit" data-box="parent"><img class="ico" src="media/{SC.E(logo_file)}" alt="" /><span class="wm">{SC.E(company)}</span></span>'
        elif logo_file:
            inner = f'<img src="media/{SC.E(logo_file)}" alt="{SC.E(company)}" />'
        else:
            inner = f'<span class="wm fit" data-box="parent">{SC.E(company)}</span>'
        return f'<div class="{cls}" style="{style}">{inner}</div>'

    warns, events, body, js_all = [], [], [], []
    for i, s in enumerate(scenes):
        lidx = [k for k, sc in enumerate(scene_of_line) if sc == i]
        c = SceneContext(i, len(scenes), B[i], B[i + 1], lidx, marks, words, cfg.get("url", ""), logo_html, warns, events)
        if i > 0: c.sfx("whoosh", B[i] - 0.1, 0.55)
        h, j = SC.BUILDERS[s["type"]](s, c)
        if s.get("photo"):
            h = f'<div class="bgphoto"><img src="media/{SC.E(s["photo"])}" alt="" /></div>' + h
            j += f'\n      tl.fromTo("#s{i} .bgphoto img", {{ scale: 1.18 }}, {{ scale: 1.02, duration: {round(B[i + 1] - B[i], 3)}, ease: "none" }}, {B[i]});\n'
            j += f'      tl.fromTo("#s{i} .bgphoto", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.6 }}, {B[i]});\n'
        body.append(f'<div id="s{i}" class="clip sc-{s["type"]}" data-start="{B[i]}" data-duration="{round(B[i + 1] - B[i], 3)}" data-track-index="1"><div class="inner">{h}</div></div>')
        js_all.append(f"      // scene {i + 1}: {s['type']}\n      " + j)
        if s["type"] in SC.HIDE_BRAND:
            js_all.append(f'      tl.to("#brand", {{ opacity: 0, duration: 0.2 }}, {max(0, B[i] - 0.2):.3f});\n')
            if i < len(scenes) - 1: js_all.append(f'      tl.to("#brand", {{ opacity: 1, duration: 0.3 }}, {B[i + 1] + 0.1:.3f});\n')

    subs, n = [], 0
    for k, ln in enumerate(lines):
        st = marks[k]["start"]; en = marks[k + 1]["start"] - 0.05 if k + 1 < len(lines) else marks[k]["end"] + 0.4
        for s0, d, txt in split_sub(ln.get("sub") or ln["say"], st, en):
            n += 1; subs.append(f'<div id="sub{n}" class="sub clip" data-start="{s0}" data-duration="{d}" data-track-index="3"><span>{SC.E(txt)}</span></div>')

    MD = [[round(math.cos(math.radians(k * 36 + 12)) * (230 + (k % 3) * 30)), round(math.sin(math.radians(k * 36 + 12)) * (230 + (k % 3) * 30) * 0.72), (k * 17) % 40 - 20] for k in range(10)]
    root_vars = ";".join(f"--{k}:{v}" for k, v in pal.items())
    js = "\n".join(js_all)
    for k, v in sorted(pal.items(), key=lambda kv: -len(kv[0])):  # GSAP needs literal colours
        js = js.replace(f"var(--{k})", v)
    html = f'''<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
    <title>{SC.E(company)}</title>
    <script src="assets/vendor/gsap.min.js"></script>
    <style>{open(os.path.join(REPO, "assets", "fonts", "fonts.css"), encoding="utf-8").read().replace("url('", "url('assets/fonts/")}</style>
    <style>:root{{{root_vars}}}\n{open(os.path.join(ENGINE, "style.css"), encoding="utf-8").read()}</style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
      <div class="dots"></div>
      <audio id="mix" src="audio/final.wav" data-start="0" data-duration="{total}" data-track-index="10" data-volume="1"></audio>
      <div id="brand" class="clip" data-start="0" data-duration="{total}" data-track-index="2" style="inset:auto;top:100px;left:0;right:0;height:60px">{logo_html("brandin").replace('class="brandin" style=""', 'style="display:contents"')}</div>
      {chr(10).join("      " + b for b in body)}
      {chr(10).join("      " + s for s in subs)}
    </div>
    <script>
      const MD = {json.dumps(MD)};
      function prepPath(sel) {{ document.querySelectorAll(sel).forEach(p => {{ const L = p.getTotalLength(); p.style.strokeDasharray = L; p.style.strokeDashoffset = L; }}); }}
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
      const pop = "back.out(1.8)", snap = "expo.out";
      tl.fromTo("#brand", {{ y: -50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: snap }}, 0.05);
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

    # 5. sound design
    mixed = FX.render_mix(vo, sr, events, total)
    sf.write(os.path.join(build, "audio", "mix_raw.wav"), mixed, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "audio/mix_raw.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "audio/final.wav"], cwd=build, check=True)
    log(f"mixed {len(events)} sound effects")
    if a.no_render: return

    # 6. render
    if subprocess.run(["npx", "hyperframes", "check"], cwd=build).returncode != 0:
        log("WARN quality check reported issues (see above); rendering anyway")
        gs = os.environ.get("GITHUB_STEP_SUMMARY")
        if gs: open(gs, "a").write("\n> ⚠️ The layout/contrast check reported issues; the video was rendered anyway. Watch it before sharing.\n")
    out = os.path.join(vdir, "out", f"{name}.mp4")
    subprocess.run(["npx", "hyperframes", "render", "-o", out, "--fps", os.environ.get("RENDER_FPS", "24")], cwd=build, check=True)
    log("done ->", os.path.relpath(out, REPO))


if __name__ == "__main__":
    main()
