#!/usr/bin/env python
"""
KAWAII DESTRUCTION - Chibi Game Hardstyle Breakcore
=====================================================
Super cute arcade game melody meets HARD hardstyle kicks
meets chaotic breakcore drums. Maximum happiness, maximum damage.
Key: C Major  |  BPM: 175  |  Stereo 44.1 kHz  |  320 kbps
"""

import numpy as np
from scipy import signal
from pydub import AudioSegment
from pedalboard import (
    Pedalboard, Reverb, Delay, Compressor, HighpassFilter,
    LowpassFilter, Chorus, Limiter, Distortion, PitchShift
)
from pathlib import Path
from datetime import datetime
import json

# ─── Constants ────────────────────────────────────────────────────────────────
SR   = 44100
BPM  = 175
BEAT = 60.0 / BPM
BAR  = BEAT * 4
S8   = BEAT / 2
S16  = BEAT / 4
S32  = BEAT / 8

# C Major + extensions (bright, happy, game-like)
FREQ = {
    "C3": 130.8, "D3": 146.8, "E3": 164.8, "G3": 196.0, "A3": 220.0,
    "C4": 261.6, "D4": 293.7, "E4": 329.6, "F4": 349.2, "G4": 392.0,
    "A4": 440.0, "B4": 493.9,
    "C5": 523.3, "D5": 587.3, "E5": 659.3, "F5": 698.5, "G5": 784.0,
    "A5": 880.0, "B5": 987.8,
    "C6": 1046.5,"D6": 1174.7,"E6": 1318.5,"G6": 1568.0,
    "Db5": 554.4, "Bb4": 466.2, "Bb5": 932.3,
}

# ─── Utility ──────────────────────────────────────────────────────────────────

def adsr(n, a, d, s, r, sr=SR):
    env = np.ones(n, dtype=np.float32)
    ai = int(a*sr); di = int(d*sr); ri = int(r*sr)
    if ai: env[:ai] = np.linspace(0, 1, ai)
    de = min(ai+di, n)
    if de > ai: env[ai:de] = np.linspace(1, s, de-ai)
    rs = max(0, n-ri)
    if rs < n: env[rs:] = np.linspace(s, 0, n-rs)
    return env

def norm(x, h=1.05):
    p = np.max(np.abs(x))
    return (x / (p*h) if p > 0 else x).astype(np.float32)

def soft_clip(x, drive=1.0):
    return np.tanh(x * drive).astype(np.float32)

def stereo(l, r=None):
    if r is None: r = l
    return np.stack([l, r], -1).astype(np.float32)

# ─── Mixer ────────────────────────────────────────────────────────────────────

class Mixer:
    def __init__(self, dur_s):
        self.n   = int(dur_s * SR)
        self.buf = np.zeros((self.n, 2), dtype=np.float32)

    def place(self, audio, pos_s, gain=1.0, pan=0.0):
        s = int(pos_s * SR)
        if s >= self.n: return
        if audio.ndim == 1: audio = stereo(audio)
        ln = min(len(audio), self.n - s)
        lv = gain * np.cos((pan+1)*np.pi/4)
        rv = gain * np.sin((pan+1)*np.pi/4)
        self.buf[s:s+ln, 0] += audio[:ln, 0] * lv
        self.buf[s:s+ln, 1] += audio[:ln, 1] * rv

    def export_mp3(self, path, bitrate="320k"):
        audio = norm(self.buf)
        board = Pedalboard([Limiter(threshold_db=-0.3, release_ms=80)])
        audio = board(audio.T.copy(), SR).T
        pcm   = (np.clip(audio,-1,1)*32767).astype(np.int16)
        seg   = AudioSegment(
            pcm.flatten().tobytes(), frame_rate=SR, sample_width=2, channels=2)
        seg.export(str(path), format="mp3", bitrate=bitrate)


# ─── Synths ───────────────────────────────────────────────────────────────────

def hardstyle_kick(vel=1.0):
    """The signature hardstyle kick: hard click, pitched sweep, heavy distortion."""
    dur_s = 0.65
    n = int(dur_s * SR)
    t = np.arange(n) / SR

    # Pitch sweep — faster and higher than 808 for that hardstyle punch
    pitch = 55 + (200 - 55) * np.exp(-t * 35)
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    body  = np.sin(phase)

    # Hard transient click (punchy attack)
    ck = int(0.004 * SR)
    click = np.random.uniform(-1, 1, ck) * np.exp(-np.arange(ck)/SR * 800)

    # Amplitude envelope — sharp
    amp = np.exp(-t * 8)
    amp[:int(0.002*SR)] = 1.0

    audio = body * amp
    audio[:ck] += click * 0.5

    # Hardstyle distortion: overdrive the body hard
    audio = soft_clip(audio * 3.5) * 0.7

    # Sub layer — add a softer sub underneath
    sub = np.sin(2*np.pi * 45 * t) * np.exp(-t * 5)
    audio += sub * 0.35

    return norm(audio) * vel

def reverse_bass_riser(vel=0.8, dur_s=0.12):
    """Hardstyle reverse bass: distorted rising pitch played BEFORE the kick."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    # Rising pitch (reverse of kick sweep)
    pitch = 40 + (180 - 40) * (t / dur_s) ** 0.5
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    osc   = np.sin(phase)
    env   = np.linspace(0, 1, n) ** 0.5     # fade in
    audio = soft_clip(osc * env * 4.0) * 0.5
    # High-pass to separate from kick
    b, a = signal.butter(2, 80, fs=SR, btype='high')
    audio = signal.lfilter(b, a, audio)
    return norm(audio) * vel

def xylophone(freq, dur_s=0.18, vel=1.0):
    """Chibi xylophone: FM bell sound, short and bright. Pure game energy."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    # FM bell: high mod ratio for metallic/woody brightness
    fm   = freq * 7.2
    mod  = 4.5 * np.sin(2*np.pi * fm * t) * np.exp(-t * 18)
    car  = np.sin(2*np.pi * freq * t + mod)
    # Second harmonic for richness
    car += 0.25 * np.sin(2*np.pi * freq * 2 * t) * np.exp(-t * 25)
    # Very short decay — plucky
    env  = adsr(n, 0.001, dur_s*0.6, 0.0, dur_s*0.15)
    return norm(car * env) * vel

def coin_sfx(vel=0.9):
    """Classic game coin collect: two-tone ping."""
    dur_s = 0.08
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    # Tone 1 (short) → Tone 2 (higher)
    mid = n // 3
    tone1 = np.sin(2*np.pi * 1046.5 * t[:mid]) * np.exp(-np.arange(mid)/SR * 60)
    tone2 = np.sin(2*np.pi * 1318.5 * t[mid:]) * np.exp(-np.arange(n-mid)/SR * 50)
    audio = np.concatenate([tone1, tone2])
    env   = adsr(n, 0.001, 0.02, 0.5, 0.03)
    return norm(audio * env) * vel

def kawaii_snare(vel=1.0):
    """Higher-pitched, cuter snare — like a cartoon boing with crack."""
    dur_s = 0.16
    n     = int(dur_s * SR)
    t     = np.arange(n) / SR
    # Pitched body (higher than normal snare)
    tone  = np.sin(2*np.pi * 320 * t) * np.exp(-t * 45)
    # Filtered noise burst
    noise = np.random.uniform(-1, 1, n).astype(np.float32)
    b, a  = signal.butter(3, [1000, 12000], fs=SR, btype='bandpass')
    noise = signal.lfilter(b, a, noise) * np.exp(-t * 35)
    # Tiny pitch up at start (boing!)
    boing = np.sin(2*np.pi*(280 + 200*np.exp(-t*80))*t) * np.exp(-t*50) * 0.2
    audio = tone*0.35 + noise*0.65 + boing
    return norm(audio) * vel

def sparkle_hat(vel=0.5, open_=False):
    """Sparkly hi-hat — brighter than normal, game-like."""
    dur_s = 0.22 if open_ else 0.025
    n     = int(dur_s * SR)
    t     = np.arange(n) / SR
    noise = np.random.uniform(-1, 1, n).astype(np.float32)
    b, a  = signal.butter(5, 9000, fs=SR, btype='high')
    noise = signal.lfilter(b, a, noise)
    amp   = np.exp(-t * (5 if open_ else 200))
    return norm(noise * amp) * vel

def chibi_bass(freq, dur_s=0.25, vel=1.0):
    """Bouncy, cartoonish bass — short and punchy with pitch wobble."""
    n   = int(dur_s * SR)
    t   = np.arange(n) / SR
    # Slight pitch bend DOWN at start (cartoon effect)
    pitch = freq * (1 + 0.04 * np.exp(-t * 50))
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    osc   = np.sin(phase)
    # Add 3rd harmonic for punch
    osc  += 0.3 * np.sin(phase * 3)
    env   = adsr(n, 0.003, 0.05, 0.4, 0.04)
    audio = soft_clip(osc * env, 2.0)
    b, a  = signal.butter(3, 400, fs=SR, btype='low')
    audio = signal.lfilter(b, a, audio)
    return norm(audio) * vel

def euphoric_lead(freq, dur_s=0.22, vel=1.0):
    """Hardstyle euphoric lead — saw-based, wide, emotional."""
    n   = int(dur_s * SR)
    t   = np.arange(n) / SR
    # Three detuned sawtooths (classic hardstyle supersaw)
    detunes = [-0.012, 0.0, 0.012]
    osc = np.zeros(n, dtype=np.float32)
    for dt in detunes:
        f   = freq * (1 + dt)
        ph  = 2*np.pi * f * t
        saw = 2*(ph/(2*np.pi) - np.floor(ph/(2*np.pi) + 0.5))
        osc += saw.astype(np.float32) * 0.4
    env = adsr(n, 0.008, dur_s*0.3, 0.55, dur_s*0.25)
    # Lowpass for warmth
    b, a = signal.butter(2, min(freq*5, 8000), fs=SR, btype='low')
    audio = signal.lfilter(b, a, osc * env)
    return norm(audio) * vel

def stab(freq, vel=0.9):
    """Short hardstyle synth stab — punchy accent."""
    dur_s = 0.09
    n   = int(dur_s * SR)
    t   = np.arange(n) / SR
    ph  = 2*np.pi * freq * t
    saw = 2*(ph/(2*np.pi) - np.floor(ph/(2*np.pi) + 0.5))
    sq  = np.sign(np.sin(2*np.pi * freq * 1.5 * t))
    osc = saw * 0.6 + sq * 0.4
    env = adsr(n, 0.001, 0.04, 0.3, 0.04)
    b, a = signal.butter(2, 3000, fs=SR, btype='low')
    audio = signal.lfilter(b, a, osc * env)
    return norm(soft_clip(audio, 2.0)) * vel

def pad_chord(freqs, dur_s, vel=0.4):
    """Dreamy detuned pad for atmosphere."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    audio = np.zeros(n, dtype=np.float32)
    for f in freqs:
        dt  = np.random.uniform(-0.006, 0.006)
        audio += np.sin(2*np.pi * f*(1+dt) * t) * 0.35
    env = adsr(n, 0.3, 0.5, 0.7, 0.8)
    b, a = signal.butter(2, min(max(freqs)*2.5, 7000), fs=SR, btype='low')
    return norm(signal.lfilter(b, a, audio*env)) * vel


# ─── FX chains ────────────────────────────────────────────────────────────────

def apply(raw, board):
    s = stereo(raw) if raw.ndim==1 else raw
    return board(s.T.copy(), SR).T

BOARD_KICK = Pedalboard([
    Compressor(threshold_db=-6, ratio=6, attack_ms=0.5, release_ms=60),
])
BOARD_XYL = Pedalboard([
    Chorus(rate_hz=4.0, depth=0.15, centre_delay_ms=4, mix=0.2),
    Reverb(room_size=0.3, damping=0.5, wet_level=0.22, dry_level=0.78),
    Delay(delay_seconds=S16*1.5, feedback=0.18, mix=0.18),
])
BOARD_LEAD = Pedalboard([
    Chorus(rate_hz=2.5, depth=0.4, centre_delay_ms=8, mix=0.45),
    Reverb(room_size=0.5, damping=0.4, wet_level=0.35, dry_level=0.65),
    Delay(delay_seconds=S8, feedback=0.22, mix=0.2),
])
BOARD_SNARE = Pedalboard([
    Reverb(room_size=0.25, wet_level=0.18, dry_level=0.82),
])
BOARD_BASS = Pedalboard([
    Distortion(drive_db=6),
    LowpassFilter(cutoff_frequency_hz=500),
    Compressor(threshold_db=-10, ratio=3),
])
BOARD_PAD = Pedalboard([
    Chorus(rate_hz=0.8, depth=0.5, mix=0.5),
    Reverb(room_size=0.85, damping=0.2, wet_level=0.65, dry_level=0.35),
])
BOARD_STAB = Pedalboard([
    Distortion(drive_db=12),
    HighpassFilter(cutoff_frequency_hz=200),
    Reverb(room_size=0.15, wet_level=0.1),
])


# ─── Melody: "KAWAII DESTRUCTION" main hook ───────────────────────────────────
# Chibi game melody in C Major, 8th-note resolution
MELODY_A = [          # 2 bars, quarter notes → cute ascending cascade
    ("C5",0),("E5",1),("G5",2),("C6",3),
    ("B5",4),("G5",5),("E5",6),("G5",7),
]
MELODY_B = [          # 2 bars, variation
    ("A5",0),("G5",1),("E5",2),("D5",3),
    ("C5",4),("E5",5),("G5",6),("E5",7),
]
MELODY_FAST = [       # 1 bar, 16th notes — drop energy
    "C5","E5","G5","C6","B5","G5","E5","D5",
    "C5","E5","G5","A5","G5","E5","C5","G5",
]
EUPHORIC_HOOK = [     # Hardstyle supersaw hook — C Major triads
    ("C5",0),("E5",1),("G5",2),("E5",3),
    ("F5",4),("A5",5),("G5",6),("E5",7),
]

def place_melody(mix, bar, speed=1, section="verse", vel=1.0):
    src = MELODY_A if bar%4 < 2 else MELODY_B
    if speed == 1:
        step = S8
        for note, i in src:
            t   = bar*BAR + i*step
            dur = step * 0.82
            raw = xylophone(FREQ[note], dur, vel)
            fxd = apply(raw, BOARD_XYL)
            mix.place(fxd, t, gain=0.55, pan=np.random.uniform(-0.08,0.08))
    elif speed == 2:   # 16th notes — breakcore speed
        step = S16
        for i, note in enumerate(MELODY_FAST):
            t   = bar*BAR + i*step
            dur = step * 0.78
            raw = xylophone(FREQ[note], dur, vel*0.9)
            fxd = apply(raw, BOARD_XYL)
            mix.place(fxd, t, gain=0.52, pan=np.random.uniform(-0.15,0.15))
    elif speed == 3:   # Intro ghost (quieter, longer decay)
        step = S8
        for note, i in src:
            t   = bar*BAR + i*step
            dur = step * 1.1
            raw = xylophone(FREQ[note], dur, vel*0.6)
            fxd = apply(raw, BOARD_XYL)
            mix.place(fxd, t, gain=0.35, pan=0.0)

def place_euphoric(mix, bar, vel=1.0):
    step = S8
    for note, i in EUPHORIC_HOOK:
        t   = bar*BAR + i*step
        dur = step * 0.88
        raw = euphoric_lead(FREQ[note], dur, vel)
        fxd = apply(raw, BOARD_LEAD)
        mix.place(fxd, t, gain=0.42, pan=0.0)

def place_stabs(mix, bar):
    """Hardstyle synth stabs on off-beats."""
    for beat in [0.5, 1.5, 2.5, 3.5]:
        t   = bar*BAR + beat*BEAT
        raw = stab(FREQ["G4"], 0.9)
        fxd = apply(raw, BOARD_STAB)
        mix.place(fxd, t, gain=0.22, pan=0.1)

# ─── Drum patterns ────────────────────────────────────────────────────────────

def place_drums(mix, bar, section="verse"):
    """Place drums for the given section."""
    def k(pos_s, v=1.0): mix.place(apply(hardstyle_kick(v), BOARD_KICK), pos_s, gain=0.72)
    def rb(pos_s, v=0.7): mix.place(stereo(reverse_bass_riser(v)), pos_s-0.09, gain=0.38, pan=-0.05)
    def sn(pos_s, v=1.0): mix.place(apply(kawaii_snare(v), BOARD_SNARE), pos_s, gain=0.58, pan=0.05)
    def hh(pos_s, v=0.5, op=False): mix.place(stereo(sparkle_hat(v, op)), pos_s, gain=0.28, pan=-0.2)
    def cn(pos_s, v=0.85): mix.place(stereo(coin_sfx(v)), pos_s, gain=0.35, pan=np.random.uniform(-0.3,0.3))

    b = bar * BAR

    if section == "intro":
        k(b); hh(b+BEAT*2, 0.4)
        hh(b+BEAT, 0.3); hh(b+BEAT*3, 0.3)

    elif section == "build":
        # Hardstyle 4/4 kick every beat, snare 2+4
        for beat in range(4):
            t = b + beat*BEAT
            rb(t); k(t)
            if beat in (1, 3): sn(t)
        # 8th hats
        for i in range(8):
            hh(b + i*S8, 0.3 + 0.2*(i%2==0))

    elif section == "drop1":
        # Hardstyle kick pattern: 1, "and of 2", 3, "and of 3.5"
        for pos in [0, 1.5, 2, 3.5]:
            t = b + pos*BEAT; rb(t); k(t)
        for pos in [1, 2.5, 3]:
            sn(b + pos*BEAT, 0.85 + 0.1*np.random.random())
        # 16th hats with velocity humanization
        for i in range(16):
            v = 0.25 + 0.35*(i%4==0) + 0.15*(i%2==0) + 0.1*np.random.random()
            hh(b + i*S16, v, op=(i==8))
        # Coin on downbeats
        if bar % 2 == 0: cn(b)

    elif section == "break":
        k(b); k(b + 2*BEAT)
        sn(b + BEAT); sn(b + 3*BEAT)
        for i in range(8): hh(b + i*S8, 0.25)

    elif section == "drop2":
        # Full chaos: every 16th note has SOMETHING
        for pos in [0, 0.5, 1.5, 2, 2.5, 3, 3.75]:
            t = b + pos*BEAT; rb(t); k(t, 0.9+0.1*np.random.random())
        for pos in [1, 2, 3, 3.5]:
            sn(b + pos*BEAT, 0.9 + 0.1*np.random.random())
        for i in range(16):
            v = 0.2 + 0.45*(i%4==0) + 0.2*(i%2==0) + 0.15*np.random.random()
            hh(b + i*S16, v, op=(i in (4,12)))
        # Rapid coins on every beat
        for beat in range(4): cn(b + beat*BEAT)
        # Extra stutter on bar boundary
        for i in range(4): k(b + 3.75*BEAT + i*S32*0.5, 0.6-i*0.1)

    elif section == "outro":
        for pos in [0, 2]: k(b + pos*BEAT)
        sn(b + BEAT); sn(b + 3*BEAT)
        for i in range(8): hh(b + i*S8, 0.2)


# ─── Bass lines ───────────────────────────────────────────────────────────────

BASS_PATTERNS = {
    "verse": [("C3",0),("C3",1),("G3",2),("C3",3)],
    "chorus": [("C3",0),("G3",0.5),("A3",1),("G3",1.5),("C3",2),("E3",2.5),("G3",3),("C3",3.5)],
    "drop": [("C3",0),("C3",0.5),("G3",1),("A3",1.5),("C3",2),("G3",2.5),("E3",3),("G3",3.5)],
}

def place_bass(mix, bar, pattern="verse"):
    pts = BASS_PATTERNS.get(pattern, BASS_PATTERNS["verse"])
    for note, beat in pts:
        t   = bar*BAR + beat*BEAT
        dur = BEAT * 0.38
        raw = chibi_bass(FREQ[note], dur)
        fxd = apply(raw, BOARD_BASS)
        mix.place(fxd, t, gain=0.38, pan=0.0)


# ─── Song: KAWAII DESTRUCTION ─────────────────────────────────────────────────
SONG_BARS = 36
mix = Mixer(SONG_BARS*BAR + 2.0)
np.random.seed(7)

print("\n" + "="*70)
print("  KAWAII DESTRUCTION  |  175 BPM  |  C Major  |  Hardstyle + Breakcore")
print("="*70)

# Dreamy C Major pad throughout (atmospheric bedrock)
c_major = [FREQ["C4"], FREQ["E4"], FREQ["G4"], FREQ["C5"]]
for b in range(0, SONG_BARS, 4):
    fade_gain = max(0.1, 0.45 - max(0, b-28)*0.08)
    raw = pad_chord(c_major, BAR*4, vel=fade_gain)
    mix.place(apply(raw, BOARD_PAD), b*BAR, gain=0.35)

# ── INTRO (0-3): Ghost melody, single kick ────────────────────────────────────
print("[INTRO]   bars 0–3   — cute melody materialises from sparkle dust")
for b in range(0, 4):
    place_melody(mix, b, speed=3, vel=0.8)
    place_drums(mix, b, "intro")
# Coin sparkle intro
for i in range(8):
    mix.place(stereo(coin_sfx(0.5+i*0.05)), i*S8*1.5, gain=0.28,
              pan=np.sin(i*0.8)*0.5)

# ── BUILD (4-7): Drums ramp up, euphoric lead enters ──────────────────────────
print("[BUILD]   bars 4–7   — hardstyle kick drops, euphoric lead enters")
for b in range(4, 8):
    place_melody(mix, b, speed=1, vel=0.9)
    place_drums(mix, b, "build")
    if b >= 6:
        place_euphoric(mix, b, vel=0.7)

# ── DROP 1 (8-15): Full hardstyle + breakcore + chibi melody ─────────────────
print("[DROP 1]  bars 8–15  — IMPACT: hardstyle kick + breakcore + xylophone")
for b in range(8, 16):
    place_melody(mix, b, speed=1, vel=1.0)
    place_euphoric(mix, b, vel=0.88)
    place_drums(mix, b, "drop1")
    place_bass(mix, b, "drop")
    if b % 2 == 0: place_stabs(mix, b)

# ── BREAK (16-19): Cute interlude — melody only, sparse ──────────────────────
print("[BREAK]   bars 16–19 — kawaii breather, melody glitters alone")
for b in range(16, 20):
    place_melody(mix, b, speed=1, vel=0.85)
    place_drums(mix, b, "break")
    place_bass(mix, b, "verse")
# Rising coin cascade into drop 2
for i in range(16):
    t   = 19*BAR + 2*BEAT + i*S16
    mix.place(stereo(coin_sfx(0.4+i*0.03)), t,
              gain=0.25+i*0.02, pan=np.sin(i*0.5)*0.6)

# ── DROP 2 (20-31): MAXIMUM KAWAII DESTRUCTION ───────────────────────────────
print("[DROP 2]  bars 20–31 — MAXIMUM KAWAII DESTRUCTION (all chaos, all cute)")
for b in range(20, 32):
    place_melody(mix, b, speed=2, vel=1.0)   # 16th-note xylo madness
    place_euphoric(mix, b, vel=0.95)
    place_drums(mix, b, "drop2")
    place_bass(mix, b, "chorus")
    place_stabs(mix, b)
    # Extra coin hits on every 4th 16th
    for i in range(0, 16, 4):
        mix.place(stereo(coin_sfx(0.7)), b*BAR+i*S16, gain=0.28,
                  pan=np.random.uniform(-0.5, 0.5))

# ── OUTRO (32-35): Fade, xylophone echoes, final coin ────────────────────────
print("[OUTRO]   bars 32–35 — fading into sparkles and game-over screen")
for b in range(32, 36):
    fade = max(0.1, 1.0 - (b-32) * 0.25)
    place_melody(mix, b, speed=1, vel=fade*0.8)
    place_drums(mix, b, "outro")
    place_bass(mix, b, "verse")

# Final coin collect sting
for i, note in enumerate(["C5","E5","G5","C6"]):
    t   = 36*BAR + i*BEAT*0.5
    raw = xylophone(FREQ[note], 0.5, vel=0.8-i*0.05)
    mix.place(apply(raw, BOARD_XYL), t, gain=0.5, pan=i*0.15)
mix.place(stereo(coin_sfx(1.0)), 36*BAR + 2.1*BEAT, gain=0.5)

# ─── Export ───────────────────────────────────────────────────────────────────
tracks_dir = Path(__file__).parent / "tracks"
tracks_dir.mkdir(exist_ok=True)
ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
mp3_name = f"kawaii_destruction_{ts}.mp3"
mp3_path = tracks_dir / mp3_name

dur_s = SONG_BARS * BAR + 2.0
print(f"\n[RENDER]  Exporting {dur_s:.1f}s stereo 320 kbps ...")
mix.export_mp3(mp3_path)

size_kb = mp3_path.stat().st_size / 1024
(tracks_dir / f"kawaii_destruction_{ts}.json").write_text(json.dumps({
    "title": "KAWAII DESTRUCTION",
    "bpm": BPM, "key": "C Major", "bars": SONG_BARS,
    "dur_s": round(dur_s,2), "sr": SR, "channels": 2, "bitrate": "320k",
    "synths": ["hardstyle_kick","reverse_bass_riser","xylophone",
               "coin_sfx","kawaii_snare","sparkle_hat",
               "chibi_bass","euphoric_lead","stab","pad_chord"],
    "fx": ["Chorus","Reverb","Delay","Distortion","LowpassFilter",
           "HighpassFilter","Compressor","Limiter"],
    "sections": ["Intro","Build","Drop1","Break","Drop2","Outro"],
    "file": mp3_name,
}, indent=2))

print("\n" + "="*70)
print("  KAWAII DESTRUCTION -- COMPLETE")
print("="*70)
print(f"  File:      {mp3_name}")
print(f"  Location:  {mp3_path.absolute()}")
print(f"  Size:      {size_kb:.0f} KB")
print(f"  Duration:  {dur_s:.1f}s  ({SONG_BARS} bars at {BPM} BPM)")
print(f"  Synths:    10 unique voices")
print(f"  FX:        Chorus+Delay+Reverb on xylo, Supersaw lead, Hard kick")
print("="*70)
print(f"\n  -> {mp3_path.absolute()}\n")
