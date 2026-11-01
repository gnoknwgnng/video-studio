"""What a video needs installed, for the GitHub workflow:  python engine/needs.py videos/<name>
Prints key=value lines (also written to $GITHUB_OUTPUT): chatterbox=true|false, fonts=none|core|cjk, voice_cached=true|false."""
import json, os, re, sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE)
import languages as L  # noqa: E402
import voices as VO    # noqa: E402


def main(vdir):
    cfg = json.load(open(os.path.join(vdir, "video.json"), encoding="utf-8"))
    lines = [ln for s in cfg.get("scenes", []) for ln in s.get("lines", [])]
    text = " ".join(ln.get("say", "") for ln in lines)
    lang = L.norm_code(cfg.get("language") or L.looks_like(text))
    named = cfg.get("voices") or {}
    specs = [VO.parse_spec(ln.get("voice") or cfg.get("voice"), lang, named) for ln in lines]
    cache = os.path.join(vdir, ".voice")
    missing = [s for ln, s in zip(lines, specs) if not os.path.exists(os.path.join(cache, VO.line_key(ln["say"], ln.get("seed", 42), s) + ".wav"))]
    chatter = any(s["engine"] == "chatterbox" for s in missing)
    allt = json.dumps(cfg, ensure_ascii=False)
    fonts = "cjk" if re.search(r"[぀-ヿ一-鿿가-힯]", allt) else "core" if re.search(r"[^\x00-ɏ -⁯₠-⃏←-⇿“”‘’…–—•·]", allt) else "none"
    out = {"chatterbox": str(chatter).lower(), "fonts": fonts, "voice_cached": str(not missing).lower(), "language": lang}
    for k, v in out.items(): print(f"{k}={v}")
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            for k, v in out.items(): f.write(f"{k}={v}\n")


if __name__ == "__main__":
    main(sys.argv[1])
