"""Picks the photo that best matches a description, using OpenAI's CLIP model (ONNX, runs offline on CPU, free).

Photo searches return many loosely related results ("clean desk" can return an event tent). CLIP looks at each
candidate image and scores how well it matches the words; the best one is used, and if none match well enough
the scene shows an icon instead of a wrong photo.

  python engine/clip_rank.py "clean minimal desk laptop" a.jpg b.jpg c.jpg
Turn it off with PHOTO_RANKING=off. Model: Xenova/clip-vit-base-patch32 (quantized, ~150 MB, downloaded once).
"""
import os, sys, threading
import numpy as np

ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE)
from voices import CACHE, download  # noqa: E402

URL = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/"
FILES = {"text": "onnx/text_model_quantized.onnx", "vision": "onnx/vision_model_quantized.onnx", "tok": "tokenizer.json"}
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
MIN_SCORE = float(os.environ.get("PHOTO_MIN_SCORE", 0.215))   # below this, no photo is better than a wrong one
_lock = threading.Lock()
_m = None


def available():
    if os.environ.get("PHOTO_RANKING", "on").lower() in ("off", "0", "no", "false"): return False
    try:
        import onnxruntime, tokenizers  # noqa: F401
        return True
    except ImportError:
        return False


def _load():
    global _m
    with _lock:
        if _m is None:
            import onnxruntime as ort
            from tokenizers import Tokenizer
            d = os.path.join(CACHE, "clip")
            p = {k: download(URL + f, os.path.join(d, os.path.basename(f)), "CLIP photo-matching model" if k == "vision" else f"CLIP {k}")
                 for k, f in FILES.items()}
            so = ort.SessionOptions(); so.intra_op_num_threads = 2
            tok = Tokenizer.from_file(p["tok"])
            tok.enable_truncation(77); tok.enable_padding(length=77, pad_id=49407)
            _m = {"text": ort.InferenceSession(p["text"], so), "vision": ort.InferenceSession(p["vision"], so), "tok": tok}
    return _m


def _norm(x): return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-9)


def text_embed(texts):
    m = _load()
    ids = np.array([e.ids for e in m["tok"].encode_batch(texts)], dtype=np.int64)
    return _norm(m["text"].run(None, {"input_ids": ids})[0])


def _pixels(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size; s = 224 / min(w, h)
    im = im.resize((max(224, round(w * s)), max(224, round(h * s))), Image.BICUBIC)
    w, h = im.size; l, t = (w - 224) // 2, (h - 224) // 2
    a = (np.asarray(im.crop((l, t, l + 224, t + 224)), dtype=np.float32) / 255.0 - MEAN) / STD
    return a.transpose(2, 0, 1)


def scores(query, paths):
    """Cosine similarity between the query and each image (about 0.15 = unrelated, 0.30 = a strong match)."""
    if not paths: return []
    m = _load()
    t = text_embed([f"a photo of {query}", query])
    px = np.stack([_pixels(p) for p in paths])
    v = _norm(m["vision"].run(None, {"pixel_values": px})[0])
    return (v @ t.T).max(axis=1).tolist()


if __name__ == "__main__":
    q, files = sys.argv[1], sys.argv[2:]
    for f, s in sorted(zip(files, scores(q, files)), key=lambda x: -x[1]): print(f"{s:.3f}  {f}")
