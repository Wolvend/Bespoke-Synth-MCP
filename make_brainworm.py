#!/usr/bin/env python
"""
BRAINWORM PROTOCOL - Breakcore Track Generator
=============================================
Full multichannel mixer, FM synthesis, pedalboard FX chain.
Key: A minor  |  BPM: 174  |  Stereo 44.1 kHz  |  320 kbps MP3
"""

import numpy as np
from scipy import signal
from scipy.signal import fftconvolve
from pydub import AudioSegment
from pedalboard import (
    Pedalboard, Reverb, Delay, Distortion, Compressor, HighpassFilter,
    LowpassFilter, Chorus, Limiter
)
from pathlib import Path
from datetime import datetime
import json

# ─── Constants ────────────────────────────────────────────────────────────────
SR   = 44100
BPM  = 174
BEAT = 60.0 / BPM                    # seconds per beat
S16  = BEAT / 4                      # 16th-note duration in seconds
BAR  = BEAT * 4                      # bar duration in seconds

# A-minor pentatonic + extensions
FREQ = {
    "A2": 110.0,  "C3": 130.8, "D3": 146.8, "E3": 164.8, "G3": 196.0,
    "A3": 220.0,  "C4": 261.6, "D4": 293.7, "E4": 329.6, "G4": 392.0,
    "A4": 440.0,  "C5": 523.3, "D5": 587.3, "E5": 659.3, "G5": 784.0,
    "F4": 349.2,  "B3": 246.9, "B4": 493.9,
}

# ─── Utility ──────────────────────────────────────────────────────────────────

def t_arr(dur_s):
    return np.linspace(0, dur_s, int(dur_s * SR), endpoint=False)

def adsr(n, atk_s, dec_s, sus_lvl, rel_s):
    env = np.ones(n)
    a = int(atk_s * SR);   d = int(dec_s * SR);   r = int(rel_s * SR)
    if a: env[:a] = np.linspace(0, 1, a)
    de = min(a + d, n)
    if de > a: env[a:de] = np.linspace(1, sus_lvl, de - a)
    re = max(0, n - r)
    if re < n: env[re:] = np.linspace(sus_lvl, 0, n - re)
    return env

def normalize(x, headroom=1.05):
    peak = np.max(np.abs(x))
    return x / (peak * headroom) if peak > 0 else x

def tanh_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)

def stereo(mono_l, mono_r=None):
    if mono_r is None: mono_r = mono_l
    return np.stack([mono_l, mono_r], axis=-1).astype(np.float32)

# ─── Mixer ────────────────────────────────────────────────────────────────────

class Mixer:
    """Stereo timeline mixer. All positions in seconds."""

    def __init__(self, duration_s):
        self.n = int(duration_s * SR)
        self.buf = np.zeros((self.n, 2), dtype=np.float32)

    def place(self, audio, pos_s, gain=1.0, pan=0.0):
        """Place mono or stereo audio at pos_s. pan: -1=L, 0=C, 1=R."""
        start = int(pos_s * SR)
        if start >= self.n:
            return
        if audio.ndim == 1:
            audio = stereo(audio)
        length = min(len(audio), self.n - start)
        lv = gain * np.cos((pan + 1) * np.pi / 4)
        rv = gain * np.sin((pan + 1) * np.pi / 4)
        self.buf[start:start + length, 0] += audio[:length, 0] * lv
        self.buf[start:start + length, 1] += audio[:length, 1] * rv

    def export_mp3(self, path, bitrate="320k"):
        audio = normalize(self.buf)
        # Render through master limiter
        board = Pedalboard([Limiter(threshold_db=-0.5, release_ms=50)])
        audio = board(audio.T.copy(), SR).T
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        seg = AudioSegment(
            pcm.flatten().tobytes(), frame_rate=SR, sample_width=2, channels=2
        )
        seg.export(str(path), format="mp3", bitrate=bitrate)

# ─── Synthesizers ─────────────────────────────────────────────────────────────

def kick_808(dur_s=0.7, f_start=200, f_end=45, vel=1.0):
    """808 kick: pitch-swept sine + transient click."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    # Exponential pitch sweep
    pitch = f_end + (f_start - f_end) * np.exp(-t * 22)
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    body  = np.sin(phase)
    # Click transient (short burst of noise → highpassed)
    ck_n  = int(0.006 * SR)
    click = np.random.uniform(-1, 1, ck_n) * np.exp(-np.arange(ck_n) / SR * 400)
    # Amplitude envelope
    amp = np.exp(-t * 6)
    amp[:int(0.003 * SR)] = 1.0
    audio = body * amp * 0.9
    audio[:ck_n] += click * 0.25
    return normalize(tanh_clip(audio, 1.8)) * vel

def snare_crack(dur_s=0.22, tone_f=230, vel=1.0):
    """Snare: noise burst + tonal body."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * tone_f * t)
    noise = np.random.uniform(-1, 1, n)
    # Filter noise: band-limited crack
    b, a = signal.butter(3, [800, 8000], fs=SR, btype='bandpass')
    noise = signal.lfilter(b, a, noise)
    amp   = np.exp(-t * 28)
    trans = np.exp(-t * 120)  # sharp transient
    audio = (tone * 0.35 + noise * 0.65) * amp + trans * 0.3
    return normalize(audio) * vel

def hihat(dur_s=0.04, open_=False, vel=1.0):
    """Closed or open hi-hat."""
    if open_: dur_s = max(dur_s, 0.28)
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    noise = np.random.uniform(-1, 1, n)
    b, a = signal.butter(4, 6000, fs=SR, btype='high')
    noise = signal.lfilter(b, a, noise)
    amp   = np.exp(-t * (8 if open_ else 80))
    return normalize(noise * amp) * vel

def tom_drum(dur_s=0.3, f_start=180, f_end=80, vel=1.0):
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    pitch = f_end + (f_start - f_end) * np.exp(-t * 18)
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    body  = np.sin(phase)
    amp   = np.exp(-t * 9)
    return normalize(body * amp) * vel

def bass_reese(freq, dur_s=0.5, vel=1.0):
    """Detuned dual-saw Reese bass with growl."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    detune = 0.008
    ph1 = 2 * np.pi * freq * (1 - detune) * t
    ph2 = 2 * np.pi * freq * (1 + detune) * t
    # Sawtooth: DSF approximation (sum of harmonics)
    def saw(ph): return 2*(ph/(2*np.pi) - np.floor(ph/(2*np.pi) + 0.5))
    osc = saw(ph1) * 0.55 + saw(ph2) * 0.55
    # Low-pass + mild drive
    b, a = signal.butter(3, min(freq * 4, 2000), fs=SR, btype='low')
    osc  = signal.lfilter(b, a, osc)
    env  = adsr(n, 0.008, 0.08, 0.75, 0.15)
    return normalize(tanh_clip(osc * env, 2.5)) * vel

def fm_lead(freq, dur_s=0.12, mod_ratio=2.14, mod_idx=6.0, vel=1.0):
    """FM synthesis lead: metallic, bright, hook-y."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    f_mod = freq * mod_ratio
    mod   = mod_idx * np.sin(2 * np.pi * f_mod * t)
    # Slight mod envelope (decay)
    mod  *= np.exp(-t * 4)
    carrier = np.sin(2 * np.pi * freq * t + mod)
    # Second partial for brightness
    carrier += 0.35 * np.sin(2 * np.pi * freq * 2 * t)
    env = adsr(n, 0.003, dur_s * 0.25, 0.5, dur_s * 0.3)
    return normalize(carrier * env) * vel

def pad_chord(freqs, dur_s=2.0, vel=0.45):
    """Lush stacked sine pad."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    audio = np.zeros(n)
    for f in freqs:
        detune = np.random.uniform(-0.003, 0.003)
        audio += np.sin(2 * np.pi * f * (1 + detune) * t)
    env = adsr(n, 0.25, 0.4, 0.7, 0.6)
    b, a = signal.butter(2, min(max(freqs) * 3, 8000), fs=SR, btype='low')
    audio = signal.lfilter(b, a, audio)
    return normalize(audio * env) * vel

# ─── FX Chains ────────────────────────────────────────────────────────────────

def fx_kick(audio):
    """Kick FX: light compression, tiny room."""
    board = Pedalboard([
        Compressor(threshold_db=-10, ratio=4, attack_ms=1, release_ms=80),
    ])
    return board(stereo(audio).T.copy(), SR).T

def fx_snare(audio):
    """Snare FX: reverb tail."""
    board = Pedalboard([
        Reverb(room_size=0.2, damping=0.8, wet_level=0.18, dry_level=0.82),
    ])
    return board(stereo(audio).T.copy(), SR).T

def fx_lead(audio):
    """Lead FX: chorus + plate reverb + delay."""
    board = Pedalboard([
        Chorus(rate_hz=0.9, depth=0.35, centre_delay_ms=6, mix=0.35),
        Delay(delay_seconds=S16 * 2, feedback=0.28, mix=0.25),
        Reverb(room_size=0.45, damping=0.5, wet_level=0.3, dry_level=0.7),
    ])
    return board(stereo(audio).T.copy(), SR).T

def fx_bass(audio):
    """Bass FX: drive + low-pass."""
    board = Pedalboard([
        Distortion(drive_db=8),
        LowpassFilter(cutoff_frequency_hz=800),
        Compressor(threshold_db=-8, ratio=3),
    ])
    return board(stereo(audio).T.copy(), SR).T

def fx_pad(audio):
    """Pad FX: wide reverb."""
    board = Pedalboard([
        Reverb(room_size=0.75, damping=0.3, wet_level=0.55, dry_level=0.45),
    ])
    return board(stereo(audio).T.copy(), SR).T

def apply_fx(raw, fx_fn):
    processed = fx_fn(raw)
    return processed

# ─── Pattern helpers ──────────────────────────────────────────────────────────

def pos(bar, beat, subdivision=0, sub_div=4):
    """Return absolute position in seconds.
       bar: 0-indexed bar
       beat: 0-indexed beat within bar (0-3)
       subdivision: 0-indexed subdivision within beat
       sub_div: number of subdivisions per beat (default 4 = 16th notes)
    """
    return bar * BAR + beat * BEAT + subdivision * (BEAT / sub_div)

def sixteenth(bar, n):
    """Return position of n-th 16th note in bar (0-indexed)."""
    return bar * BAR + n * S16

# ─── Song: "Brainworm Protocol" ───────────────────────────────────────────────

SONG_BARS = 24                        # Total bars
mix = Mixer(SONG_BARS * BAR + 2.0)   # Extra tail

# ── Brainworm Hook melody (8th-note grid) ────────────────────────────────────
# Repeating 2-bar hook in A minor, obsessively catchy
hook_bar1 = [
    ("E4", 0), ("E4", 1), ("G4", 2), ("A4", 3),
    ("G4", 4), ("E4", 5), ("D4", 6), ("C4", 7),
]
hook_bar2 = [
    ("D4", 0), ("E4", 1), ("G4", 2), ("A4", 3),
    ("G4", 4), ("E4", 5), ("A4", 6),
]

def place_hook(bar, gain=1.0, vel=1.0):
    """Place 2-bar brainworm hook starting at 'bar'."""
    dur = S16 * 2  # 8th note
    for note, step in hook_bar1:
        t = bar * BAR + step * dur
        raw = fm_lead(FREQ[note], dur * 0.92, vel=vel)
        fxd = apply_fx(raw, fx_lead)
        mix.place(fxd, t, gain=gain, pan=0.0)
    for note, step in hook_bar2:
        t = (bar + 1) * BAR + step * dur
        raw = fm_lead(FREQ[note], dur * 0.92, vel=vel)
        fxd = apply_fx(raw, fx_lead)
        mix.place(fxd, t, gain=gain, pan=0.0)

# ── Bass line (syncopated A minor) ───────────────────────────────────────────
bass_pattern = [
    ("A2", 0.0),  ("A2", 0.5), ("E3", 1.0),
    ("G3", 1.5),  ("A2", 2.0), ("D3", 2.5),
    ("E3", 3.0),  ("A2", 3.5),
]

def place_bass(bar, gain=0.9, vel=1.0):
    for note, beat_pos in bass_pattern:
        t = bar * BAR + beat_pos * BEAT
        raw = bass_reese(FREQ[note], BEAT * 0.45, vel=vel)
        fxd = apply_fx(raw, fx_bass)
        mix.place(fxd, t, gain=gain, pan=0.05)

# ── Drums ─────────────────────────────────────────────────────────────────────
# 16th-note positions (0-15) within a bar
kick_grid  = [0, 6, 8, 11, 14]          # syncopated breakcore kick
snare_grid = [4, 10, 12, 15]            # snare positions
hh_grid    = list(range(16))            # all 16th notes
hh_open    = [8]                        # open hat every half-bar
tom_fills  = {                          # special bars get tom fills
    "A": [(12, 280, 140), (13, 230, 110), (14, 180, 90)],   # (16th, f_start, f_end)
    "B": [(12, 200, 100), (13, 180, 85), (14, 150, 70)],
}

def place_drums(bar, gain=1.0, fill=None, vel_scale=1.0):
    # Kicks
    for s in kick_grid:
        t = sixteenth(bar, s)
        vel = (0.85 + 0.15 * np.random.random()) * vel_scale
        raw = kick_808(vel=vel)
        fxd = apply_fx(raw, fx_kick)
        mix.place(fxd, t, gain=gain)

    # Snares
    for s in snare_grid:
        t = sixteenth(bar, s)
        vel = (0.75 + 0.2 * np.random.random()) * vel_scale
        raw = snare_crack(vel=vel)
        fxd = apply_fx(raw, fx_snare)
        mix.place(fxd, t, gain=gain * 0.9, pan=0.05)

    # Hi-hats with velocity humanization
    for s in hh_grid:
        t = sixteenth(bar, s)
        is_open = s in hh_open
        vel = (0.4 + 0.5 * np.random.random()) * vel_scale
        raw = hihat(open_=is_open, vel=vel)
        mix.place(stereo(raw), t, gain=gain * 0.55, pan=-0.2)

    # Optional tom fills (last 4 16th notes of bar)
    if fill in tom_fills:
        for s, fs, fe in tom_fills[fill]:
            t = sixteenth(bar, s)
            raw = tom_drum(f_start=fs, f_end=fe, vel=0.85 * vel_scale)
            fxd = apply_fx(raw, fx_snare)
            mix.place(fxd, t, gain=gain * 0.8, pan=0.1)

# ─── Arrange the song ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  BRAINWORM PROTOCOL  |  174 BPM  |  A minor  |  Stereo 44.1kHz")
print("=" * 70)

# === SECTION 1: INTRO (bars 0-3) =============================================
# Sparse: just pad + ghost melody
print("\n[INTRO]  bars 0–3  — atmospheric pad + ghost hook")
a_minor_pad = [FREQ["A3"], FREQ["E4"], FREQ["G4"], FREQ["C4"]]
for b in range(0, 4, 2):
    raw = pad_chord(a_minor_pad, BAR * 2)
    fxd = apply_fx(raw, fx_pad)
    mix.place(fxd, b * BAR, gain=0.5)

# Ghost hook (quiet, lead only, no bass)
for b in [0, 2]:
    place_hook(b, gain=0.35, vel=0.6)

# Single kick on bar 0 beat 0 for timing cue
raw = kick_808(vel=0.5)
mix.place(apply_fx(raw, fx_kick), 0.0, gain=0.6)
raw = kick_808(vel=0.5)
mix.place(apply_fx(raw, fx_kick), BAR * 2, gain=0.6)

# === SECTION 2: DROP 1 (bars 4-11) ==========================================
# Full energy: drums + bass + hook
print("[DROP 1] bars 4–11  — full kit + bass + brainworm hook")

for b in range(4, 12):
    fill = "A" if (b - 4) % 4 == 3 else None
    place_drums(b, gain=1.0, fill=fill)
    place_bass(b, gain=0.92)

# Hook loops every 2 bars
for b in range(4, 12, 2):
    place_hook(b, gain=0.88, vel=0.95)

# Extra accent hits on the drop
raw = kick_808(f_start=250, f_end=50, vel=1.0)
mix.place(apply_fx(raw, fx_kick), 4 * BAR, gain=1.1)

# === SECTION 3: BREAK (bars 12-15) ==========================================
# Tension: bass + hook only (drums drop out mostly), rising pads
print("[BREAK]  bars 12–15 — bass + hook, drums stripped back")

for b in range(12, 16):
    # Sparse kick only
    for s in [0, 8]:
        raw = kick_808(vel=0.7)
        mix.place(apply_fx(raw, fx_kick), sixteenth(b, s), gain=0.75)
    # Snare on 2 and 4 only
    for s in [4, 12]:
        raw = snare_crack(vel=0.65)
        mix.place(apply_fx(raw, fx_snare), sixteenth(b, s), gain=0.7)
    place_bass(b, gain=0.8)

for b in range(12, 16, 2):
    place_hook(b, gain=0.95, vel=1.0)

# Rising pad for tension
rise_freqs = [FREQ["E4"], FREQ["G4"], FREQ["A4"], FREQ["C5"]]
raw = pad_chord(rise_freqs, 4 * BAR, vel=0.5)
fxd = apply_fx(raw, fx_pad)
mix.place(fxd, 12 * BAR, gain=0.6)

# === SECTION 4: DROP 2 (bars 16-23) =========================================
# Maximum energy: everything + tom fills + extra syncopation
print("[DROP 2] bars 16–23 — full chaos + fills + climax")

for b in range(16, 24):
    fill = "B" if (b - 16) % 2 == 1 else ("A" if (b - 16) % 4 == 3 else None)
    place_drums(b, gain=1.05, fill=fill, vel_scale=1.05)
    place_bass(b, gain=0.95)

for b in range(16, 24, 2):
    place_hook(b, gain=0.95, vel=1.0)

# Extra high hook (octave up) for climax
hook_octave = [(note.replace("4", "5").replace("3", "4"), step) for note, step in hook_bar1]
for step_idx, (note, step) in enumerate(hook_octave):
    if note not in FREQ:
        continue
    t = 20 * BAR + step * S16 * 2
    raw = fm_lead(FREQ[note], S16 * 2 * 0.9, mod_ratio=1.5, mod_idx=4.0, vel=0.8)
    fxd = apply_fx(raw, fx_lead)
    mix.place(fxd, t, gain=0.6, pan=0.3)

# Crash into final bar
raw = hihat(dur_s=1.2, open_=True, vel=1.0)
mix.place(stereo(raw), 22 * BAR, gain=0.8, pan=-0.15)
raw = hihat(dur_s=1.2, open_=True, vel=1.0)
mix.place(stereo(raw), 23 * BAR, gain=0.6)

# Final hit
raw = kick_808(f_start=220, f_end=40, vel=1.0)
mix.place(apply_fx(raw, fx_kick), 24 * BAR, gain=1.2)
raw = snare_crack(vel=1.0)
mix.place(apply_fx(raw, fx_snare), 24 * BAR + 0.01, gain=1.0)

# ─── Export ───────────────────────────────────────────────────────────────────
tracks_dir = Path(__file__).parent / "tracks"
tracks_dir.mkdir(exist_ok=True)

timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
mp3_name   = f"brainworm_protocol_{timestamp}.mp3"
mp3_path   = tracks_dir / mp3_name

print(f"\n[RENDER] Exporting {SONG_BARS * BAR + 2.0:.1f} seconds of audio...")
mix.export_mp3(mp3_path, bitrate="320k")

# Metadata
meta = {
    "title":      "Brainworm Protocol",
    "timestamp":  datetime.now().isoformat(),
    "bpm":        BPM,
    "key":        "A minor",
    "bars":       SONG_BARS,
    "duration_s": round(SONG_BARS * BAR + 2.0, 2),
    "sample_rate": SR,
    "channels":   2,
    "bitrate":    "320kbps",
    "presets_used": [
        "kick_808 (pitch-swept sine + click transient)",
        "snare_crack (bandpass noise + tonal body)",
        "hihat (closed/open noise burst)",
        "tom_drum (pitch-swept sine)",
        "bass_reese (dual-detuned sawtooth + drive)",
        "fm_lead (frequency modulation, mod_ratio=2.14)",
        "pad_chord (stacked sine detuned)",
    ],
    "fx_chains": {
        "kick":  "Compressor",
        "snare": "Reverb",
        "lead":  "Chorus + Delay + Reverb",
        "bass":  "Distortion + LowpassFilter + Compressor",
        "pad":   "Wide Reverb",
        "master": "Limiter",
    },
    "sections": [
        {"name": "Intro",  "bars": "0-3",   "description": "Pad + ghost hook"},
        {"name": "Drop 1", "bars": "4-11",  "description": "Full drums + bass + hook"},
        {"name": "Break",  "bars": "12-15", "description": "Sparse drums + hook"},
        {"name": "Drop 2", "bars": "16-23", "description": "Full chaos + fills + octave hook"},
    ],
    "file": mp3_name,
}

meta_path = tracks_dir / f"brainworm_protocol_{timestamp}.json"
meta_path.write_text(json.dumps(meta, indent=2))

size_kb = mp3_path.stat().st_size / 1024
dur = SONG_BARS * BAR + 2.0

print("\n" + "=" * 70)
print("  BRAINWORM PROTOCOL — COMPLETE")
print("=" * 70)
print(f"  File:       {mp3_path.name}")
print(f"  Location:   {mp3_path.absolute()}")
print(f"  Size:       {size_kb:.0f} KB")
print(f"  Duration:   {dur:.1f}s  ({SONG_BARS} bars @ {BPM} BPM)")
print(f"  Format:     Stereo 44.1 kHz  320 kbps MP3")
print(f"  Key/BPM:    A minor / {BPM}")
print(f"  Sections:   Intro > Drop1 > Break > Drop2 > Hit")
print(f"  Presets:    7 synth voices")
print(f"  FX:         Chorus, Delay, Reverb, Distortion, Compressor, Limiter")
print("=" * 70)
print(f"\n  -> {mp3_path.absolute()}\n")
