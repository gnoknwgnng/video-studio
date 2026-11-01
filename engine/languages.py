"""Languages: names, writing direction, default voices and speaking rates.

Any language that a voice engine supports works. This table holds the curated defaults; languages that
are not listed still work (the engine picks the first Microsoft Edge voice for that language).
"""
import json, os, re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# code: (English name, native name, default female voice, default male voice)
# Voices are written as "engine:id". Kokoro is offline and used for English; Edge neural voices cover 75 languages.
LANGS = {
    "en":    ("English", "English", "kokoro:af_heart", "kokoro:am_michael"),
    "en-in": ("English (India)", "English (India)", "edge:en-IN-NeerjaExpressiveNeural", "edge:en-IN-PrabhatNeural"),
    "en-gb": ("English (UK)", "English (UK)", "kokoro:bf_emma", "kokoro:bm_george"),
    "en-au": ("English (Australia)", "English (Australia)", "edge:en-AU-NatashaNeural", "edge:en-AU-WilliamMultilingualNeural"),
    "hi":    ("Hindi", "हिन्दी", "edge:hi-IN-SwaraNeural", "edge:hi-IN-MadhurNeural"),
    "hinglish": ("Hinglish (Hindi in Latin script)", "Hinglish", "edge:en-IN-NeerjaExpressiveNeural", "edge:en-IN-PrabhatNeural"),
    "bn":    ("Bengali", "বাংলা", "edge:bn-IN-TanishaaNeural", "edge:bn-IN-BashkarNeural"),
    "ta":    ("Tamil", "தமிழ்", "edge:ta-IN-PallaviNeural", "edge:ta-IN-ValluvarNeural"),
    "te":    ("Telugu", "తెలుగు", "edge:te-IN-ShrutiNeural", "edge:te-IN-MohanNeural"),
    "mr":    ("Marathi", "मराठी", "edge:mr-IN-AarohiNeural", "edge:mr-IN-ManoharNeural"),
    "gu":    ("Gujarati", "ગુજરાતી", "edge:gu-IN-DhwaniNeural", "edge:gu-IN-NiranjanNeural"),
    "kn":    ("Kannada", "ಕನ್ನಡ", "edge:kn-IN-SapnaNeural", "edge:kn-IN-GaganNeural"),
    "ml":    ("Malayalam", "മലയാളം", "edge:ml-IN-SobhanaNeural", "edge:ml-IN-MidhunNeural"),
    "ur":    ("Urdu", "اردو", "edge:ur-PK-UzmaNeural", "edge:ur-PK-AsadNeural"),
    "ne":    ("Nepali", "नेपाली", "edge:ne-NP-HemkalaNeural", "edge:ne-NP-SagarNeural"),
    "si":    ("Sinhala", "සිංහල", "edge:si-LK-ThiliniNeural", "edge:si-LK-SameeraNeural"),
    "es":    ("Spanish", "Español", "edge:es-ES-ElviraNeural", "edge:es-ES-AlvaroNeural"),
    "es-mx": ("Spanish (Mexico)", "Español (México)", "edge:es-MX-DaliaNeural", "edge:es-MX-JorgeNeural"),
    "fr":    ("French", "Français", "edge:fr-FR-VivienneMultilingualNeural", "edge:fr-FR-RemyMultilingualNeural"),
    "de":    ("German", "Deutsch", "edge:de-DE-SeraphinaMultilingualNeural", "edge:de-DE-FlorianMultilingualNeural"),
    "it":    ("Italian", "Italiano", "edge:it-IT-ElsaNeural", "edge:it-IT-GiuseppeMultilingualNeural"),
    "pt":    ("Portuguese (Brazil)", "Português (Brasil)", "edge:pt-BR-ThalitaMultilingualNeural", "edge:pt-BR-AntonioNeural"),
    "pt-pt": ("Portuguese (Portugal)", "Português", "edge:pt-PT-RaquelNeural", "edge:pt-PT-DuarteNeural"),
    "nl":    ("Dutch", "Nederlands", "edge:nl-NL-FennaNeural", "edge:nl-NL-MaartenNeural"),
    "ru":    ("Russian", "Русский", "edge:ru-RU-SvetlanaNeural", "edge:ru-RU-DmitryNeural"),
    "uk":    ("Ukrainian", "Українська", "edge:uk-UA-PolinaNeural", "edge:uk-UA-OstapNeural"),
    "pl":    ("Polish", "Polski", "edge:pl-PL-ZofiaNeural", "edge:pl-PL-MarekNeural"),
    "tr":    ("Turkish", "Türkçe", "edge:tr-TR-EmelNeural", "edge:tr-TR-AhmetNeural"),
    "ar":    ("Arabic", "العربية", "edge:ar-SA-ZariyahNeural", "edge:ar-SA-HamedNeural"),
    "ar-eg": ("Arabic (Egypt)", "العربية (مصر)", "edge:ar-EG-SalmaNeural", "edge:ar-EG-ShakirNeural"),
    "fa":    ("Persian", "فارسی", "edge:fa-IR-DilaraNeural", "edge:fa-IR-FaridNeural"),
    "he":    ("Hebrew", "עברית", "edge:he-IL-HilaNeural", "edge:he-IL-AvriNeural"),
    "zh":    ("Chinese (Mandarin)", "中文", "edge:zh-CN-XiaoxiaoNeural", "edge:zh-CN-YunxiNeural"),
    "zh-tw": ("Chinese (Taiwan)", "中文（台灣）", "edge:zh-TW-HsiaoChenNeural", "edge:zh-CN-YunxiNeural"),
    "yue":   ("Cantonese", "粵語", "edge:zh-HK-HiuMaanNeural", "edge:zh-HK-WanLungNeural"),
    "ja":    ("Japanese", "日本語", "edge:ja-JP-NanamiNeural", "edge:ja-JP-KeitaNeural"),
    "ko":    ("Korean", "한국어", "edge:ko-KR-SunHiNeural", "edge:ko-KR-HyunsuMultilingualNeural"),
    "id":    ("Indonesian", "Bahasa Indonesia", "edge:id-ID-GadisNeural", "edge:id-ID-ArdiNeural"),
    "ms":    ("Malay", "Bahasa Melayu", "edge:ms-MY-YasminNeural", "edge:ms-MY-OsmanNeural"),
    "vi":    ("Vietnamese", "Tiếng Việt", "edge:vi-VN-HoaiMyNeural", "edge:vi-VN-NamMinhNeural"),
    "th":    ("Thai", "ไทย", "edge:th-TH-PremwadeeNeural", "edge:th-TH-NiwatNeural"),
    "fil":   ("Filipino", "Filipino", "edge:fil-PH-BlessicaNeural", "edge:fil-PH-AngeloNeural"),
    "sw":    ("Swahili", "Kiswahili", "edge:sw-KE-ZuriNeural", "edge:sw-KE-RafikiNeural"),
    "el":    ("Greek", "Ελληνικά", "edge:el-GR-NestorasNeural", "edge:el-GR-NestorasNeural"),
    "sv":    ("Swedish", "Svenska", "edge:sv-SE-SofieNeural", "edge:sv-SE-MattiasNeural"),
    "da":    ("Danish", "Dansk", "edge:da-DK-ChristelNeural", "edge:da-DK-JeppeNeural"),
    "nb":    ("Norwegian", "Norsk", "edge:nb-NO-PernilleNeural", "edge:nb-NO-FinnNeural"),
    "fi":    ("Finnish", "Suomi", "edge:fi-FI-NooraNeural", "edge:fi-FI-HarriNeural"),
    "cs":    ("Czech", "Čeština", "edge:cs-CZ-VlastaNeural", "edge:cs-CZ-AntoninNeural"),
    "ro":    ("Romanian", "Română", "edge:ro-RO-AlinaNeural", "edge:ro-RO-EmilNeural"),
    "hu":    ("Hungarian", "Magyar", "edge:hu-HU-NoemiNeural", "edge:hu-HU-TamasNeural"),
}

RTL = {"ar", "fa", "he", "ur", "ps", "ug", "yi", "ckb", "sd", "dv"}
NO_SPACES = {"zh", "ja", "th", "lo", "km", "my", "yue", "bo"}   # no spaces between words

# Kokoro (offline) language codes. Japanese and Chinese are left to Edge (better pronunciation).
KOKORO_LANG = {"en": "en-us", "en-us": "en-us", "en-gb": "en-gb", "es": "es", "fr": "fr-fr", "hi": "hi", "it": "it", "pt": "pt-br"}
KOKORO_PREFIX = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "p": "pt-br", "j": "ja", "z": "cmn"}

# Rough speaking rate of a lively narrator, in words per second (characters per second for NO_SPACES languages)
RATE = {"default": 2.6, "en": 2.75, "hinglish": 2.7, "es": 2.9, "it": 2.8, "fr": 2.8, "pt": 2.7, "de": 2.4, "ru": 2.3, "pl": 2.3,
        "hi": 2.7, "bn": 2.4, "ta": 2.0, "te": 2.1, "ml": 1.8, "kn": 2.0, "mr": 2.3, "gu": 2.4, "fi": 2.0, "tr": 2.3, "ar": 2.4,
        "zh": 4.8, "yue": 4.8, "ja": 7.0, "th": 6.0, "ko": 3.0, "vi": 3.3, "id": 2.5, "ms": 2.5}

# Whisper (word timing) language code for a video language
WHISPER = {"hinglish": "en", "en-in": "en", "en-gb": "en", "en-au": "en", "es-mx": "es", "pt-pt": "pt", "zh-tw": "zh", "yue": "yue",
           "ar-eg": "ar", "fil": "tl", "nb": "no"}


def norm_code(code):
    c = str(code or "en").strip().lower().replace("_", "-")
    aliases = {"english": "en", "hindi": "hi", "tamil": "ta", "telugu": "te", "bengali": "bn", "bangla": "bn", "marathi": "mr",
               "gujarati": "gu", "kannada": "kn", "malayalam": "ml", "urdu": "ur", "spanish": "es", "french": "fr", "german": "de",
               "arabic": "ar", "chinese": "zh", "mandarin": "zh", "japanese": "ja", "korean": "ko", "portuguese": "pt",
               "russian": "ru", "italian": "it", "en-us": "en", "zh-cn": "zh", "pt-br": "pt", "iw": "he", "tl": "fil", "no": "nb"}
    return aliases.get(c, c)


def base(code): return norm_code(code).split("-")[0] if norm_code(code) not in ("hinglish", "fil", "yue") else norm_code(code)


def name(code):
    c = norm_code(code)
    if c in LANGS: return LANGS[c][0]
    if base(c) in LANGS: return LANGS[base(c)][0]
    return c


def is_rtl(code): return base(code) in RTL
def no_spaces(code): return base(code) in NO_SPACES
def rate(code): c = norm_code(code); return RATE.get(c, RATE.get(base(c), RATE["default"]))
def whisper_code(code): c = norm_code(code); return WHISPER.get(c, base(c))


_edge = None


def edge_voices():
    global _edge
    if _edge is None:
        try: _edge = json.load(open(os.path.join(DATA, "edge_voices.json"), encoding="utf-8"))
        except Exception: _edge = []
    return _edge


# The most human-sounding default per language (Chatterbox + real donated voices). VOICE_QUALITY=fast switches back to
# the fast voices above (Kokoro / Edge), which is also what is used if Chatterbox cannot run.
NATURAL = {"en": ("chatterbox:haku", "chatterbox:a59a"), "en-us": ("chatterbox:haku", "chatterbox:a59a"),
           "en-in": ("chatterbox:bathri", "chatterbox:indian_guy"), "hi": ("chatterbox:bathri", "chatterbox:indian_guy")}


def defaults(code, natural=None):
    """(female, male) default voices for a language, as 'engine:id'."""
    c = norm_code(code)
    if natural is None: natural = os.environ.get("VOICE_QUALITY", "natural").lower() != "fast"
    if natural and c in NATURAL: return NATURAL[c]
    for k in (c, base(c)):
        if k in LANGS: return LANGS[k][2], LANGS[k][3]
    loc = c if "-" in c else c + "-"
    vs = [v for v in edge_voices() if v["locale"].lower().startswith(loc)] or \
         [v for v in edge_voices() if v["locale"].lower().split("-")[0] == base(c)]
    f = next((v["id"] for v in vs if v["gender"] == "F"), None)
    m = next((v["id"] for v in vs if v["gender"] == "M"), None)
    if not (f or m): return LANGS["en"][2], LANGS["en"][3]
    return "edge:" + (f or m), "edge:" + (m or f)


def edge_locale_of(code):
    """An Edge locale like hi-IN for a language code (used to check that a chosen Edge voice speaks it)."""
    f, _ = defaults(code)
    return f.split(":", 1)[1].rsplit("-", 1)[0] if f.startswith("edge:") else ""


def all_languages():
    """Every language any engine can speak: [{code, name}] (curated ones first)."""
    seen, out = set(), []
    for k, v in LANGS.items():
        out.append({"code": k, "name": v[0], "native": v[1]}); seen.add(k)
    for v in edge_voices():
        b = v["locale"].split("-")[0].lower()
        if b not in seen:
            seen.add(b); out.append({"code": b, "name": v["locale"], "native": ""})
    return out


def looks_like(text):
    """Best guess of the language of a text from its script (used when no language was given)."""
    t = str(text or "")
    checks = [(r"[ऀ-ॿ]", "hi"), (r"[ঀ-৿]", "bn"), (r"[஀-௿]", "ta"), (r"[ఀ-౿]", "te"),
              (r"[઀-૿]", "gu"), (r"[ಀ-೿]", "kn"), (r"[ഀ-ൿ]", "ml"), (r"[؀-ۿ]", "ar"),
              (r"[֐-׿]", "he"), (r"[぀-ヿ]", "ja"), (r"[가-힯]", "ko"), (r"[一-鿿]", "zh"),
              (r"[฀-๿]", "th"), (r"[Ѐ-ӿ]", "ru"), (r"[Ͱ-Ͽ]", "el")]
    best, n = "en", 0
    for rx, code in checks:
        k = len(re.findall(rx, t))
        if k > n: best, n = code, k
    return best if n >= 3 else "en"
