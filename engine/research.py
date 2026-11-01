"""Proper research before writing: questions first, then several free sources, then one checked research brief.

  1. plan       the AI lists what a good video on this topic must answer, the search queries and the Wikipedia articles to read
  2. sources    (all free; any that fails is skipped)
                - Wikipedia: the FULL articles (not just the summary), the paragraphs that answer the questions
                - Groq web search (model "groq/compound", same free Groq key): current answers from the web, with links
                - GDELT: what the news said about it in the last 6 months (headlines + dates, open data)
                - Tavily web search, if TAVILY_API_KEY is set
  3. brief      the AI turns everything into a research brief: key facts with numbers, dates and their source,
                the most surprising facts, a short timeline, and what is uncertain. Every fact is tied to a source [n].

The brief is what the script is written from, and it's saved next to the video as research.md.
"""
import json, os, re, time, urllib.parse, urllib.request
import urllib.error

UA = "video-studio/2.0 (https://github.com/gnoknwgnng/video-studio)"
GROQ = os.environ.get("GROQ_API_URL") or "https://api.groq.com/openai/v1/chat/completions"


def log(*a): print("[research]", *a, flush=True)


def _get(url, data=None, headers=None, timeout=30, tries=3, as_json=True):
    h = {"User-Agent": UA, "Accept": "application/json" if as_json else "*/*"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body: h["Content-Type"] = "application/json"
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
                raw = r.read()
            return json.loads(raw) if as_json else raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 or e.code >= 500: time.sleep(6 * (k + 1)); continue
            raise
        except Exception as e:
            last = e; time.sleep(3 * (k + 1))
    raise last


# ------------------------------------------------------------------ sources
def wiki_lang(lang):
    lang = (lang or "en").split("-")[0]
    return {"hinglish": "en", "fil": "tl", "nb": "no", "yue": "zh-yue"}.get(lang, lang)


def wikipedia_search(query, wl="en", n=3):
    s = _get(f"https://{wl}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query[:250], "srlimit": n, "format": "json"}))
    return [h["title"] for h in s.get("query", {}).get("search", [])[:n]]


def wikipedia_article(title, wl="en"):
    d = _get(f"https://{wl}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "prop": "extracts|info", "explaintext": 1, "exsectionformat": "plain", "inprop": "url",
         "redirects": 1, "titles": title, "format": "json"}))
    for p in d.get("query", {}).get("pages", {}).values():
        if p.get("extract"): return p.get("title", title), p.get("fullurl", ""), p["extract"]
    return None


def relevant(text, words, limit=2600, intro=700):
    """The intro plus the paragraphs that share the most words with the questions."""
    paras = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) > 60]
    if not paras: return ""
    head = paras[0][:intro]
    scored = sorted(((sum(1 for w in words if w in p.lower()) + 0.3 * bool(re.search(r"\d", p)), i, p) for i, p in enumerate(paras[1:], 1)),
                    reverse=True)
    out, n = [head], len(head)
    for sc, i, p in scored:
        if sc <= 0 or n > limit: break
        out.append(p[:700]); n += min(len(p), 700)
    return "\n".join(out)[:limit + 700]


def gdelt(query, n=8):
    """Recent news headlines (open data, no key). One request per 5 s is the polite limit."""
    q = query if " " not in query else f'"{query}"' if len(query.split()) <= 3 else query
    d = _get("https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
        {"query": q + " sourcelang:english", "mode": "artlist", "maxrecords": n, "format": "json", "timespan": "6months", "sort": "hybridrel"}),
        timeout=30, tries=2)
    out = []
    for a in (d or {}).get("articles", [])[:n]:
        dt = str(a.get("seendate", ""))[:8]
        out.append({"title": a.get("title", ""), "url": a.get("url", ""), "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}" if len(dt) == 8 else "",
                    "site": a.get("domain", "")})
    return out


def groq_web(questions, topic, key, lang="en"):
    """Groq's compound model searches the web itself (free tier, same key). Returns (answer text, [urls])."""
    if not key or os.environ.get("RESEARCH_WEB", "on") == "off": return "", []
    prompt = (f"Research this topic for a short, accurate explainer video: {topic}\n\nAnswer each question with concrete, current facts "
              f"(numbers with their year, names, places). Say when something is uncertain. Cite the source URL after each fact.\n\n"
              + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions[:8])))
    for model in [m for m in (os.environ.get("GROQ_RESEARCH_MODEL", "groq/compound"), "groq/compound-mini") if m]:
        try:
            d = _get(GROQ, {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_completion_tokens": 2200},
                     headers={"Authorization": f"Bearer {key}"}, timeout=180, tries=2)
            msg = d["choices"][0]["message"]
            text = msg.get("content") or ""
            urls = re.findall(r"https?://[^\s)\]>\"']+", text)
            for t in msg.get("executed_tools") or []:
                for r in ((t.get("search_results") or {}).get("results") or []):
                    if r.get("url"): urls.append(r["url"])
            urls = list(dict.fromkeys(u.rstrip(".,;") for u in urls))[:12]
            if text.strip(): return text.strip()[:4500], urls
        except Exception as e:
            log(f"web search with {model} failed ({str(e)[:100]})")
    return "", []


def tavily(query, n=6):
    key = os.environ.get("TAVILY_API_KEY")
    if not key: return []
    d = _get("https://api.tavily.com/search", {"query": query[:400], "search_depth": "advanced", "max_results": n, "include_answer": True},
             headers={"Authorization": f"Bearer {key}"}, timeout=60, tries=2)
    out = []
    if d.get("answer"): out.append({"title": "Web search summary", "url": "", "text": d["answer"]})
    for r in d.get("results", [])[:n]:
        out.append({"title": r.get("title", ""), "url": r.get("url", ""), "text": re.sub(r"\s+", " ", r.get("content", ""))[:900]})
    return out


# ------------------------------------------------------------------ the whole research step
PLAN = """You are the researcher for a short explainer video. Return ONLY JSON:
{"questions":[5-8 questions a great, accurate video on this topic must answer: what it is, how it works, the key numbers (with year),
              who/where, the history in brief, what is new or surprising, common misconceptions],
 "queries":[2-4 short web search queries in English],
 "wikipedia":[1-3 exact English Wikipedia article titles that most likely cover it]}"""

BRIEF = """You write the research brief a scriptwriter will rely on. Use ONLY the SOURCES below (and very well-known stable facts).
Return ONLY JSON:
{"summary":"<3-4 sentences: what this is and why it matters, in plain English>",
 "facts":[8-16 {"fact":"<one concrete fact: a number with its year, a name, a date, a place, how something works>","src":<source number>}],
 "surprising":["<2-4 facts most viewers won't know, each with [n]>"],
 "timeline":["<year: event [n]>", ...] (only if relevant, max 6),
 "careful":["<claims that are disputed, outdated or that sources disagree on>"]}
Prefer the most recent numbers; say the year for every number. Never invent a figure. If sources disagree, use the most reliable and note it in "careful"."""


def research(topic, notes="", lang="en", llm=None, key=None):
    """Returns (brief_text, sources, brief_markdown). Never raises: if everything fails, the script is written from the topic alone.
    llm(messages, max_out) -> parsed JSON (the script writer's Groq helper)."""
    q = re.sub(r"\s+", " ", topic).strip()[:300]
    plan = {"questions": [], "queries": [q], "wikipedia": []}
    if llm:
        try:
            p = llm([{"role": "system", "content": PLAN}, {"role": "user", "content": f"TOPIC: {q}" + (f"\nNOTES: {notes[:800]}" if notes else "")}], 900)
            plan.update({k: [str(x) for x in p.get(k, []) if str(x).strip()] for k in ("questions", "queries", "wikipedia") if p.get(k)})
            log(f"{len(plan['questions'])} questions to answer: " + " | ".join(plan["questions"][:3]) + (" ..." if len(plan["questions"]) > 3 else ""))
        except Exception as e:
            log(f"research plan skipped ({str(e)[:80]})")
    words = {w for w in re.findall(r"[a-z]{4,}", " ".join(plan["questions"] + [q]).lower())} - {"what", "which", "when", "does", "with", "that", "this", "from", "have", "their", "there", "about", "most"}
    found = []   # {"title","url","text"}

    # Wikipedia: full articles (video language first for non-English, then English)
    titles, seen = [], set()
    for wl in dict.fromkeys([wiki_lang(lang), "en"]):
        try:
            cands = (plan["wikipedia"] if wl == "en" else []) + wikipedia_search(q, wl, 2) + (wikipedia_search(plan["queries"][0], wl, 1) if plan["queries"] and wl == "en" else [])
            for t in cands:
                if (wl, t.lower()) in seen or len([x for x in titles if x[0] == wl]) >= (3 if wl == "en" else 1): continue
                seen.add((wl, t.lower()))
                art = wikipedia_article(t, wl)
                if art:
                    titles.append((wl, art[0]))
                    found.append({"title": f"Wikipedia ({wl}): {art[0]}", "url": art[1], "text": relevant(art[2], words)})
                time.sleep(0.4)
        except Exception as e:
            log(f"Wikipedia ({wl}) failed: {str(e)[:100]}")
    if titles: log("Wikipedia: " + ", ".join(t for _, t in titles))

    # the web (Groq compound search), then Tavily if configured
    web, urls = groq_web(plan["questions"] or [q], q, key, lang)
    if web:
        found.append({"title": "Web search (Groq)", "url": urls[0] if urls else "", "text": web, "urls": urls})
        log(f"web search: {len(web)} characters, {len(urls)} links")
    try:
        t = tavily(plan["queries"][0] if plan["queries"] else q)
        if t: found += t; log(f"Tavily: {len(t)} results")
    except Exception as e:
        log(f"Tavily failed: {str(e)[:80]}")

    # recent news
    try:
        news = gdelt(plan["queries"][0] if plan["queries"] else q)
        if news:
            found.append({"title": "Recent news (GDELT, last 6 months)", "url": "",
                          "text": "\n".join(f"{n['date']} {n['site']}: {n['title']}" for n in news), "news": news})
            log(f"news: {len(news)} recent headlines")
    except Exception as e:
        log(f"news search skipped ({str(e)[:80]})")

    if not found: log("no sources reachable; writing from the topic alone"); return "", [], ""
    src_text = "\n\n".join(f"[{i + 1}] {r['title']}{' (' + r['url'] + ')' if r.get('url') else ''}\n{r['text']}" for i, r in enumerate(found))[:14000]
    sources = []
    for r in found:
        if r.get("url"): sources.append({"title": r["title"], "url": r["url"]})
        for u in (r.get("urls") or [])[1:6]: sources.append({"title": re.sub(r"^https?://(www\.)?", "", u).split("/")[0], "url": u})
        for n in (r.get("news") or [])[:4]: sources.append({"title": f"{n['site']}: {n['title'][:80]} ({n['date']})", "url": n["url"]})
    sources = list({s["url"]: s for s in sources}.values())

    brief = None
    if llm:
        try:
            brief = llm([{"role": "system", "content": BRIEF},
                         {"role": "user", "content": f"TOPIC: {q}\nQUESTIONS: " + "; ".join(plan["questions"]) + f"\n\nSOURCES:\n{src_text}"}], 2600)
        except Exception as e:
            log(f"research brief skipped ({str(e)[:80]})")
    if brief and brief.get("facts"):
        ref = lambda n: f" [{n}]" if isinstance(n, int) else ""
        lines = [f"SUMMARY: {brief.get('summary', '')}", "KEY FACTS:"]
        lines += [f"- {f.get('fact', '')}{ref(f.get('src'))}" for f in brief["facts"] if isinstance(f, dict) and f.get("fact")]
        if brief.get("surprising"): lines += ["MOST SURPRISING:"] + [f"- {x}" for x in brief["surprising"]]
        if brief.get("timeline"): lines += ["TIMELINE:"] + [f"- {x}" for x in brief["timeline"]]
        if brief.get("careful"): lines += ["BE CAREFUL WITH:"] + [f"- {x}" for x in brief["careful"]]
        text = "\n".join(lines)
        log(f"brief: {len(brief['facts'])} facts, {len(brief.get('surprising', []))} surprising, from {len(found)} sources")
    else:
        text = src_text[:6000]
    md = (f"# Research: {q}\n\n" + (("## Questions\n" + "\n".join(f"- {x}" for x in plan["questions"]) + "\n\n") if plan["questions"] else "")
          + "## Brief\n\n" + text + "\n\n## Sources\n" + "\n".join(f"{i + 1}. {r['title']} {r.get('url', '')}" + "".join(f"\n   - {u}" for u in (r.get("urls") or [])[1:8])
                    + "".join(f"\n   - {n['date']} {n['site']}: {n['title']} {n['url']}" for n in (r.get("news") or []))
                    for i, r in enumerate(found)) + "\n")
    return text[:7000], sources, md


if __name__ == "__main__":
    import sys
    t, s, md = research(" ".join(sys.argv[1:]) or "UPI payments India")
    print(md[:3000])
