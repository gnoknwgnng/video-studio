"""Topic -> video.json, written by an LLM on Groq (default model: openai/gpt-oss-120b).

  export GROQ_API_KEY=gsk_...            # never put the key in a file in this repo
  python engine/write_script.py "How UPI payments work"
  python engine/write_script.py "DocsDocs dental billing" --folder docsdocs2 --notes "Audience: US dentists"

Writes videos/<folder>/video.json and prints the folder path. Then run:
  python engine/make_video.py videos/<folder>
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
API = "https://api.groq.com/openai/v1/chat/completions"
TYPES = ["problem", "stats", "intro", "steps", "flip", "question", "compare", "end"]
ICONS = ["tooth", "document", "heart", "shield", "building", "box", "chip"]

SYSTEM = """You write scripts for 45-70 second vertical explainer videos (1080x1920) with an AI voiceover.
Return ONLY one JSON object, no markdown, matching this format exactly.

{
  "company": "<short name of the subject, 1-3 words; shown as a big wordmark>",
  "url": "<website if the topic is a real product/company and you are sure of it, else empty string>",
  "colors": {"primary": "#hex", "accent": "#hex", "alert": "#hex", "ink": "#hex", "background": "#hex"},
  "scenes": [ ...6 to 8 scenes, see types below... ]
}

Colours: primary = strong brand colour (dark enough for white text on it); accent = lighter tint of a related hue;
alert = a red/orange for problems; ink = near-black text colour; background = very light tint (near white).

Every scene has "type" and "lines": [{"say": "...", "seed": <int>}]. "say" is what the voice speaks.
Write names the way they should SOUND (e.g. "Docs, Docs" for DocsDocs, "U P I" for UPI) and then add
"sub": "<same sentence with the real spelling>" for the subtitle. Keep sentences short, clear and spoken.
Scene types (use each at most once; order should tell a story):

1. "problem" (ALWAYS FIRST): {"type":"problem","kicker":"The problem","title":"<3-5 words>","title_em":"<2-4 words, ends the sentence>",
   "alert_word":"<last word of title_em, exactly, including its punctuation>","icon":"<one of: tooth, document, heart, shield, building, box, chip>",
   "meter_label":"<2 words, e.g. Stress level>","cards":[4 x {"text":"<2-3 words>","cue":"<one word>"}],
   "lines":[1 line that says the problem, then names the 4 cards in order]}
2. "stats" (OPTIONAL; only with a real, widely reported statistic you are confident about; never invent numbers):
   {"type":"stats","label":"<what the bars measure, <=6 words>","bars":[2 x {"name":"<1-2 words>","value":<0-100>,"display":"<e.g. 55%>","cue":"<word>"}],
    "callout":{"em":"<e.g. 1 in 5>","text":"<=8 words","people":5,"empty":1,"cue":"<word>","empty_cue":"<word>"},"lines":[1 line]}
   Omit the callout if you have no real "1 in N" style fact.
3. "intro": {"type":"intro","logo_cue":"<word right after the name, e.g. comes>","tagline":"<3-5 words>","tagline_em":"<1-3 words>",
   "tagline_cue":"<word>","photos":[],"tags":[3 x {"text":"<1-3 words: who it is for>","cue":"<word>"}],"lines":[1 line: "That's where X comes in..." naming who it helps]}
   Mark the last tag with "highlight": true and no cue.
4. "steps": {"type":"steps","title":"How it works","steps":[3 x {"title":"<2-4 words>","chips":[2-4 x "<1-2 words>"],"cue":"<first word of that step's sentence>"}],
   "lines":[3 lines, one per step, each starting with that step's cue word]}
5. "flip" (OPTIONAL): a card that shows a failure, gets stamped, then flips to show how it is fixed.
   {"type":"flip","title":"<3-4 words>","title_em":"<1-2 words>",
    "front":{"kicker":"<category · item>","title":"<2-3 words>","rows":[3 x {"k":"<label>","v":"<value>"}] (last row "style":"alert"),"stamp":"<1 word, caps>","cue":"<word>"},
    "back":{"kicker":"<label>","title":"<2-3 words>","rows":[3 x {"k":"<label>","v":"<value>"}] (2nd row "style":"ok","cue":"<word>", 3rd row "style":"primary","cue":"<word>")},
    "lines":[1 line]}
6. "question": {"type":"question","pre":"So what makes","em":"<name>","post":"different?","em_cue":"<first word of the name as spoken>","mark_cue":"different",
   "lines":[{"say":"So what makes <name as spoken> different?"}]}
7. "compare": {"type":"compare","left_label":"<the usual alternative, 1-3 words>","right_label":"<name>",
   "rows":[3-4 x {"left":"<2-5 words>","right":"<2-5 words>","left_cue":"<word>","right_cue":"<word>"}],
   "lines":[2-3 lines contrasting each row in order]}
8. "end" (ALWAYS LAST): {"type":"end","tagline":"<2-4 words>","tagline_em":"<2-4 words>","logo_cue":"<word: the name as spoken, last word of the line>",
   "tagline_cue":"<first word of the line>","lines":[1 short line: tagline then the name]}

RULES
- If the topic is a general subject or idea (not one named product or company), the "company" is that subject in
  1-3 words (e.g. "Solar power", "UPI", "Compound interest"). NEVER invent a brand or product name; "url" is "".
- Use the exact "company" text for the "question" "em", the "compare" "right_label", and as the name everywhere on screen.
- The "end" line says the tagline, then the name exactly once (e.g. "Your practice. Your revenue cycle. Docs, Docs.").
- Phonetic spellings ("U P I", "Docs, Docs") go ONLY in "say". Every on-screen field (titles, cards, labels, "em",
  "right_label", tags, "company") uses the normal spelling ("UPI", "DocsDocs").
- "title" + "title_em" read as ONE sentence with no repeated words (e.g. "Insurance paperwork is" + "dentistry's biggest headache.").
  Same for "tagline" + "tagline_em" (e.g. "Revenue cycle & insurance work," + "handled.").
- Problem cards are the 4 concrete pains or chores people face today (e.g. "Checking coverage", "Chasing payments"),
  never product features or solutions. The problem line names who suffers, then lists the 4 pains as short spoken phrases.
- Narration must sound like a confident human narrator: natural sentences, no lists of nouns, no repeated words.
- Every "cue" / "*_cue" MUST be a single word that appears in the "say" text of THAT SAME scene, in the order the visuals appear.
- On-screen text must be short (the limits above). Never put long sentences on cards.
- Total spoken words: 110-170. Seeds: use 42, 43, 44, ... one per line.
- Be accurate. Do not invent statistics, customers, prices or features. If unsure, describe the general idea.
"""


def example():
    """The hand-made DocsDocs script, shown to the model as a quality bar."""
    p = os.path.join(REPO, "videos", "docsdocs", "video.json")
    try:
        cfg = json.load(open(p, encoding="utf-8"))
        cfg.pop("logo", None); cfg.pop("voice", None)
        for sc in cfg["scenes"]:
            if sc["type"] == "intro": sc["photos"] = []
        return json.dumps(cfg, ensure_ascii=False)
    except Exception:
        return ""


REVIEW = """You are the editor of this explainer video script. Return the FULL corrected JSON only, same format and rules.
Check and fix:
1. Facts: correct anything wrong or doubtful (be conservative: remove a claim rather than guess). Example: UPI payments are approved with a UPI PIN, not an OTP.
2. Narration: natural, spoken, confident; no noun lists; no awkward or repeated phrasing.
3. Problem cards are real pains (not features); title + title_em and tagline + tagline_em read as one phrase with no repeats.
4. Phonetic spellings appear only in "say"; on-screen text uses the normal spelling.
5. Every cue word appears in its own scene's "say" text.
6. For a general topic, no invented brand names: the name is the subject itself (e.g. "Solar power").
7. Grammar: every sentence is correct and reads aloud smoothly (e.g. "solar power helps", not "Solar panels helps").
8. No overclaiming: avoid absolute words (zero, never, always, guaranteed, all) unless strictly true; add the needed
   condition instead (e.g. "power during cuts, with a battery").
If everything is already good, return it unchanged."""


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:40].strip("-") or "video"


def call_groq(messages, key, model, temperature=0.5, effort="medium", max_out=3800):
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
                # free tier = 8,000 tokens/minute: wait as long as Groq asks, then retry
                m = re.search(r"try again in ([\d.]+)(ms|s|m)", msg)
                wait = float(m.group(1)) * {"ms": 0.001, "s": 1, "m": 60}[m.group(2)] if m else 0
                wait = max(wait + 2, 6 * (attempt + 1)) if e.code == 429 else 5 * (attempt + 1)
                print(f"[script] Groq {'rate limit' if e.code == 429 else 'busy'}; waiting {wait:.0f}s", flush=True)
                time.sleep(min(wait, 65)); continue
            if e.code == 401: sys.exit("Groq rejected the API key (401). Check the GROQ_API_KEY secret.")
            if e.code == 413: sys.exit("Request too large for your Groq tier (8,000 tokens/minute on free). Shorten --notes, or upgrade the Groq tier.")
            if e.code == 400 and "json" in msg.lower() and "response_format" in body:
                body.pop("response_format"); req.data = json.dumps(body).encode(); continue
            sys.exit(f"Groq API error {e.code}: {msg}")
        except urllib.error.URLError as e:
            if attempt < 3: time.sleep(5); continue
            sys.exit(f"Could not reach Groq: {e}")


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a: return json.loads(text[a:b + 1])
        raise


norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())


def spoken_words(scene):
    return [norm(w) for ln in scene.get("lines", []) for w in str(ln.get("say", "")).split()]


def validate(cfg):
    """Return a list of problems the LLM must fix (empty = good)."""
    errs = []
    if not isinstance(cfg, dict): return ["Top level must be a JSON object."]
    if not str(cfg.get("company", "")).strip(): errs.append('Missing "company".')
    sc = cfg.get("scenes")
    if not isinstance(sc, list) or not (4 <= len(sc) <= 9): return errs + ['"scenes" must be a list of 6-8 scenes.']
    types = [s.get("type") for s in sc]
    if types[0] != "problem": errs.append('The first scene must be type "problem".')
    if types[-1] != "end": errs.append('The last scene must be type "end".')
    for i, s in enumerate(sc, 1):
        t = s.get("type")
        if t not in TYPES: errs.append(f'Scene {i}: unknown type "{t}".'); continue
        lines = s.get("lines")
        if not isinstance(lines, list) or not lines or any(not str(l.get("say", "")).strip() for l in lines):
            errs.append(f"Scene {i} ({t}): needs lines with non-empty \"say\"."); continue
        words = spoken_words(s)
        for path, cue in iter_cues(s):
            if cue and norm(cue) and not any(norm(cue) in w for w in words):
                errs.append(f'Scene {i} ({t}): cue "{cue}" at {path} is not spoken in this scene\'s lines.')
        if t == "problem":
            if len(s.get("cards", [])) not in (3, 4): errs.append(f"Scene {i}: problem needs 3-4 cards.")
            if s.get("icon") not in ICONS: s["icon"] = "document"
        if t == "steps" and not (2 <= len(s.get("steps", [])) <= 4): errs.append(f"Scene {i}: steps needs 2-4 steps.")
        if t == "compare" and not (2 <= len(s.get("rows", [])) <= 4): errs.append(f"Scene {i}: compare needs 2-4 rows.")
        if t == "stats":
            for b in s.get("bars", []):
                try: b["value"] = float(b["value"])
                except (KeyError, TypeError, ValueError): errs.append(f"Scene {i}: every stats bar needs a numeric value.")
    spaced = re.compile(r"\b(?:[A-Z] ){1,}[A-Z]\b")
    for i, s in enumerate(sc, 1):
        for path, txt in on_screen(s):
            if spaced.search(txt): errs.append(f'Scene {i}: on-screen text "{txt}" at {path} uses a phonetic spelling; use the normal spelling on screen.')
        for a_, b_ in (("title", "title_em"), ("tagline", "tagline_em")):
            a, b = norm(s.get(a_, "")), norm(s.get(b_, ""))
            if a and b and (a == b or b in a or a in b): errs.append(f'Scene {i}: "{a_}" and "{b_}" repeat each other; together they must read as one phrase.')
    if spaced.search(str(cfg.get("company", ""))): errs.append('"company" must use the normal spelling.')
    comp = str(cfg.get("company", "")).strip()
    for i, s in enumerate(sc, 1):
        for k in (("em",) if s.get("type") == "question" else ("right_label",) if s.get("type") == "compare" else ()):
            if s.get(k) and s[k].strip() != comp: errs.append(f'Scene {i}: "{k}" must be exactly the company name "{comp}".')
    n = sum(len(str(l.get("say", "")).split()) for s in sc for l in s.get("lines", []))
    if not 70 <= n <= 220: errs.append(f"Total spoken words is {n}; aim for 110-170.")
    return errs


def on_screen(s):
    keys = ("title", "title_em", "kicker", "tagline", "tagline_em", "label", "em", "pre", "post", "left_label", "right_label", "meter_label")
    for k in keys:
        if isinstance(s.get(k), str): yield k, s[k]
    for key, fields in (("cards", ("text",)), ("tags", ("text",)), ("steps", ("title",)), ("rows", ("left", "right")), ("bars", ("name",))):
        for j, it in enumerate(s.get(key, []) or []):
            if isinstance(it, dict):
                for f in fields:
                    if isinstance(it.get(f), str): yield f"{key}[{j}].{f}", it[f]


def iter_cues(s):
    for k, v in s.items():
        if k.endswith("cue") and isinstance(v, str): yield k, v
    for key in ("cards", "tags", "steps", "bars", "rows"):
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


def tidy(cfg):
    """Small safe fixes: seeds, voice settings, colour format, alert word."""
    seed = 42
    for s in cfg["scenes"]:
        for ln in s["lines"]:
            ln["seed"] = int(ln.get("seed", seed)) if str(ln.get("seed", "")).lstrip("-").isdigit() else seed
            if ln.get("sub") == ln.get("say"): ln.pop("sub", None)
            seed += 1
        if s["type"] == "problem" and s.get("title_em"):
            last = s["title_em"].split()[-1]
            if s.get("alert_word") not in s["title_em"].split(): s["alert_word"] = last
        if s["type"] == "intro": s.setdefault("photos", [])
    cfg["voice"] = {"exaggeration": 0.6, "cfg_weight": 0.45}
    hexok = lambda v: isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)
    defaults = {"primary": "#024c87", "accent": "#85bbe0", "alert": "#d64545", "ink": "#0d2440", "background": "#f3f6fb"}
    col = cfg.get("colors") if isinstance(cfg.get("colors"), dict) else {}
    cfg["colors"] = {k: (col.get(k) if hexok(col.get(k)) else v) for k, v in defaults.items()}
    order = ["company", "url", "logo", "colors", "voice", "scenes"]
    return {k: cfg[k] for k in order if k in cfg}


def write_script(topic, notes="", model="openai/gpt-oss-120b", key=None, tries=3):
    key = key or os.environ.get("GROQ_API_KEY")
    if not key: sys.exit("Set the GROQ_API_KEY environment variable (a GitHub secret in Actions).")
    ex = example()
    sysmsg = SYSTEM + (f"\nEXAMPLE of a finished, high-quality script (different topic; match its quality and style, not its content):\n{ex}\n" if ex else "")
    user = f"Topic: {topic}\n" + (f"Extra notes from the creator: {notes}\n" if notes else "") + "Write the video JSON now."
    msgs = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}]
    last_errs = []
    for attempt in range(1, tries + 1):
        raw = call_groq(msgs, key, model, effort="medium" if attempt == 1 else "low")
        try:
            cfg = parse_json(raw); errs = validate(cfg)
        except Exception as e:
            cfg, errs = None, [f"Output was not valid JSON ({e}). Return only the JSON object."]
        print(f"[script] attempt {attempt}: {'ok' if not errs else str(len(errs)) + ' issue(s)'}", flush=True)
        if not errs: return tidy(review(cfg, key, model))
        for e in errs[:8]: print("   -", e, flush=True)
        last_errs = errs
        # compact follow-up (fits the free tier's 8,000 tokens/minute): rules + current JSON + the problems
        draft = json.dumps(cfg, ensure_ascii=False, separators=(",", ":")) if cfg else raw[:6000]
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Topic: {topic}\nHere is a draft:\n{draft}\n\nFix these problems and return the full corrected JSON only:\n- " + "\n- ".join(errs)}]
    # last resort: accept if only cue problems remain (the renderer falls back gracefully)
    if cfg and all("cue" in e for e in last_errs):
        print("[script] accepting with minor cue issues; those animations will use estimated timing", flush=True)
        return tidy(cfg)
    sys.exit("The model could not produce a valid script. Try rewording the topic or adding --notes.")


def review(cfg, key, model):
    """Second pass: an editor checks facts, narration and on-screen text. Keeps the draft if the edit is worse."""
    cur, extra = cfg, ""
    for attempt in range(2):
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": REVIEW + extra + "\n\nDRAFT:\n" + json.dumps(cur, ensure_ascii=False, separators=(",", ":"))}]
        raw = call_groq(msgs, key, model, temperature=0.2, effort="low")
        try:
            new = parse_json(raw); errs = validate(new)
        except Exception as e:
            new, errs = None, [f"invalid JSON ({e})"]
        if not errs:
            print("[script] editor pass: ok", flush=True); return new
        if new: cur = new
        extra = "\nAlso fix these problems:\n- " + "\n- ".join(errs)
    print("[script] editor pass failed validation; keeping the draft", flush=True)
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--folder", help="folder name under videos/ (default: made from the topic)")
    ap.add_argument("--notes", default="", help="extra guidance: audience, tone, facts to include")
    ap.add_argument("--model", default=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    ap.add_argument("--logo", default="", help="optional logo image URL")
    a = ap.parse_args()
    folder = slugify(a.folder or a.topic)
    vdir = os.path.join(REPO, "videos", folder)
    print(f"[script] writing '{a.topic}' with {a.model} -> videos/{folder}/video.json", flush=True)
    cfg = write_script(a.topic, a.notes, a.model)
    if a.logo: cfg["logo"] = a.logo
    os.makedirs(vdir, exist_ok=True)
    json.dump(cfg, open(os.path.join(vdir, "video.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    n = sum(len(l["say"].split()) for s in cfg["scenes"] for l in s["lines"])
    print(f"[script] {cfg['company']}: {len(cfg['scenes'])} scenes ({', '.join(s['type'] for s in cfg['scenes'])}), {n} words", flush=True)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh: open(gh, "a").write(f"folder={folder}\n")
    print(f"videos/{folder}")


if __name__ == "__main__":
    main()
