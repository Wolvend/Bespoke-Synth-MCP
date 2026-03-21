"""
render_beat.py
Synthesize the hardstyle / techno / breakcore + chibi cute beat and export as MP3.

160 BPM | F# minor | 4 bars | 5 layers
  1. Kick        — hardstyle pitch-envelope + saturation
  2. Snare/HH    — noise burst drums with ghost notes
  3. Bass        — sawtooth with LP filter and overdrive
  4. Chord stabs — 7-voice supersaw
  5. Chibi lead  — FM synthesis with vibrato + sparkle overtone

Run:  python render_beat.py
Out:  tracks/hardstyle_chibi_final.mp3
"""

import pathlib, time
import numpy as np
from scipy.signal import butter, sosfilt

SR     = 44100
BPM    = 160.0
S16    = 60_000 / BPM / 4          # 16th note duration in ms = 93.75
rng    = np.random.default_rng(42)  # deterministic noise

TRACKS = pathlib.Path(__file__).resolve().parent / "tracks"
TRACKS.mkdir(exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────────────

def samp(ms):        return int(ms * SR / 1000)
def hz(midi):        return 440.0 * 2.0 ** ((midi - 69) / 12.0)
def ms_step(step):   return round(step * S16)

def lpf(x, cut, order=4):
    sos = butter(order, min(cut, SR/2 - 1) / (SR / 2), btype="low",  output="sos")
    return sosfilt(sos, x)

def hpf(x, cut, order=2):
    sos = butter(order, min(cut, SR/2 - 1) / (SR / 2), btype="high", output="sos")
    return sosfilt(sos, x)

def adsr(n, atk_s, dec_s, sus, rel_s):
    env = np.zeros(n)
    a = min(int(atk_s * SR), n)
    d = min(int(dec_s * SR), n - a)
    r = min(int(rel_s * SR), n - a - d)
    s = n - a - d - r
    if a: env[:a]           = np.linspace(0, 1, a)
    if d: env[a:a+d]        = np.linspace(1, sus, d)
    if s: env[a+d:a+d+s]   = sus
    if r: env[-r:]          = np.linspace(sus, 0, r)
    return env

def stamp(buf, sig, start_ms):
    s = samp(start_ms)
    end = min(s + len(sig), len(buf))
    if end > s >= 0:
        buf[s:end] += sig[:end - s]

def sawtooth(freq, n):
    """Additive sawtooth — 8 harmonics."""
    t = np.arange(n) / SR
    w = np.zeros(n)
    for k in range(1, 9):
        w += ((-1) ** (k + 1)) * np.sin(2 * np.pi * freq * k * t) / k
    return w

# ── instruments ──────────────────────────────────────────────────────────────

def make_kick():
    dur = 0.58
    n   = samp(dur * 1000)
    t   = np.arange(n) / SR
    # pitch envelope: 195 Hz → 42 Hz
    freq = 42.0 + (195.0 - 42.0) * np.exp(-t * 14)
    phase = np.cumsum(2 * np.pi * freq / SR)
    body  = np.sin(phase)
    sub   = np.sin(2 * np.pi * 42 * t)
    amp   = np.exp(-t * 5.2)
    amp[:samp(6)] *= np.linspace(0, 1, samp(6))
    # click transient
    cn    = samp(14)
    click = rng.uniform(-1, 1, n)
    click = hpf(click, 2800) * np.exp(-np.arange(n) * 350 / SR)
    click[cn:] = 0
    raw = (body * 0.72 + sub * 0.28) * amp + click * 0.38
    return np.tanh(raw * 2.4) / np.tanh(2.4) * 0.88


def make_snare(vel=1.0):
    dur = 0.20
    n   = samp(dur * 1000)
    t   = np.arange(n) / SR
    noise = hpf(rng.uniform(-1, 1, n), 1400)
    tone  = np.sin(2 * np.pi * 195 * t)
    env   = np.exp(-t * 20)
    return (noise * 0.68 + tone * 0.32) * env * vel * 0.72


def make_chh():
    n   = samp(40)
    t   = np.arange(n) / SR
    sig = hpf(rng.uniform(-1, 1, n), 9000)
    return sig * np.exp(-t * 90) * 0.42


def make_ohh():
    n   = samp(230)
    t   = np.arange(n) / SR
    sig = hpf(rng.uniform(-1, 1, n), 6500)
    return sig * np.exp(-t * 11) * 0.50


def make_crash():
    n   = samp(700)
    t   = np.arange(n) / SR
    lo  = hpf(rng.uniform(-1, 1, n), 1500)
    hi  = hpf(rng.uniform(-1, 1, n), 5000)
    env = np.exp(-t * 4.5)
    return (lo * 0.55 + hi * 0.45) * env * 0.65


def make_bass(pitch, dur_ms):
    f = hz(pitch)
    n = samp(dur_ms)
    w = sawtooth(f, n)
    w = lpf(w, min(f * 4.5, 1100))
    w = w * adsr(n, 0.004, 0.025, 0.78, 0.04)
    return np.tanh(w * 1.8) / np.tanh(1.8) * 0.54


def make_stab(pitch, dur_ms, vel=0.85):
    f = hz(pitch)
    n = samp(dur_ms)
    detunes = [-0.16, -0.09, -0.04, 0.0, 0.04, 0.09, 0.16]
    wave = np.zeros(n)
    for det in detunes:
        fd   = f * (2 ** (det / 12))
        wave += sawtooth(fd, n) / len(detunes)
    wave = wave * adsr(n, 0.007, 0.07, 0.45, 0.04)
    wave = lpf(wave, 4000)
    return wave * vel * 0.30


def make_lead(pitch, dur_ms, vel=1.0):
    f = hz(pitch)
    n = samp(dur_ms)
    t = np.arange(n) / SR
    # FM: modulator at 3× carrier, index scales with velocity
    mod_idx = 2.6 + vel * 0.7
    # Vibrato (ramps in after 18 ms)
    vib_start = samp(18)
    vib = np.zeros(n)
    if n > vib_start:
        vt   = np.arange(n - vib_start) / SR
        ramp = np.minimum(vt * 14, 1.0)
        vib[vib_start:] = np.sin(2 * np.pi * 5.4 * vt) * 0.0045 * f * ramp
    mod     = mod_idx * np.sin(2 * np.pi * f * 3 * t)
    carrier = np.sin(2 * np.pi * f * t + mod + vib)
    sparkle = np.sin(2 * np.pi * f * 2 * t) * 0.20   # bright overtone
    wave    = (carrier * 0.80 + sparkle) * adsr(n, 0.003, 0.035, 0.74, 0.025)
    return wave * vel * 0.38


def simple_reverb(sig, decay=0.28):
    """Multi-tap delay reverb for the lead channel."""
    out = sig.copy()
    for delay_ms, gain in [(38, decay), (72, decay * 0.55), (118, decay * 0.28)]:
        d = samp(delay_ms)
        if len(sig) > d:
            padded = np.zeros(len(sig))
            padded[d:] = sig[:-d]
            out += padded * gain
    return out


def limit(sig, threshold=0.92):
    """Soft brick-wall limiter."""
    over   = np.abs(sig) > threshold
    sig[over] = np.sign(sig[over]) * (threshold + np.tanh(np.abs(sig[over]) - threshold) * (1 - threshold))
    return sig

# ── beat schedule ─────────────────────────────────────────────────────────────

def build_beat():
    """Return full note list: (at_ms, layer, pitch, velocity, dur_ms)."""
    notes = []

    def add(at_ms, layer, pitch, vel, dur_ms):
        notes.append((at_ms, layer, pitch, vel, dur_ms))

    # KICK — hardstyle 4-on-floor bars 1-2, double-kick bar 3, breakcore fill bar 4
    for s in [0, 8, 16, 24,
              32, 36, 40, 42, 44,
              48, 50, 54, 56, 58, 60, 62]:
        add(ms_step(s), "kick", 36, 127, 0)

    # SNARE — beats 2 & 4
    for s in [4, 12, 20, 28, 36, 44, 52, 60]:
        add(ms_step(s), "snare", 38, 100, 0)

    # GHOST SNARES
    for s in [2, 6, 10, 14, 22, 26, 30, 38, 46, 50, 54, 58]:
        add(ms_step(s), "ghost", 38, 40, 0)

    # CLOSED HI-HAT — every 8th note
    for s in range(0, 64, 2):
        add(ms_step(s), "chh", 42, 65, 0)

    # OPEN HI-HAT — off-beats
    for s in [2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 50, 54, 58, 62]:
        add(ms_step(s), "ohh", 46, 82, 0)

    # CRASH — bar 1 and bar 3 downbeat
    for s in [0, 32]:
        add(ms_step(s), "crash", 49, 110, 0)

    # BASS — syncopated F# minor walking line
    for s, p, v in [
        (0, 54, 100), (3, 57, 90), (6, 54, 95), (11, 59, 85),
        (16, 61, 100), (19, 59, 90), (22, 57, 88), (27, 56, 82),
        (32, 54, 100), (35, 57, 95), (38, 54, 92), (40, 62, 100), (43, 61, 95),
        (48, 54, 100), (50, 57, 95), (52, 54, 90), (54, 64, 100), (56, 62, 97), (58, 61, 93),
    ]:
        add(ms_step(s), "bass", p, v, 140)

    # CHORD STABS — supersaw triads
    def stab_chord(steps, pitches):
        for s in steps:
            for p in pitches:
                add(ms_step(s), "stab", p, 82, 185)

    stab_chord([0, 4, 8, 12],    [66, 69, 73])   # bar 1: F# minor
    stab_chord([16, 20, 24],     [71, 74, 78])   # bar 2: B minor
    stab_chord([32, 36, 40],     [62, 66, 69])   # bar 3: D major (bright pivot)
    stab_chord([48, 52, 56],     [66, 69, 73])   # bar 4: F# minor

    # CHIBI SPARKLE LEAD — FM synth, F#5–F#6 range
    lead_schedule = [
        # bar 1: ascending then descending sparkle
        (0,78,95),(1,81,100),(2,85,105),(3,88,110),(4,85,105),(5,81,100),(6,80,90),(7,78,85),
        (8,81,95),(9,85,100),(10,88,105),(11,86,108),(12,85,100),(13,83,95),(14,81,90),(15,80,85),
        # bar 2: upper register, energetic
        (16,90,110),(17,88,105),(18,85,100),(19,83,95),(20,81,90),(21,83,95),(22,85,100),(23,88,105),
        (24,90,110),(25,88,105),(26,85,100),(27,81,95),(28,80,90),(29,81,92),(30,83,95),(31,85,100),
        # bar 3: breakcore intensity — ascending flurry then repeat
        (32,78,110),(33,81,110),(34,85,110),(35,88,110),(36,90,110),(37,88,105),(38,85,100),(39,81,95),
        (40,90,110),(41,88,105),(42,85,100),(43,81,95),(44,80,90),(45,81,92),(46,83,95),(47,85,100),
        # bar 4: chibi resolution — descend then reascend to final peak
        (48,88,105),(49,86,102),(50,85,100),(51,83,97),(52,81,95),(53,80,90),(54,78,85),(55,80,88),
        (56,81,92),(57,83,95),(58,85,100),(59,88,105),(60,90,110),(61,88,105),(62,85,100),(63,81,95),
    ]
    for s, p, v in lead_schedule:
        add(ms_step(s), "lead", p, v, 78)

    return notes


# ── render ────────────────────────────────────────────────────────────────────

def render():
    print("Building beat schedule...")
    notes = build_beat()
    print(f"  {len(notes)} events across 4 bars")

    total_ms = ms_step(64) + 700     # 4 bars + 700ms tail for reverb/decay
    total_n  = samp(total_ms)

    # Separate mix buses
    drums_bus = np.zeros(total_n)
    bass_bus  = np.zeros(total_n)
    chord_bus = np.zeros(total_n)
    lead_bus  = np.zeros(total_n)

    # Pre-cache percussion samples (deterministic noise)
    kick_s  = make_kick()
    snare_s = make_snare(1.0)
    ghost_s = make_snare(0.40)
    chh_s   = make_chh()
    ohh_s   = make_ohh()
    crash_s = make_crash()

    print("Rendering notes...")
    for at_ms, layer, pitch, vel, dur_ms in notes:
        v = vel / 127.0
        if   layer == "kick":  stamp(drums_bus, kick_s,               at_ms)
        elif layer == "snare": stamp(drums_bus, snare_s,              at_ms)
        elif layer == "ghost": stamp(drums_bus, ghost_s,              at_ms)
        elif layer == "chh":   stamp(drums_bus, chh_s * v,            at_ms)
        elif layer == "ohh":   stamp(drums_bus, ohh_s * v,            at_ms)
        elif layer == "crash": stamp(drums_bus, crash_s,              at_ms)
        elif layer == "bass":  stamp(bass_bus,  make_bass(pitch, dur_ms), at_ms)
        elif layer == "stab":  stamp(chord_bus, make_stab(pitch, dur_ms, v), at_ms)
        elif layer == "lead":  stamp(lead_bus,  make_lead(pitch, dur_ms, v), at_ms)

    print("Applying effects...")
    # Lead reverb for shimmer
    lead_wet = simple_reverb(lead_bus, decay=0.30)

    # Mix buses with careful levels
    master = (
        drums_bus * 0.90
        + bass_bus  * 0.82
        + chord_bus * 0.70
        + lead_wet  * 0.88
    )

    # Normalize to -2 dBFS then limit
    peak = np.max(np.abs(master))
    if peak > 0:
        master = master / peak * 0.80
    master = limit(master, threshold=0.94)

    # Stereo: slight width on stabs and lead
    t_arr  = np.arange(total_n) / SR
    pan_hz = 0.15    # very slow pan LFO
    pan_l  = np.cos(2 * np.pi * pan_hz * t_arr) * 0.08
    left   = master + pan_l * chord_bus * 0.25 + pan_l * lead_wet * 0.20
    right  = master - pan_l * chord_bus * 0.25 - pan_l * lead_wet * 0.20
    stereo = np.stack([left, right], axis=-1)

    # Final clip guard
    stereo = np.clip(stereo, -1.0, 1.0)

    # ── export ───────────────────────────────────────────────────────────────
    print("Exporting...")
    wav_path = TRACKS / "hardstyle_chibi_final.wav"
    mp3_path = TRACKS / "hardstyle_chibi_final.mp3"

    import soundfile as sf
    sf.write(str(wav_path), stereo.astype(np.float32), SR, subtype="FLOAT")
    size_wav = wav_path.stat().st_size / 1024
    print(f"  WAV: {wav_path.name}  ({size_wav:.0f} KB)")

    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_wav(str(wav_path))
        seg.export(str(mp3_path), format="mp3", bitrate="320k",
                   tags={"title": "Hardstyle Chibi Final",
                         "artist": "BespokeSynth MCP",
                         "genre":  "Hardstyle / Breakcore",
                         "bpm":    "160"})
        size_mp3 = mp3_path.stat().st_size / 1024
        dur_s    = len(stereo) / SR
        print(f"  MP3: {mp3_path.name}  ({size_mp3:.0f} KB  {dur_s:.2f}s  320kbps)")
        wav_path.unlink()   # keep only the MP3
        return mp3_path
    except Exception as exc:
        print(f"  MP3 conversion failed ({exc}), WAV kept.")
        return wav_path


if __name__ == "__main__":
    t0  = time.perf_counter()
    out = render()
    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.2f}s  ->  {out}")
