"""Word timing: when each word of the script is spoken. Works in every language and writing system.

Sources, best first:
  1. the voice engine's own word timings (Microsoft Edge voices)
  2. Groq Whisper (uses the GROQ_API_KEY that writes the scripts)
  3. local Whisper (faster-whisper, free, offline; installed by the workflow)
  4. an estimate from the length of each word (always works)

The recognised words are only used as a clock: the script's own words are aligned onto them character by
character, so subtitles always show the script's spelling, and numbers, names and other scripts never break.
"""
import difflib, json, os, re, subprocess, sys, time, unicodedata

ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE)
import languages as L  # noqa: E402


def log(*a): print("[timing]", *a, flush=True)


def norm(s):
    """Letters, digits and combining marks only, lower-cased, any script ("में" stays "में", "Docs," -> "docs")."""
    s = unicodedata.normalize("NFKC", str(s)).casefold()
    return "".join(ch for ch in s if unicodedata.category(ch)[0] in "LNM")


def strip_punct(w):
    """Remove leading/trailing punctuation and symbols but keep letters and their combining marks."""
    w = str(w)
    is_p = lambda ch: unicodedata.category(ch)[0] in "PSZ"
    a, b = 0, len(w)
    while a < b and is_p(w[a]): a += 1
    while b > a and is_p(w[b - 1]): b -= 1
    return w[a:b]


PUNCT_END = (".", "!", "?", ",", ":", ";", "…", "।", "॥", "。", "！", "？", "，", "、", "؟", "،", "؛")


def tokens(text, lang):
    """Script words of a line. Languages without spaces are cut into short chunks at punctuation."""
    text = str(text or "").strip()
    if not L.no_spaces(lang) or len(text.split()) >= max(3, len(text) // 12):
        return text.split()
    out = []
    for part in re.split(r"(?<=[。！？，、,.!?：；…])", text):
        part = part.strip()
        if not part: continue
        if " " in part: out.extend(part.split()); continue
        n = 4 if L.base(lang) in ("zh", "ja", "yue") else 6
        while len(part) > n + 2:
            out.append(part[:n]); part = part[n:]
        out.append(part)
    return out


# ------------------------------------------------------------------ aligning script words to a clock
def align(toks, rec, t0, t1):
    """Give every script token a start/end time within [t0, t1].
    `rec` = recognised words [{text, start, end}] (absolute seconds), possibly empty or partly wrong."""
    n = len(toks)
    if not n: return []
    keys = [norm(t) for t in toks]
    weight = [max(1, len(k)) + (2.5 if str(t).endswith(PUNCT_END) else 0) for t, k in zip(toks, keys)]
    starts, ends = [None] * n, [None] * n
    rec = [w for w in (rec or []) if norm(w.get("text", ""))]
    if rec:
        script, owner = "", []
        for i, k in enumerate(keys):
            script += k; owner += [i] * len(k)
        heard, ctime = "", []
        for w in rec:
            k = norm(w["text"]); st, en = float(w["start"]), float(w["end"])
            heard += k
            ctime += [(st + (en - st) * j / len(k), st + (en - st) * (j + 1) / len(k)) for j in range(len(k))]
        sm = difflib.SequenceMatcher(None, script, heard, autojunk=False)
        hit = {}
        for blk in sm.get_matching_blocks():
            for j in range(blk.size): hit.setdefault(owner[blk.a + j], []).append(ctime[blk.b + j])
        matched_chars = sum(b.size for b in sm.get_matching_blocks())
        if matched_chars >= 0.25 * max(1, len(script)):
            for i, h in hit.items():
                if len(h) >= max(1, len(keys[i]) * 0.34) or len(keys[i]) <= 2:
                    starts[i], ends[i] = h[0][0], h[-1][1]
    # fill the gaps proportionally to word length, between the nearest known neighbours
    i = 0
    while i < n:
        if starts[i] is not None: i += 1; continue
        j = i
        while j < n and starts[j] is None: j += 1
        a = ends[i - 1] if i > 0 else t0
        b = starts[j] if j < n else t1
        if b < a: b = a
        tot = sum(weight[i:j]) or 1; t = a
        for k in range(i, j):
            d = (b - a) * weight[k] / tot; starts[k], ends[k] = t, t + d; t += d
        i = j
    out, prev = [], t0
    for k in range(n):   # monotonic, inside the line
        st = min(max(starts[k], prev, t0), t1)
        en = min(max(ends[k], st + 0.05), t1)
        out.append({"text": toks[k], "start": round(st, 3), "end": round(en, 3)}); prev = st
    return out


def map_onto(sub_toks, say_words):
    """Times for subtitle tokens when the subtitle text differs from what is spoken ("DocsDocs" vs "Docs, Docs")."""
    if not say_words: return []
    t0, t1 = say_words[0]["start"], say_words[-1]["end"]
    rec = [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in say_words]
    return align(sub_toks, rec, t0, t1)


# ------------------------------------------------------------------ recognisers
def _decode16(path):
    import numpy as np   # imported here: write_script.py runs before packages are installed
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def groq_words(wav_path, lang, key):
    import urllib.request, urllib.error, uuid
    mp3 = wav_path[:-4] + "_16k.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-ac", "1", "-ar", "16000", "-b:a", "48k", mp3], check=True)
    bnd = uuid.uuid4().hex
    fields = {"model": os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"), "response_format": "verbose_json",
              "timestamp_granularities[]": "word", "temperature": "0"}
    wl = L.whisper_code(lang)
    if wl and wl not in ("yue",): fields["language"] = wl
    body = b"".join(f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    body += f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="vo.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode()
    body += open(mp3, "rb").read() + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={bnd}", "User-Agent": "video-studio"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
            return [{"text": w["word"], "start": float(w["start"]), "end": float(w["end"])} for w in d.get("words", [])]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4: time.sleep(8 * (attempt + 1)); continue
            raise


def local_words(wav_path, lang):
    from faster_whisper import WhisperModel
    size = os.environ.get("WHISPER_MODEL", "small")
    m = WhisperModel(size, device="cpu", compute_type="int8")
    wl = L.whisper_code(lang)
    segs, _ = m.transcribe(_decode16(wav_path), language=wl or None, word_timestamps=True, condition_on_previous_text=False,
                           beam_size=1, vad_filter=False)
    return [{"text": w.word.strip(), "start": float(w.start), "end": float(w.end)} for s in segs for w in s.words]


def recognise(wav_path, lang):
    """Words heard in the whole voiceover, or [] (then estimates are used)."""
    if os.environ.get("TIMING", "") == "estimate": return [], "estimate"
    key = os.environ.get("GROQ_API_KEY")
    if key:
        try:
            W = groq_words(wav_path, lang, key)
            if W: return W, "Groq Whisper"
        except Exception as e:
            log(f"Groq Whisper failed ({str(e)[:120]}); trying local Whisper")
    try:
        t = time.time(); W = local_words(wav_path, lang)
        if W: return W, f"local Whisper ({time.time() - t:.0f}s)"
    except ImportError:
        pass
    except Exception as e:
        log(f"local Whisper failed ({str(e)[:120]})")
    return [], "estimate"


def segment_like(text, rec):
    """Cut `text` (no spaces, e.g. Chinese) into the words the voice engine used, keeping punctuation."""
    target = [norm(w["text"]) for w in rec]
    if not target or "".join(target) != norm(text): return None
    out, cur, ti, need = [], "", 0, len(target[0])
    for ch in str(text):
        k = norm(ch)
        if not k:
            if cur: cur += ch
            elif out: out[-1] += ch
            continue
        cur += ch; need -= len(k)
        if need <= 0:
            out.append(cur); cur = ""; ti += 1
            if ti < len(target): need = len(target[ti])
    if cur: out.append(cur)
    return [t.strip() for t in out if t.strip()]


def word_times(lines, marks, engine_words, wav_path, lang):
    """Every spoken word with its time. Returns (words, sources) where words = [{text, start, end, t, line}]."""
    need_rec = any(engine_words[k] is None for k in range(len(lines)))
    heard, src = (recognise(wav_path, lang) if need_rec else ([], "voice engine"))
    out, used = [], set()
    for k, ln in enumerate(lines):
        m = marks[k]
        toks = tokens(ln["say"], lang)
        if engine_words[k] and L.no_spaces(lang):
            toks = segment_like(ln["say"], engine_words[k]) or toks
        if engine_words[k]:
            rec = [{"text": w["text"], "start": m["start"] + w["start"] - m.get("trim", 0), "end": m["start"] + w["end"] - m.get("trim", 0)}
                   for w in engine_words[k]]
            used.add("voice engine")
        else:
            rec = [w for w in heard if m["start"] - 0.15 <= (w["start"] + w["end"]) / 2 <= m["end"] + 0.15]
            used.add(src if rec else "estimate")
        for w in align(toks, rec, m["start"], m["end"]):
            w["t"] = w["start"]; w["line"] = k; out.append(w)
    return out, sorted(used)


def subtitle_words(lines, words, lang):
    """Words to show as subtitles per line: the "sub" text (or "say"), timed by the spoken words."""
    out = []
    for k, ln in enumerate(lines):
        say_w = [w for w in words if w["line"] == k]
        sub = ln.get("sub")
        if sub and L.no_spaces(lang):
            seg = segment_like(sub, say_w)
            if seg: out.append(align(seg, say_w, say_w[0]["start"], say_w[-1]["end"])); continue
        if not sub or norm(sub) == norm(ln["say"]):
            out.append([dict(w) for w in say_w])
        else:
            out.append(map_onto(tokens(sub, lang), say_w))
    return out
