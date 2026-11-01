"""2.5D photos and subject cutouts, on the CPU, with open models (downloaded once, then cached):

  IS-Net general use   (Apache-2.0, Qin et al. "DIS"; the model behind rembg) -> the main subject cut out of the photo
  Depth Anything V2 S  (Apache-2.0, Yang et al.)         -> what is near / far, for scenery without one clear subject

layers(photo) writes two pictures next to the photo:
  <name>.fg.png   the subject (or the near part of the scene) with a soft transparent edge
  <name>.bg.jpg   the photo with that part smudged away, so nothing doubles when the layers move apart
The photo scene then moves the two layers at different speeds -> a "3D camera" move from one still photo.
"""
import os, time, urllib.request
import numpy as np
from PIL import Image, ImageFilter

CACHE = os.environ.get("VIDEO_STUDIO_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "video-studio")
MODELS = {
    "cutout": ("https://huggingface.co/tomjackson2023/rembg/resolve/main/isnet-general-use.onnx", "isnet-general-use.onnx", 1024),
    "depth": ("https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_quantized.onnx", "depth_anything_v2_small_q.onnx", 518),
}
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
_sessions = {}


def log(*a): print("[2.5d]", *a, flush=True)


def _session(kind):
    if kind not in _sessions:
        import onnxruntime as ort
        url, fn, _ = MODELS[kind]
        path = os.path.join(CACHE, "models", fn)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            log(f"downloading the {kind} model (first run only)")
            req = urllib.request.Request(url, headers={"User-Agent": "video-studio"})
            with urllib.request.urlopen(req, timeout=300) as r, open(path + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            os.replace(path + ".part", path)
        so = ort.SessionOptions(); so.intra_op_num_threads = max(1, os.cpu_count() or 1)
        _sessions[kind] = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
    return _sessions[kind]


def _prep(img, w, h):
    x = np.asarray(img.convert("RGB").resize((w, h), Image.BICUBIC), np.float32) / 255.0
    return ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)


def cutout_mask(img):
    s = _session("cutout"); n = MODELS["cutout"][2]
    x = np.asarray(img.convert("RGB").resize((n, n), Image.LANCZOS), np.float32)
    x = (x / max(x.max(), 1e-6) - 0.5).transpose(2, 0, 1)[None].astype(np.float32)        # rembg's IS-Net preprocessing
    m = np.squeeze(s.run(None, {s.get_inputs()[0].name: x})[0]).astype(np.float32)
    m = (m - m.min()) / (m.max() - m.min() + 1e-6)
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR), np.float32) / 255


def depth_map(img):
    s = _session("depth"); n = MODELS["depth"][2]
    w, h = img.size; sc = n / min(w, h)
    W, H = max(14, int(round(w * sc / 14)) * 14), max(14, int(round(h * sc / 14)) * 14)
    d = np.squeeze(s.run(None, {s.get_inputs()[0].name: _prep(img, W, H)})[0]).astype(np.float32)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)          # 1 = near
    return np.asarray(Image.fromarray((d * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR), np.float32) / 255


def _fill_behind(img, alpha, radius=None):
    """Fill the area behind the foreground from its surroundings, coarse to fine (pyramid of normalised blurs),
    so the hole is never black however big it is, and moved layers never show a doubled edge."""
    x = np.asarray(img.convert("RGB"), np.float32)
    H, W = alpha.shape
    keep = np.clip(1 - alpha * 1.8, 0, 1)
    fill = None
    for f in (64, 32, 16, 8, 4):
        w, h = max(2, W // f), max(2, H // f)
        k = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).resize((w, h), Image.BOX), np.float32) / 255
        xi = np.asarray(img.convert("RGB").resize((w, h), Image.BOX), np.float32)
        kb = np.asarray(Image.fromarray((k * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
        nb = np.stack([np.asarray(Image.fromarray(np.clip(xi[..., c] * k, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)
                       for c in range(3)], -1)
        est = nb / np.maximum(kb[..., None], 1e-3)
        ok = (kb > 0.08)[..., None]
        if fill is None: est = np.where(ok, est, xi.mean(axis=(0, 1)))
        else:
            up = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32)
            est = np.where(ok, est, up)
        fill = est
    fill = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3)), np.float32)
    a = np.clip(alpha * 1.4, 0, 1)[..., None]
    return Image.fromarray(np.clip(x * (1 - a) + fill * a, 0, 255).astype(np.uint8))


def layers(photo_path, max_side=1440):
    """Make <photo>.fg.png and <photo>.bg.jpg. Returns {"fg", "bg", "mode": "cutout"|"depth", "box": [x,y,w,h] (0-1)} or None."""
    base = os.path.splitext(photo_path)[0]
    fg_p, bg_p = base + ".fg.png", base + ".bg.jpg"
    try:
        img = Image.open(photo_path).convert("RGB")
        if max(img.size) > max_side:
            k = max_side / max(img.size); img = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
        t0 = time.time()
        m = cutout_mask(img)
        cov = float((m > 0.5).mean())
        confident = float(np.mean(np.abs(m - 0.5) > 0.4))
        mode = "cutout"
        if not (0.05 <= cov <= 0.75 and confident > 0.85):
            d = depth_map(img)
            thr = np.quantile(d, 0.72)
            m = np.clip((d - thr) / 0.12, 0, 1)
            cov = float((m > 0.5).mean()); mode = "depth"
            if not (0.06 <= cov <= 0.55): log(f"no clear foreground in {os.path.basename(photo_path)}; plain photo"); return None
        alpha = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2 if mode == "cutout" else 6)), np.float32) / 255
        ys, xs = np.where(alpha > 0.5)
        box = [float(xs.min() / img.width), float(ys.min() / img.height), float((xs.max() - xs.min()) / img.width), float((ys.max() - ys.min()) / img.height)]
        fg = img.copy(); fg.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
        fg.save(fg_p, optimize=True)
        _fill_behind(img, alpha).save(bg_p, quality=90)
        log(f"{os.path.basename(photo_path)}: {mode} layer ({cov:.0%} of the picture, {time.time() - t0:.1f}s)")
        return {"fg": fg_p, "bg": bg_p, "mode": mode, "box": box}
    except Exception as e:
        log(f"WARN 2.5D skipped for {os.path.basename(photo_path)} ({str(e)[:140]})")
        return None
