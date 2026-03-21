#!/usr/bin/env python
"""
BLUBBER BEATS: DIG DUG FOREVER
================================
Spec-faithful implementation of the BespokeSynth build guide.
Hook: B4-D5-G4-B4 looping forever in G Major at 160 BPM.
Sections: Intro → Verse → Chorus → Bridge → Final Chorus → Outro
"""

import numpy as np
from scipy import signal
from pydub import AudioSegment
from pedalboard import (
    Pedalboard, Reverb, Delay, Compressor, HighpassFilter,
    LowpassFilter, Chorus, Limiter, Distortion
)
from pathlib import Path
from datetime import datetime
import json

# ─── Constants ────────────────────────────────────────────────────────────────
SR   = 44100
BPM  = 160
BEAT = 60.0 / BPM          # 0.375 s per quarter note
BAR  = BEAT * 4            # 1.500 s per bar
S8   = BEAT / 2            # 8th note
S16  = BEAT / 4            # 16th note

# G Major frequencies (spec: B4=71, D5=74, G4=67)
FREQ = {
    "G2": 98.0,  "B2": 123.5, "D3": 146.8, "G3": 196.0,
    "B3": 246.9, "D4": 293.7, "G4": 392.0, "B4": 493.9,
    "D5": 587.3, "G5": 784.0, "A4": 440.0, "E4": 329.6,
    "C5": 523.3, "F4": 349.2, "A3": 220.0,
}

# THE HOOK: B4-D5-G4-B4 (quarter notes)
HOOK = ["B4", "D5", "G4", "B4"]

# ─── Utility ──────────────────────────────────────────────────────────────────

def adsr_env(n, atk_s, dec_s, sus, rel_s, sr=SR):
    env = np.ones(n, dtype=np.float32)
    a = int(atk_s * sr); d = int(dec_s * sr); r = int(rel_s * sr)
    if a: env[:a] = np.linspace(0, 1, a)
    de = min(a+d, n)
    if de > a: env[a:de] = np.linspace(1, sus, de-a)
    rs = max(0, n-r)
    if rs < n: env[rs:] = np.linspace(sus, 0, n-rs)
    return env

def normalize(x):
    p = np.max(np.abs(x))
    return x / (p * 1.05) if p > 0 else x

def stereo(a, b=None):
    if b is None: b = a
    return np.stack([a, b], axis=-1).astype(np.float32)

def db(val): return 10 ** (val / 20.0)    # dB → linear


# ─── Mixer ────────────────────────────────────────────────────────────────────

class Mixer:
    def __init__(self, dur_s):
        self.n   = int(dur_s * SR)
        self.buf = np.zeros((self.n, 2), dtype=np.float32)

    def place(self, audio, pos_s, gain=1.0, pan=0.0):
        start = int(pos_s * SR)
        if start >= self.n: return
        if audio.ndim == 1:
            audio = stereo(audio)
        length = min(len(audio), self.n - start)
        lv = gain * np.cos((pan+1)*np.pi/4)
        rv = gain * np.sin((pan+1)*np.pi/4)
        self.buf[start:start+length, 0] += audio[:length, 0] * lv
        self.buf[start:start+length, 1] += audio[:length, 1] * rv

    def export_mp3(self, path, bitrate="320k"):
        audio = normalize(self.buf)
        board = Pedalboard([Limiter(threshold_db=-0.3, release_ms=100)])
        audio = board(audio.T.copy(), SR).T
        pcm   = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        seg   = AudioSegment(
            pcm.flatten().tobytes(), frame_rate=SR, sample_width=2, channels=2
        )
        seg.export(str(path), format="mp3", bitrate=bitrate)


# ─── Synthesizers (spec-faithful) ─────────────────────────────────────────────

def lead_sine(freq, dur_s, vel=1.0, lfo_depth=5.0, lfo_rate=6.5):
    """Spec: Sine Osc, A=4ms D=50ms S=0.6 R=40ms + LFO shimmer."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    # LFO: arcade shimmer (+/- 5 Hz depth at 6.5 Hz)
    lfo  = lfo_depth * np.sin(2 * np.pi * lfo_rate * t)
    # Integrate phase with LFO modulation
    phase = 2 * np.pi * np.cumsum(freq + lfo) / SR
    osc  = np.sin(phase)
    env  = adsr_env(n, 0.004, 0.05, 0.6, 0.04)
    return (osc * env * vel).astype(np.float32)

def bass_sine(freq, dur_s, vel=1.0):
    """Spec: Sine Bass, A=3ms D=40ms S=0.4 R=30ms — bouncy."""
    n   = int(dur_s * SR)
    t   = np.arange(n) / SR
    osc = np.sin(2 * np.pi * freq * t)
    env = adsr_env(n, 0.003, 0.04, 0.4, 0.03)
    return (osc * env * vel).astype(np.float32)

def kick_synth(vel=1.0):
    """Spec: KickSynth — 110→50 Hz sweep, 100ms decay, gain 0.60."""
    dur_s = 0.55
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    pitch = 50 + (110 - 50) * np.exp(-t * 22)
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    body  = np.sin(phase)
    amp   = np.exp(-t * (1/0.10))      # 100ms amplitude decay
    # Click transient
    ck_n  = int(0.005 * SR)
    click = np.random.uniform(-1, 1, ck_n) * np.exp(-np.arange(ck_n)/SR*500)
    audio = body * amp
    audio[:ck_n] += click * 0.3
    return (normalize(audio) * vel).astype(np.float32)

def clap_synth(vel=1.0):
    """Spec: White noise, HP ~300 Hz, 80ms decay, gain 0.25."""
    dur_s = 0.20
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    noise = np.random.uniform(-1, 1, n).astype(np.float32)
    b, a  = signal.butter(3, 300, fs=SR, btype='high')
    noise = signal.lfilter(b, a, noise)
    amp   = np.exp(-t * (1/0.08))      # 80ms decay
    return (normalize(noise * amp) * vel).astype(np.float32)

def hihat_synth(open_=False, vel=0.4):
    """Hi-hat (extra color, not in spec but realistic)."""
    dur_s = 0.25 if open_ else 0.03
    n     = int(dur_s * SR)
    t     = np.arange(n) / SR
    noise = np.random.uniform(-1, 1, n).astype(np.float32)
    b, a  = signal.butter(4, 7000, fs=SR, btype='high')
    noise = signal.lfilter(b, a, noise)
    amp   = np.exp(-t * (8 if open_ else 120))
    return (normalize(noise * amp) * vel).astype(np.float32)


# ─── FX chains ────────────────────────────────────────────────────────────────

def fx_lead(raw, section="verse"):
    """Lead: mild chorus + reverb tail."""
    depth = 0.25 if section == "chorus" else 0.15
    board = Pedalboard([
        Chorus(rate_hz=6.5, depth=depth, centre_delay_ms=3, mix=0.3),
        Reverb(room_size=0.2, damping=0.7, wet_level=0.12, dry_level=0.88),
    ])
    return board(stereo(raw).T.copy(), SR).T

def fx_bass(raw):
    board = Pedalboard([
        LowpassFilter(cutoff_frequency_hz=600),
        Compressor(threshold_db=-12, ratio=3, attack_ms=5, release_ms=60),
    ])
    return board(stereo(raw).T.copy(), SR).T

def fx_kick(raw):
    board = Pedalboard([
        Compressor(threshold_db=-8, ratio=5, attack_ms=1, release_ms=80),
    ])
    return board(stereo(raw).T.copy(), SR).T

def fx_clap(raw):
    board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=300),
        Reverb(room_size=0.18, wet_level=0.20, dry_level=0.80),
    ])
    return board(stereo(raw).T.copy(), SR).T

def fx_master_section(mix_buf, section="verse"):
    """Per-section bus glue — compression, slight reverb for chorus."""
    if section == "chorus":
        board = Pedalboard([
            Compressor(threshold_db=-6, ratio=2.5),
            Distortion(drive_db=2),
        ])
    else:
        board = Pedalboard([Compressor(threshold_db=-8, ratio=2)])
    return board(mix_buf.T.copy(), SR).T


# ─── Spec gain values (linear) ────────────────────────────────────────────────
G_LEAD  = db(-3)    # -3 dB
G_BASS  = db(-6)    # -6 dB
G_KICK  = db(0)     # 0 dB (spec: gain 0.60 — will apply internally)
G_CLAP  = db(-6)    # -6 dB


# ─── Placing helpers ──────────────────────────────────────────────────────────

def place_hook(mix, bar, notes_per_bar=1, vel=1.0, section="verse"):
    """Place the B4-D5-G4-B4 hook. notes_per_bar controls speed."""
    hook_len = len(HOOK)
    if notes_per_bar == 1:
        # One full hook (4 quarter notes) per bar
        for i, note in enumerate(HOOK):
            t   = bar * BAR + i * BEAT
            raw = lead_sine(FREQ[note], BEAT * 0.88, vel=vel)
            fxd = fx_lead(raw, section)
            mix.place(fxd, t, gain=G_LEAD * 0.40, pan=0.0)
    elif notes_per_bar == 2:
        # Two hooks per bar (8th notes)
        step = S8
        for rep in range(2):
            for i, note in enumerate(HOOK):
                t   = bar * BAR + rep * (BEAT * 2) + i * step
                raw = lead_sine(FREQ[note], step * 0.85, vel=vel, lfo_depth=6.0)
                fxd = fx_lead(raw, section)
                mix.place(fxd, t, gain=G_LEAD * 0.40, pan=0.0)
    elif notes_per_bar == 3:
        # Three hooks (16th notes — final chorus chaos)
        step = S16
        for rep in range(4):
            for i, note in enumerate(HOOK):
                t   = bar * BAR + rep * BEAT + i * step
                raw = lead_sine(FREQ[note], step * 0.8, vel=vel, lfo_depth=8.0, lfo_rate=8.0)
                fxd = fx_lead(raw, section)
                mix.place(fxd, t, gain=G_LEAD * 0.42, pan=np.random.uniform(-0.15, 0.15))
    elif notes_per_bar == 0.5:
        # Half-speed (bridge) — one hook every 2 bars
        for i, note in enumerate(HOOK):
            t   = bar * BAR + i * BEAT * 2
            raw = lead_sine(FREQ[note], BEAT * 1.8, vel=vel, lfo_depth=3.0)
            fxd = fx_lead(raw, section)
            mix.place(fxd, t, gain=G_LEAD * 0.40, pan=0.0)

def place_bass(mix, bar, pattern="verse"):
    """Spec bass patterns per section."""
    if pattern == "off":
        return
    elif pattern == "verse":
        # G3 beat 0, D3 beat 2
        for note, beat in [("G3", 0), ("D3", 2)]:
            t   = bar * BAR + beat * BEAT
            raw = bass_sine(FREQ[note], BEAT * 0.85)
            fxd = fx_bass(raw)
            mix.place(fxd, t, gain=G_BASS * 0.15, pan=0.05)
    elif pattern == "chorus":
        # Every beat: G3 D3 G3 B2
        for note, beat in [("G3", 0), ("D3", 1), ("G3", 2), ("B2", 3)]:
            t   = bar * BAR + beat * BEAT
            raw = bass_sine(FREQ[note], BEAT * 0.80)
            fxd = fx_bass(raw)
            mix.place(fxd, t, gain=G_BASS * 0.15, pan=0.05)
    elif pattern == "bridge":
        # G3 held 4 beats
        t   = bar * BAR
        raw = bass_sine(FREQ["G3"], BAR * 0.9)
        fxd = fx_bass(raw)
        mix.place(fxd, t, gain=G_BASS * 0.15, pan=0.05)
    elif pattern == "final":
        # Every half-beat (8th note), busy ascending pattern
        busy = ["G3", "B3", "D4", "G3", "B2", "D3", "G3", "B3"]
        for i, note in enumerate(busy):
            t   = bar * BAR + i * S8
            raw = bass_sine(FREQ[note], S8 * 0.75, vel=0.9)
            fxd = fx_bass(raw)
            mix.place(fxd, t, gain=G_BASS * 0.17, pan=0.05)

def place_kick(mix, bar, pattern="verse"):
    """Kick patterns per section."""
    if pattern == "intro":
        # Beat 1 only
        beats = [0]
    elif pattern == "verse":
        # Beats 1 and 3 (X.X.)
        beats = [0, 2]
    elif pattern == "chorus":
        # Syncopated: 1, 2.5, 3
        beats = [0, 1.5, 2, 3.5]
    elif pattern == "bridge":
        # Beat 1 only
        beats = [0]
    elif pattern == "final":
        # Busy: 1, 1.75, 2, 2.5, 3, 3.5
        beats = [0, 0.75, 1, 1.5, 2, 2.5, 3, 3.5]
    elif pattern == "outro":
        beats = [0, 2]
    else:
        beats = [0, 2]

    for beat in beats:
        t   = bar * BAR + beat * BEAT
        vel = 0.85 + 0.15 * np.random.random()
        raw = kick_synth(vel=vel)
        fxd = fx_kick(raw)
        mix.place(fxd, t, gain=G_KICK * 0.60, pan=0.0)

def place_clap(mix, bar, pattern="verse"):
    """Clap patterns per section."""
    if pattern == "intro":
        # Occasional, beat 3 only
        beats = [2]
    elif pattern == "verse":
        # Beats 2 and 4 (.X.X)
        beats = [1, 3]
    elif pattern == "chorus":
        # Syncopated: 2, 3, 4
        beats = [1, 2, 3, 3.5]
    elif pattern == "bridge":
        beats = []
    elif pattern == "final":
        # All claps + offbeats
        beats = [0.5, 1, 1.5, 2, 2.5, 3, 3.5]
    elif pattern == "outro":
        beats = [1, 3]
    else:
        beats = [1, 3]

    for beat in beats:
        t   = bar * BAR + beat * BEAT
        vel = 0.7 + 0.25 * np.random.random()
        raw = clap_synth(vel=vel)
        fxd = fx_clap(raw)
        mix.place(fxd, t, gain=G_CLAP * 0.25, pan=0.08)


# ─── Song structure ───────────────────────────────────────────────────────────
# Total: 8+8+8+4+8+4 = 40 bars × 1.5 s = 60 s + 2 s tail
SONG_BARS = 40
mix = Mixer(SONG_BARS * BAR + 2.5)

np.random.seed(42)   # reproducible humanization

print("\n" + "=" * 70)
print("  BLUBBER BEATS: DIG DUG FOREVER  |  160 BPM  |  G Major  |  Stereo")
print("=" * 70)

# ─── INTRO (bars 0-7): Lead only, kick on beat 1, occasional clap ────────────
print("\n[INTRO]  bars 0–7   — hook enters alone, kick on 1, sparse clap")
for b in range(0, 8):
    place_hook(mix, b, notes_per_bar=1, vel=0.70, section="intro")
    place_kick(mix, b, "intro")
    if b % 2 == 1:
        place_clap(mix, b, "intro")

# ─── VERSE (bars 8-15): Lead + Bass, kick 1&3, clap 2&4 ─────────────────────
print("[VERSE]  bars 8–15  — bass enters, full kick+clap pattern")
for b in range(8, 16):
    place_hook(mix, b, notes_per_bar=1, vel=0.85, section="verse")
    place_bass(mix, b, "verse")
    place_kick(mix, b, "verse")
    place_clap(mix, b, "verse")

# ─── CHORUS (bars 16-23): 2x hook, full busy drums, all bass ─────────────────
print("[CHORUS] bars 16–23 — 2x hook speed, busy drums, chorus bass")
for b in range(16, 24):
    place_hook(mix, b, notes_per_bar=2, vel=0.95, section="chorus")
    place_bass(mix, b, "chorus")
    place_kick(mix, b, "chorus")
    place_clap(mix, b, "chorus")
    # Add open hi-hat on off-beats
    for beat in [0.5, 1.5, 2.5, 3.5]:
        t   = b * BAR + beat * BEAT
        raw = hihat_synth(open_=True, vel=0.35)
        mix.place(stereo(raw), t, gain=0.18, pan=-0.25)

# ─── BRIDGE (bars 24-27): Slow hook, bass hold, kick on 1 only ───────────────
print("[BRIDGE] bars 24–27 — slow, clear, tension (half-speed hook)")
for b in range(24, 28):
    if b % 2 == 0:   # half-speed: one hook per 2 bars
        place_hook(mix, b, notes_per_bar=0.5, vel=0.80, section="bridge")
    place_bass(mix, b, "bridge")
    place_kick(mix, b, "bridge")
    # No clap in bridge

# ─── FINAL CHORUS (bars 28-35): 4x hook (16ths), max chaos ──────────────────
print("[FINAL]  bars 28–35 — 4x hook, busiest drums, maximum energy")
for b in range(28, 36):
    place_hook(mix, b, notes_per_bar=3, vel=1.0, section="chorus")
    place_bass(mix, b, "final")
    place_kick(mix, b, "final")
    place_clap(mix, b, "final")
    # Closed hi-hat 16th notes
    for s in range(16):
        t   = b * BAR + s * S16
        raw = hihat_synth(vel=0.3 + 0.2 * (s % 4 == 0))
        mix.place(stereo(raw), t, gain=0.14, pan=-0.2)

# ─── OUTRO (bars 36-39): Slow fade, hook thins out ───────────────────────────
print("[OUTRO]  bars 36–39 — fading, slowing, goodbye")
for b in range(36, 40):
    fade = 1.0 - (b - 36) / 5.0     # linear fade
    place_hook(mix, b, notes_per_bar=1, vel=fade * 0.75, section="verse")
    place_bass(mix, b, "verse")
    place_kick(mix, b, "outro")
    if b < 38:
        place_clap(mix, b, "outro")

# Final sting
t_sting = 40 * BAR
raw = lead_sine(FREQ["G4"], 1.0, vel=0.9)
mix.place(fx_lead(raw, "verse"), t_sting, gain=G_LEAD * 0.40 * 0.8)
raw = kick_synth(vel=1.0)
mix.place(fx_kick(raw), t_sting, gain=0.6)

# ─── Export ───────────────────────────────────────────────────────────────────
tracks_dir = Path(__file__).parent / "tracks"
tracks_dir.mkdir(exist_ok=True)

ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
mp3_name = f"blubber_beats_{ts}.mp3"
mp3_path = tracks_dir / mp3_name

dur_s = SONG_BARS * BAR + 2.5
print(f"\n[RENDER] Exporting {dur_s:.1f}s stereo at 320 kbps ...")
mix.export_mp3(mp3_path)

size_kb = mp3_path.stat().st_size / 1024
meta = {
    "title":    "Blubber Beats: Dig Dug Forever",
    "bpm":      BPM,
    "key":      "G Major",
    "hook":     "B4-D5-G4-B4",
    "bars":     SONG_BARS,
    "dur_s":    round(dur_s, 2),
    "sr":       SR,
    "channels": 2,
    "bitrate":  "320k",
    "sections": [
        {"name": "Intro",        "bars": "0–7"},
        {"name": "Verse",        "bars": "8–15"},
        {"name": "Chorus",       "bars": "16–23"},
        {"name": "Bridge",       "bars": "24–27"},
        {"name": "Final Chorus", "bars": "28–35"},
        {"name": "Outro",        "bars": "36–39"},
    ],
    "synth_spec": {
        "lead_osc":   "SINE, A=4ms D=50ms S=0.6 R=40ms, LFO 6.5Hz/5Hz depth",
        "bass_osc":   "SINE, A=3ms D=40ms S=0.4 R=30ms",
        "kick":       "Pitch sweep 110→50 Hz, 100ms decay",
        "clap":       "White noise, HP 300Hz, 80ms decay",
        "mixer_gain": "Lead -3dB, Bass -6dB, Kick 0dB, Clap -6dB",
    },
    "file": mp3_name,
}
(tracks_dir / f"blubber_beats_{ts}.json").write_text(json.dumps(meta, indent=2))

print("\n" + "=" * 70)
print("  BLUBBER BEATS: DIG DUG FOREVER — DONE")
print("=" * 70)
print(f"  File:      {mp3_name}")
print(f"  Location:  {mp3_path.absolute()}")
print(f"  Size:      {size_kb:.0f} KB")
print(f"  Duration:  {dur_s:.1f}s  ({SONG_BARS} bars)")
print(f"  Format:    Stereo 44.1 kHz  320 kbps  MP3")
print(f"  Key/BPM:   G Major / {BPM} BPM")
print(f"  Hook:      B4 → D5 → G4 → B4  (forever)")
print("=" * 70)
print(f"\n  -> {mp3_path.absolute()}\n")
