# Models, voices and music used by Video Studio

All free to use. Models are downloaded on first use (not stored in this repo); voices and fallback music are included.

| What | Used for | Licence | Source |
|---|---|---|---|
| Chatterbox Turbo, Chatterbox Multilingual V3, Chatterbox Multilingual Hindi (Resemble AI) | human-sounding voices | MIT | https://huggingface.co/ResembleAI/chatterbox · https://huggingface.co/ResembleAI/chatterbox-turbo · https://huggingface.co/ResembleAI/Chatterbox-Multilingual-hi |
| `voices/*.wav` (8 voices: haku, bathri, bevi, hkl, a59a, gyroo, indian_guy, 7020) | the people the voices sound like | CC0 (Unmute Voice Donation Project, Kyutai; "enhanced" versions) | https://huggingface.co/kyutai/tts-voices (`voice-donations/`) |
| IS-Net "general use" (Qin et al., DIS) | cutting the subject out of photos | Apache-2.0 | https://github.com/xuebinqin/DIS (ONNX as shipped by rembg) |
| Depth Anything V2 Small (Yang et al.) | near/far layers for 2.5D photos | Apache-2.0 (Small model only) | https://huggingface.co/depth-anything/Depth-Anything-V2-Small |
| `music/upbeat.mp3`, `music/news.mp3`, `music/calm.mp3` by Soundrider/Dope ("Upbeat Corporate", "The Corporate Upbeat", "Upbeat Lounge Background") | fallback background music | CC BY 3.0 (credit added to every video that uses them) | see `music/credits.json` (Jamendo) |
| Music found online at render time | background music | CC0 or CC BY (credit added automatically) | Openverse (Jamendo, Freesound, Wikimedia) |

Every Chatterbox clip carries Resemble AI's inaudible Perth watermark, which identifies it as AI-generated.
Only clone a real person's voice with their permission.
