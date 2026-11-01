# Video Studio 2

Type a **topic in any language** (or paste a job post, article or announcement) and get a vertical 1080×1920 video
for Reels, Shorts and TikTok: a researched script, a natural AI voice, animations synced to every spoken word,
subtitles, music and sound design. It runs **for free on GitHub Actions** and publishes the MP4, its subtitles (.srt)
and a thumbnail as a **GitHub Release**, shown on a small website.

```
Topic / pasted text ─► research (Wikipedia, Tavily) ─► AI script (Groq) ─► checks + editor pass ─► video.json
video.json ─► voice (Kokoro · Edge · Piper · Chatterbox) ─► word timing ─► 31 scene types: photos, charts, diagrams, icons, maps ─► fonts
           ─► music + sound design ─► HyperFrames render ─► MP4 + .srt + thumbnail ─► Release + Gallery
```

## What's new in version 2

| | Version 1 | Version 2 |
|---|---|---|
| Voices | 1 (Chatterbox) | **540+ free voices**: 54 Kokoro, 316 Microsoft Edge neural, 178 Piper, plus Chatterbox cloning. Several speakers per video. |
| Languages | English | **75+ languages** incl. Hindi, Hinglish, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Urdu, Arabic (right-to-left), Chinese, Japanese, Korean… |
| Scene types | 9 | **32**: picture-first **spotlight, photo, gallery, chart (bar/column/line/donut/pie), flow diagram, icons, versus, world map, pictogram, KPI dashboard, bubbles, gauge, funnel, cycle, chat, before/after reveal**, plus hook, number, timeline, list, quote, broll (stock footage), presenter |
| Visuals | text cards | **shows instead of tells**: numbers become charts, places become maps, processes become flow diagrams, examples become photo tiles; 2,292 icons; photos inside lists, steps and timelines |
| Formats | product / hiring / education | + listicle, news, story, tutorial, comparison, pitch, announcement, motivational |
| Look | light | light or **dark** theme, 26 icons, brand colours kept readable automatically |
| Subtitles | kinetic | kinetic, **bold**, **karaoke**, classic or none; plus an `.srt` file for uploads |
| Music | one beat | **upbeat, calm, dramatic, tech, news**, or your own track (auto-ducked under the voice) |
| Facts | model memory | **research first** (Wikipedia always, Tavily web search optional), sources in the release notes |
| Footage | photos | photos + **stock video** (Pexels / Pixabay, optional free keys) |
| First render | 25–35 min (installs PyTorch) | **about 5–10 min** (PyTorch only if a video uses Chatterbox) |

Old videos keep working: a `video.json` from version 1 still uses Chatterbox and its cached voice lines.

## One-time setup (about 5 minutes)

1. **Create the repo** (Public, so Actions minutes are free) and push this folder:
   ```bash
   git init && git add . && git commit -m "Video Studio 2"
   git branch -M main && git remote add origin https://github.com/<you>/video-studio.git && git push -u origin main
   ```
   Updating an existing Video Studio repo? Copy these files over it and push; your `videos/` stay as they are.
2. *Settings → Actions → General → Workflow permissions* → **Read and write permissions**.
3. *Settings → Secrets and variables → Actions → New repository secret*:

   | Secret | Needed? | What it does | Free? |
   |---|---|---|---|
   | `GROQ_API_KEY` | **yes**, for topic mode | writes the scripts, fast word timing | free tier ([console.groq.com](https://console.groq.com)) |
   | `PEXELS_API_KEY` | optional | stock video clips + photos | free ([pexels.com/api](https://www.pexels.com/api/)) |
   | `PIXABAY_API_KEY` | optional | more stock video + photos | free ([pixabay.com/api/docs](https://pixabay.com/api/docs/)) |
   | `TAVILY_API_KEY` | optional | web research for current facts | free 1,000 searches/month ([tavily.com](https://tavily.com)) |

   Voices need **no key**. Optional *Variables*: `GROQ_MODEL` (default `openai/gpt-oss-120b`), `GROQ_FALLBACK_MODELS`.
4. *Settings → Pages → Source:* **GitHub Actions**, then *Actions → Deploy website → Run workflow*.

## Making a video

**From a topic:** *Actions → Make video → Run workflow*, or the website's **From a topic** tab:

| Field | Examples |
|---|---|
| topic | `How UPI payments work in India` · `UPI kaise kaam karta hai` · `मानसून क्यों ज़रूरी है` · a pasted job post |
| language | `en`, `hi`, `hinglish`, `ta`, `te`, `bn`, `mr`, `gu`, `kn`, `ml`, `ur`, `es`, `fr`, `de`, `ar`, `zh`, `ja`, `ko`… (empty = detect) |
| voice | `auto`, `female`, `male`, or an id: `am_michael`, `edge:hi-IN-MadhurNeural`, `piper:en_US-ryan-high` |
| options | `format=listicle; duration=short; tone=funny; theme=dark; music=calm; subtitles=bold; pace=normal; research=no` |

The AI writes `videos/<topic>/video.json` (commit edits to it to re-render), then the video is built.
**Always watch the result before sharing:** AI can still get facts wrong.

**Write your own:** create `videos/<name>/video.json` (copy an example, or use the website's *Write my own* tab) and commit.

**On your computer:**
```bash
npm ci && npx hyperframes browser ensure
pip install -r requirements.txt                    # + requirements-chatterbox.txt only for Chatterbox
export GROQ_API_KEY=gsk_...
python engine/write_script.py "Top 5 habits of great founders" --lang hinglish --voice male --format listicle --duration short
python engine/make_video.py videos/top-5-habits-of-great-founders
python engine/make_video.py videos/docsdocs --no-render      # fast: build the HTML + audio only
```

## Picture-first videos

By default the AI writes **picture-first** scripts: at least two thirds of the scenes are photos, charts, diagrams, icons or maps,
and on-screen text is cut to 1–4 word labels while the voice carries the detail. The checks send a script back to the AI if it is
too text-heavy. (For the old text style: `--text-style`, or `visual=no` in the workflow options / *Visual style* on the website.)

| The script says… | The video shows… | Scene |
|---|---|---|
| a number, or several | an animated bar / column / line / donut / pie chart, or a giant counting number | `chart`, `number` |
| a place | a world map that zooms in and drops labelled pins | `map` |
| a process, a journey, "how it works" | icon nodes joined by arrows, a dot travelling along | `flow` |
| examples, kinds, products, places | 2–4 real photo tiles | `gallery` |
| benefits, features, tips | big icons with short labels | `icons` |
| A vs B, then vs now | two photo cards side by side with "VS" | `versus` |
| a moment, a mood | one full-screen photo with a caption | `photo` |
| "1 in 5 people…" | a grid of people icons with the share lit up | `pictogram` |
| several key results | 2–4 dashboard tiles with counting numbers and icons | `kpis` |
| "X is ten times bigger than Y" | circles sized by value | `bubbles` |
| a score, rating or risk level | a meter whose needle swings to the value | `gauge` |
| numbers that narrow (applicants → hired) | a funnel | `funnel` |
| a repeating loop (water cycle, plan → review) | icons around a circle with arrows | `cycle` |
| a conversation, complaint or DM | a phone chat, bubble by bubble, with a different voice per person | `chat` |
| a transformation | before/after photos with a sliding wipe | `reveal` |
| a problem or a win, as a picture | a big line-drawn icon; related icons fly in and orbit it; then it shakes red (problem) or glows with a burst (win) | `spotlight` |

**Motion everywhere** (the energy of the original Video Studio, now in every scene): icons and line art **draw themselves**
stroke by stroke, the **camera punches in** (and shakes on big hits) at each scene's key moments, and **particle bursts** mark
a number landing, a gauge settling, a funnel's last stage or the winner of a comparison. `"camera": false` turns the punch-ins off.

Every video also gets **transitions** between scenes (`"transition": "wipe"`, `"flash"` or `"none"`), a thin **progress bar**
at the top (`"progress_bar": false` to hide it) and a slowly **moving background** (`"background_motion": false` to turn it off).

Any item can carry an `"icon"` (any English word, matched to one of 2,292 [Lucide](https://lucide.dev/icons) icons) and an
`"image_query"` (a photo search). Photos come from Pexels/Pixabay when their free keys are set, otherwise from Openverse,
Wikimedia Commons and NASA (searched in parallel, with a time limit so a slow archive never stalls a render). When no photo
is found, the tile shows its icon instead. Charts must use real figures: the AI may only chart numbers from its research or your notes.

## Smart photos, stickers, covers and other formats

- **Photos that match the script.** Each photo search gathers up to 8 candidates from all sources and an AI image model
  (OpenAI's CLIP, running offline on the runner, free) picks the one that best matches the words. If nothing matches well,
  the scene shows an icon instead of a wrong photo. `PHOTO_RANKING=off` turns it off; `PHOTO_MIN_SCORE` (default 0.215) sets how strict it is.
- **Icon stickers.** When the voice says a clear key word ("money", "phone", "rain", "students"), a matching icon pops up beside
  the subtitles (English and Hinglish videos, at most one every 3 seconds). `"stickers": false` turns them off.
- **Designed covers.** Every video gets `<name>.jpg` (9:16 cover for Reels/Shorts) and `<name>-youtube.jpg` (16:9 thumbnail):
  the best photo, the opening line as a headline, the brand. Set your own with `"cover": {"kicker": "...", "title": "...", "em": "..."}`.
- **Other formats.** `"formats": ["16:9", "1:1", "4:5"]` in video.json (or the repo variable `VIDEO_FORMATS`, or `formats=16:9,1:1`
  in the workflow options) also makes YouTube/LinkedIn/feed versions, with a blurred copy of the video filling the sides.
  They are attached to the Release and offered in the gallery.

## Voices

```bash
python engine/voices.py --list hi                  # every voice that speaks Hindi
python engine/voices.py --say "Hello there" --voice edge:en-IN-NeerjaExpressiveNeural -o test.wav
```

| Engine | Voices | Languages | Notes |
|---|---|---|---|
| `kokoro` | 54 | English (US/UK), Hindi, Spanish, French, Italian, Portuguese | offline, very natural, default for English. Blend voices: `{"engine":"kokoro","blend":{"af_heart":0.6,"af_bella":0.4}}` |
| `edge` | 316 | 75 languages | Microsoft Edge neural voices; exact word timing; `speed`, `pitch` (`"+5Hz"`) |
| `piper` | 178 | ~50 languages | offline, downloaded once |
| `chatterbox` | clone | English + 22 languages | expressive; `"reference": "myvoice.wav"` clones a voice from ~10 s of audio (with consent). Slow on CPU. |

If a voice fails (e.g. the Edge service hiccups), every line of that speaker is re-voiced with a similar free voice,
so the voice never changes mid-video. The website has a voice picker with samples (`engine/voice_samples.py` builds it).

## The script (`video.json`)

```jsonc
{
  "company": "UPI",                    // subject name, shown big (or a "logo")
  "url": "npci.org.in",
  "language": "hi",                    // any code; text, fonts, subtitles and number formats follow it
  "voice": "edge:hi-IN-SwaraNeural",   // narrator (string or {"engine","id","speed","pitch"})
  "voices": { "guest": "edge:hi-IN-MadhurNeural" },   // extra speakers: "voice": "guest" on a line
  "theme": "light",                    // light | dark
  "subtitles": "karaoke",              // kinetic | bold | karaoke | classic | none
  "subtitle_position": "lower",        // lower | bottom | middle
  "music": "calm",                     // upbeat | calm | dramatic | tech | news | none | "song.mp3"
  "music_volume": 0.12,                // optional
  "pace": "fast",                      // fast | normal | relaxed
  "colors": { "primary": "#5a2ca0", "accent": "#f0a030", "alert": "#e2453c", "ink": "#1a1030", "background": "#f7f4fc", "highlight": "#FFE600" },
  "scenes": [ { "type": "hook", "...": "...", "lines": [ { "say": "spoken text", "sub": "subtitle", "seed": 42, "voice": "guest", "pause_after": 0.5 } ] } ]
}
```

**Scene types:** picture-first `photo`, `gallery`, `chart`, `flow`, `icons`, `versus`, `map`; and `hook`, `problem`, `number`, `stats`,
`intro`, `steps`, `timeline`, `list`, `flip`, `compare`, `question`, `quote`, `broll`, `presenter`, `website`, `end`. Fields are listed on the website (*Write my own → Scene types*) and in
`engine/write_script.py`. Any scene can have a background: `image_query`, `photo`, `video` or `video_query`.

- **cue**: a word from that scene's lines; the animation fires when it is spoken. Works in every script.
- **say vs sub**: write names/numbers the way they sound in `say` ("Docs, Docs", "nineteen eighty-three") and the real spelling in `sub`.
- **seed**: change it to re-voice one line (Chatterbox); other engines re-voice when the text or voice changes.

## Outputs

`videos/<name>/out/<name>.mp4` (1080×1920, 30 fps), `<name>.srt` (captions for YouTube/Instagram/LinkedIn),
`<name>.jpg` (designed 9:16 cover), `<name>-youtube.jpg` (16:9 thumbnail), optional `<name>-16x9.mp4` / `-1x1.mp4` / `-4x5.mp4`,
`info.json` (voices, timing source, warnings). The Release also lists sources and image credits.

## What's inside

```
engine/write_script.py  topic -> video.json (digest pasted text, research, Groq draft, checks, editor pass, model fallback)
engine/research.py      Wikipedia (free) + Tavily web search (optional key)
engine/make_video.py    pipeline: voice -> join -> word timing -> scenes -> fonts -> music -> render -> srt + thumbnail
engine/voices.py        Kokoro, Edge, Piper, Chatterbox; caching; consistent fallbacks; voice catalog
engine/timing.py        word timing in any language (engine timings, Groq/local Whisper, estimates) + alignment
engine/languages.py     languages, default voices, right-to-left, speaking rates
engine/fonts.py         Noto fonts for every script, cut down to the characters used
engine/scenes.py        text-led scene types (HTML + GSAP)
engine/scenes_visual.py picture-first scenes: photo, gallery, chart, flow, icons, versus, map
engine/scenes_visual2.py pictogram, kpis, bubbles, gauge, funnel, cycle, chat, reveal, spotlight
engine/motion.py        draw-on icons, particle bursts, shakes (camera punch-ins are added in make_video.py)
engine/visuals.py       2,292 Lucide icons (ISC) + world map (svg-maps, CC BY 4.0), word -> icon matching
engine/media.py         photos, logos, stock video (Pexels, Pixabay, Openverse, Wikimedia, NASA)
engine/clip_rank.py     CLIP photo matching (offline ONNX model): picks the photo that fits the words
engine/cover.cjs        renders the designed cover images in headless Chrome
engine/sfx.py           sound effects + 5 music moods, synthesised in code
engine/style.css        shared look; brand colours, themes and subtitle styles
engine/needs.py         tells the workflow what to install for a video
engine/voice_samples.py builds the voice picker (site/voices, web/voices)
site/                   GitHub Pages site: topic box with language/voice/style, gallery, video.json builder
web/                    private Vercel site with logins (see web/README.md)
.github/workflows/      make-video.yml (script -> render -> release), pages.yml (website)
videos/                 one folder per video (examples: acme-motion, how-the-internet-reaches-you, acme-visual-tour, docsdocs, internet-history, upi-hindi)
```

Tech: Groq · Kokoro-82M (ONNX) · Microsoft Edge neural TTS · Piper · Chatterbox · faster-whisper · HyperFrames 0.8.181 ·
GSAP 3.14.2 · Google Noto fonts · Python/NumPy · FFmpeg. Footage: Pexels, Pixabay, Openverse, Wikimedia Commons, NASA.
