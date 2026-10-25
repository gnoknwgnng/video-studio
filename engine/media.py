"""Free real photos and company logos for a video (no API keys needed).

Photos:  Openverse (800M+ openly licensed images) -> Wikimedia Commons -> NASA Images
Logos:   Wikidata/Wikimedia official logo -> Simple Icons -> the company's own website icon
Every downloaded image is checked, resized and saved as a local file; credits are collected
for the release notes. Anything that fails is skipped quietly and the video still renders.
"""
import hashlib, io, json, os, re, time, urllib.error, urllib.parse, urllib.request

UA = "video-studio/1.0 (https://github.com/gnoknwgnng/video-studio; open-source explainer video maker)"
MAX_BYTES = 12 * 1024 * 1024
STOP = {"with", "from", "that", "this", "your", "their", "into", "over", "about", "happy", "people", "person", "photo", "image", "real"}


def log(*a): print("[media]", *a, flush=True)


def _get(url, timeout=25, accept=None):
    headers = {"User-Agent": UA}
    if accept: headers["Accept"] = accept
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES: raise ValueError("file too large")
                return data, r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2: time.sleep(3 * (attempt + 1)); continue
            raise


def _json(url):
    return json.loads(_get(url, accept="application/json")[0].decode("utf-8", "replace"))


def _save_image(data, ctype, out_dir, stem, max_side=1600):
    """Validate + normalise to JPEG/PNG with Pillow. SVG is kept as-is. Returns file name or None."""
    os.makedirs(out_dir, exist_ok=True)
    if "svg" in ctype or data[:200].lstrip().startswith((b"<svg", b"<?xml")):
        fn = stem + ".svg"; open(os.path.join(out_dir, fn), "wb").write(data); return fn
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)); im.load()
        if im.width < 120 or im.height < 120: return None
        im.thumbnail((max_side, max_side))
        has_alpha = im.mode in ("RGBA", "LA", "P")
        if has_alpha:
            fn = stem + ".png"; im.convert("RGBA").save(os.path.join(out_dir, fn), optimize=True)
        else:
            fn = stem + ".jpg"; im.convert("RGB").save(os.path.join(out_dir, fn), quality=86)
        return fn
    except Exception:
        return None


# ------------------------------------------------------------------ photos
def openverse(query, aspect=None, n=8):
    q = {"q": query, "page_size": n, "license_type": "commercial,modification", "mature": "false",
         "category": "photograph"}
    if aspect: q["aspect_ratio"] = aspect
    d = _json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(q))
    out = []
    for r in d.get("results", []):
        if (r.get("width") or 0) < 700: continue
        out.append({"url": r["url"], "title": r.get("title") or "", "creator": r.get("creator") or "unknown",
                    "tags": " ".join(t.get("name", "") for t in (r.get("tags") or []) if isinstance(t, dict)),
                    "license": f'CC {str(r.get("license", "")).upper()} {r.get("license_version") or ""}'.strip(),
                    "page": r.get("foreign_landing_url") or r.get("detail_url") or ""})
    return out


def wikimedia(query, n=8):
    q = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
         "gsrnamespace": 6, "gsrlimit": n, "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600}
    d = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q))
    out = []
    for p in sorted(d.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        if (ii.get("width") or 0) < 700: continue
        md = ii.get("extmetadata", {})
        lic = re.sub("<[^>]+>", "", md.get("LicenseShortName", {}).get("value", ""))
        if any(x in lic.upper() for x in ("NC", "ND", "FAIR USE")): continue
        out.append({"url": ii.get("thumburl") or ii.get("url"), "title": p.get("title", "").replace("File:", ""),
                    "creator": re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "unknown"))[:80],
                    "license": lic or "see page", "page": ii.get("descriptionurl", "")})
    return out


def nasa(query, n=5):
    d = _json("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": query, "media_type": "image"}))
    out = []
    for it in d.get("collection", {}).get("items", [])[:n]:
        links = [l["href"] for l in it.get("links", []) if l.get("render") == "image"]
        if not links: continue
        data = (it.get("data") or [{}])[0]
        out.append({"url": links[0].replace("~thumb", "~medium"), "title": data.get("title", ""), "creator": "NASA",
                    "license": "Public domain", "page": f'https://images.nasa.gov/details/{data.get("nasa_id", "")}'})
    return out


def find_photo(query, out_dir, used, credits, aspect=None):
    """Try each source in order and return a saved local file name, or None."""
    short = " ".join([w for w in query.split() if w.lower() not in STOP and len(w) > 2][:2]) or query
    sources = [("Openverse", lambda: openverse(query, aspect), 2), ("Openverse", lambda: openverse(query), 2),
               ("Wikimedia", lambda: wikimedia(query), 2), ("Openverse", lambda: openverse(short), 1),
               ("Wikimedia", lambda: wikimedia(short), 1)]
    if re.search(r"\b(space|planet|nasa|moon|mars|rocket|satellite|galaxy|earth)\b", query, re.I):
        sources.insert(0, ("NASA", lambda: nasa(query), 1))
    for name, fn, need in sources:
        try: cands = fn()
        except Exception as e:
            log(f"{name} search failed for '{query}': {e}"); continue
        # relevance check: the photo's title/tags must mention at least one real word from the search
        words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 3 and w not in STOP]
        def score(c):
            text = (c.get("title", "") + " " + c.get("tags", "")).lower()
            return sum(1 for w in words if w in text or (w.endswith("s") and w[:-1] in text))
        need = min(need, len(words))   # 2 matching words for full searches, 1 for the short fallback
        cands = sorted([c for c in cands if not words or score(c) >= need], key=score, reverse=True)
        for c in cands:
            if c["url"] in used: continue
            try:
                data, ctype = _get(c["url"])
                saved = _save_image(data, ctype, out_dir, "ph_" + hashlib.sha1(c["url"].encode()).hexdigest()[:10])
            except Exception:
                continue
            if saved:
                used.add(c["url"])
                credits.append(f'- "{c["title"][:70]}" by {c["creator"]} ({c["license"]}), via {name}: {c["page"]}')
                log(f"photo for '{query}': {name}")
                return saved
    log(f"no photo found for '{query}'")
    return None


# ------------------------------------------------------------------ the company's own website
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 video-studio"
_site_cache = {}


def site_assets(domain):
    """Read the homepage once: returns {"base", "logos": [urls], "photos": [urls]} (best first)."""
    domain = re.sub(r"^https?://", "", domain or "").split("/")[0].lower()
    if not domain or "." not in domain: return {"base": "", "logos": [], "photos": []}
    if domain in _site_cache: return _site_cache[domain]
    base = "https://" + domain
    res = {"base": base, "logos": [], "photos": []}
    try:
        req = urllib.request.Request(base, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=20) as r:
            base = r.geturl(); html = r.read(3_000_000).decode("utf-8", "replace")
    except Exception as e:
        log(f"could not read {domain}: {e}"); _site_cache[domain] = res; return res
    res["base"] = base
    absu = lambda u: urllib.parse.urljoin(base, u.strip()) if u and not u.startswith("data:") else None
    # logo declared in structured data: "logo": "https://..."
    for m in re.finditer(r'"logo"\s*:\s*(?:\{[^}]*?"url"\s*:\s*)?"([^"]+)"', html):
        u = absu(m.group(1).replace("\\/", "/"))
        if u: res["logos"].append(u)
    header = (re.search(r"<header.*?</header>", html, re.S | re.I) or re.search(r"<nav.*?</nav>", html, re.S | re.I))
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    head_imgs = re.findall(r"<img\b[^>]*>", header.group(0), re.I) if header else []
    attr = lambda tag, a: (re.search(a + r'\s*=\s*["\']([^"\']+)', tag, re.I) or [None, None])[1]
    for tag in head_imgs + imgs:   # header images first
        blob = " ".join(filter(None, [attr(tag, "src"), attr(tag, "alt"), attr(tag, "class"), attr(tag, "id")])).lower()
        if "logo" in blob:
            u = absu(attr(tag, "src"))
            if u: res["logos"].append(u)
    # photos: the page's share image, then large content images
    for prop in ("og:image", "twitter:image"):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']' + prop + r'["\'][^>]+content=["\']([^"\']+)', html, re.I) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']' + prop, html, re.I)
        if m and absu(m.group(1)): res["photos"].append(absu(m.group(1)))
    for tag in imgs:
        srcset = attr(tag, "srcset")
        src = srcset.split(",")[-1].strip().split(" ")[0] if srcset else attr(tag, "src")
        blob = (str(src) + " " + str(attr(tag, "class")) + " " + str(attr(tag, "alt"))).lower()
        if not src or any(w in blob for w in ("logo", "icon", "sprite", "avatar", "badge", "flag", ".svg", ".gif", "pixel", "tracking")): continue
        u = absu(src)
        if u: res["photos"].append(u)
    dedup = lambda xs: list(dict.fromkeys(xs))
    res["logos"], res["photos"] = dedup(res["logos"])[:6], dedup(res["photos"])[:12]
    log(f"{domain}: {len(res['logos'])} logo candidate(s), {len(res['photos'])} photo candidate(s)")
    _site_cache[domain] = res
    return res


def _too_light(data, ctype):
    """True for white/very light logos that would vanish on the light background."""
    if "svg" in ctype or data[:200].lstrip().startswith((b"<svg", b"<?xml")):
        cols = re.findall(rb'(?:fill|stroke|stop-color)\s*[:=]\s*["\']?(#[0-9a-fA-F]{3,6}|white|rgb\([^)]*\))', data)
        return bool(cols) and all(c.lower() in (b"#fff", b"#ffffff", b"white") for c in cols)
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGBA"); im.thumbnail((200, 200))
        px = [p for p in im.getdata() if p[3] > 128]
        if not px: return True
        return sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b, a in px) / len(px) > 225
    except Exception:
        return False


def logo_site(domain, out_dir):
    for u in site_assets(domain)["logos"]:
        try:
            data, ctype = _get(u, timeout=15)
            if _too_light(data, ctype): continue
            saved = _save_image(data, ctype, out_dir, "logo_site")
            if saved: return saved, "full"
        except Exception:
            continue
    return None, None


def site_photos(domain, out_dir, used, credits, n):
    out = []
    for u in site_assets(domain)["photos"]:
        if len(out) >= n: break
        if u in used: continue
        try:
            data, ctype = _get(u, timeout=20)
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            if im.width < 600 or im.height < 300: continue
            saved = _save_image(data, ctype, out_dir, "site_" + hashlib.sha1(u.encode()).hexdigest()[:10])
        except Exception:
            continue
        if saved:
            used.add(u); out.append(saved)
            credits.append(f"- Photo from {domain}: {u}")
    if out: log(f"{len(out)} photo(s) from {domain}")
    return out


# ------------------------------------------------------------------ logos
def logo_wikidata(company, out_dir):
    d = _json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "wbsearchentities", "search": company, "language": "en", "type": "item", "limit": 5, "format": "json"}))
    want = re.sub(r"[^a-z0-9]", "", company.lower())
    for ent in d.get("search", []):
        label = re.sub(r"[^a-z0-9]", "", str(ent.get("label", "")).lower())
        if label != want and re.sub(r"(inc|ltd|limited|corp|corporation|company|co)$", "", label) != want: continue
        e = _json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "wbgetentities", "ids": ent["id"], "props": "claims", "format": "json"}))
        claims = e.get("entities", {}).get(ent["id"], {}).get("claims", {})
        for c in claims.get("P154", []):  # P154 = logo image
            fname = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if not fname: continue
            url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fname.replace(" ", "_")) + "?width=1000"
            data, ctype = _get(url)
            saved = _save_image(data, ctype, out_dir, "logo_wd")
            if saved: return saved, "full"
    return None, None


def logo_simpleicons(company, out_dir, color):
    slug = re.sub(r"[^a-z0-9]", "", company.lower().replace("+", "plus").replace("&", "and"))
    data, ctype = _get(f"https://cdn.simpleicons.org/{slug}/{color.lstrip('#')}")
    saved = _save_image(data, "image/svg+xml", out_dir, "logo_si")
    return (saved, "icon") if saved else (None, None)


def logo_website(domain, out_dir):
    domain = re.sub(r"^https?://", "", domain).split("/")[0].lower()
    if not domain or "." not in domain: return None, None
    base = "https://" + domain
    html = _get(base, timeout=15)[0].decode("utf-8", "replace")
    cands = []
    for tag in re.findall(r"<link[^>]+>", html, re.I):
        rel = re.search(r'rel=["\']([^"\']+)', tag, re.I); href = re.search(r'href=["\']([^"\']+)', tag, re.I)
        if rel and href and ("apple-touch-icon" in rel.group(1).lower() or "icon" in rel.group(1).lower()):
            size = re.search(r'sizes=["\'](\d+)', tag)
            cands.append((int(size.group(1)) if size else (180 if "apple" in rel.group(1).lower() else 32), urllib.parse.urljoin(base, href.group(1))))
    cands.append((180, base + "/apple-touch-icon.png"))
    for _, url in sorted(cands, reverse=True):
        try:
            data, ctype = _get(url, timeout=15)
            saved = _save_image(data, ctype, out_dir, "logo_web")
            if saved: return saved, "icon"
        except Exception:
            continue
    return None, None


def logo_favicon_service(domain, out_dir):
    """Large site icon via Google's free favicon service (no key)."""
    domain = re.sub(r"^https?://", "", domain).split("/")[0].lower()
    if not domain or "." not in domain: return None, None
    data, ctype = _get(f"https://www.google.com/s2/favicons?domain={domain}&sz=256")
    saved = _save_image(data, ctype, out_dir, "logo_fav")
    return (saved, "icon") if saved else (None, None)


def find_logo(company, domain, out_dir, color):
    for name, fn in (("company website", lambda: logo_site(domain, out_dir)),
                     ("Wikidata", lambda: logo_wikidata(company, out_dir)),
                     ("Simple Icons", lambda: logo_simpleicons(company, out_dir, color)),
                     ("website", lambda: logo_website(domain, out_dir)),
                     ("favicon service", lambda: logo_favicon_service(domain, out_dir))):
        try:
            saved, kind = fn()
            if saved:
                log(f"logo for '{company}': {name} ({kind})"); return saved, kind
        except Exception as e:
            log(f"{name} logo lookup failed: {e}")
    log(f"no logo found for '{company}'; using the name as text")
    return None, None


# ------------------------------------------------------------------ main hook
def enrich(cfg, media_dir):
    """Fill missing logo/photos in cfg using its "images" hints. Returns credit lines (may be empty)."""
    credits, used = [], set()
    hints = cfg.get("images") or {}
    if hints.get("enabled") is False: return credits
    company, domain = cfg.get("company", ""), hints.get("logo_domain") or cfg.get("url", "")
    # only real companies/products get a logo lookup (the AI leaves logo_domain empty for general topics)
    if not cfg.get("logo") and hints.get("logo", True) and company and hints.get("logo_domain"):
        saved, kind = find_logo(company, domain, media_dir, cfg.get("colors", {}).get("primary", "#024c87"))
        if saved: cfg["logo"], cfg["logo_kind"] = saved, kind
    # photos from the company's own website: only when allowed ("site_photos": true), since they are the company's property
    site = site_photos(domain, media_dir, used, credits, 6) if hints.get("site_photos") and domain else []
    for s in cfg.get("scenes", []):
        q = s.get("image_query")
        if s["type"] == "intro" and not s.get("photos"):
            qs = s.get("image_queries") or ([q] if q else [])
            mine = [site.pop(0) for _ in range(min(2, len(site)))]
            s["photos"] = mine + [p for p in (find_photo(x, media_dir, used, credits, "wide") for x in qs[:2 - len(mine)]) if p]
        elif s["type"] in ("problem", "end", "question", "steps") and (q or site) and not s.get("photo"):
            s["photo"] = site.pop(0) if site else find_photo(q, media_dir, used, credits, "tall")
    return credits
