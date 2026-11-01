"""Research before writing: current facts and their sources, so scripts are accurate and checkable.

  Tavily web search   if TAVILY_API_KEY is set (free tier: 1,000 searches a month)
  Wikipedia           always (free, no key), in the video's language when that Wikipedia exists

Returns notes for the script writer and a list of sources that are saved in video.json and the release notes.
"""
import json, os, re, urllib.parse, urllib.request

UA = "video-studio/2.0 (https://github.com/gnoknwgnng/video-studio)"


def log(*a): print("[research]", *a, flush=True)


def _json(url, data=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body: h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        return json.load(r)


def tavily(query, n=6):
    key = os.environ.get("TAVILY_API_KEY")
    if not key: return []
    d = _json("https://api.tavily.com/search", {"query": query[:400], "search_depth": "advanced", "max_results": n,
                                                  "include_answer": True}, headers={"Authorization": f"Bearer {key}"}, timeout=60)
    out = []
    if d.get("answer"): out.append({"title": "Summary of web results", "url": "", "text": d["answer"]})
    for r in d.get("results", [])[:n]:
        out.append({"title": r.get("title", ""), "url": r.get("url", ""), "text": re.sub(r"\s+", " ", r.get("content", ""))[:900]})
    return out


def wikipedia(query, lang="en", n=2):
    lang = (lang or "en").split("-")[0]
    lang = {"hinglish": "en", "fil": "tl", "nb": "no", "yue": "zh-yue"}.get(lang, lang)
    out = []
    for wl in dict.fromkeys([lang, "en"]):
        try:
            s = _json(f"https://{wl}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "query", "list": "search", "srsearch": query[:250], "srlimit": n, "format": "json"}))
            for hit in s.get("query", {}).get("search", [])[:n]:
                t = hit["title"]
                p = _json(f"https://{wl}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_")))
                if p.get("extract"):
                    out.append({"title": f"Wikipedia: {t}", "url": p.get("content_urls", {}).get("desktop", {}).get("page", ""),
                                "text": p["extract"][:1200]})
        except Exception as e:
            log(f"Wikipedia ({wl}) failed: {e}")
        if out: break
    return out


def research(topic, notes="", lang="en"):
    """Returns (facts_text, sources). Never raises: research is a bonus, not a requirement."""
    q = re.sub(r"\s+", " ", topic).strip()[:300]
    found = []
    try:
        found += tavily(q)
        if found: log(f"Tavily: {len(found)} result(s)")
    except Exception as e:
        log(f"Tavily failed: {e}")
    try:
        w = wikipedia(q, lang)
        if w: log(f"Wikipedia: {len(w)} article(s)")
        found += w
    except Exception as e:
        log(f"Wikipedia failed: {e}")
    if not found: return "", []
    facts = "\n".join(f"- [{i + 1}] {r['title']}: {r['text']}" for i, r in enumerate(found))
    sources = [{"title": r["title"], "url": r["url"]} for r in found if r.get("url")]
    return facts[:6000], sources


if __name__ == "__main__":
    import sys
    f, s = research(" ".join(sys.argv[1:]) or "UPI payments India")
    print(f[:2000]); print(s)
