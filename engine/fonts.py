"""Fonts for every writing system. The built-in fonts (Inter + Instrument Serif) cover English and Western
European languages. For anything else, Google's Noto fonts are downloaded at build time, cut down to only the
characters the video uses (so even Chinese fonts stay tiny) and stored next to the video, never loaded from a CDN
at render time. If the download fails, the system's Noto fonts (installed by the workflow) are used instead.
"""
import hashlib, os, re, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

# script: (sans family, serif/display family) on Google Fonts
SCRIPTS = [
    (r"[ऀ-ॿ]", "Noto Sans Devanagari", "Noto Serif Devanagari"),
    (r"[ঀ-৿]", "Noto Sans Bengali", "Noto Serif Bengali"),
    (r"[਀-੿]", "Noto Sans Gurmukhi", "Noto Serif Gurmukhi"),
    (r"[઀-૿]", "Noto Sans Gujarati", "Noto Serif Gujarati"),
    (r"[଀-୿]", "Noto Sans Oriya", "Noto Serif Oriya"),
    (r"[஀-௿]", "Noto Sans Tamil", "Noto Serif Tamil"),
    (r"[ఀ-౿]", "Noto Sans Telugu", "Noto Serif Telugu"),
    (r"[ಀ-೿]", "Noto Sans Kannada", "Noto Serif Kannada"),
    (r"[ഀ-ൿ]", "Noto Sans Malayalam", "Noto Serif Malayalam"),
    (r"[඀-෿]", "Noto Sans Sinhala", "Noto Serif Sinhala"),
    (r"[؀-ۿݐ-ݿ]", "Noto Sans Arabic", "Noto Naskh Arabic"),
    (r"[֐-׿]", "Noto Sans Hebrew", "Noto Serif Hebrew"),
    (r"[฀-๿]", "Noto Sans Thai", "Noto Serif Thai"),
    (r"[຀-໿]", "Noto Sans Lao", "Noto Serif Lao"),
    (r"[ក-៿]", "Noto Sans Khmer", "Noto Serif Khmer"),
    (r"[က-႟]", "Noto Sans Myanmar", "Noto Serif Myanmar"),
    (r"[Ⴀ-ჿ]", "Noto Sans Georgian", "Noto Serif Georgian"),
    (r"[԰-֏]", "Noto Sans Armenian", "Noto Serif Armenian"),
    (r"[ሀ-፿]", "Noto Sans Ethiopic", "Noto Serif Ethiopic"),
    (r"[가-힯ᄀ-ᇿ]", "Noto Sans KR", "Noto Serif KR"),
    (r"[぀-ヿ]", "Noto Sans JP", "Noto Serif JP"),
    (r"[一-鿿㐀-䶿]", "Noto Sans SC", "Noto Serif SC"),
    # Latin beyond Western Europe (Polish, Czech, Vietnamese...), Cyrillic and Greek
    (r"[Ā-ɏḀ-ỿЀ-ӿͰ-Ͽ]", "Inter", "Noto Serif"),
]


def log(*a): print("[fonts]", *a, flush=True)


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        return r.read()


def needed(text, lang=""):
    fams = []
    for rx, sans, serif in SCRIPTS:
        if re.search(rx, text):
            if lang.startswith(("zh-tw", "yue")) and sans == "Noto Sans SC": sans, serif = "Noto Sans TC", "Noto Serif TC"
            fams.append((sans, serif))
    if re.search(r"[぀-ヿ]", text):   # Japanese text also uses kanji: the JP font covers them
        fams = [f for f in fams if f[0] != "Noto Sans SC"]
    return fams


def build(text, out_dir, lang=""):
    """Download subset fonts for the characters in `text`. Returns (css, sans_stack, serif_stack)."""
    fams = needed(text, lang)
    if not fams: return "", "", ""
    chars = "".join(sorted(set(ch for ch in text if not ch.isspace())))
    os.makedirs(out_dir, exist_ok=True)
    css_all, sans, serif = [], [], []
    for s_fam, d_fam in fams:
        for fam, weights, alias, bucket in ((s_fam, "400;500;600;700;800", "VS Sans " + s_fam, sans), (d_fam, "400;700", "VS Serif " + d_fam, serif)):
            q = urllib.parse.urlencode({"family": f"{fam}:wght@{weights}", "text": chars, "display": "block"}, safe=":;@")
            try:
                css = _get("https://fonts.googleapis.com/css2?" + q).decode()
            except Exception as e:
                try:   # some families have fewer weights
                    q = urllib.parse.urlencode({"family": fam, "text": chars}, safe=":;@"); css = _get("https://fonts.googleapis.com/css2?" + q).decode()
                except Exception:
                    log(f"could not download {fam} ({e}); using system fonts"); continue

            def save(m):
                url = m.group(1); fn = "f_" + hashlib.sha1(url.encode()).hexdigest()[:12] + ".woff2"
                p = os.path.join(out_dir, fn)
                if not os.path.exists(p): open(p, "wb").write(_get(url))
                return f"url('assets/fonts/extra/{fn}')"
            try:
                css = re.sub(r"url\((https://[^)]+)\)", save, css)
            except Exception as e:
                log(f"font file download failed for {fam}: {e}"); continue
            css_all.append(css.replace(f"font-family: '{fam}'", f"font-family: '{alias}'"))
            bucket.append(f"'{alias}'")
        sans.append(f"'{s_fam}'"); serif.append(f"'{d_fam}'")   # system font of the same name, if installed
    if css_all: log(f"{len(css_all)} font file set(s) for: {', '.join(f[0] for f in fams)}")
    return "\n".join(css_all), ", ".join(sans), ", ".join(serif)
