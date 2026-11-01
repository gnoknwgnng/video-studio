"""Voice engines for Video Studio. All free, none needs an API key.

  kokoro      54 voices (English US/UK, Hindi, Spanish, French, Italian, Portuguese). Offline, fast, very natural.
              Voices can be blended: "blend": {"af_heart": 0.6, "af_bella": 0.4}.
  edge        Microsoft Edge neural voices: 320+ voices in 75 languages, exact word timings. Needs internet.
  piper       178 offline voices in ~50 languages (downloaded once from Hugging Face).
  chatterbox  The most human-sounding voices (Resemble AI, MIT licence). English uses Chatterbox Turbo, Hindi a dedicated
              Hindi model, 21 more languages Chatterbox Multilingual V3. Voices are real people (CC0 voice donations,
              engine/data/voices/) or YOUR voice: put a 10-20 s recording in voices/<name>.wav and use "chatterbox:<name>".

A voice in video.json can be written three ways:
  "voice": "af_heart"                       -> engine detected from the id
  "voice": "edge:hi-IN-SwaraNeural"         -> engine:id
  "voice": {"engine": "kokoro", "id": "am_michael", "speed": 1.05}
Several speakers: "voices": {"host": {...}, "guest": "edge:en-US-AvaMultilingualNeural"}, then "voice": "guest" on a line.
Old videos ("voice": {"exaggeration": .., "cfg_weight": ..}) keep using Chatterbox and their cached audio.

  python engine/voices.py --list hi         # list every voice for a language
  python engine/voices.py --say "Hello" --voice edge:en-IN-NeerjaExpressiveNeural -o hello.wav
"""
import asyncio, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.request
try:
    import numpy as np, soundfile as sf
except ImportError:   # engine/needs.py only reads voice settings, before packages are installed
    np = sf = None

ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE)
import languages as L  # noqa: E402

CACHE = os.environ.get("VIDEO_STUDIO_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "video-studio")
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = {"model": os.environ.get("KOKORO_MODEL", "kokoro-v1.0.onnx"), "voices": "voices-v1.0.bin"}
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
ENGINES = ("kokoro", "edge", "piper", "chatterbox")
KOKORO_VOICES = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah",
                 "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
                 "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "ef_dora", "em_alex",
                 "em_santa", "ff_siwis", "hf_alpha", "hf_beta", "hm_omega", "hm_psi", "if_sara", "im_nicola", "jf_alpha",
                 "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo", "pf_dora", "pm_alex", "pm_santa", "zf_xiaobei", "zf_xiaoni",
                 "zf_xiaoxiao", "zf_xiaoyi", "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang"]
VOICE_DIR = os.path.join(ENGINE, "data", "voices")
REPO = os.path.dirname(ENGINE)
# Real people who donated their voices under CC0 (Kyutai "Unmute" voice donations). (gender, label)
HUMAN_VOICES = {"haku": ("F", "Haku"), "bathri": ("F", "Bathri"), "bevi": ("F", "Bevi"), "hkl": ("F", "Hkl"),
                "a59a": ("M", "Arlo"), "gyroo": ("M", "Gyroo"), "indian_guy": ("M", "Dev (Indian English)"), "7020": ("M", "Baron (deep)")}
CHATTERBOX_LANGS = {"ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv",
                    "sw", "tr", "zh"}


def log(*a): print("[voice]", *a, flush=True)


# ------------------------------------------------------------------ voice specs
def detect_engine(vid):
    v = str(vid or "")
    if v in KOKORO_VOICES or re.fullmatch(r"[abefhijpz][fm]_[a-z]+", v): return "kokoro"
    if re.fullmatch(r"[a-z]{2,3}-[A-Z]{2,4}(-[A-Za-z]+)?-\w+Neural", v): return "edge"
    if re.fullmatch(r"[a-z]{2,3}_[A-Z]{2}-[\w]+-(x_low|low|medium|high)", v): return "piper"
    if v in ("chatterbox", "clone"): return "chatterbox"
    return None


def parse_spec(v, lang, named=None):
    """Turn any accepted voice form into {"engine", "id", ...}."""
    named = named or {}
    if isinstance(v, str) and v in named: v = named[v]
    if v in (None, "", "auto", "female", "male"):
        f, m = L.defaults(lang)
        v = m if v == "male" else f
    if isinstance(v, str):
        if ":" in v:
            e, i = v.split(":", 1); spec = {"engine": e.strip().lower(), "id": i.strip()}
        else:
            spec = {"engine": detect_engine(v) or "edge", "id": v}
    elif isinstance(v, dict):
        spec = dict(v)
        if not spec.get("engine"):
            if spec.get("id"): spec["engine"] = detect_engine(spec["id"]) or "edge"
            elif spec.get("blend"):
                spec["engine"] = "kokoro"
            elif "exaggeration" in spec or "cfg_weight" in spec or spec.get("reference"):
                spec["engine"] = "chatterbox"          # the original Video Studio voice
            else:
                spec.update(parse_spec(spec.get("gender") or "auto", lang))
        if spec.get("id") and ":" in str(spec["id"]):
            e, i = spec["id"].split(":", 1); spec["engine"], spec["id"] = e, i
    else:
        raise ValueError(f"voice must be a string or an object, got {v!r}")
    spec["engine"] = spec["engine"].lower()
    if spec["engine"] not in ENGINES: raise ValueError(f'unknown voice engine "{spec["engine"]}". Use one of: {", ".join(ENGINES)}')
    if spec["engine"] == "kokoro" and not spec.get("id") and not spec.get("blend"): spec["id"] = "af_heart"
    if spec["engine"] == "chatterbox":
        spec.setdefault("id", "default")
        vid = str(spec["id"])
        if not spec.get("reference") and vid not in ("default", "builtin"):
            # a bundled human voice, or the creator's own recording: voices/<id>.wav (repo) or <id>.wav next to video.json
            spec["reference"] = os.path.join(VOICE_DIR, vid.lower() + ".wav") if vid.lower() in HUMAN_VOICES else \
                (vid if vid.lower().endswith((".wav", ".mp3", ".m4a", ".flac")) else os.path.join("voices", vid + ".wav"))
    spec.setdefault("speed", 1.0)
    spec["lang"] = L.norm_code(spec.get("lang") or lang)
    return spec


def voice_label(spec):
    if spec.get("blend"): return "kokoro blend " + "+".join(spec["blend"])
    return f'{spec["engine"]}:{spec.get("id", "")}'


def line_key(text, seed, spec):
    e = spec["engine"]
    if e == "chatterbox" and not spec.get("reference") and spec["lang"] in ("en",) and float(spec.get("speed", 1)) == 1.0:
        # same key as the original engine, so existing .voice caches stay valid
        raw = f'{text}|{seed}|{spec.get("exaggeration", 0.6)}|{spec.get("cfg_weight", 0.45)}'
    else:
        ref = spec.get("reference") or ""
        if ref and os.path.exists(ref): ref = hashlib.sha1(open(ref, "rb").read()).hexdigest()[:12]
        blend = json.dumps(spec.get("blend") or {}, sort_keys=True)
        raw = "|".join(str(x) for x in (e if e != "chatterbox" or spec.get("id") == "default" else "chatterbox2", spec.get("id"), blend, spec.get("speed", 1), spec.get("pitch", ""), spec["lang"], text, seed,
                                         spec.get("exaggeration", ""), spec.get("cfg_weight", ""), ref, spec.get("speaker", "")))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ downloads
def download(url, dst, what):
    if os.path.exists(dst) and os.path.getsize(dst) > 0: return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    log(f"downloading {what} (first run only)")
    tmp = dst + ".part"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "video-studio"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f: shutil.copyfileobj(r, f, 1 << 20)
            os.replace(tmp, dst); return dst
        except Exception as e:
            if attempt == 3: raise RuntimeError(f"could not download {what}: {e}")
            time.sleep(4 * (attempt + 1))


def to_float(x):
    x = np.asarray(x, dtype="float32")
    return x.mean(axis=1) if x.ndim > 1 else x


def ffmpeg_decode(path, sr=24000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy(), sr


def change_speed(x, sr, speed):
    """Tempo change without pitch change (ffmpeg atempo), for engines without a speed setting."""
    if abs(speed - 1.0) < 0.01: return x
    tmp_in, tmp_out = os.path.join(CACHE, "_sp_in.wav"), os.path.join(CACHE, "_sp_out.wav")
    os.makedirs(CACHE, exist_ok=True); sf.write(tmp_in, x, sr)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_in, "-filter:a", f"atempo={max(0.5, min(2.0, speed))}", tmp_out], check=True)
    y, _ = sf.read(tmp_out, dtype="float32"); return to_float(y)


# ------------------------------------------------------------------ engines
class Kokoro:
    def __init__(self):
        from kokoro_onnx import Kokoro as K
        d = os.path.join(CACHE, "kokoro")
        m = download(KOKORO_URL + KOKORO_FILES["model"], os.path.join(d, KOKORO_FILES["model"]), "Kokoro voice model (~320 MB)")
        v = download(KOKORO_URL + KOKORO_FILES["voices"], os.path.join(d, KOKORO_FILES["voices"]), "Kokoro voices (~27 MB)")
        self.k = K(m, v)

    def say(self, text, spec):
        lang = L.KOKORO_LANG.get(spec["lang"]) or L.KOKORO_LANG.get(L.base(spec["lang"]))
        if spec.get("blend"):
            tot = sum(float(w) for w in spec["blend"].values()) or 1.0
            style = sum(self.k.get_voice_style(n) * (float(w) / tot) for n, w in spec["blend"].items())
            first = next(iter(spec["blend"]))
        else:
            style, first = spec["id"], spec["id"]
        lang = lang or L.KOKORO_PREFIX.get(first[0], "en-us")
        audio, sr = self.k.create(text, voice=style, speed=float(spec.get("speed", 1.0)), lang=lang)
        return to_float(audio), sr, None


class Edge:
    def __init__(self):
        import edge_tts  # noqa: F401
        ca = os.environ.get("EDGE_TTS_CA_BUNDLE")      # only for networks with a TLS-inspecting proxy
        if ca:
            import ssl, edge_tts.communicate as C
            C._SSL_CTX = ssl.create_default_context(cafile=ca)

    def say(self, text, spec):
        import edge_tts
        sp = float(spec.get("speed", 1.0))
        rate = f"{round((sp - 1) * 100):+d}%"
        pitch = spec.get("pitch") or "+0Hz"
        if re.fullmatch(r"[+-]?\d+", str(pitch)): pitch = f"{int(pitch):+d}Hz"
        volume = spec.get("volume") or "+0%"

        async def run():
            c = edge_tts.Communicate(text, spec["id"], rate=rate, pitch=pitch, volume=volume, boundary="WordBoundary")
            buf, words = bytearray(), []
            async for ch in c.stream():
                if ch["type"] == "audio": buf += ch["data"]
                elif ch["type"] == "WordBoundary":
                    st = ch["offset"] / 1e7; words.append({"text": ch["text"], "start": st, "end": st + ch["duration"] / 1e7})
            return bytes(buf), words

        last = None
        for attempt in range(6):        # the free Edge service has short hiccups: retry patiently
            try:
                data, words = asyncio.run(run())
                if not data: raise RuntimeError("no audio returned")
                tmp = os.path.join(CACHE, "_edge.mp3"); os.makedirs(CACHE, exist_ok=True)
                open(tmp, "wb").write(data)
                x, sr = ffmpeg_decode(tmp, 24000)
                return x, sr, words
            except Exception as e:
                last = e; time.sleep(2 + 3 * attempt)
        raise RuntimeError(f"Edge voice {spec['id']} failed: {last}")


class Piper:
    def __init__(self):
        from piper import PiperVoice  # noqa: F401
        self.loaded = {}
        try: self.catalog = {v["id"]: v for v in json.load(open(os.path.join(L.DATA, "piper_voices.json"), encoding="utf-8"))}
        except Exception: self.catalog = {}

    def _voice(self, vid):
        if vid not in self.loaded:
            from piper import PiperVoice
            info = self.catalog.get(vid)
            if info: rel = info["path"]
            else:   # en_US-lessac-medium -> en/en_US/lessac/medium/en_US-lessac-medium.onnx
                loc, rest = vid.split("-", 1); nm, q = rest.rsplit("-", 1); rel = f"{loc.split('_')[0]}/{loc}/{nm}/{q}/{vid}.onnx"
            d = os.path.join(CACHE, "piper")
            m = download(PIPER_URL + rel, os.path.join(d, vid + ".onnx"), f"Piper voice {vid}")
            download(PIPER_URL + rel + ".json", os.path.join(d, vid + ".onnx.json"), f"Piper voice {vid} config")
            self.loaded[vid] = PiperVoice.load(m)
        return self.loaded[vid]

    def say(self, text, spec):
        import wave, io
        from piper import SynthesisConfig
        v = self._voice(spec["id"])
        cfg = SynthesisConfig(length_scale=1.0 / max(0.5, float(spec.get("speed", 1.0))),
                              speaker_id=int(spec["speaker"]) if str(spec.get("speaker", "")).isdigit() else None)
        bio = io.BytesIO()
        with wave.open(bio, "wb") as w: v.synthesize_wav(text, w, syn_config=cfg)
        bio.seek(0); x, sr = sf.read(bio, dtype="float32")
        return to_float(x), sr, None


def _chatterbox_fixes():
    """Small fixes for chatterbox-tts 0.1.7: float32 reference audio (Turbo) and loading the newer V3 / Hindi checkpoints."""
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    if getattr(ChatterboxTurboTTS, "_vs_fixed", False): return
    nl = ChatterboxTurboTTS.norm_loudness
    ChatterboxTurboTTS.norm_loudness = lambda self, wav, sr, target_lufs=-27: np.asarray(nl(self, wav, sr, target_lufs), dtype=np.float32)
    ChatterboxTurboTTS._vs_fixed = True


def _load_multilingual(dev, lang):
    """Chatterbox Multilingual V3, or the dedicated Hindi model for Hindi (both MIT, Resemble AI)."""
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS, T3, T3Config, S3Gen, VoiceEncoder, MTLTokenizer, Conditionals
    B, H = "ResembleAI/chatterbox", "ResembleAI/Chatterbox-Multilingual-hi"
    hindi = lang == "hi"
    get = lambda repo, f: hf_hub_download(repo, f)
    ve = VoiceEncoder(); ve.load_state_dict(torch.load(get(B, "ve.pt"), map_location="cpu", weights_only=True)); ve.to(dev).eval()
    t3 = T3(T3Config.multilingual())
    st = load_file(get(H, "t3_hi.safetensors") if hindi else get(B, "t3_mtl23ls_v3.safetensors"))
    if "model" in st: st = st["model"][0]
    t3.load_state_dict(st); t3.to(dev).eval()
    s3 = S3Gen()
    s3.load_state_dict(torch.load(get(H if hindi else B, "s3gen_v3.pt"), map_location="cpu", weights_only=True), strict=False)  # mel buffers are rebuilt
    s3.to(dev).eval()
    tok = MTLTokenizer(get(H if hindi else B, "grapheme_mtl_merged_expanded_v1.json"))
    conds = Conditionals.load(get(B, "conds.pt"), map_location="cpu").to(dev)
    return ChatterboxMultilingualTTS(t3, s3, ve, tok, dev, conds=conds)


def trim_silence(x, sr, pad=0.06, thr_db=-42):
    """Cut the silence the model leaves before and after a line (the mix adds natural pauses itself)."""
    if len(x) < sr // 4: return x
    hop = int(sr * 0.01); n = len(x) // hop
    e = 20 * np.log10(np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9)
    loud = np.where(e > max(thr_db, e.max() - 45))[0]
    if not len(loud): return x
    a = max(0, loud[0] * hop - int(pad * sr)); b = min(len(x), (loud[-1] + 1) * hop + int(pad * sr))
    return x[a:b]


class Chatterbox:
    def __init__(self):
        import torch
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        if self.dev == "cpu": torch.set_num_threads(max(1, os.cpu_count() or 1))
        self.models, self.ref_ready = {}, {}

    def _model(self, kind):
        if kind not in self.models:
            if self.models:   # keep one Chatterbox model in memory at a time (each is 2-3 GB)
                import gc
                self.models.clear(); self.ref_ready.clear(); gc.collect()
            t0 = time.time()
            if kind == "legacy-en":
                from chatterbox.tts import ChatterboxTTS
                self.models[kind] = ChatterboxTTS.from_pretrained(device=self.dev)
            elif kind == "legacy-mtl":
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                self.models[kind] = ChatterboxMultilingualTTS.from_pretrained(device=self.dev)
            elif kind == "turbo":
                _chatterbox_fixes()
                from chatterbox.tts_turbo import ChatterboxTurboTTS
                self.models[kind] = ChatterboxTurboTTS.from_pretrained(device=self.dev)
            else:
                self.models[kind] = _load_multilingual(self.dev, "hi" if kind == "hi" else "multi")
            log(f"Chatterbox {kind} model loaded on {self.dev} ({time.time() - t0:.0f}s)")
        return self.models[kind]

    def say(self, text, spec, seed=42):
        lang = L.base(spec["lang"]); lang = "no" if lang == "nb" else lang
        if lang not in CHATTERBOX_LANGS: raise RuntimeError(f"Chatterbox does not speak '{spec['lang']}'")
        legacy = spec.get("id") == "default" and not spec.get("model")
        kind = ("legacy-en" if lang == "en" else "legacy-mtl") if legacy else \
               ("turbo" if lang == "en" and spec.get("model") != "original" else "legacy-en" if lang == "en" else "hi" if lang == "hi" else "v3")
        m = self._model(kind)
        ex = float(spec.get("exaggeration", 0.6 if legacy else 0.55))
        ref = spec.get("reference")
        if ref and self.ref_ready.get(kind) != (ref, ex):   # condition on the voice once, not for every line
            if kind == "turbo": m.prepare_conditionals(ref, exaggeration=0.0)
            else: m.prepare_conditionals(ref, exaggeration=ex)
            self.ref_ready[kind] = (ref, ex)
        words = len(text.split()) if not L.no_spaces(spec["lang"]) else len(text) / 2.5
        expect = max(1.2, words / 2.6)
        best = None
        for attempt in range(3):     # a rare run-on or cut-off take is re-generated with another seed
            self.torch.manual_seed(int(seed) + 1000 * attempt)
            if kind == "turbo": wav = m.generate(text, temperature=float(spec.get("temperature", 0.75)))
            elif kind.startswith("legacy") and lang == "en":
                wav = m.generate(text, exaggeration=ex, cfg_weight=float(spec.get("cfg_weight", 0.45)), **({"audio_prompt_path": ref} if ref and legacy else {}))
            else:
                wav = m.generate(text, language_id=lang, exaggeration=ex, cfg_weight=float(spec.get("cfg_weight", 0.45 if legacy else 0.4)))
            x = trim_silence(wav.squeeze(0).cpu().numpy().astype("float32"), m.sr)
            d = len(x) / m.sr
            ok = 0.45 * expect <= d <= 2.3 * expect + 1.0
            if best is None or ok: best = x
            if ok: break
            log(f"  take {attempt + 1} sounded off ({d:.1f}s for ~{expect:.1f}s of text); trying again")
        return change_speed(best, m.sr, float(spec.get("speed", 1.0))), m.sr, None


_engines = {}


def engine(name):
    if name not in _engines:
        _engines[name] = {"kokoro": Kokoro, "edge": Edge, "piper": Piper, "chatterbox": Chatterbox}[name]()
    return _engines[name]


def can_speak(spec):
    """Quick check that the engine/voice can speak the language at all (before generating anything)."""
    e, lang = spec["engine"], spec["lang"]
    if e == "kokoro":
        first = next(iter(spec["blend"])) if spec.get("blend") else spec.get("id", "")
        if first not in KOKORO_VOICES: return False
        return (L.KOKORO_LANG.get(lang) or L.KOKORO_LANG.get(L.base(lang))) is not None or lang in ("hinglish",)
    if e == "chatterbox": return L.base(lang) in CHATTERBOX_LANGS or lang == "hinglish"
    return True


def fallback_spec(spec):
    """Another free voice in the same language and of the same gender, used when an engine fails."""
    lang = spec["lang"]
    female = True
    vid = str(spec.get("id", ""))
    if spec["engine"] == "chatterbox":
        female = HUMAN_VOICES.get(vid.lower(), ("F",))[0] == "F"
        f, m = L.defaults(lang, natural=False)
        choice = parse_spec(f if female else m, lang); choice["speed"] = spec.get("speed", 1.0)
        return choice
    if spec["engine"] == "kokoro" and len(vid) > 1: female = vid[1] == "f"
    elif spec["engine"] == "edge":
        g = next((v["gender"] for v in L.edge_voices() if v["id"] == vid), "F"); female = g == "F"
    f, m = L.defaults(lang)
    choice = parse_spec(f if female else m, lang)
    if voice_label(choice) == voice_label(spec):                  # the default itself failed: try the other engine
        if spec["engine"] == "edge" and (L.KOKORO_LANG.get(lang) or L.KOKORO_LANG.get(L.base(lang))):
            pair = {"en": ("af_heart", "am_michael"), "hi": ("hf_alpha", "hm_omega"), "es": ("ef_dora", "em_alex"),
                    "fr": ("ff_siwis", "ff_siwis"), "it": ("if_sara", "im_nicola"), "pt": ("pf_dora", "pm_alex")}.get(L.base(lang), ("af_heart", "am_michael"))
            choice = parse_spec("kokoro:" + pair[0 if female else 1], lang)
        else:
            piper = [v for v in json.load(open(os.path.join(L.DATA, "piper_voices.json"))) if v["locale"].split("-")[0] == L.base(lang)]
            piper.sort(key=lambda v: {"high": 0, "medium": 1, "low": 2, "x_low": 3}.get(v["quality"], 4))
            if piper: choice = parse_spec("piper:" + piper[0]["id"], lang)
            elif spec["engine"] != "edge": choice = parse_spec(L.defaults(lang)[0 if female else 1], lang)
            else: return None
    choice["speed"] = spec.get("speed", 1.0)
    return choice if voice_label(choice) != voice_label(spec) else None


# ------------------------------------------------------------------ main entry
def make_voice(vdir, lines, specs, skip_voice=False):
    """Voice every line (cached in <video>/.voice/). `specs[i]` is the parsed voice of line i.
    Returns [(wav_path, words_or_None)] where words are the engine's own word timings (Edge)."""
    cache = os.path.join(vdir, ".voice"); os.makedirs(cache, exist_ok=True)
    specs = [dict(s) for s in specs]
    for s in specs:
        if s.get("reference") and not os.path.isabs(s["reference"]):
            cands = [os.path.join(vdir, s["reference"]), os.path.join(REPO, s["reference"]), os.path.join(vdir, os.path.basename(s["reference"]))]
            s["reference"] = next((c for c in cands if os.path.exists(c)), cands[0])
        if s.get("reference") and not os.path.exists(s["reference"]):
            raise SystemExit(f'voice "{s.get("id")}": recording "{s["reference"]}" not found. Put a 10-20 s .wav of the voice in voices/ (repo) or next to video.json.')
    # a voice that can't speak the language is swapped up front for every line that uses it
    for s in specs:
        if not can_speak(s):
            fb = fallback_spec(s) or parse_spec("auto", s["lang"])
            log(f"WARN {voice_label(s)} cannot speak '{s['lang']}'; using {voice_label(fb)}")
            s.clear(); s.update(fb)
    groups = {}
    for i, s in enumerate(specs): groups.setdefault(voice_label(s), []).append(i)
    out = [None] * len(lines)
    for label, idx in groups.items():
        spec = specs[idx[0]]
        for attempt in range(3):
            try:
                _voice_group(cache, lines, idx, spec, out, skip_voice); break
            except SystemExit: raise
            except Exception as e:
                fb = fallback_spec(spec)
                if not fb or attempt == 2: raise
                log(f"WARN {voice_label(spec)} failed ({str(e)[:160]}); re-voicing its lines with {voice_label(fb)} so the voice stays consistent")
                spec = fb
                for i in idx: specs[i] = fb
    keep = set()
    for p, _ in out:
        keep.add(os.path.basename(p)); keep.add(os.path.basename(p)[:-4] + ".json")
    for f in os.listdir(cache):      # drop cache files no longer used by any line
        if f.endswith((".wav", ".json")) and f not in keep: os.remove(os.path.join(cache, f))
    return out, specs


def _voice_group(cache, lines, idx, spec, out, skip_voice):
    todo = []
    for i in idx:
        ln = lines[i]
        p = os.path.join(cache, line_key(ln["say"], ln.get("seed", 42), spec) + ".wav")
        out[i] = (p, None)
        if not os.path.exists(p): todo.append(i)
    if todo and skip_voice: raise SystemExit(f"{len(todo)} voice line(s) missing from {cache} and --skip-voice was given")
    if todo:
        log(f"{voice_label(spec)}: generating {len(todo)} line(s) (cached: {len(idx) - len(todo)})")
        eng = engine(spec["engine"])
        for k, i in enumerate(todo, 1):
            ln = lines[i]
            t0 = time.time()
            if spec["engine"] == "chatterbox": x, sr, words = eng.say(ln["say"], spec, ln.get("seed", 42))
            else: x, sr, words = eng.say(ln["say"], spec)
            if len(x) < sr * 0.15: raise RuntimeError(f"almost no audio for line: {ln['say'][:50]}")
            p = out[i][0]
            sf.write(p, x, sr)
            if words: json.dump(words, open(p[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False)
            log(f"  {k}/{len(todo)} ({time.time() - t0:.1f}s): {ln['say'][:60]}")
    for i in idx:
        p = out[i][0]; j = p[:-4] + ".json"
        out[i] = (p, json.load(open(j, encoding="utf-8")) if os.path.exists(j) else None)


def catalog(lang=None):
    """Every available voice, optionally for one language: [{engine, id, label, gender, locale}]."""
    out = []
    lc = L.norm_code(lang) if lang else None
    def ok(locale): return not lc or locale.lower().startswith(L.base(lc)) or (lc == "hinglish" and locale.lower().startswith(("en-in", "hi")))
    for vid, (g, label) in HUMAN_VOICES.items():
        for loc in ("en-US", "hi-IN") if vid in ("indian_guy", "bathri") else ("en-US",):
            if ok(loc): out.append({"engine": "chatterbox", "id": vid, "label": label + " (human-like)", "gender": g, "locale": loc})
    for v in KOKORO_VOICES:
        loc = {"a": "en-US", "b": "en-GB", "e": "es", "f": "fr", "h": "hi", "i": "it", "p": "pt-BR", "j": "ja", "z": "zh"}[v[0]]
        if ok(loc): out.append({"engine": "kokoro", "id": v, "label": v.split("_")[1].title(), "gender": v[1].upper(), "locale": loc})
    for v in L.edge_voices():
        if ok(v["locale"]):
            nm = re.sub(r"(Multilingual|Expressive)?Neural$", "", v["id"].split("-", 2)[2])
            out.append({"engine": "edge", "id": v["id"], "label": nm + (" (multilingual)" if "Multilingual" in v["id"] else ""),
                        "gender": v["gender"], "locale": v["locale"], "style": v.get("style", "")})
    try:
        for v in json.load(open(os.path.join(L.DATA, "piper_voices.json"), encoding="utf-8")):
            if ok(v["locale"]):
                out.append({"engine": "piper", "id": v["id"], "label": v["id"].split("-")[1].replace("_", " ").title() + f' ({v["quality"]})',
                            "gender": "", "locale": v["locale"]})
    except Exception:
        pass
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description="List or try voices")
    ap.add_argument("--list", metavar="LANG", nargs="?", const="", help="list voices (optionally for one language)")
    ap.add_argument("--say", help="text to speak")
    ap.add_argument("--voice", default="auto")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("-o", "--out", default="voice_test.wav")
    a = ap.parse_args()
    if a.list is not None:
        for v in catalog(a.list or None): print(f'{v["engine"]:7} {v["id"]:42} {v["gender"]:2} {v["locale"]:8} {v.get("style", "")}')
        return
    if a.say:
        spec = parse_spec(a.voice, a.lang); spec["speed"] = a.speed
        x, sr, words = engine(spec["engine"]).say(a.say, spec)
        sf.write(a.out, x, sr); print(f"{voice_label(spec)} -> {a.out} ({len(x) / sr:.1f}s)")
        if words: print("word timings:", words[:8])


if __name__ == "__main__":
    main()
