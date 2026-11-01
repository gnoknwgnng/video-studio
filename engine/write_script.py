"""Topic (or any pasted text) -> video.json, written by an LLM on Groq, in any language.

  export GROQ_API_KEY=gsk_...            # never put the key in a file in this repo
  python engine/write_script.py "How UPI payments work"
  python engine/write_script.py "UPI kaise kaam karta hai" --lang hi --voice male --duration short
  python engine/write_script.py "Top 5 mistakes first-time founders make" --format listicle --tone funny --theme dark
  python engine/write_script.py "<paste a job post, press release or article>" --lang ta

Steps: (1) understand the input (pasted posts are digested into facts), (2) research current facts
(Tavily if TAVILY_API_KEY is set, Wikipedia always), (3) draft, (4) automatic checks sent back to the model
until they pass, (5) an editor pass for facts, grammar and flow. Writes videos/<folder>/video.json.

  python engine/write_script.py --upgrade videos/docsdocs   # rewrite an existing script picture-first (keeps facts + voice lines)
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
sys.path.insert(0, ENGINE)
import languages as LANG  # noqa: E402
import timing as TM       # noqa: E402
import research as RS     # noqa: E402
import visuals as VIS     # noqa: E402

API = os.environ.get("GROQ_API_URL") or "https://api.groq.com/openai/v1/chat/completions"   # any OpenAI-compatible endpoint works
TYPES = ["spotlight", "photo", "gallery", "chart", "flow", "icons", "versus", "map", "pictogram", "kpis", "bubbles", "gauge", "funnel", "cycle",
         "chat", "reveal", "hook", "problem", "number", "stats", "intro", "steps",
         "timeline", "list", "flip", "compare", "question", "quote", "broll", "presenter", "website", "end"]
PICTURE = {"photo", "gallery", "chart", "flow", "icons", "versus", "map", "broll", "number", "stats", "presenter", "website",
           "pictogram", "kpis", "bubbles", "gauge", "funnel", "cycle", "chat", "reveal", "spotlight"}
TEXT_LED = {"hook", "question", "quote", "compare", "flip"}
SUPPORT = {"problem", "intro", "steps", "timeline", "list"}   # text-heavy layouts; visualize() turns them into picture scenes
CHART_KINDS = ("bar", "column", "line", "donut", "pie")
ICONS = ["document", "tooth", "heart", "shield", "building", "box", "chip", "phone", "globe", "rocket", "bulb", "bag", "user",
         "briefcase", "lock", "chart", "leaf", "book", "home", "cap", "mail", "chat", "bolt", "cloud", "cross", "coin"]
FORMATS = {
    "auto": "choose the best structure for the topic, picture scenes first",
    "explainer": "spotlight or photo -> flow (how it works) -> gallery or icons -> chart or number -> versus -> end",
    "product": "spotlight (mood bad: the pain) -> number or chart -> spotlight or gallery (the product) -> website (if it has one) -> flow -> versus -> end",
    "listicle": "photo or spotlight -> gallery (photos) or icons -> chart, kpis or number -> icons -> end",
    "news": "photo -> map (where it happened) -> chart or number -> flow (what happened) -> icons (what it means) -> end",
    "story": "photo -> map -> flow (the turning points) -> number or chart -> reveal (before/after) -> end",
    "tutorial": "photo or spotlight -> flow (the steps) -> icons (mistakes to avoid) -> reveal or versus -> end",
    "comparison": "spotlight or photo -> versus -> chart (bar or column) -> bubbles or kpis -> end",
    "hiring": "spotlight (kicker \"We're hiring\", satellites = the roles) -> gallery (the workplace) -> icons (perks) -> kpis (pay, openings) -> map (if locations) -> end (how to apply)",
    "pitch": "presenter -> spotlight (mood bad: the problem) -> number -> flow -> versus -> end (the ask)",
    "motivational": "photo -> spotlight -> icons -> broll -> end",
    "announcement": "spotlight (mood good) -> gallery or icons (what's new) -> chart, kpis or number -> flow -> end (call to action)",
}
DURATIONS = {"short": (20, 35), "standard": (35, 55), "long": (60, 100)}
TONES = ["energetic", "friendly", "professional", "dramatic", "funny", "calm", "inspirational", "authoritative", "casual"]

SYSTEM = """You write scripts for vertical (9:16) videos with an AI voiceover, for Reels, Shorts and TikTok. You adapt to ANY topic:
products, companies, education, news, history, how-tos, lists, hiring, personal pitches, announcements.
Return ONLY one JSON object (no markdown):
{"company":"<subject name, 1-3 words, shown big; the real company/brand/person/topic name>","url":"<website or empty>",
 "colors":{"primary":"#hex","accent":"#hex","alert":"#hex","ink":"#hex","background":"#hex"},"theme":"light|dark",
 "music":"upbeat|calm|dramatic|tech|news","images":{"logo_domain":"<company domain, or empty for general topics>"},
 "scenes":[...]}

Every scene: {"type":..., <fields>, "lines":[{"say":"<spoken sentence(s)>","sub":"<optional subtitle spelling>","seed":<int>}]}.
Scene types (fields; w = words). PICTURE scenes first:
- spotlight {kicker:1-3w, title:1-4w (optional), icon:<the subject as one icon>, satellites:[3-6 {icon, label:1-2w, cue}], mood:"bad"|"good",
  climax_cue (optional), caption:<=5w (optional)} a big line-drawn icon; related icons fly in and orbit it as they are named, then a climax:
  "bad" = shake + red (a problem, pain, risk), "good" = glow + burst (a win, solution, benefit). The best OPENER and a great closer before "end".
- photo {kicker:1-4w, caption:2-5w, caption_em:1-4w, image_query} one full-screen real photo. Great opener and breather.
- gallery {kicker, title:2-5w, tiles:[2-4 {label:1-3w, icon, image_query, cue}]} photo tiles that pop in as each is named (examples, kinds, places, products).
- chart {kind:"bar"|"column"|"line"|"donut"|"pie", kicker, title:2-5w, unit:"%"/"B"/" cr"..., source:"<who measured it>", highlight:<label>, data:[2-8 {label:1-3w, value:<number>, display:"<optional text>", icon, cue}]}
  line = change over time; column/bar = compare amounts; donut/pie = parts of a whole (center, center_label optional). REAL figures only.
- flow {kicker, title:2-5w, nodes:[3-5 {label:1-3w, sub:<=4w optional, icon, cue}]} a process / journey / how it works, arrows between nodes.
- icons {kicker, title:2-5w, items:[3-6 {label:1-3w, icon, cue}]} ideas, benefits, features, tips shown as big icons.
- versus {kicker, title, left:{label:1-3w, image_query, points:[2-3 x 2-5w], cue}, right:{...}} two things side by side (then/now, A vs B).
- map {kicker, title, places:[1-6 {country:<English country name>, label:<1-3w in the video language>, value:<optional short figure>, cue}]} where something is or happened.
- pictogram {kicker, total:10|20|100, highlight:<how many of total>, icon:"user", display:"1 in 5", label:2-5w, label_em:1-3w, cue} a share of people/things.
- kpis {kicker, title, items:[2-4 {value:<number>, prefix, suffix, label:2-4w, icon, cue}]} several key figures at once, counting up.
- bubbles {kicker, title, unit, items:[2-5 {label:1-3w, value, display, icon, cue}], note} sizes compared (circles sized by value).
- gauge {kicker, title, value:0-100, suffix:"/100" or "%", zones:[3 x 1w], label:2-4w, label_em, cue} a score, rating, risk or level.
- funnel {kicker, title, stages:[3-5 {label:1-3w, value, display, icon, cue}]} numbers that narrow step by step (applicants -> hired).
- cycle {kicker, title, center:1-2w, nodes:[3-6 {label:1-2w, icon, cue}]} a repeating loop (water cycle, plan-do-review).
- chat {kicker, name:<who the "them" side is>, messages:[2-6 {from:"me"|"them", text:<=10w, cue}]} a conversation; one line per message, "voice" may differ per speaker.
- reveal {kicker, title, before:{label:1-2w, image_query, cue}, after:{label, image_query, cue}, caption:<=6w} a before/after transformation with photos.
- number {kicker, value:<number>, prefix, suffix ("%", "+", " crore"), percent:true for %, label:2-5w, label_em:1-3w, note:<=10w, cue, image_query} ONE striking real figure.
- broll {kicker, caption:2-5w, caption_em:1-3w, video_query:<3-6 English words of real footage>, image_query} full-screen footage.
- presenter {name, role, points:[2-4 {text:1-4w, cue}]} a real person the video is about or by.
- website {url:<domain>, kicker, title:3-6w} only for ONE specific company/product with a real website.
Supporting scenes (keep few):
- hook {kicker:2-4w, text:4-8w, em:2-5w ending the sentence, highlight:<one word>, image_query} big statement, word by word.
- problem {kicker, title:3-5w, title_em:2-4w, alert_word:<last word of title_em>, icon, meter_label:2w, cards:[4 {text:2-3w, icon, cue}]} a pain; the line names the 4 cards.
- stats {label:<=6w, bars:[2-3 {name:1-2w, value:0-100, display:"55%", cue}], callout:{em:"1 in 5", text:<=8w, people:5, empty:1, cue, empty_cue}} real figures; callout only with a "1 in N" fact.
- intro {logo_cue:<word right after the name>, tagline:3-5w, tagline_em:1-3w, tagline_cue, tags:[3 {text:1-3w, cue}] (last tag "highlight":true, no cue), image_queries:[2]} introduces the subject.
- steps {title:2-4w, steps:[3 {title:2-4w, icon, chips:[2-3 x 1-2w], image_query (optional), cue:<first word of its line>}]} one line per step.
- timeline {title:2-5w, events:[3-5 {date, text:3-6w, image_query (optional), cue}]} dated events in order.
- list {kicker, title:2-6w, items:[3-5 {text:2-5w, note:<=5w, icon, image_query, cue}], countdown:false} tips, top-N, mistakes.
- flip {title:3-4w, title_em:1-2w, front:{kicker, title:2-3w, rows:[3 {k,v}] (last "style":"alert"), stamp:<1 CAPS word>, cue}, back:{kicker, title, rows:[3 {k,v}] (2nd "style":"ok"+"cue", 3rd "style":"primary"+"cue")}}
- compare {left_label:1-3w, right_label:<company exactly>, rows:[3-4 {left:2-5w, right:2-5w, left_cue, right_cue}]}
- question {pre:"So what makes", em:<company exactly>, post:"different?", em_cue, mark_cue}
- quote {text:<=20w, author, role, cue:<word of the author's name as spoken>} ONLY a verbatim quote from FACTS/notes.
- end {tagline:2-4w, tagline_em:2-4w, logo_cue:<subject name as spoken, last word of the line>, tagline_cue:<first word of the line>, image_query} ALWAYS LAST.
"icon" = a simple English noun or a Lucide icon name (smartphone, landmark, truck, graduation-cap, chart-line, users, shield-check, map-pin, wallet...).
"image_query" = 3-6 plain English words naming a concrete, photographable thing (no text, logos, abstract ideas or famous people).

SHOW, DON'T WRITE (most important):
- At least three quarters of the scenes are PICTURE scenes; at most ONE "supporting" scene in the whole video.
- Open with a picture, not a sentence: a "spotlight" (mood "bad" for a problem hook) or a "photo". Use "hook" only when a line of text is the point.
- Keep on-screen words to a minimum: titles are optional in picture scenes; let icons, photos and numbers carry the meaning.
- Numbers -> chart or number scene. A series of numbers -> chart. Several key figures -> kpis. A share of people -> pictogram.
  Sizes compared -> bubbles. A score or level -> gauge. Numbers that narrow -> funnel. Places -> map. A process or journey -> flow.
  A repeating loop -> cycle. Examples or kinds of things -> gallery (photos) or icons. Two options or then/now -> versus.
  A transformation -> reveal. A conversation, complaint or DM -> chat. Use a variety: avoid repeating the same scene type.
- Every item of cards/steps/list/icons/tiles/nodes has an "icon". Photos for tiles, versus sides and list items when they are real things.
- On-screen labels are 1-4 words; the voice carries the detail.

RULES
- First 7 spoken words = a scroll-stopping hook (surprising fact, bold claim, question). No greetings, no "welcome", no "in this video", no company name first.
- Spoken lines: short, punchy, natural speech. One idea per sentence. No lists of nouns read aloud without verbs. No filler.
- Every "cue"/"*_cue" is ONE word copied exactly from the "say" text of THAT scene, in the order the visuals appear.
- On-screen text is short (see word limits) and never repeats title/title_em or tagline/tagline_em.
- Use the exact "company" text as question.em and compare.right_label.
- Facts: numbers, dates, names and quotes must come from FACTS or the creator's notes, or be well-known stable facts. Never invent statistics. If unsure, say it without a number.
- Seeds: 42, 43, 44... one per line.
- Colours: primary = strong brand/topic colour; accent = lighter related hue; alert = red/orange; ink = near-black; background = near-white (light theme) or near-black (dark theme).

EXAMPLE scenes (style and quality bar only; different topic):
{"type":"spotlight","kicker":"Every Friday","icon":"file-text","mood":"bad","satellites":[{"icon":"sheet","label":"Spreadsheets","cue":"spreadsheets"},{"icon":"copy","label":"Copy-paste","cue":"copy"},{"icon":"moon","label":"Late nights","cue":"late"},{"icon":"mail-warning","label":"Angry emails","cue":"angry"}],"lines":[{"say":"Every Friday it's the same. Spreadsheets, copy and paste, late nights, and angry emails.","seed":41}]}
{"type":"photo","kicker":"One click","caption":"Every page you open","caption_em":"crosses the world.","image_query":"person using laptop at night","lines":[{"say":"Every web page you open crosses the world in under a second.","seed":42}]}
{"type":"flow","title":"Where your click goes","nodes":[{"label":"Your phone","icon":"smartphone","cue":"phone"},{"label":"Router","icon":"router","cue":"router"},{"label":"Undersea cables","icon":"cable","cue":"cables"},{"label":"Data center","icon":"server","cue":"center"}],"lines":[{"say":"Your phone sends it to your router, along undersea cables, and into a data center.","seed":43}]}
{"type":"chart","kind":"line","title":"People online","unit":"B","source":"ITU estimates","data":[{"label":"2005","value":1.0,"cue":"two"},{"label":"2015","value":3.2},{"label":"2023","value":5.4,"cue":"today"}],"lines":[{"say":"In two thousand five, one billion people were online. Today, more than five billion.","seed":44}]}
{"type":"end","tagline":"Fifty years old.","tagline_em":"Still day one.","logo_cue":"internet","tagline_cue":"fifty","lines":[{"say":"Fifty years old, and still day one. That's the internet.","seed":50}]}
"""

LANG_RULES = {
    "en": 'Write names the way they should SOUND in "say" (e.g. "Docs, Docs", "U P I") and add "sub" with the real spelling. '
          'Write numbers and years in "say" as spoken words ("nineteen eighty-three", "two thousand"), with digits in "sub".',
    "hinglish": 'Write "say" in Hinglish: Hindi in Latin script mixed with English, the way Indian creators talk ("Aaj hum dekhenge ki UPI kaise kaam karta hai"). '
                'On-screen text in simple English or Hinglish. Numbers in "say" as spoken words, digits in "sub".',
    "other": 'Write ALL "say" text and ALL on-screen text in {name}, in natural everyday {name} (not a literal translation). '
             'Use the normal {name} script. Brand names may stay in their usual spelling. Numbers in "say" as spoken words, digits in "sub" if needed. '
             'Keep JSON keys, "type" values, icons, colours, image_query and video_query in English. Cue words are copied exactly from the {name} "say" text{nospace}.',
}

REVIEW = """You are the editor of this video script. Return the FULL corrected JSON only, same format and rules.
Check and fix: (1) the first 7 words hook hard, no greetings; (2) length fits the target; (3) facts: remove or soften anything not supported
by the FACTS/notes, never invent numbers or quotes; (4) narration is natural spoken {lang}, grammatical, punchy, no awkward repetition;
(5) on-screen text is short, correct and in {lang}; (6) every cue word appears in its own scene's "say" text; (7) no absolute claims
(always, never, guaranteed, zero) unless strictly true; (8) keep it visual: keep picture scenes (photo, gallery, chart, flow, icons, versus, map),
never turn them into text, and remove any chart figure not supported by the FACTS/notes. If everything is already good, return it unchanged."""

DIGEST_SYSTEM = """You are an expert video producer. The user gave text that may be a short topic, or a pasted job post, flyer, announcement,
press release, article or notes. Return ONLY JSON:
{"company":"<the TRUE subject: company/brand/person/organisation/topic, 1-3 words; for job posts the actual employer, never 'Job Opening' or 'Hiring'>",
 "topic":"<crisp 4-10 word video title>","format":"<one of: FORMATS>","url":"<website if mentioned, else empty>",
 "notes":"<bullet list of EVERY important fact: numbers, dates, names, roles, pay, locations, perks, requirements, deadlines, contact/apply instructions>"}"""


def log(*a): print("[script]", *a, flush=True)


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:40].strip("-")
    return s or "video-" + time.strftime("%m%d-%H%M%S")   # titles in other scripts get a dated name


def models():
    main = os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"
    fb = [m.strip() for m in os.environ.get("GROQ_FALLBACK_MODELS", "llama-3.3-70b-versatile,openai/gpt-oss-20b").split(",") if m.strip()]
    return [main] + [m for m in fb if m != main]


def call_groq(messages, key, model=None, temperature=0.5, effort="medium", max_out=3600):
    tried = []
    for m in ([model] if model else []) + [x for x in models() if x != model]:
        tried.append(m)
        try:
            return _call(messages, key, m, temperature, effort, max_out)
        except _TryNext as e:
            log(f"model {m} unavailable ({e}); trying the next one")
    sys.exit(f"No Groq model worked (tried: {', '.join(tried)}). Check GROQ_API_KEY and GROQ_MODEL.")


class _TryNext(Exception):
    pass


def _call(messages, key, model, temperature, effort, max_out):
    body = {"model": model, "messages": messages, "temperature": temperature, "max_completion_tokens": max_out,
            "response_format": {"type": "json_object"}}
    if "gpt-oss" in model: body["reasoning_effort"] = effort
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "video-studio"})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:600]
            if e.code in (429, 500, 502, 503) and attempt < 7:
                # free tier = a few thousand tokens per minute: wait as long as Groq asks, then retry
                m = re.search(r"try again in ([\d.]+)(ms|s|m)", msg)
                wait = float(m.group(1)) * {"ms": 0.001, "s": 1, "m": 60}[m.group(2)] if m else 0
                if wait > 120: raise _TryNext("daily limit reached")
                wait = max(wait + 2, 6 * (attempt + 1)) if e.code == 429 else 5 * (attempt + 1)
                log(f"Groq {'rate limit' if e.code == 429 else 'busy'}; waiting {wait:.0f}s")
                time.sleep(min(wait, 65)); continue
            if e.code == 401: sys.exit("Groq rejected the API key (401). Check the GROQ_API_KEY secret.")
            if e.code in (404,) or "model" in msg.lower() and ("not found" in msg.lower() or "decommission" in msg.lower() or "does not exist" in msg.lower()):
                raise _TryNext(f"HTTP {e.code}")
            if e.code == 413: raise _TryNext("request too large for this model's free tier")
            if e.code == 400 and "json" in msg.lower() and "response_format" in body:
                body.pop("response_format"); req.data = json.dumps(body).encode(); continue
            if e.code == 429: raise _TryNext("rate limited")
            sys.exit(f"Groq API error {e.code}: {msg}")
        except urllib.error.URLError as e:
            if attempt < 3: time.sleep(5); continue
            sys.exit(f"Could not reach Groq: {e}")
    raise _TryNext("no answer")


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a: return json.loads(text[a:b + 1])
        raise


# ------------------------------------------------------------------ checks
def spoken(scene):
    return " ".join(str(ln.get("say", "")) for ln in scene.get("lines", []))


def count_units(text, lang):
    """Words (or characters / 2 for languages without spaces) - compared with LANG.rate to estimate seconds."""
    if LANG.no_spaces(lang): return len(TM.norm(text))
    return len(str(text).split())


def word_range(duration, lang):
    lo, hi = DURATIONS.get(duration, DURATIONS["standard"])
    r = LANG.rate(lang)
    return int(lo * r * 0.92), int(hi * r * 1.05)


def scene_limits(duration):
    return {"short": (4, 7), "standard": (5, 9), "long": (7, 14)}.get(duration, (5, 9))


def iter_cues(s):
    for k, v in s.items():
        if k.endswith("cue") and isinstance(v, str): yield k, v
    for key in ("cards", "tags", "steps", "bars", "rows", "events", "items", "points"):
        for j, it in enumerate(s.get(key, []) or []):
            if isinstance(it, dict):
                for k, v in it.items():
                    if k.endswith("cue") and isinstance(v, str): yield f"{key}[{j}].{k}", v
    co = s.get("callout")
    if isinstance(co, dict):
        for k, v in co.items():
            if k.endswith("cue") and isinstance(v, str): yield f"callout.{k}", v
    for side in ("front", "back"):
        f = s.get(side)
        if isinstance(f, dict):
            if isinstance(f.get("cue"), str): yield f"{side}.cue", f["cue"]
            for j, r in enumerate(f.get("rows", []) or []):
                if isinstance(r, dict) and isinstance(r.get("cue"), str): yield f"{side}.rows[{j}].cue", r["cue"]


def on_screen(s):
    keys = ("title", "title_em", "kicker", "tagline", "tagline_em", "label", "label_em", "em", "pre", "post", "left_label", "right_label",
            "meter_label", "text", "caption", "caption_em", "name", "role", "author", "note")
    for k in keys:
        if isinstance(s.get(k), str): yield k, s[k]
    for key, fields in (("cards", ("text",)), ("tags", ("text",)), ("steps", ("title",)), ("rows", ("left", "right")), ("bars", ("name",)),
                        ("events", ("date", "text")), ("items", ("text", "note")), ("points", ("text",))):
        for j, it in enumerate(s.get(key, []) or []):
            if isinstance(it, dict):
                for f in fields:
                    if isinstance(it.get(f), str): yield f"{key}[{j}].{f}", it[f]


def validate(cfg, opts):
    """Problems the LLM must fix (empty list = good)."""
    errs, lang, duration = [], opts["lang"], opts["duration"]
    if not isinstance(cfg, dict): return ["Top level must be a JSON object."]
    if not str(cfg.get("company", "")).strip(): errs.append('Missing "company".')
    sc = cfg.get("scenes")
    lo_n, hi_n = scene_limits(duration)
    if not isinstance(sc, list) or not (lo_n <= len(sc) <= hi_n + 1):
        return errs + [f'"scenes" must be a list of {lo_n}-{hi_n} scenes.']
    types = [s.get("type") if isinstance(s, dict) else None for s in sc]
    if types[-1] != "end": errs.append('The last scene must be type "end".')
    if types[0] in ("end", "intro", "question", "compare", "chart", "funnel", "kpis"): errs.append(f'Scene 1 cannot be "{types[0]}"; open with a hook (hook, problem, number, timeline, list, presenter or broll).')
    if types.count("end") > 1: errs.append('Only one "end" scene.')
    for i, s in enumerate(sc, 1):
        t = s.get("type")
        if t not in TYPES: errs.append(f'Scene {i}: unknown type "{t}". Use one of: {", ".join(TYPES)}.'); continue
        lines = s.get("lines")
        if not isinstance(lines, list) or not lines or any(not isinstance(l, dict) or not str(l.get("say", "")).strip() for l in lines):
            errs.append(f'Scene {i} ({t}): needs "lines" with non-empty "say".'); continue
        said = TM.norm(spoken(s))
        for path, cue in iter_cues(s):
            if cue and TM.norm(cue) and TM.norm(cue) not in said:
                errs.append(f'Scene {i} ({t}): cue "{cue}" at {path} is not in this scene\'s "say" text. Copy one word exactly from it.')
        need = {"problem": ("cards", 3, 4), "steps": ("steps", 2, 4), "compare": ("rows", 2, 4), "timeline": ("events", 3, 5),
                "list": ("items", 3, 6), "presenter": ("points", 0, 4), "gallery": ("tiles", 2, 4), "flow": ("nodes", 3, 5),
                "icons": ("items", 3, 6), "chart": ("data", 2, 10), "map": ("places", 1, 6), "kpis": ("items", 2, 4),
                "bubbles": ("items", 2, 5), "funnel": ("stages", 3, 5), "cycle": ("nodes", 3, 6), "chat": ("messages", 2, 7),
                "spotlight": ("satellites", 3, 8)}
        if t in need:
            k, a, b = need[t]
            if not (a <= len(s.get(k, []) or []) <= b): errs.append(f"Scene {i} ({t}): needs {a}-{b} {k}.")
        for k in ("cards", "steps", "rows", "events", "items", "tags", "bars", "tiles", "nodes", "data", "places", "stages", "messages", "satellites"):
            if any(not isinstance(x, dict) for x in (s.get(k) or [])):
                errs.append(f'Scene {i} ({t}): every entry of "{k}" must be an object like {{"text": ..., "cue": ...}}, not a plain string.')
        if t == "problem" and s.get("icon") not in ICONS: s["icon"] = "document"
        if t == "number":
            try: float(str(s.get("value", "")).replace(",", ""))
            except ValueError: errs.append(f'Scene {i} (number): "value" must be a number (put words in "label").')
        if t == "stats":
            for b in s.get("bars", []):
                try: b["value"] = float(b["value"])
                except (KeyError, TypeError, ValueError): errs.append(f"Scene {i}: every stats bar needs a numeric value.")
        if t == "chart":
            if s.get("kind") not in CHART_KINDS: errs.append(f'Scene {i} (chart): "kind" must be one of {", ".join(CHART_KINDS)}.')
            for d in s.get("data") or []:
                try: float(str(d.get("value", "")).replace(",", "")) if isinstance(d, dict) else 1 / 0
                except (ValueError, ZeroDivisionError): errs.append(f'Scene {i} (chart): every data entry needs a numeric \"value\" (words go in \"label\" or \"display\").'); break
        if t == "map":
            bad = [str(p.get("country") if isinstance(p, dict) else p) for p in s.get("places") or [] if not VIS.country_id(p.get("country") if isinstance(p, dict) else p)]
            if bad: errs.append(f'Scene {i} (map): unknown countries {bad}; use English country names (e.g. "India", "United States").')
        if t in ("kpis", "bubbles", "funnel"):
            for it in s.get("items") or s.get("stages") or []:
                if isinstance(it, dict) and it.get("value") not in (None, ""):
                    try: float(str(it["value"]).replace(",", ""))
                    except ValueError: errs.append(f'Scene {i} ({t}): "value" must be a number.'); break
        if t == "gauge":
            try: assert 0 <= float(s.get("value")) <= 100
            except (TypeError, ValueError, AssertionError): errs.append(f'Scene {i} (gauge): "value" must be a number from 0 to 100.')
        if t == "reveal" and not (isinstance(s.get("before"), dict) and isinstance(s.get("after"), dict)):
            errs.append(f'Scene {i} (reveal): needs "before" and "after" objects.')
        if t == "versus" and not (isinstance(s.get("left"), dict) and isinstance(s.get("right"), dict)):
            errs.append(f'Scene {i} (versus): needs "left" and "right" objects.')
        if t == "quote" and len(str(s.get("text", "")).split()) > 26: errs.append(f"Scene {i} (quote): keep the quote under 25 words.")
        if t == "broll" and not s.get("video_query"): errs.append(f'Scene {i} (broll): add "video_query" (3-6 English words).')
    spaced = re.compile(r"\b(?:[A-Z] ){1,}[A-Z]\b")
    for i, s in enumerate(sc, 1):
        if not isinstance(s, dict): continue
        for path, txt in on_screen(s):
            if spaced.search(txt): errs.append(f'Scene {i}: on-screen text "{txt}" at {path} uses a phonetic spelling; use the normal spelling on screen.')
        for a_, b_ in (("title", "title_em"), ("tagline", "tagline_em"), ("caption", "caption_em"), ("text", "em")):
            wa = [TM.norm(w) for w in str(s.get(a_, "")).split() if TM.norm(w)]
            wb = [TM.norm(w) for w in str(s.get(b_, "")).split() if TM.norm(w)]
            def run_in(x, y): return bool(x) and len(x) <= len(y) and any(y[k:k + len(x)] == x for k in range(len(y) - len(x) + 1))
            if wa and wb and (wa == wb or run_in(wb, wa) or run_in(wa, wb)): errs.append(f'Scene {i}: "{a_}" and "{b_}" repeat each other; together they must read as one phrase.')
    comp = str(cfg.get("company", "")).strip()
    if spaced.search(comp): errs.append('"company" must use the normal spelling.')
    if comp.lower() in ("job opening", "multiple job openings", "job openings", "we are hiring", "hiring alert", "hiring", "careers"):
        errs.append(f'"company" cannot be "{comp}". It must be the real company, person or subject name.')
    for i, s in enumerate(sc, 1):
        for k in (("em",) if s.get("type") == "question" else ("right_label",) if s.get("type") == "compare" else ()):
            if s.get(k) and s[k].strip() != comp: errs.append(f'Scene {i}: "{k}" must be exactly the company name "{comp}".')
    real = [s for s in sc if isinstance(s, dict)]
    textled = sum(1 for s in real if s.get("type") in TEXT_LED)
    body = [s for s in real if s.get("type") != "end"]
    pics = sum(1 for s in body if s.get("type") in PICTURE)
    wordy = sum(1 for s in body if s.get("type") in TEXT_LED | SUPPORT)
    if opts.get("visual", True):
        if wordy > 1: errs.append(f"Too much text: {wordy} text scenes (hook/question/quote/compare/flip/problem/intro/steps/timeline/list). Use at most 1; "
                                  "show the rest as spotlight, photo, gallery, flow, icons, chart, kpis, pictogram, versus, map or reveal.")
        if pics < max(2, -(-3 * len(body) // 4)): errs.append(f"Only {pics} of {len(body)} scenes are pictures. At least three quarters must be picture scenes.")
        if body and body[0].get("type") not in PICTURE: errs.append('Scene 1 must be a picture: a "spotlight" or a "photo".')
    n = sum(count_units(spoken(s), lang) for s in sc if isinstance(s, dict))
    lo, hi = word_range(duration, lang)
    unit = "characters" if LANG.no_spaces(lang) else "words"
    if not lo * 0.85 <= n <= hi * 1.12: errs.append(f"Total spoken {unit}: {n}. Target {lo}-{hi} {unit} for a {duration} video ({DURATIONS[duration][0]}-{DURATIONS[duration][1]} s).")
    first = str((sc[0].get("lines") or [{}])[0].get("say", "")).strip().lower() if sc and isinstance(sc[0], dict) else ""
    for bad in ("welcome", "hello", "hi there", "in this video", "today we are", "today we will", "let me tell you", "hey guys", "hey everyone", "hi everyone", "namaste doston"):
        if first.startswith(bad): errs.append(f"The opening line starts with '{bad}'. Cut greetings; open with an immediate hook.")
    return errs


# ------------------------------------------------------------------ cleanup
def tidy(cfg, opts):
    """Safe fixes and the creator's choices (language, voice, look, music, subtitles)."""
    seed = 42
    is_img_file = lambda v: isinstance(v, str) and (v.startswith(("http://", "https://")) or (v.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")) and " " not in v))
    if cfg.get("logo") and not is_img_file(cfg["logo"]): cfg.pop("logo", None)
    for s in cfg["scenes"]:
        if s.get("photo") and not is_img_file(s["photo"]):
            s.setdefault("image_query", str(s["photo"]).strip()); s.pop("photo", None)
        if s.get("photos"):
            ok = [p for p in s["photos"] if is_img_file(p)]; extra = [p.strip() for p in s["photos"] if isinstance(p, str) and not is_img_file(p) and p.strip()]
            s["photos"] = ok
            if extra and not s.get("image_queries"): s["image_queries"] = extra
        for ln in s["lines"]:
            ln["seed"] = int(ln["seed"]) if str(ln.get("seed", "")).lstrip("-").isdigit() else seed
            if ln.get("sub") and TM.norm(ln["sub"]) == TM.norm(ln["say"]) and ln["sub"] == ln["say"]: ln.pop("sub", None)
            seed += 1
        if s["type"] == "problem" and s.get("title_em"):
            last = s["title_em"].split()[-1]
            if s.get("alert_word") not in s["title_em"].split(): s["alert_word"] = last
        if s["type"] == "intro":
            s.setdefault("photos", [])
            if not s.get("image_queries"): s["image_queries"] = [cfg.get("company", ""), cfg.get("company", "") + " people"]
        if s["type"] in ("problem", "end") and not s.get("image_query"): s["image_query"] = cfg.get("company", "")
        # icons: every item gets a real Lucide icon (missing ones are chosen from the label)
        for key, lab in (("cards", "text"), ("steps", "title"), ("items", "label"), ("tiles", "label"), ("nodes", "label"), ("data", None), ("stages", "label"), ("satellites", "label")):
            for it in s.get(key) or []:
                if not isinstance(it, dict): continue
                if it.get("icon"): it["icon"] = VIS.resolve_icon(it["icon"])
                elif lab and s["type"] in ("icons", "flow", "gallery", "kpis", "cycle", "funnel", "spotlight") and it.get(lab):
                    it["icon"] = VIS.resolve_icon(it.get("image_query") or it[lab])
        if s["type"] == "list":
            for it in s.get("items") or []:
                if isinstance(it, dict) and it.get("icon") == "sparkles": it.pop("icon")
        if s.get("icon") and s["type"] != "problem": s["icon"] = VIS.resolve_icon(s["icon"])
        if s["type"] == "spotlight":
            if not s.get("icon"): s["icon"] = VIS.resolve_icon(s.get("title") or cfg.get("company", ""))
            if s.get("mood") not in ("good", "bad", "neutral"): s["mood"] = "good"
        if s["type"] == "map":
            for p in s.get("places") or []:
                if isinstance(p, dict) and VIS.country_id(p.get("country")): p["country"] = VIS.world()["countries"][VIS.country_id(p["country"])]["name"]
    hexok = lambda v: isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)
    theme = opts.get("theme") if opts.get("theme") in ("light", "dark") else (cfg.get("theme") if cfg.get("theme") in ("light", "dark") else "light")
    defaults = {"primary": "#024c87", "accent": "#85bbe0", "alert": "#d64545", "ink": "#0d2440", "background": "#f3f6fb" if theme == "light" else "#0a0d16"}
    col = cfg.get("colors") if isinstance(cfg.get("colors"), dict) else {}
    cfg["colors"] = {k: (col.get(k) if hexok(col.get(k)) else v) for k, v in defaults.items()}
    cfg["language"] = opts["lang"]
    cfg["voice"] = opts.get("voice") or "auto"
    cfg["theme"] = theme
    cfg["music"] = opts.get("music") or (cfg.get("music") if cfg.get("music") in ("upbeat", "calm", "dramatic", "tech", "news") else "upbeat")
    cfg["subtitles"] = opts.get("subtitles") or "kinetic"
    if opts.get("pace"): cfg["pace"] = opts["pace"]
    if opts.get("transition") in ("wipe", "flash", "none"): cfg["transition"] = opts["transition"]
    if opts.get("formats"): cfg["formats"] = [f.strip() for f in str(opts["formats"]).split(",") if f.strip() in ("16:9", "1:1", "4:5")]
    if not isinstance(cfg.get("images"), dict): cfg["images"] = {}
    if opts.get("sources"): cfg["sources"] = opts["sources"]
    order = ["company", "url", "logo", "language", "voice", "theme", "music", "subtitles", "pace", "transition", "formats", "colors", "images", "sources", "scenes"]
    return {k: cfg[k] for k in order if k in cfg}


# ------------------------------------------------------------------ websites
TLDS = ("com|in|online|io|ai|co|org|net|app|dev|xyz|me|tech|store|shop|site|so|gg|tv|us|uk|info|biz|cloud|studio|digital|"
        "live|world|space|website|page|link|club|design|agency|health|finance|money|edu|gov|ac")
DOMAIN_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:" + TLDS + r"))\b(?![a-z0-9-])", re.I)


def topic_domain(topic):
    """The website named in the topic, e.g. 'Tell me about vcfriend.online' -> 'vcfriend.online' (else '')."""
    m = DOMAIN_RE.search(re.sub(r"https?://", "", topic or ""))
    return re.sub(r"^www\.", "", m.group(1).lower()) if m else ""


def _w(t, n):
    """First n words of t (whole text when it is already short)."""
    t = str(t or "").strip(); parts = t.split()
    return t if len(parts) <= n else " ".join(parts[:n])


def visualize(cfg, keep=1):
    """Safety net: whatever the AI wrote, text-heavy scenes become picture scenes.
    hook/question -> photo, problem/intro -> spotlight, steps/timeline -> flow, list -> gallery or icons,
    compare/flip -> versus. The first `keep` text scene may stay (never as the opener); a real quote is kept."""
    ico = VIS.resolve_icon
    subject = cfg.get("company") or ""
    out, kept = [], 0
    for idx, s in enumerate(cfg.get("scenes") or []):
        t = s.get("type")
        if t in ("end", "quote") or t not in TEXT_LED | SUPPORT:
            out.append(s); continue
        if idx > 0 and kept < keep and t in ("intro", "timeline") and t not in [x.get("type") for x in out]:
            # an intro with a real logo, or a timeline with photos, already looks good
            if (t == "intro" and (cfg.get("images") or {}).get("logo_domain")) or \
               (t == "timeline" and sum(1 for e in s.get("events") or [] if isinstance(e, dict) and e.get("image_query")) >= 3):
                kept += 1; out.append(s); continue
        base = {"lines": s["lines"]}
        if s.get("kicker"): base["kicker"] = s["kicker"]
        n = None
        if t in ("hook", "question"):
            cap = s.get("text") or s.get("pre") or ""
            em = s.get("em") if t == "hook" else " ".join(x for x in (s.get("em"), s.get("post")) if x)
            n = dict(base, type="photo", caption=_w(cap, 6), caption_em=_w(em, 4), cue=s.get("em_cue") or "",
                     image_query=s.get("image_query") or subject)
        elif t == "problem":
            n = dict(base, type="spotlight", mood="bad", icon=ico(s.get("icon") or s.get("title") or subject),
                     title=_w(s.get("title_em") or s.get("title"), 4),
                     satellites=[{"icon": ico(c.get("icon") or c.get("text", "")), "label": _w(c.get("text"), 2), "cue": c.get("cue", "")}
                                 for c in (s.get("cards") or [])[:6] if isinstance(c, dict)])
        elif t == "intro":
            tags = [x for x in s.get("tags") or [] if isinstance(x, dict)]
            n = dict(base, type="spotlight", mood="good", icon=ico(subject), title=_w(subject, 3), climax_cue=s.get("tagline_cue", ""),
                     caption=_w(" ".join(x for x in (s.get("tagline"), s.get("tagline_em")) if x), 5),
                     satellites=[{"icon": ico(x.get("text", "")), "label": _w(x.get("text"), 2), "cue": x.get("cue", "")} for x in tags[:6]])
        elif t == "steps":
            n = dict(base, type="flow", title=_w(s.get("title"), 4),
                     nodes=[{"label": _w(x.get("title"), 4), "sub": _w(" · ".join((x.get("chips") or [])[:2]), 4),
                             "icon": ico(x.get("icon") or x.get("title", "")), "cue": x.get("cue", "")}
                            for x in (s.get("steps") or [])[:5] if isinstance(x, dict)])
        elif t == "timeline":
            n = dict(base, type="flow", title=_w(s.get("title"), 4),
                     nodes=[{"label": str(e.get("date", "")), "sub": _w(e.get("text"), 5),
                             "icon": ico(e.get("image_query") or e.get("text", "")), "cue": e.get("cue", "")}
                            for e in (s.get("events") or [])[:5] if isinstance(e, dict)])
        elif t == "list":
            items = [x for x in s.get("items") or [] if isinstance(x, dict)]
            if 2 <= len(items) <= 4 and all(x.get("image_query") for x in items):
                n = dict(base, type="gallery", title=_w(s.get("title"), 4),
                         tiles=[{"label": _w(x.get("text"), 4), "icon": ico(x.get("icon") or x.get("text", "")),
                                 "image_query": x["image_query"], "cue": x.get("cue", "")} for x in items])
            else:
                n = dict(base, type="icons", title=_w(s.get("title"), 4),
                         items=[{"label": _w(x.get("text"), 5), "icon": ico(x.get("icon") or x.get("image_query") or x.get("text", "")),
                                 "cue": x.get("cue", "")} for x in items[:6]])
        elif t == "compare":
            rows = [r for r in s.get("rows") or [] if isinstance(r, dict)]
            n = dict(base, type="versus",
                     left={"label": s.get("left_label", ""), "icon": ico(s.get("left_label", "")), "points": [_w(r.get("left"), 4) for r in rows[:3]],
                           "cue": (rows[0].get("left_cue") if rows else "") or ""},
                     right={"label": s.get("right_label", subject), "icon": ico(s.get("right_label") or subject), "points": [_w(r.get("right"), 4) for r in rows[:3]],
                            "cue": (rows[0].get("right_cue") if rows else "") or ""})
        elif t == "flip":
            f, b = s.get("front") or {}, s.get("back") or {}
            side = lambda d: {"label": _w(d.get("title"), 3), "icon": ico(d.get("title", "")), "cue": d.get("cue", ""),
                              "points": [_w(f"{r.get('k', '')} {r.get('v', '')}", 4) for r in (d.get("rows") or [])[:3] if isinstance(r, dict)]}
            n = dict(base, type="versus", title=_w(" ".join(x for x in (s.get("title"), s.get("title_em")) if x), 5), left=side(f), right=side(b))
        if not n: out.append(s); continue
        for k in [k for k, v in n.items() if v in ("", None, [])]: n.pop(k)
        out.append(n)
    cfg["scenes"] = out
    return cfg


def apply_website_rule(cfg, dom, lang="en"):
    """Website scroll only for specific companies/products: forced when the topic names a site, removed for general topics."""
    sc, imgs = cfg["scenes"], cfg.setdefault("images", {})
    if dom:
        imgs["logo_domain"] = dom
        if not cfg.get("url"): cfg["url"] = dom
    site = dom or imgs.get("logo_domain") or ""
    web = [x for x in sc if x.get("type") == "website"]
    if not site:
        cfg["scenes"] = [x for x in sc if x.get("type") != "website"]; return cfg
    for x in web[1:]: sc.remove(x)
    if web:
        web[0]["url"] = dom or web[0].get("url") or site
    elif dom and LANG.base(lang) == "en" and lang != "hinglish":   # other languages: the model must write it (see the prompt)
        name = cfg.get("company", dom)
        at = next((i + 1 for i, x in enumerate(sc) if x.get("type") == "intro"), 1)
        sc.insert(at, {"type": "website", "url": dom, "kicker": "See it live", "title": f"Inside {name}",
                       "lines": [{"say": f"Here's {name}, live, right on your phone.", "seed": 41}]})
    return cfg


# ------------------------------------------------------------------ steps
def digest(topic, notes, key):
    """Pasted posts/articles -> clean title, format and complete notes. Short topics pass through."""
    raw = (topic or "").strip()
    long_input = len(raw) > 90 or "\n" in raw or any(k in raw.lower() for k in ("hiring", "job opening", "apply now", "ctc", "salary", "apply through", "mailto:"))
    if not long_input: return topic, notes, None
    log("reading the pasted text and extracting every fact...")
    try:
        res = call_groq([{"role": "system", "content": DIGEST_SYSTEM.replace("FORMATS", ", ".join(FORMATS))},
                         {"role": "user", "content": f"TEXT:\n{raw[:6000]}\n" + (f"\nCREATOR NOTES:\n{notes}" if notes else "")}],
                        key, temperature=0.1, effort="low", max_out=1800)
        d = parse_json(res)
        title = str(d.get("topic") or "").strip() or raw.split("\n")[0][:80]
        parts = [f"Subject: {d['company']}" if d.get("company") else "", f"Website: {d['url']}" if d.get("url") else "",
                 str(d.get("notes") or ""), f"Creator notes: {notes}" if notes else ""]
        log(f"subject: '{d.get('company', '')}', title: '{title}', format: {d.get('format')}")
        return title, "\n".join(p for p in parts if p), d.get("format") if d.get("format") in FORMATS else None
    except SystemExit:
        raise
    except Exception as e:
        log(f"could not digest the text ({e}); using it as notes")
        return raw.split("\n")[0][:80], f"{raw}\n{notes}".strip(), None


def user_prompt(topic, notes, facts, opts):
    lang = opts["lang"]
    lo, hi = word_range(opts["duration"], lang)
    unit = "characters" if LANG.no_spaces(lang) else "words"
    lo_n, hi_n = scene_limits(opts["duration"])
    rule = LANG_RULES["en"] if LANG.base(lang) == "en" and lang != "hinglish" else LANG_RULES["hinglish"] if lang == "hinglish" else \
        LANG_RULES["other"].format(name=LANG.name(lang), nospace=" (a 2-4 character piece of it)" if LANG.no_spaces(lang) else "")
    fmt = opts.get("format") or "auto"
    dom = topic_domain(topic)
    vis = "" if opts.get("visual", True) else "\nSTYLE: text-led scenes are allowed this time (the creator chose a text style)."
    p = [f"TOPIC: {topic}" + vis,
         f"LANGUAGE: {LANG.name(lang)}. {rule}",
         f"LENGTH: {DURATIONS[opts['duration']][0]}-{DURATIONS[opts['duration']][1]} seconds = {lo}-{hi} spoken {unit} in total, {lo_n}-{hi_n} scenes.",
         f"FORMAT: {fmt} ({FORMATS.get(fmt, FORMATS['auto'])}).",
         f"TONE: {opts.get('tone') or 'energetic'}." + (f" AUDIENCE: {opts['audience']}." if opts.get("audience") else "")]
    if opts.get("theme"): p.append(f'THEME: {opts["theme"]} (set "theme":"{opts["theme"]}" and matching colours).')
    if notes: p.append(f"CREATOR NOTES (must be used, every fact kept):\n{notes[:3500]}")
    if facts: p.append(f"FACTS from research (use for numbers, dates and quotes; do not invent others):\n{facts[:3200]}")
    if dom: p.append(f'This topic names the website {dom}: include a "website" scene with "url":"{dom}" after the intro and set images.logo_domain to "{dom}".')
    p.append("Write the video JSON now.")
    return "\n\n".join(p)


def write_script(topic, notes="", opts=None, key=None, tries=3):
    opts = dict(opts or {})
    opts.setdefault("lang", "en"); opts.setdefault("duration", "standard")
    key = key or os.environ.get("GROQ_API_KEY")
    if not key: sys.exit("Set the GROQ_API_KEY environment variable (a GitHub secret in Actions).")
    topic, notes, fmt = digest(topic, notes, key)
    if fmt and (opts.get("format") in (None, "", "auto")): opts["format"] = fmt
    facts, sources = ("", [])
    if opts.get("research", True):
        facts, sources = RS.research(topic + (" " + notes[:200] if notes and len(topic) < 30 else ""), notes, opts["lang"])
    opts["sources"] = sources
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(topic, notes, facts, opts)}]
    cfg, last_errs = None, []
    for attempt in range(1, tries + 1):
        raw = call_groq(msgs, key, effort="medium" if attempt == 1 else "low")
        try:
            cfg = parse_json(raw)
            if opts.get("visual", True): cfg = visualize(cfg)   # text-heavy scenes become pictures before checking
            errs = validate(cfg, opts)
        except Exception as e:
            cfg, errs = None, [f"Output was not valid JSON ({e}). Return only the JSON object."]
        log(f"attempt {attempt}: {'ok' if not errs else str(len(errs)) + ' issue(s)'}")
        if not errs:
            cfg = review(cfg, key, opts, facts); break
        for e in errs[:10]: print("   -", e, flush=True)
        last_errs = errs
        draft = json.dumps(cfg, ensure_ascii=False, separators=(",", ":")) if cfg else raw[:6000]
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_prompt(topic, notes, facts[:1500], opts) + f"\n\nYOUR DRAFT:\n{draft}\n\nFix these problems and return the full corrected JSON only:\n- " + "\n- ".join(errs)}]
    else:
        minor = ("cue", "Total spoken", "are pictures", "Too much text", "must be a picture")
        if not (cfg and all(any(m in e for m in minor) for e in last_errs)):
            sys.exit("The model could not produce a valid script. Try rewording the topic or adding --notes.")
        log("accepting with minor issues (missed cues use estimated timing)")
    if opts.get("visual", True): cfg = visualize(cfg)
    return apply_website_rule(tidy(cfg, opts), topic_domain(topic), opts["lang"])


def review(cfg, key, opts, facts):
    """Second pass: an editor checks facts, narration and on-screen text. Keeps the draft if the edit is worse."""
    cur, extra = cfg, ""
    for _ in range(2):
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": REVIEW.format(lang=LANG.name(opts["lang"])) + extra +
                 (f"\n\nFACTS:\n{facts[:1500]}" if facts else "") + "\n\nDRAFT:\n" + json.dumps(cur, ensure_ascii=False, separators=(",", ":"))}]
        raw = call_groq(msgs, key, temperature=0.2, effort="low")
        try:
            new = parse_json(raw)
            if opts.get("visual", True): new = visualize(new)
            errs = validate(new, opts)
        except Exception as e:
            new, errs = None, [f"invalid JSON ({e})"]
        if not errs:
            log("editor pass: ok"); return new
        if new: cur = new
        extra = "\nAlso fix these problems:\n- " + "\n- ".join(errs)
    log("editor pass failed the checks; keeping the draft")
    return cfg


UPGRADE = """UPGRADE this existing video script to the picture-first style described above. Return the FULL new JSON only.
Keep: "company", "url", the language, the facts, numbers, names, the call to action and the final "end" scene.
Keep each spoken line ("say", "sub", "seed", "voice") word for word wherever it still fits, so its recorded voice is reused;
change a line only when a new visual needs it. Replace text-led scenes (problem, intro, steps, question, compare, flip, list, hook)
with picture scenes (spotlight, photo, gallery, chart, flow, icons, versus, map, pictogram, kpis, bubbles, gauge, funnel, cycle, chat, reveal)
whose cue words come from those same lines. Open with a picture (spotlight or photo). Do not invent new facts or figures."""
KEEP_KEYS = ("logo", "logo_kind", "voice", "voices", "language", "theme", "music", "music_volume", "subtitles", "subtitle_position", "pace",
             "transition", "formats", "colors", "images", "sources", "cover", "stickers", "camera", "progress_bar", "background_motion", "_comment")


def upgrade(vdir, key=None, tries=3):
    """Rewrite an existing video.json picture-first, keeping its facts, voice lines and settings. Saves a backup."""
    key = key or os.environ.get("GROQ_API_KEY")
    if not key: sys.exit("Set the GROQ_API_KEY environment variable (a GitHub secret in Actions).")
    path = os.path.join(vdir, "video.json")
    old = json.load(open(path, encoding="utf-8"))
    pics = sum(1 for s in old["scenes"] if s.get("type") in PICTURE)
    if pics >= max(2, (2 * (len(old["scenes"]) - 1)) // 3) and not os.environ.get("FORCE_UPGRADE"):
        log(f"{os.path.basename(vdir.rstrip('/'))} is already picture-first ({pics}/{len(old['scenes'])} picture scenes); left unchanged")
        return old
    lang = LANG.norm_code(old.get("language") or LANG.looks_like(" ".join(l.get("say", "") for s in old["scenes"] for l in s.get("lines", []))))
    words = sum(count_units(spoken(s), lang) for s in old["scenes"])
    secs = words / LANG.rate(lang)
    opts = {"lang": lang, "duration": "short" if secs < 33 else "standard" if secs <= 56 else "long", "visual": True}
    log(f"upgrading {os.path.basename(vdir.rstrip('/'))}: {len(old['scenes'])} scenes, {LANG.name(lang)}, {opts['duration']}")
    base = UPGRADE + "\n\nCURRENT SCRIPT:\n" + json.dumps(old, ensure_ascii=False, separators=(",", ":"))
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": base}]
    new, errs = None, []
    for attempt in range(1, tries + 1):
        raw = call_groq(msgs, key, effort="medium" if attempt == 1 else "low", temperature=0.35)
        try:
            new = parse_json(raw)
            if opts.get("visual", True): new = visualize(new)
            errs = validate(new, opts)
        except Exception as e:
            new, errs = None, [f"Output was not valid JSON ({e}). Return only the JSON object."]
        log(f"attempt {attempt}: {'ok' if not errs else str(len(errs)) + ' issue(s)'}")
        if not errs: break
        for e in errs[:8]: print("   -", e, flush=True)
        draft = json.dumps(new, ensure_ascii=False, separators=(",", ":")) if new else raw[:6000]
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": base + f"\n\nYOUR DRAFT:\n{draft}\n\nFix these problems and return the full corrected JSON only:\n- " + "\n- ".join(errs)}]
    if errs and not (new and all("cue" in e or "Total spoken" in e for e in errs)):
        sys.exit("The model could not upgrade this script; it was left unchanged.")
    opts.update({"voice": old.get("voice") or "auto", "theme": old.get("theme"), "music": old.get("music"), "subtitles": old.get("subtitles"),
                 "pace": old.get("pace"), "transition": old.get("transition")})
    new = tidy(visualize(new), opts)
    for k in KEEP_KEYS:            # the creator's settings always survive the upgrade
        if k in old: new[k] = old[k]
    new["company"] = old.get("company", new.get("company"))
    if old.get("url"): new["url"] = old["url"]
    backup = os.path.join(vdir, "video.before-upgrade.json")
    if not os.path.exists(backup): json.dump(old, open(backup, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(new, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    reused = len({l["say"] for s in old["scenes"] for l in s["lines"]} & {l["say"] for s in new["scenes"] for l in s["lines"]})
    log(f"upgraded: {', '.join(s['type'] for s in new['scenes'])} ({reused} voice line(s) reused; backup: video.before-upgrade.json)")
    return new


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--upgrade":   # python engine/write_script.py --upgrade videos/<name> [videos/<other> ...]
        for v in sys.argv[2:]:
            upgrade(v if os.path.isdir(v) else os.path.join(REPO, "videos", v))
        return
    ap = argparse.ArgumentParser(description="Write a video script (video.json) from a topic or pasted text")
    ap.add_argument("topic")
    ap.add_argument("--folder", help="folder name under videos/ (default: made from the topic)")
    ap.add_argument("--notes", default="", help="extra guidance: audience, facts to include, call to action")
    ap.add_argument("--lang", default=os.environ.get("VIDEO_LANG", ""), help="language code: en, hi, hinglish, ta, te, es, ar, zh... (default: detected)")
    ap.add_argument("--voice", default="", help='auto | female | male | a voice id like "am_michael" or "edge:hi-IN-MadhurNeural"')
    ap.add_argument("--format", default="auto", choices=list(FORMATS))
    ap.add_argument("--duration", default="standard", choices=list(DURATIONS))
    ap.add_argument("--tone", default="", help=", ".join(TONES))
    ap.add_argument("--audience", default="")
    ap.add_argument("--theme", default="", choices=["", "light", "dark"])
    ap.add_argument("--music", default="", choices=["", "upbeat", "calm", "dramatic", "tech", "news", "none"])
    ap.add_argument("--subtitles", default="", choices=["", "kinetic", "bold", "karaoke", "classic", "none"])
    ap.add_argument("--pace", default="", choices=["", "fast", "normal", "relaxed"])
    ap.add_argument("--no-research", action="store_true", help="skip the web/Wikipedia research step")
    ap.add_argument("--text-style", action="store_true", help="allow text-heavy scripts (default: picture-first)")
    ap.add_argument("--logo", default="", help="optional logo image URL")
    ap.add_argument("--site-photos", action="store_true", help="use photos from the company's own website (needs permission)")
    ap.add_argument("--options", default="", help='extra options as "key=value; key=value" (used by the GitHub workflow)')
    a = ap.parse_args()
    opts = {"lang": a.lang, "voice": a.voice, "format": a.format, "duration": a.duration, "tone": a.tone, "audience": a.audience,
            "theme": a.theme, "music": a.music, "subtitles": a.subtitles, "pace": a.pace, "research": not a.no_research, "visual": not a.text_style, "transition": "", "formats": ""}
    for part in re.split(r"[;\n]", a.options or ""):
        if "=" in part:
            k, v = part.split("=", 1); k, v = k.strip().lower(), v.strip()
            if k in ("research", "visual"): opts[k] = v.lower() not in ("no", "false", "off", "0", "text")
            elif k in opts and v: opts[k] = v
    opts["lang"] = LANG.norm_code(opts["lang"] or LANG.looks_like(a.topic))
    if opts["duration"] not in DURATIONS: opts["duration"] = "standard"
    if opts["format"] not in FORMATS: opts["format"] = "auto"
    v = opts.get("voice") or ""
    if v in ("", "auto", "female", "male"):   # turn the choice into a concrete voice for this language
        f, m = LANG.defaults(opts["lang"]); opts["voice"] = m if v == "male" else f
    log(f"language {LANG.name(opts['lang'])}, voice {opts['voice']}, format {opts['format']}, length {opts['duration']}")

    cfg = write_script(a.topic, a.notes, opts)
    folder = slugify(a.folder) if a.folder else slugify(a.topic if len(a.topic) <= 60 else cfg.get("company", ""))
    vdir = os.path.join(REPO, "videos", folder)
    if a.logo: cfg["logo"] = a.logo
    if a.site_photos: cfg.setdefault("images", {})["site_photos"] = True
    os.makedirs(vdir, exist_ok=True)
    json.dump(cfg, open(os.path.join(vdir, "video.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    n = sum(count_units(spoken(s), opts["lang"]) for s in cfg["scenes"])
    log(f"{cfg['company']}: {len(cfg['scenes'])} scenes ({', '.join(s['type'] for s in cfg['scenes'])}), {n} {'characters' if LANG.no_spaces(opts['lang']) else 'words'}")
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh: open(gh, "a").write(f"folder={folder}\n")
    print(f"videos/{folder}")


if __name__ == "__main__":
    main()
