"""Audio finishing for Video Studio: a human-sounding voice and real background music. All free and open.

  polish_voice()   "studio" chain on the narration: rumble cut, de-esser, gentle compression, warmth + presence EQ,
                   a touch of room, and soft room tone in the gaps (real recordings are never digitally silent).
  find_music()     a real track for the video, in this order:
                     1. "music": "song.mp3" in video.json (a file next to it, or a URL)
                     2. your own tracks in music/ (repo root) - music/<mood>/*.mp3 or any file in music/
                     3. a free CC0 / CC BY track from Openverse (Jamendo, Freesound, Wikimedia) - credit saved
                     4. a free track shipped in engine/data/music/ (when the online search is down)
                     5. the synthesised bed in sfx.py (always works offline)
  beats()          tempo + beat times of a track (numpy only)
  align_start()    where to start the track so its beats land on the scene cuts
  mix()            voice on top: music sits well below the voice and dips further while someone speaks

Music volume: "off" | "low" (default) | "medium" | "high", or a number (old videos: 0.16 = the old default).
"""
import hashlib, json, os, re, subprocess, time, urllib.parse, urllib.request
import numpy as np

CACHE = os.environ.get("VIDEO_STUDIO_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "video-studio")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus")
# music level below the voice (dB, RMS vs RMS) and the extra dip while someone is speaking
LEVELS = {"low": (-19.0, 6.0), "medium": (-15.0, 6.0), "high": (-11.0, 5.0)}
QUERIES = {"upbeat": ["upbeat background", "happy corporate", "upbeat instrumental"],
           "calm": ["calm ambient background", "soft piano background", "chill instrumental"],
           "dramatic": ["cinematic background", "epic cinematic", "dramatic instrumental"],
           "tech": ["electronic background", "technology corporate", "synth instrumental"],
           "news": ["news background", "corporate background", "documentary background"]}
GOOD_WORDS = ("background", "instrumental", "corporate", "ambient", "cinematic", "underscore", "lounge", "documentary",
              "piano", "chill", "soundtrack", "motivational", "inspiring", "electronic", "loop")
BAD_WORDS = ("vocal", "feat", "remix", "live", "karaoke", "song", "lyrics", "rap", "acapella", "voice")
GOOD_GENRES = {"corporate", "ambient", "filmscore", "soundtrack", "electronic", "lounge", "chillout", "classical", "easylistening",
               "instrumental", "cinematic", "downtempo", "piano", "newage", "experimental", "electronica", "triphop"}


def log(*a): print("[audio]", *a, flush=True)


def _ff(args, data=None):
    return subprocess.run(["ffmpeg", "-v", "error", "-y"] + args, input=data, capture_output=True, check=True).stdout


def decode(path, sr, af=None):
    raw = _ff(["-i", path, "-ac", "1", "-ar", str(sr)] + (["-af", af] if af else []) + ["-f", "f32le", "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def _filter(x, sr, af):
    raw = _ff(["-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-af", af, "-f", "f32le", "-"], x.astype(np.float32).tobytes())
    y = np.frombuffer(raw, dtype=np.float32).copy()
    return np.pad(y, (0, max(0, len(x) - len(y))))[:len(x)]


def _rms(x): return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)) + 1e-12))


def speech_mask(vo, sr, win=0.05):
    """True where someone is speaking (frame energy well above the quiet parts)."""
    hop = max(1, int(sr * win)); n = len(vo) // hop
    if n == 0: return np.zeros(len(vo), bool)
    e = np.sqrt(np.mean(vo[:n * hop].reshape(n, hop) ** 2, axis=1))
    thr = max(1e-4, np.percentile(e[e > 0], 90) * 0.08) if np.any(e > 0) else 1e-4
    m = np.repeat(e > thr, hop)
    return np.pad(m, (0, len(vo) - len(m)))


# ------------------------------------------------------------------ voice
def polish_voice(vo, sr, room=True):
    """Make synthetic narration sound like a voice recorded on a good mic in a real room."""
    if not np.any(vo): return vo
    chain = ("highpass=f=70,deesser=i=0.35:m=0.5:f=0.5,"
             "acompressor=threshold=-21dB:ratio=2.6:attack=8:release=140:makeup=1.6:knee=4,"
             "equalizer=f=170:t=q:w=0.9:g=1.4,equalizer=f=3300:t=q:w=1.1:g=1.6,equalizer=f=9500:t=q:w=1.2:g=-1.2")
    if room: chain += ",aecho=0.92:0.9:17|29:0.045|0.03"     # a small room, barely there
    try:
        peak = np.abs(vo).max(); y = _filter(vo / peak * 0.7, sr, chain + ",alimiter=limit=0.89") * (peak / 0.7)
    except Exception as e:
        log(f"WARN voice polish skipped ({str(e)[:120]})"); y = vo.copy()
    if room:   # room tone: soft, darkened noise ~48 dB below the voice, so pauses never go "digitally dead"
        speech = speech_mask(y, sr)
        lvl = _rms(y[speech]) if speech.any() else _rms(y)
        rng = np.random.default_rng(11)
        noise = rng.standard_normal(len(y)).astype(np.float32)
        k = int(sr / 2500); noise = np.convolve(noise, np.ones(k) / k, mode="same")      # darker, like air
        noise *= lvl * 10 ** (-48 / 20) / (_rms(noise) + 1e-12)
        y = y + noise.astype(np.float32)
    return y.astype(np.float32)


# ------------------------------------------------------------------ music: where it comes from
def _pick(cands, key):
    if not cands: return None
    h = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    return cands[h % len(cands)]


def _local_tracks(mood):
    d = os.path.join(REPO, "music")
    if not os.path.isdir(d): return []
    sub = os.path.join(d, mood)
    files = [os.path.join(sub, f) for f in sorted(os.listdir(sub))] if os.path.isdir(sub) else []
    if not files: files = [os.path.join(d, f) for f in sorted(os.listdir(d))]
    return [f for f in files if f.lower().endswith(AUDIO_EXT) and os.path.isfile(f)]


def _openverse(mood, need_s):
    """CC0 / CC BY instrumental-sounding tracks from Openverse (no key needed)."""
    out, seen = [], set()
    for q in QUERIES.get(mood, QUERIES["upbeat"]):
        url = "https://api.openverse.org/v1/audio/?" + urllib.parse.urlencode(
            {"q": q, "license": "cc0,by", "category": "music", "page_size": 20})
        res = None
        for attempt in range(3):   # the free API is sometimes slow: retry patiently
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "video-studio (open-source video maker)"})
                res = json.load(urllib.request.urlopen(req, timeout=30)).get("results", []); break
            except Exception as e:
                if attempt == 2: log(f"Openverse music search '{q}' failed ({str(e)[:80]})")
                else: time.sleep(4 * (attempt + 1))
        if res is None: continue
        for r in res:
            if r.get("id") in seen or not r.get("url"): continue
            seen.add(r.get("id"))
            dur = (r.get("duration") or 0) / 1000
            title = (r.get("title") or "").lower(); genres = {g.lower() for g in (r.get("genres") or [])}
            if dur and not (max(25, min(need_s, 90)) <= dur <= 420): continue
            if any(b in title for b in BAD_WORDS): continue
            score = 2 * any(g in title for g in GOOD_WORDS) + 2 * bool(genres & GOOD_GENRES) + (1 if dur >= need_s else 0) + (r.get("license") == "cc0")
            out.append((score, r))
        if len([1 for s, _ in out if s >= 3]) >= 8: break
    out.sort(key=lambda t: (-t[0], t[1].get("id")))
    return [r for s, r in out if s >= 2][:12] or [r for s, r in out][:6]


def _download(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 50000: return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "video-studio (open-source video maker)"})
    with urllib.request.urlopen(req, timeout=90) as r, open(dst + ".part", "wb") as f:
        while True:
            b = r.read(1 << 16)
            if not b: break
            f.write(b)
    os.replace(dst + ".part", dst)
    return dst


def credit_line(r):
    lic = "CC0" if r.get("license") == "cc0" else f'CC {(r.get("license") or "").upper()} {r.get("license_version") or ""}'.strip()
    by = r.get("creator") or "unknown artist"
    return f'Music: "{r.get("title", "untitled")}" by {by} ({lic}) {r.get("foreign_landing_url") or r.get("url")}'


def _bundled(mood):
    """A free track shipped with Video Studio (engine/data/music/<mood>.mp3), used when the online search is down."""
    d = os.path.join(REPO, "engine", "data", "music")
    mood = mood if os.path.exists(os.path.join(d, mood + ".mp3")) else {"tech": "upbeat"}.get(mood, mood)
    p = os.path.join(d, mood + ".mp3")
    if not os.path.exists(p): return None, {}
    try: meta = json.load(open(os.path.join(d, "credits.json"), encoding="utf-8")).get(mood, {})
    except Exception: meta = {}
    return p, {"source": "bundled", "file": f"engine/data/music/{mood}.mp3", **meta, **({"credit": credit_line(meta)} if meta.get("title") else {})}


def find_music(vdir, cfg, mood, need_s, build_dir):
    """Returns (path or None, info dict). A track chosen once is remembered in <video>/music.json for re-renders."""
    name = os.path.basename(os.path.normpath(vdir))
    m = cfg.get("music")
    if isinstance(m, str) and m.lower().endswith(AUDIO_EXT) or (isinstance(m, str) and m.startswith(("http://", "https://"))):
        src = m if m.startswith("http") else (m if os.path.isabs(m) else os.path.join(vdir, m))
        if src.startswith("http"):
            try: src = _download(src, os.path.join(build_dir, "audio", "music_src" + os.path.splitext(urllib.parse.urlparse(src).path)[1]))
            except Exception as e: log(f"WARN could not download music '{m}' ({e})"); src = None
        if src and os.path.exists(src): return src, {"source": "video.json", "file": m}
    local = _local_tracks(mood)
    if local:
        p = _pick(local, name); return p, {"source": "music folder", "file": os.path.relpath(p, REPO)}
    if os.environ.get("NO_ONLINE_MUSIC") or cfg.get("online_music") is False: return _bundled(mood)
    memo = os.path.join(vdir, "music.json")
    try:
        r = json.load(open(memo, encoding="utf-8"))
        if r.get("mood") != mood: r = None
    except Exception:
        r = None
    if not r:
        cands = _openverse(mood, need_s)
        r = _pick(cands, name + mood)
        if r: r = {k: r.get(k) for k in ("id", "title", "creator", "license", "license_version", "url", "foreign_landing_url", "duration", "source")}
    if not r: return _bundled(mood)
    r["mood"] = mood
    try:
        p = _download(r["url"], os.path.join(CACHE, "music", re.sub(r"[^\w-]", "", str(r["id"]))[:40] + ".mp3"))
    except Exception as e:
        log(f"WARN could not download the music track ({str(e)[:100]})"); return _bundled(mood)
    json.dump(r, open(memo, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return p, {"source": "openverse", "credit": credit_line(r), **r}


# ------------------------------------------------------------------ beats
def beats(x, sr):
    """Tempo (BPM) and beat times (s) from a spectral-flux onset envelope + autocorrelation. Numpy only."""
    hop, n = 512, 2048
    if len(x) < sr * 4: return 0.0, np.array([])
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    S = np.abs(np.fft.rfft(x[idx] * np.hanning(n), axis=1))
    L = np.log1p(30 * S)
    flux = np.maximum(0, np.diff(L, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux]); flux -= np.convolve(flux, np.ones(16) / 16, mode="same"); flux = np.maximum(flux, 0)
    flux /= flux.max() + 1e-9
    fps = sr / hop
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    lags = np.arange(len(ac)); bpm = 60 * fps / np.maximum(lags, 1)
    ok = (bpm >= 70) & (bpm <= 180)
    prior = np.exp(-0.5 * (np.log2(bpm / 112) / 0.9) ** 2)
    lag = int(lags[ok][np.argmax((ac * prior)[ok])])
    phase = int(np.argmax([flux[p::lag].sum() for p in range(lag)]))
    times = (np.arange(phase, len(flux), lag) / fps).astype(float)
    return 60 * fps / lag, times


def align_start(track, sr, cuts, need_s):
    """Pick where to start the track: past any quiet intro, then shifted (< 1 beat) so beats land on the scene cuts."""
    bpm, bt = beats(track, sr)
    hop = int(sr * 0.1); n = len(track) // hop
    e = np.sqrt(np.mean(track[:n * hop].reshape(n, hop) ** 2, axis=1)) if n else np.array([1.0])
    loud = np.where(e >= 0.45 * np.median(e[e > 0]) if np.any(e > 0) else e >= 0)[0]
    start0 = (loud[0] * hop / sr) if len(loud) else 0.0
    start0 = min(start0, max(0.0, len(track) / sr - need_s - 1))
    if not len(bt) or not cuts: return start0, bpm, 0
    period = 60 / bpm
    cuts = np.asarray(cuts, float)
    best, best_s = start0, -1
    for s in np.arange(start0, start0 + period, 0.01):
        b = bt[(bt >= s) & (bt <= s + need_s + 1)] - s
        if not len(b): continue
        d = np.min(np.abs(cuts[:, None] - b[None, :]), axis=1)
        sc = float(np.sum(np.exp(-(d / 0.06) ** 2)))
        if sc > best_s: best, best_s = s, sc
    hits = int(np.sum(np.min(np.abs(cuts[:, None] - (bt[(bt >= best)] - best)[None, :]), axis=1) < 0.08)) if len(bt[bt >= best]) else 0
    return float(best), bpm, hits


# ------------------------------------------------------------------ mix
def _envelope(mask, sr, attack=0.12, release=0.45):
    """Smooth 0..1 'someone is speaking' curve (fast attack, slow release) for ducking."""
    x = mask.astype(np.float32); hop = int(sr * 0.01); n = len(x) // hop + 1
    f = np.array([x[i * hop:(i + 1) * hop].max() if i * hop < len(x) else 0 for i in range(n)], np.float32)
    a, r = np.exp(-0.01 / attack), np.exp(-0.01 / release); y = np.zeros_like(f); s = 0.0
    for i, v in enumerate(f):
        s = (a if v > s else r) * s + (1 - (a if v > s else r)) * v; y[i] = s
    return np.interp(np.arange(len(x)) / hop, np.arange(n), y).astype(np.float32)


def prepare_track(path, sr, need, start):
    """Decode, carve room for the voice (dip around 1-4 kHz, no sub rumble), loop if short, fade in/out."""
    x = decode(path, sr, af="highpass=f=45,equalizer=f=2600:t=q:w=1.0:g=-4.5,equalizer=f=1200:t=q:w=1.2:g=-2")
    s = int(start * sr)
    x = x[s:] if s < len(x) - sr * 5 else x
    if len(x) < need:     # loop with a 1.5 s crossfade
        cf = int(1.5 * sr); y = x.copy()
        while len(y) < need:
            fade = np.linspace(0, 1, cf, dtype=np.float32)
            y = np.concatenate([y[:-cf], y[-cf:] * (1 - fade) + x[:cf] * fade, x[cf:]])
        x = y
    x = x[:need].copy()
    fi, fo = int(0.6 * sr), min(len(x) // 3, int(2.5 * sr))
    x[:fi] *= np.linspace(0, 1, fi); x[-fo:] *= np.linspace(1, 0, fo)
    return x


def music_level(volume):
    """'off' -> None; 'low'/'medium'/'high' -> (dB under voice, duck dB); numbers keep working for old videos."""
    if volume is None or volume == "": volume = "low"
    if isinstance(volume, str):
        v = volume.strip().lower()
        if v in ("off", "none", "no", "0"): return None
        if v in LEVELS: return LEVELS[v]
        try: volume = float(v)
        except ValueError: return LEVELS["low"]
    volume = float(volume)
    if volume <= 0: return None
    return (max(-30.0, min(-8.0, -19.0 + 20 * np.log10(volume / 0.10))), 6.0)


def mix(vo, fx, bed, sr, level):
    """vo + fx + bed. The bed's loudness is set relative to the voice, then dips while someone talks."""
    speech = speech_mask(vo, sr)
    v_rms = _rms(vo[speech]) if speech.any() else _rms(vo)
    out = vo + fx
    if bed is not None and level is not None and np.any(bed):
        under_db, duck_db = level
        bed = bed / (_rms(bed[bed != 0]) + 1e-12) * v_rms * 10 ** (under_db / 20)
        env = _envelope(speech, sr)
        bed = bed * (1 - (1 - 10 ** (-duck_db / 20)) * env)
        out = out + bed[:len(out)]
    return (out / max(1.0, np.abs(out).max() / 0.95)).astype(np.float32)
