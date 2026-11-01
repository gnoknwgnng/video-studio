"""Graphics drawn in code: 2,292 Lucide icons (ISC licence) and a world map (svg-maps, CC BY 4.0).

  icon_svg("smartphone")          -> <svg> for any icon name; unknown names are matched to the closest icon
  resolve_icon("payment")         -> "credit-card"   (by name, synonyms and Lucide's own tags)
  country_id("India") / ("in")    -> "in"
  python engine/visuals.py money  -> list matching icons
"""
import json, os, re, difflib

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_icons = _world = None

# words people (and LLMs) use -> Lucide icon names
SYN = {
    "money": "banknote", "cash": "banknote", "payment": "credit-card", "pay": "credit-card", "card": "credit-card", "bank": "landmark",
    "upi": "smartphone", "phone": "smartphone", "mobile": "smartphone", "app": "smartphone", "qr": "qr-code", "scan": "scan-line",
    "rupee": "indian-rupee", "inr": "indian-rupee", "dollar": "dollar-sign", "usd": "dollar-sign", "euro": "euro", "price": "tag",
    "growth": "trending-up", "increase": "trending-up", "decline": "trending-down", "decrease": "trending-down", "chart": "chart-column",
    "graph": "chart-line", "stats": "chart-column", "data": "database", "ai": "brain-circuit", "robot": "bot", "brain": "brain",
    "idea": "lightbulb", "bulb": "lightbulb", "rocket": "rocket", "launch": "rocket", "startup": "rocket", "goal": "target", "target": "target",
    "time": "clock", "fast": "zap", "speed": "zap", "instant": "zap", "energy": "zap", "power": "zap", "secure": "shield-check",
    "security": "shield-check", "safe": "shield-check", "privacy": "lock", "password": "key-round", "pin": "key-round", "lock": "lock",
    "user": "user", "person": "user", "people": "users", "team": "users", "community": "users", "customer": "user-round",
    "job": "briefcase", "work": "briefcase", "hiring": "user-plus", "career": "briefcase", "office": "building-2", "company": "building-2",
    "factory": "factory", "shop": "store", "store": "store", "merchant": "store", "shopping": "shopping-cart", "cart": "shopping-cart",
    "delivery": "truck", "shipping": "truck", "package": "package", "parcel": "package", "home": "house", "house": "house",
    "school": "graduation-cap", "education": "graduation-cap", "student": "graduation-cap", "learn": "book-open", "book": "book-open",
    "health": "heart-pulse", "hospital": "hospital", "doctor": "stethoscope", "medicine": "pill", "food": "utensils", "water": "droplet",
    "rain": "cloud-rain", "weather": "cloud-sun", "sun": "sun", "climate": "thermometer", "earth": "earth", "world": "globe", "global": "globe",
    "internet": "globe", "web": "globe", "website": "globe", "network": "network", "cloud": "cloud", "server": "server", "code": "code",
    "email": "mail", "mail": "mail", "message": "message-circle", "chat": "message-circle", "call": "phone", "video": "video",
    "camera": "camera", "photo": "image", "music": "music", "game": "gamepad-2", "car": "car", "train": "train-front", "flight": "plane",
    "plane": "plane", "travel": "plane", "map": "map", "location": "map-pin", "city": "building", "law": "scale", "justice": "scale",
    "government": "landmark", "vote": "vote", "election": "vote", "war": "swords", "peace": "dove" if False else "hand-heart",
    "news": "newspaper", "warning": "triangle-alert", "alert": "triangle-alert", "problem": "circle-alert", "error": "circle-x",
    "check": "circle-check", "done": "circle-check", "success": "badge-check", "verified": "badge-check", "star": "star", "award": "award",
    "trophy": "trophy", "win": "trophy", "gift": "gift", "heart": "heart", "love": "heart", "tooth": "smile", "dental": "smile",
    "document": "file-text", "paper": "file-text", "paperwork": "files", "contract": "file-signature", "invoice": "receipt",
    "receipt": "receipt", "tax": "receipt-indian-rupee", "insurance": "shield-plus", "claim": "file-check", "search": "search",
    "settings": "settings", "tool": "wrench", "tools": "wrench", "build": "hammer", "calendar": "calendar", "date": "calendar",
    "battery": "battery-charging", "electric": "plug-zap", "solar": "sun", "plant": "sprout", "tree": "tree-pine", "farm": "tractor",
    "investment": "piggy-bank", "savings": "piggy-bank", "stock": "candlestick-chart", "market": "chart-candlestick", "crypto": "bitcoin",
    "salary": "wallet", "wage": "wallet", "income": "wallet", "wallet": "wallet", "inflation": "trending-up", "loan": "hand-coins",
    "debt": "hand-coins", "profit": "trending-up", "loss": "trending-down", "revenue": "chart-no-axes-combined", "budget": "calculator",
    "question": "circle-help", "help": "life-buoy", "support": "headphones", "time-saving": "timer", "speaker": "mic", "podcast": "mic",
    "drone": "plane", "satellite": "satellite", "space": "rocket", "moon": "moon", "fire": "flame", "eye": "eye", "click": "mouse-pointer-click",
}


def _load():
    global _icons
    if _icons is None:
        _icons = json.load(open(os.path.join(DATA, "icons.json"), encoding="utf-8"))
    return _icons


def resolve_icon(name, default="sparkles"):
    """Closest Lucide icon for any word or phrase ("UPI payment" -> "smartphone")."""
    d = _load(); icons, tags = d["icons"], d["tags"]
    raw = str(name or "").strip().lower()
    if not raw: return default
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if slug in icons: return slug
    words = [w for w in re.split(r"[^a-z0-9]+", raw) if w]
    for w in [slug] + words[::-1]:          # the last word is usually the main noun ("electric car" -> car)
        if w in SYN and SYN[w] in icons: return SYN[w]
        if w in icons: return w
        if w.endswith("s") and w[:-1] in icons: return w[:-1]
    best, score = None, 0
    for k, tg in tags.items():   # Lucide's tags: "banknote" -> ["bill", "currency", "money", ...]
        s = sum(2 if w in tg else 0 for w in words) + sum(1 for w in words if w in k.split("-"))
        if s > score: best, score = k, s
    if best: return best
    return default


def icon_svg(name, cls="ico", size=None, stroke=None):
    n = resolve_icon(name)
    inner = _load()["icons"][n]
    sz = f' width="{size}" height="{size}"' if size else ""
    sw = stroke or 1.9
    return (f'<svg class="{cls}" data-icon="{n}" viewBox="0 0 24 24"{sz} fill="none" stroke="currentColor" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')


# ------------------------------------------------------------------ stickers: icons for key spoken words
STICKER_WORDS = set(SYN) | {"phone", "car", "bus", "train", "bike", "book", "coffee", "pizza", "dog", "cat", "house", "rocket", "trophy",
    "clock", "camera", "laptop", "computer", "key", "gift", "wallet", "heart", "star", "fire", "bell", "map", "globe", "sun", "moon",
    "cloud", "umbrella", "tree", "leaf", "mountain", "ship", "anchor", "factory", "hospital", "school", "church", "landmark", "bitcoin",
    "headphones", "microphone", "mic", "newspaper", "pen", "pencil", "calculator", "printer", "tv", "television", "radio", "wifi",
    "bluetooth", "battery", "lightbulb", "magnet", "flask", "atom", "dna", "pill", "syringe", "stethoscope", "baby", "apple", "carrot",
    "fish", "bird", "bug", "flower", "sprout", "wheat", "tractor", "truck", "plane", "helicopter", "sailboat", "medal", "crown", "diamond",
    "coins", "bank", "chart", "email", "inbox", "calendar", "lock", "shield", "eye", "brain", "robot", "ai", "code", "server", "database"}
STICKER_ALIAS = {"phones": "phone", "smartphone": "phone", "smartphones": "phone", "cars": "car", "books": "book", "dogs": "dog",
    "rupees": "rupee", "dollars": "dollar", "jobs": "job", "students": "student", "schools": "school", "trees": "tree", "houses": "house",
    "homes": "home", "computers": "computer", "laptops": "laptop", "emails": "email", "messages": "message", "payments": "payment",
    "banks": "bank", "farmers": "farm", "farmer": "farm", "coins": "coins", "rockets": "rocket", "ideas": "idea", "goals": "goal",
    "customers": "customer", "users": "user", "teams": "team", "videos": "video", "photos": "photo", "games": "game", "cities": "city",
    "planes": "plane", "trains": "train", "doctors": "doctor", "hospitals": "hospital", "deliveries": "delivery", "orders": "package",
    "salaries": "salary", "loans": "loan", "taxes": "tax", "elections": "election", "votes": "vote", "robots": "robot", "apps": "app"}


def sticker_for(word):
    """A Lucide icon for a spoken key word, or None (only clear, concrete words get a sticker)."""
    w = re.sub(r"[^a-z]", "", str(word).lower())
    if len(w) < 2: return None
    w = STICKER_ALIAS.get(w, w)
    if w not in STICKER_WORDS: return None
    n = resolve_icon(w)
    return None if n == "sparkles" else n


# ------------------------------------------------------------------ world map
def world():
    global _world
    if _world is None: _world = json.load(open(os.path.join(DATA, "world.json"), encoding="utf-8"))
    return _world


ALIASES = {"usa": "us", "united states": "us", "america": "us", "us": "us", "uk": "gb", "britain": "gb", "england": "gb",
           "united kingdom": "gb", "russia": "ru", "south korea": "kr", "korea": "kr", "north korea": "kp", "uae": "ae", "dubai": "ae",
           "iran": "ir", "syria": "sy", "vietnam": "vn", "laos": "la", "czechia": "cz", "czech republic": "cz", "palestine": "ps",
           "gaza": "ps", "west bank": "ps", "taiwan": "tw", "bolivia": "bo", "venezuela": "ve", "tanzania": "tz", "congo": "cd",
           "drc": "cd", "ivory coast": "ci", "turkey": "tr", "turkiye": "tr", "holland": "nl", "the netherlands": "nl", "moldova": "md"}


def country_id(name):
    w = world()["countries"]; s = str(name or "").strip().lower()
    if not s: return None
    if s in w: return s
    if s in ALIASES and ALIASES[s] in w: return ALIASES[s]
    for k, v in w.items():
        if v["name"].lower() == s: return k
    close = difflib.get_close_matches(s, [v["name"].lower() for v in w.values()], n=1, cutoff=0.8)
    if close: return next(k for k, v in w.items() if v["name"].lower() == close[0])
    return None


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "money"
    print("best:", resolve_icon(q))
    print("names containing it:", [k for k in _load()["icons"] if q in k][:30])
