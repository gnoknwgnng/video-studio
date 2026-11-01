"""Build the voice picker for the websites: a catalog (voices.json) and a short MP3 sample per curated voice.

  python engine/voice_samples.py                 # writes site/voices/ and web/voices/
  python engine/voice_samples.py --no-audio      # catalog only

Every language gets its default female and male voice; English and Hindi get a longer curated list.
All other voices are still usable by id (python engine/voices.py --list <lang>), they just have no sample.
"""
import argparse, json, os, shutil, subprocess, sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
sys.path.insert(0, ENGINE)
import languages as L  # noqa: E402
import voices as VO    # noqa: E402

SAMPLE = {
    "en": "Hi! This is how I'll sound in your next video.",
    "hi": "नमस्ते! आपके अगले वीडियो में मेरी आवाज़ ऐसी सुनाई देगी।",
    "hinglish": "Hi! Aapke next video mein meri awaaz aisi sunai degi.",
    "bn": "নমস্কার! আপনার পরের ভিডিওতে আমার কণ্ঠ এমন শোনাবে।",
    "ta": "வணக்கம்! உங்கள் அடுத்த வீடியோவில் என் குரல் இப்படித்தான் இருக்கும்.",
    "te": "నమస్కారం! మీ తదుపరి వీడియోలో నా గొంతు ఇలా వినిపిస్తుంది.",
    "mr": "नमस्कार! तुमच्या पुढच्या व्हिडिओमध्ये माझा आवाज असा ऐकू येईल.",
    "gu": "નમસ્તે! તમારા આગામી વિડિયોમાં મારો અવાજ આવો સંભળાશે.",
    "kn": "ನಮಸ್ಕಾರ! ನಿಮ್ಮ ಮುಂದಿನ ವಿಡಿಯೋದಲ್ಲಿ ನನ್ನ ಧ್ವನಿ ಹೀಗೆ ಕೇಳಿಸುತ್ತದೆ.",
    "ml": "നമസ്കാരം! നിങ്ങളുടെ അടുത്ത വീഡിയോയിൽ എന്റെ ശബ്ദം ഇങ്ങനെയായിരിക്കും.",
    "ur": "السلام علیکم! آپ کی اگلی ویڈیو میں میری آواز ایسی سنائی دے گی۔",
    "ne": "नमस्ते! तपाईंको अर्को भिडियोमा मेरो आवाज यस्तो सुनिनेछ।",
    "si": "ආයුබෝවන්! ඔබේ ඊළඟ වීඩියෝවේ මගේ හඬ මෙහෙම ඇසෙයි.",
    "es": "¡Hola! Así sonaré en tu próximo video.",
    "fr": "Bonjour ! Voici ma voix pour votre prochaine vidéo.",
    "de": "Hallo! So klinge ich in deinem nächsten Video.",
    "it": "Ciao! Ecco come suonerò nel tuo prossimo video.",
    "pt": "Olá! É assim que vou soar no seu próximo vídeo.",
    "nl": "Hallo! Zo klink ik in je volgende video.",
    "ru": "Привет! Вот так я буду звучать в вашем следующем видео.",
    "uk": "Привіт! Ось так я звучатиму у вашому наступному відео.",
    "pl": "Cześć! Tak będę brzmieć w twoim następnym filmie.",
    "tr": "Merhaba! Bir sonraki videonda sesim böyle olacak.",
    "ar": "مرحبًا! هكذا سيبدو صوتي في الفيديو القادم.",
    "fa": "سلام! صدای من در ویدیوی بعدی شما این‌طور خواهد بود.",
    "he": "שלום! כך הקול שלי יישמע בסרטון הבא שלך.",
    "zh": "你好！这就是我在你下一个视频里的声音。",
    "zh-tw": "你好！這就是我在你下一個影片裡的聲音。",
    "yue": "你好！呢個就係我喺你下一條片嘅聲音。",
    "ja": "こんにちは！次の動画では、こんな声でお届けします。",
    "ko": "안녕하세요! 다음 영상에서 제 목소리는 이렇게 들릴 거예요.",
    "id": "Halo! Beginilah suaraku di video berikutnya.",
    "ms": "Hai! Beginilah suara saya dalam video anda yang seterusnya.",
    "vi": "Xin chào! Đây là giọng của tôi trong video tiếp theo của bạn.",
    "th": "สวัสดี! นี่คือเสียงของฉันในวิดีโอถัดไปของคุณ",
    "fil": "Kumusta! Ganito ang magiging boses ko sa susunod mong video.",
    "sw": "Habari! Hivi ndivyo sauti yangu itakavyosikika kwenye video yako ijayo.",
    "el": "Γεια σου! Έτσι θα ακούγεται η φωνή μου στο επόμενο βίντεό σου.",
    "sv": "Hej! Så här låter jag i din nästa video.",
    "da": "Hej! Sådan kommer jeg til at lyde i din næste video.",
    "nb": "Hei! Slik kommer jeg til å høres ut i den neste videoen din.",
    "fi": "Hei! Tältä kuulostan seuraavassa videossasi.",
    "cs": "Ahoj! Takhle budu znít ve tvém příštím videu.",
    "ro": "Salut! Așa voi suna în următorul tău videoclip.",
    "hu": "Szia! Így fogok szólni a következő videódban.",
}

EXTRA = {   # curated extra voices (beyond each language's female/male default)
    "en": ["kokoro:af_bella", "kokoro:af_nicole", "kokoro:af_sarah", "kokoro:af_nova", "kokoro:am_fenrir", "kokoro:am_puck",
           "kokoro:am_adam", "kokoro:am_echo", "kokoro:bf_emma", "kokoro:bf_isabella", "kokoro:bm_george", "kokoro:bm_fable",
           "edge:en-US-AvaMultilingualNeural", "edge:en-US-AndrewMultilingualNeural", "edge:en-US-EmmaMultilingualNeural",
           "edge:en-US-BrianMultilingualNeural", "edge:en-US-AriaNeural", "edge:en-US-GuyNeural", "edge:en-US-JennyNeural",
           "edge:en-US-ChristopherNeural", "edge:en-GB-SoniaNeural", "edge:en-GB-RyanNeural", "edge:en-AU-NatashaNeural",
           "edge:en-IN-NeerjaExpressiveNeural", "edge:en-IN-PrabhatNeural", "piper:en_US-ryan-high", "piper:en_US-lessac-high",
           "piper:en_GB-alan-medium", "chatterbox:default"],
    "hi": ["kokoro:hf_alpha", "kokoro:hf_beta", "kokoro:hm_omega", "kokoro:hm_psi", "piper:hi_IN-pratham-medium",
           "piper:hi_IN-priyamvada-medium", "piper:hi_IN-rohan-medium"],
    "es": ["kokoro:ef_dora", "kokoro:em_alex", "edge:es-MX-DaliaNeural", "edge:es-MX-JorgeNeural"],
    "fr": ["kokoro:ff_siwis"], "it": ["kokoro:if_sara", "kokoro:im_nicola"], "pt": ["kokoro:pf_dora", "kokoro:pm_alex"],
    "ta": ["edge:ta-LK-SaranyaNeural", "edge:ta-SG-VenbaNeural"], "te": ["piper:te_IN-padmavathi-medium", "piper:te_IN-venkatesh-medium"],
    "ml": ["piper:ml_IN-meera-medium", "piper:ml_IN-arjun-medium"], "ur": ["edge:ur-IN-GulNeural", "edge:ur-IN-SalmanNeural"],
}


def describe(engine, vid, lang):
    gender = ""
    if engine == "kokoro": gender = {"f": "Female", "m": "Male"}.get(vid[1:2], "")
    elif engine == "edge": gender = {"F": "Female", "M": "Male"}.get(next((v["gender"] for v in L.edge_voices() if v["id"] == vid), ""), "")
    if engine == "kokoro": nm = vid.split("_")[1].title() + {"a": " (US)", "b": " (UK)"}.get(vid[0], "")
    elif engine == "edge":
        parts = vid.split("-"); nm = parts[2].replace("MultilingualNeural", " · multilingual").replace("ExpressiveNeural", " · expressive").replace("Neural", "")
        if parts[0] == "en" or parts[1] not in ("IN",) and parts[0] in ("es", "pt", "zh", "ar", "ta", "ur"): nm += f" ({parts[1]})"
    elif engine == "piper": nm = vid.split("-")[1].replace("_", " ").title()
    else: nm = "Expressive (clone-able)"
    style = next((v.get("style", "") for v in L.edge_voices() if v["id"] == vid), "") if engine == "edge" else \
        {"kokoro": "offline, very natural", "piper": "offline", "chatterbox": "expressive, slow on CPU"}.get(engine, "")
    return {"label": f"{nm} — {gender.lower() + ', ' if gender else ''}{engine.title()}", "gender": gender[:1], "note": style}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--out", nargs="*", default=[os.path.join(REPO, "site", "voices"), os.path.join(REPO, "web", "voices")])
    a = ap.parse_args()
    main_out = a.out[0]; os.makedirs(main_out, exist_ok=True)
    cat = {"languages": [], "voices": {}}
    for code, (name, native, f, m) in L.LANGS.items():
        cat["languages"].append({"code": code, "name": name, "native": native})
        ids = list(dict.fromkeys([f, m] + EXTRA.get(code, [])))
        vs = []
        for full in ids:
            engine, vid = full.split(":", 1)
            d = describe(engine, vid, code)
            item = {"id": full, **d, "default": "female" if full == f else "male" if full == m else ""}
            fn = full.replace(":", "_").replace("/", "_") + ".mp3"
            text = SAMPLE.get(code) or SAMPLE.get(L.base(code)) or SAMPLE["en"]
            mp3 = os.path.join(main_out, fn)
            if not a.no_audio and engine != "chatterbox" and not os.path.exists(mp3):
                try:
                    spec = VO.parse_spec(full, code)
                    x, sr, _ = VO.engine(engine).say(text, spec)
                    import soundfile as sf
                    wav = mp3[:-4] + ".wav"; sf.write(wav, x, sr)
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-ac", "1", "-b:a", "40k", mp3], check=True); os.remove(wav)
                    print("sample", full, flush=True)
                except Exception as e:
                    print("WARN no sample for", full, e, flush=True)
            if os.path.exists(mp3): item["sample"] = "voices/" + fn
            vs.append(item)
        cat["voices"][code] = vs
    json.dump(cat, open(os.path.join(main_out, "voices.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for other in a.out[1:]:
        os.makedirs(other, exist_ok=True)
        for fn in os.listdir(main_out): shutil.copy(os.path.join(main_out, fn), os.path.join(other, fn))
    n = sum(len(v) for v in cat["voices"].values()); s = sum(1 for v in cat["voices"].values() for x in v if x.get("sample"))
    print(f"{len(cat['languages'])} languages, {n} curated voices, {s} samples -> {', '.join(a.out)}")


if __name__ == "__main__":
    main()
