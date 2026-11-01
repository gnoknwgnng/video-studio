"""Sound design synthesised in code (no files, no licences): whooshes, pops, ticks, thuds, shimmers and a
background music bed in one of several moods. The music ducks automatically under the voice.

Moods: upbeat (default), calm, dramatic, tech, news, none. Or bring your own track: "music": "song.mp3".
"""
import numpy as np

_rng = np.random.default_rng(7)   # fixed seed -> identical mix every run
MOODS = ("upbeat", "calm", "dramatic", "tech", "news", "none")


def _t(d, sr): return np.arange(int(d * sr)) / sr


def whoosh(sr, d=0.45):
    n = int(d * sr); x = _rng.standard_normal(n)
    # one-pole low-pass with a rising cutoff, vectorised in blocks
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


GEN = {"whoosh": whoosh, "pop": pop, "tick": tick, "thud": thud, "shimmer": shimmer}


# ------------------------------------------------------------------ music
def _hz(midi): return 440.0 * 2 ** ((midi - 69) / 12)


def _place(out, src, start):
    s = int(start); e = min(len(out), s + len(src))
    if e > s: out[s:e] += src[: e - s]


def _env(n, sr, a=0.01, r=0.3):
    e = np.ones(n); na = max(1, min(n, int(a * sr))); nr = max(1, min(n, int(r * sr)))
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr); return e


def _kick(sr): k = _t(0.25, sr); return np.sin(2 * np.pi * np.cumsum(70 * np.exp(-k * 12) + 42) / sr) * np.exp(-k * 9)
def _hat(sr): h = _t(0.05, sr); return _rng.standard_normal(len(h)) * np.exp(-h * 70) * 0.25
def _snare(sr): s = _t(0.18, sr); return (_rng.standard_normal(len(s)) * 0.5 + np.sin(2 * np.pi * 190 * s) * 0.5) * np.exp(-s * 22)


def _pad(sr, notes, d, bright=0.3):
    t = _t(d, sr); x = np.zeros(len(t))
    for n in notes:
        f = _hz(n)
        for det in (-0.12, 0.0, 0.12):   # slightly detuned saw-ish tone (3 harmonics)
            ff = f * 2 ** (det / 12)
            x += np.sin(2 * np.pi * ff * t) + bright * np.sin(4 * np.pi * ff * t) / 2 + bright * 0.5 * np.sin(6 * np.pi * ff * t) / 3
    return x / (len(notes) * 3) * _env(len(t), sr, a=min(0.8, d * 0.3), r=min(1.0, d * 0.4))


def _pluck(sr, note, d=0.35):
    t = _t(d, sr); f = _hz(note)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 9)


def _bass(sr, note, d):
    t = _t(d, sr); f = _hz(note)
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * _env(len(t), sr, 0.01, 0.12)


# I - V - vi - IV and friends, as (root, chord) in MIDI notes
PROG = {
    "upbeat":   [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [57, 60, 64]), (41, [57, 60, 65])],
    "calm":     [(41, [57, 60, 64, 69]), (43, [59, 62, 67]), (45, [57, 60, 64, 67]), (48, [60, 64, 67, 71])],
    "dramatic": [(38, [50, 53, 57]), (34, [50, 53, 58]), (36, [48, 52, 55]), (33, [49, 52, 57])],
    "tech":     [(45, [57, 60, 64]), (41, [57, 60, 65]), (48, [55, 60, 64]), (43, [55, 59, 62])],
    "news":     [(40, [52, 55, 59]), (36, [52, 55, 60]), (38, [50, 54, 57]), (35, [50, 54, 59])],
}
BPM = {"upbeat": 104, "calm": 72, "dramatic": 80, "tech": 118, "news": 96}


def music_bed(sr, total, mood="upbeat"):
    mood = mood if mood in PROG else "upbeat"
    N = int(total * sr); out = np.zeros(N + sr)
    beat = 60 / BPM[mood]; bar = beat * 4; prog = PROG[mood]
    nb = int(np.ceil(total / bar)) + 1
    for b in range(nb):
        t0 = b * bar; root, chord = prog[b % len(prog)]
        if mood in ("calm", "dramatic", "news"):
            _place(out, _pad(sr, chord, bar * 1.05, 0.15 if mood == "calm" else 0.35) * 0.55, t0 * sr)
        if mood == "upbeat":
            _place(out, _pad(sr, chord, bar, 0.25) * 0.25, t0 * sr)
            for k in range(8):
                _place(out, _kick(sr) if k % 4 == 0 else (_snare(sr) * 0.7 if k % 4 == 2 else _hat(sr)), (t0 + k * beat / 2) * sr)
                if k % 2 == 0: _place(out, _bass(sr, root, beat * 0.45) * 0.5, (t0 + k * beat / 2) * sr)
        elif mood == "tech":
            for k in range(16):
                _place(out, _pluck(sr, chord[k % len(chord)] + (12 if k % 8 >= 4 else 0)) * 0.28, (t0 + k * beat / 4) * sr)
                if k % 4 == 0: _place(out, _kick(sr) * 0.8, (t0 + k * beat / 4) * sr)
                if k % 4 == 2: _place(out, _hat(sr), (t0 + k * beat / 4) * sr)
            _place(out, _bass(sr, root, bar * 0.9) * 0.35, t0 * sr)
        elif mood == "dramatic":
            _place(out, _bass(sr, root - 12, bar) * 0.6, t0 * sr)
            _place(out, _kick(sr) * 1.2, t0 * sr)
            if b % 2 == 1: _place(out, _kick(sr) * 0.9, (t0 + beat * 2.5) * sr)
        elif mood == "news":
            for k in range(8): _place(out, _hat(sr) * (0.9 if k % 2 == 0 else 0.5), (t0 + k * beat / 2) * sr)
            _place(out, _pluck(sr, chord[0] + 12, 0.25) * 0.3, t0 * sr)
            _place(out, _kick(sr) * 0.6, t0 * sr); _place(out, _kick(sr) * 0.6, (t0 + 2 * beat) * sr)
        elif mood == "calm":
            for k in range(4): _place(out, _pluck(sr, chord[k % len(chord)] + 12, 0.6) * 0.12, (t0 + k * beat) * sr)
    out = out[:N]
    nf = min(N // 2, int(1.5 * sr)); fade = np.ones(N); fade[:nf] = np.linspace(0, 1, nf); fade[-nf:] = np.linspace(1, 0, nf)
    out *= fade
    return out / (np.abs(out).max() + 1e-9)


def beat_bed(sr, total, bpm=100):   # kept for compatibility with older code
    return music_bed(sr, total, "upbeat")


def render_mix(vo, sr, events, total, mood="upbeat", music=None, music_volume=None, sfx_volume=1.0):
    """Voice + sound effects + music (synthesised `mood`, or `music` = a float array at `sr`), with ducking."""
    N = len(vo); fx = np.zeros(N)
    for kind, t, gain, args in events:
        s = GEN[kind](sr, *args); st = max(0, int(t * sr)); e = min(N, st + len(s))
        if e > st: fx[st:e] += gain * s[: e - st]
    if music is not None:
        bed = np.resize(music, N) if len(music) < N else music[:N]   # loop a short track
        nf = min(N // 2, int(2.0 * sr)); bed = bed.copy(); bed[-nf:] *= np.linspace(1, 0, nf)
        bed = bed / (np.abs(bed).max() + 1e-9)
        vol = 0.16 if music_volume is None else float(music_volume)
    elif mood and mood != "none":
        bed = np.pad(music_bed(sr, N / sr, mood), (0, N))[:N]
        vol = {"calm": 0.13, "dramatic": 0.14, "upbeat": 0.10, "tech": 0.11, "news": 0.11}.get(mood, 0.10) if music_volume is None else float(music_volume)
    else:
        bed, vol = np.zeros(N), 0.0
    w = int(0.2 * sr); venv = np.convolve(np.abs(vo), np.ones(w) / w, mode="same")
    duck = 1 - 0.55 * np.clip(venv / (venv.max() + 1e-9) * 4, 0, 1)
    m = vo + fx * 0.22 * float(sfx_volume) + bed * vol * duck
    return (m / max(1.0, np.abs(m).max() / 0.95)).astype("float32")
