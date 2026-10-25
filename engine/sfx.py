"""Sound design synthesised in code: whoosh, pop, tick, thud, shimmer and a soft ducked beat."""
import numpy as np

_rng = np.random.default_rng(7)   # fixed seed -> identical mix every run


def _t(d, sr): return np.arange(int(d * sr)) / sr


def whoosh(sr, d=0.45):
    n = int(d * sr); x = _rng.standard_normal(n)
    cut = np.linspace(0.02, 0.35, n) ** 1.5; y = np.empty(n); s = 0.0
    for i in range(n): s += cut[i] * (x[i] - s); y[i] = s
    return 0.9 * y * np.sin(np.linspace(0, np.pi, n)) ** 2 / (np.abs(y).max() + 1e-9)


def pop(sr, f=900):
    t = _t(0.09, sr); return np.sin(2 * np.pi * np.cumsum(f * np.exp(-t * 18)) / sr) * np.exp(-t * 40)


def tick(sr, *_): t = _t(0.03, sr); return np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 160) * 0.8


def thud(sr, *_):
    t = _t(0.45, sr)
    return np.sin(2 * np.pi * np.cumsum(95 * np.exp(-t * 6) + 40) / sr) * np.exp(-t * 7) + _rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.25


def shimmer(sr, d=0.7):
    t = _t(d, sr); x = sum(np.sin(2 * np.pi * f * t) for f in (1760, 2217, 2637, 3520)) / 4
    e = np.ones(len(t)); na = int(0.02 * sr); e[:na] = np.linspace(0, 1, na); nr = int(d * 0.8 * sr); e[-nr:] *= np.linspace(1, 0, nr)
    return x * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)) * e * 0.5


def beat_bed(sr, total, bpm=100):
    out = np.zeros(int(total * sr)); step = 60 / bpm
    k = _t(0.25, sr); kick = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-k * 12) + 42) / sr) * np.exp(-k * 9)
    h = _t(0.05, sr); hat = _rng.standard_normal(len(h)) * np.exp(-h * 70) * 0.25
    t, i = 0.0, 0
    while t < total:
        s = int(t * sr); src = kick if i % 2 == 0 else hat
        e = min(len(out), s + len(src)); out[s:e] += src[: e - s]; t += step / 2; i += 1
    nf = min(len(out) // 2, int(1.5 * sr)); fade = np.ones(len(out)); fade[:nf] = np.linspace(0, 1, nf); fade[-nf:] = np.linspace(1, 0, nf)
    return out * fade


GEN = {"whoosh": whoosh, "pop": pop, "tick": tick, "thud": thud, "shimmer": shimmer}


def render_mix(vo, sr, events, total):
    N = len(vo); fx = np.zeros(N)
    for kind, t, gain, args in events:
        s = GEN[kind](sr, *args); st = max(0, int(t * sr)); e = min(N, st + len(s))
        if e > st: fx[st:e] += gain * s[: e - st]
    bed = np.pad(beat_bed(sr, N / sr), (0, N))[:N]
    w = int(0.2 * sr); venv = np.convolve(np.abs(vo), np.ones(w) / w, mode="same")
    duck = 1 - 0.55 * np.clip(venv / (venv.max() + 1e-9) * 4, 0, 1)
    m = vo + fx * 0.22 + bed * 0.10 * duck
    return (m / max(1.0, np.abs(m).max() / 0.95)).astype("float32")
