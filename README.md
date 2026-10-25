# Video Studio

Type a **topic** and get a vertical (1080×1920) explainer video. An LLM on **Groq** (`openai/gpt-oss-120b`) writes the
script, and **GitHub Actions** renders it for free. You can also write the script yourself.
Each video gets an AI voice (Chatterbox), animations synced to the spoken words, subtitles and
sound design, then it's published as a **GitHub Release** and shown on a small **GitHub Pages** website.

```
Topic ──► Groq LLM writes video.json ──► AI voice ──► word timing ──► animated scenes ──► sound ──► MP4 (Release + Gallery)
          (or you write video.json)       Chatterbox     Whisper          GSAP/HTML           Python     HyperFrames
```

## One-time setup (about 5 minutes)

1. **Create the repo.** On GitHub: *New repository* → name it `video-studio` → **Public** (Actions minutes are unlimited for public repos) → create.
2. **Upload this folder.** Either drag the files into *Add file → Upload files*, or:
   ```bash
   cd video-studio
   git init && git add . && git commit -m "Video Studio"
   git branch -M main
   git remote add origin https://github.com/<you>/video-studio.git
   git push -u origin main
   ```
3. **Let Actions write to the repo.** *Settings → Actions → General → Workflow permissions* → **Read and write permissions** → Save.
4. **Add your Groq key as a secret** (never put it in a file; this repo is public).
   *Settings → Secrets and variables → Actions → New repository secret* → Name: `GROQ_API_KEY`, Value: your `gsk_…` key.
   Optional: under the *Variables* tab, add `GROQ_MODEL` to use a different model (default `openai/gpt-oss-120b`).
5. **Turn on the website.** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
   Then *Actions → Deploy website → Run workflow*. Your site will be at `https://<you>.github.io/video-studio/`.

The first push also builds every video in `videos/` (DocsDocs and Acme are included as examples).

## Making a video

**From a topic (easiest):** *Actions → Make video → Run workflow* → type the topic (e.g. `How UPI payments work in India`)
→ **Run workflow**. Or use the website's **From a topic** tab. The AI writes the script, commits it to
`videos/<topic>/video.json` (so you can edit it and re-run), then the video is built and published.

How the AI writing works (`engine/write_script.py`):
1. A draft is written from detailed scene rules plus the hand-made DocsDocs script as a quality example.
2. Code checks it (scene order, text lengths, every cue word actually spoken, no phonetic spellings on screen, no invented brand names) and sends any problems back to the model to fix.
3. A second "editor" pass reviews facts, grammar and overclaiming.
It retries automatically within Groq's free-tier limit (8,000 tokens/minute), so writing takes about 1 minute.
**Always watch the result before sharing:** AI can still get facts wrong. Fix lines in `video.json` and commit to re-render.

**From the website (write your own):** *New video* → fill in the name, colours and script → **Create on GitHub** → **Commit changes**.

**On GitHub directly:** create `videos/<name>/video.json` (copy one of the examples), commit.
Put a logo or photos next to it, or use image URLs in the JSON.

Then watch *Actions → Make video*. When it's green, the MP4 is under **Releases** and in the site's **Gallery**.

| | First run of a new video | Re-run, visuals changed only |
|---|---|---|
| Time | ~25–35 min (installs + voice on CPU) | ~8–10 min (voice cached) |

Voice lines are saved in `videos/<name>/.voice/` by the workflow, so only lines whose words or seed changed are re-voiced.

**Rebuild without changes:** *Actions → Make video → Run workflow* → type the folder name.

## The script (`video.json`)

```jsonc
{
  "company": "Acme",               // shown when there is no logo
  "url": "acme.com",               // shown on the end card
  "logo": "logo.png",              // file next to video.json, or an https:// image URL (optional)
  "colors": { "primary": "#024c87", "accent": "#85bbe0", "alert": "#d64545", "ink": "#0d2440", "background": "#f3f6fb" },
  "voice": { "exaggeration": 0.6, "cfg_weight": 0.45 },
  "scenes": [ { "type": "problem", "...": "...", "lines": [ { "say": "What the voice says", "sub": "Subtitle (optional)", "seed": 42 } ] } ]
}
```

Scene types, in any order and repeatable: `problem`, `stats`, `intro`, `steps`, `flip`, `question`, `compare`, `end`.
Their fields are listed on the website under *New video → Scene types and their fields*, and both example videos use all of them.

- **cue**: a word from that scene's lines; the animation fires when the voice says it. If a cue word isn't heard, the log shows `WARN … did not hear` and the animation falls back to a sensible time.
- **say vs sub**: write names the way they sound in `say` (e.g. `"Docs, Docs"`) and the real spelling in `sub`.
- **seed**: if a line is mispronounced, change its seed and commit; only that line is re-voiced.

## Run it on your own computer (optional)

Needs Node 22+, Python 3.10/3.11 and FFmpeg.

```bash
npm ci && npx hyperframes browser ensure
pip install -r requirements.txt
python engine/make_video.py videos/docsdocs          # -> videos/docsdocs/out/docsdocs.mp4
python engine/make_video.py videos/docsdocs --no-render   # fast: just build the HTML

export GROQ_API_KEY=gsk_...                                 # from a topic, locally
python engine/write_script.py "How UPI payments work" && python engine/make_video.py videos/how-upi-payments-work
```

## What's inside

```
engine/write_script.py topic -> video.json with Groq (draft, checks, editor pass)
engine/make_video.py   pipeline: voice → join → Whisper word timing → scenes → sound → render
engine/scenes.py       the 8 scene types (HTML + GSAP animation per type)
engine/style.css       shared look; brand colours come from video.json
engine/sfx.py          whooshes, pops, thuds, shimmers and beat, synthesised in code
assets/                fonts + GSAP (local, no CDN at render time)
site/index.html        GitHub Pages site: topic box, gallery, video.json builder, run status
.github/workflows/     make-video.yml (render + release), pages.yml (website)
videos/                one folder per video
```

Tech: Groq (openai/gpt-oss-120b) · HyperFrames 0.8.181 · GSAP 3.14.2 · Chatterbox TTS 0.1.7 · Whisper (via HyperFrames) · Python/NumPy · FFmpeg.
