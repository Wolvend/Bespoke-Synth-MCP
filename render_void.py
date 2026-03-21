"""
render_void.py  --  "VOID"
180 BPM | D minor | Hardstyle Breakcore
Deep sub bass. Massive kick. Complex breakbeats. Sparse stabs. No buzz.

Run: python render_void.py
Needs: numpy  (pip install numpy)
Needs: pydub + ffmpeg for MP3
"""

import numpy as np
import wave, os

SR   = 44100
BPM  = 180.0
BEAT = 60.0 / BPM        # 0.3333s
BAR  = BEAT * 4           # 1.3333s
S16  = BEAT / 4           # 16th = 0.0833s
S32  = BEAT / 8           # 32nd = 0.0417s

def midi_hz(m): return 440.0 * 2 ** ((m - 69) / 12.0)

# ---- song sections ----------------------------------------------------------
INTRO   = 0
BUILD   = 4  * BAR
DROP1   = 8  * BAR
BREAK   = 20 * BAR
DROP2   = 24 * BAR
OUTRO   = 36 * BAR
END     = 40 * BAR

N = int(END * SR) + SR
L = np.zeros(N, np.float64)
R = np.zeros(N, np.float64)
rng = np.random.default_rng(42)

# ---- place ------------------------------------------------------------------
def place(ch, sig, t, amp=1.0):
    s = int(t * SR)
    if s >= len(ch): return
    e = min(len(ch), s + len(sig))
    ch[s:e] += sig[:e - s] * amp

# ---- envelopes --------------------------------------------------------------
def exp_env(dur, decay):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    return np.exp(-t * decay).astype(np.float64)

def tanh_sat(x, amt=1.0):
    return np.tanh(x * amt) / (np.tanh(amt) + 1e-9)

# =============================================================================
# DRUMS
# =============================================================================

def kick(hard=True):
    """
    Deep hardstyle kick.
    Pitch sweep: 180 -> 38 Hz over 600ms.
    Layered: sine body + sub thump + transient click.
    """
    dur = 0.65
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)

    # Exponential pitch sweep
    f0, f1 = 185.0, 38.0
    tau     = 0.038
    freq    = f1 + (f0 - f1) * np.exp(-t / tau)
    phase   = 2 * np.pi * np.cumsum(freq) / SR

    # Main body: pure sine
    body = np.sin(phase)
    body_env = np.exp(-t * 5.5) * 1.0 + np.exp(-t * 1.4) * 0.55
    body *= body_env

    # Sub layer: half-frequency thump
    sub_phase = 2 * np.pi * np.cumsum(freq * 0.5) / SR
    sub = np.sin(sub_phase) * np.exp(-t * 2.8) * 0.45

    # Transient click: 3ms noise burst
    click = np.zeros(n)
    cl = int(0.003 * SR)
    click[:cl] = rng.standard_normal(cl) * np.linspace(1, 0, cl) * (1.0 if hard else 0.6)

    # Combine — NO distortion, keep it clean and deep
    sig = (body + sub + click).astype(np.float64)
    # Very gentle saturation just for warmth
    sig = tanh_sat(sig, amt=1.2)

    peak = np.max(np.abs(sig))
    if peak > 0: sig /= peak
    return sig * (1.0 if hard else 0.75)


def snare(pitch_hz=220, snap=True):
    """Punchy snare: short tone + noise."""
    dur = 0.18
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)

    freq = pitch_hz * np.exp(-t * 22)
    ph   = 2 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(ph) * np.exp(-t * 32) * 0.50

    noise = rng.standard_normal(n) * np.exp(-t * 28) * 0.60

    sig = (tone + noise).astype(np.float64)
    if snap:
        snp = int(0.003 * SR)
        sig[:snp] += rng.standard_normal(snp) * np.linspace(1.2, 0, snp)
    return sig * 0.75


def ghost_snare():
    """Very quiet ghost note."""
    return snare(pitch_hz=200, snap=False) * 0.22


def hat_closed(accent=False):
    dur = 0.032
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n) * np.exp(-t * 130)
    # Thin metallic ring
    ring = np.sin(2 * np.pi * 8000 * t) * np.exp(-t * 90) * 0.3
    sig  = (noise + ring).astype(np.float64)
    return sig * (0.22 if accent else 0.13)


def hat_open():
    dur = 0.14
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n) * np.exp(-t * 14)
    ring  = np.sin(2 * np.pi * 6500 * t) * np.exp(-t * 20) * 0.25
    return ((noise + ring) * 0.15).astype(np.float64)


def rimshot():
    dur = 0.08
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    tone  = np.sin(2 * np.pi * 400 * t) * np.exp(-t * 60) * 0.6
    noise = rng.standard_normal(n) * np.exp(-t * 80) * 0.5
    return ((tone + noise) * 0.4).astype(np.float64)


# =============================================================================
# BREAKCORE PATTERNS
# Indexes are 32nd-note steps within a 2-bar phrase (64 steps)
# =============================================================================

# Kick positions (32nd-note indices in a 1-bar = 32 steps)
KICK_NORMAL  = [0, 8, 16, 24]                     # 4-on-floor
KICK_BREAK1  = [0, 6, 8, 14, 16, 20, 24, 28, 30]  # syncopated breakcore
KICK_BREAK2  = [0, 3, 8, 11, 16, 20, 21, 24, 28]  # asymmetric
KICK_ROLL    = [0, 1, 8, 9, 16, 17, 24, 25]        # double-kick rolls

SNARE_NORMAL = [8, 24]                             # 2 & 4
SNARE_BREAK1 = [8, 18, 24, 30]                     # extra snares
SNARE_BREAK2 = [6, 8, 22, 24, 28]

GHOST_POS    = [2, 5, 10, 13, 18, 21, 26, 29]      # ghost 32nds
HAT_POS      = [0, 4, 8, 12, 16, 20, 24, 28]       # 8th-note hats
HAT_OPEN_POS = [12, 28]                            # open hat
RIM_POS      = [4, 20]                             # rimshots

KICK_TIMES_ALL = []

def add_bar(t0, kick_pos, snare_pos, ghost_pos=None,
            hat_pos=None, hat_open_pos=None, rim_pos=None,
            kick_amp=1.0, snare_amp=1.0):
    k = kick(hard=True)
    s = snare()
    g = ghost_snare()
    hc = hat_closed()
    ha = hat_closed(accent=True)
    ho = hat_open()
    rm = rimshot()

    for i in kick_pos:
        t = t0 + i * S32
        KICK_TIMES_ALL.append(t)
        place(L, k, t, amp=kick_amp)
        place(R, k, t, amp=kick_amp)

    for i in snare_pos:
        t = t0 + i * S32
        place(L, s, t, amp=snare_amp)
        place(R, s, t, amp=snare_amp * 0.95)

    if ghost_pos:
        for i in ghost_pos:
            t = t0 + i * S32
            place(L, g, t)
            place(R, g, t)

    if hat_pos:
        for i in hat_pos:
            t = t0 + i * S32
            accent = (i % 8 == 0)
            h = ha if accent else hc
            place(L, h, t, amp=0.8)
            place(R, h, t, amp=0.8)

    if hat_open_pos:
        for i in hat_open_pos:
            t = t0 + i * S32
            place(L, ho, t, amp=0.85)
            place(R, ho, t, amp=0.85)

    if rim_pos:
        for i in rim_pos:
            t = t0 + i * S32
            place(L, rm, t, amp=0.7)
            place(R, rm, t, amp=0.65)


# INTRO (bars 0-3): simple 4/4 kick + hat, building tension
for b in range(4):
    add_bar(INTRO + b * BAR, KICK_NORMAL, SNARE_NORMAL,
            hat_pos=HAT_POS, hat_open_pos=HAT_OPEN_POS,
            kick_amp=0.80, snare_amp=0.70)

# BUILD (bars 4-7): add ghost notes + rimshots
for b in range(4):
    add_bar(BUILD + b * BAR, KICK_NORMAL, SNARE_NORMAL,
            ghost_pos=GHOST_POS, hat_pos=HAT_POS,
            rim_pos=RIM_POS, kick_amp=0.90, snare_amp=0.85)

# DROP 1 (bars 8-19): full breakcore — alternating patterns every 2 bars
drop1_kicks  = [KICK_BREAK1, KICK_BREAK2, KICK_ROLL, KICK_BREAK1,
                KICK_BREAK2, KICK_ROLL, KICK_BREAK1, KICK_ROLL,
                KICK_BREAK2, KICK_BREAK1, KICK_ROLL, KICK_BREAK2]
drop1_snares = [SNARE_BREAK1, SNARE_NORMAL, SNARE_BREAK2, SNARE_BREAK1,
                SNARE_NORMAL, SNARE_BREAK1, SNARE_BREAK2, SNARE_NORMAL,
                SNARE_BREAK1, SNARE_BREAK2, SNARE_NORMAL, SNARE_BREAK2]

for b in range(12):
    kp = drop1_kicks[b]
    sp = drop1_snares[b]
    add_bar(DROP1 + b * BAR, kp, sp,
            ghost_pos=GHOST_POS, hat_pos=HAT_POS, hat_open_pos=HAT_OPEN_POS,
            rim_pos=RIM_POS if b % 2 == 0 else None,
            kick_amp=1.0, snare_amp=1.0)

# BREAK (bars 20-23): stripped — just kick + sparse hat
for b in range(4):
    add_bar(BREAK + b * BAR, KICK_NORMAL, [],
            hat_pos=[0, 16], kick_amp=0.70, snare_amp=0)

# DROP 2 (bars 24-35): harder — double rolls everywhere
drop2_kicks  = [KICK_ROLL, KICK_BREAK2, KICK_BREAK1, KICK_ROLL,
                KICK_BREAK1, KICK_ROLL, KICK_BREAK2, KICK_BREAK1,
                KICK_ROLL, KICK_BREAK2, KICK_ROLL, KICK_BREAK1]
drop2_snares = [SNARE_BREAK2, SNARE_BREAK1, SNARE_BREAK2, SNARE_NORMAL,
                SNARE_BREAK1, SNARE_BREAK2, SNARE_NORMAL, SNARE_BREAK1,
                SNARE_BREAK2, SNARE_NORMAL, SNARE_BREAK1, SNARE_BREAK2]

for b in range(12):
    kp = drop2_kicks[b]
    sp = drop2_snares[b]
    add_bar(DROP2 + b * BAR, kp, sp,
            ghost_pos=GHOST_POS, hat_pos=HAT_POS, hat_open_pos=HAT_OPEN_POS,
            rim_pos=RIM_POS,
            kick_amp=1.05, snare_amp=1.05)

# OUTRO (bars 36-39): wind down
for b in range(4):
    add_bar(OUTRO + b * BAR, KICK_NORMAL, SNARE_NORMAL,
            hat_pos=HAT_POS, kick_amp=0.65, snare_amp=0.60)


# =============================================================================
# SUB BASS — pure sine, deep, clean
# D minor root movement: D1(26), A1(33), F1(29), C1(24) — very deep
# =============================================================================

BASS_PATTERN = [
    # (32nd-step, midi, dur_32nds)
    (0,  26, 6),   # D1
    (6,  26, 2),
    (8,  33, 4),   # A1
    (12, 26, 2),
    (14, 26, 2),
    (16, 29, 6),   # F1
    (22, 29, 2),
    (24, 24, 6),   # C1
    (30, 26, 2),
]

def sub_note(midi, dur_s, amp=0.65):
    """Pure sine sub bass — clean, no harmonics."""
    n   = int(dur_s * SR)
    t   = np.linspace(0, dur_s, n, endpoint=False)
    f   = midi_hz(midi)
    sig = np.sin(2 * np.pi * f * t)
    # Smooth envelope: fast attack, smooth release
    ai = int(0.010 * SR)
    ri = int(min(0.08 * SR, n // 3))
    env = np.ones(n)
    if ai < n: env[:ai] = np.linspace(0, 1, ai)
    if ri < n: env[-ri:] = np.linspace(1, 0, ri)
    return (sig * env * amp).astype(np.float64)


def add_bass_section(t_start, num_bars, amp=0.65):
    for b in range(num_bars):
        t0 = t_start + b * BAR
        for (step, midi, dur_steps) in BASS_PATTERN:
            t   = t0 + step * S32
            dur = dur_steps * S32
            sig = sub_note(midi, dur + 0.015, amp=amp)
            place(L, sig, t)
            place(R, sig, t)   # bass stays mono / centered

add_bass_section(INTRO,  4,  amp=0.50)
add_bass_section(BUILD,  4,  amp=0.58)
add_bass_section(DROP1,  12, amp=0.68)
add_bass_section(DROP2,  12, amp=0.72)
add_bass_section(OUTRO,  4,  amp=0.45)


# =============================================================================
# STABS — short, punchy chord hits (not sustained buzz)
# D minor: D+F+A  /  Bb+D+F  /  C+E+G  — just stabs at phrase starts
# =============================================================================

STAB_NOTES = [
    [38, 41, 45],   # Dm  (D2 F2 A2)
    [34, 38, 41],   # Bb  (Bb1 D2 F2)
    [36, 40, 43],   # C   (C2 E2 G2)
    [38, 41, 45],   # Dm
]

def stab(notes, dur=0.06, amp=0.22):
    """Short punchy chord stab — sine tones only, fast decay."""
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    sig = np.zeros(n, np.float64)
    for m in notes:
        f    = midi_hz(m)
        tone = np.sin(2 * np.pi * f * t)
        sig += tone
    env = np.exp(-t * 28).astype(np.float64)
    # tiny gentle tanh to add warmth
    sig = tanh_sat(sig * 0.5, amt=0.8) * 2.0
    return sig * env * amp


def add_stabs(t_start, num_bars, every_n_bars=2, amp=0.22):
    """Place a stab at the start of every N bars."""
    prog_idx = 0
    for b in range(0, num_bars, every_n_bars):
        t = t_start + b * BAR
        notes = STAB_NOTES[prog_idx % len(STAB_NOTES)]
        s = stab(notes, dur=0.055, amp=amp)
        place(L, s, t)
        place(R, s, t + 0.001)  # 1ms stereo spread
        prog_idx += 1


add_stabs(DROP1, 12, every_n_bars=2, amp=0.22)
add_stabs(DROP2, 12, every_n_bars=2, amp=0.26)
add_stabs(BUILD, 4,  every_n_bars=2, amp=0.16)


# =============================================================================
# ATMOSPHERIC RISER (build sections only)
# =============================================================================

def add_riser(t_start, dur_s, f0=55.0, f1=800.0, amp=0.07):
    n    = int(dur_s * SR)
    t    = np.linspace(0, dur_s, n, endpoint=False)
    freq = f0 * (f1 / f0) ** (t / dur_s)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    noise = rng.standard_normal(n) * 0.15
    tone  = np.sin(phase)
    env   = (t / dur_s) ** 1.8
    sig   = ((tone + noise) * env * amp).astype(np.float64)
    place(L, sig, t_start)
    place(R, sig, t_start)

add_riser(BUILD,  4 * BAR, f0=50,  f1=600,  amp=0.07)
add_riser(BREAK,  3 * BAR, f0=40,  f1=1000, amp=0.08)


# =============================================================================
# SIDECHAIN PUMP — duck everything on the kick
# =============================================================================

def sidechain(kick_times, n_samples, attack=0.002, release=0.22):
    env = np.ones(n_samples, np.float64)
    a = int(attack * SR)
    r = int(release * SR)
    for kt in kick_times:
        s = int(kt * SR)
        if s >= n_samples: continue
        chunk = min(a + r, n_samples - s)
        ai = min(a, chunk)
        ri = min(r, chunk - ai)
        env[s:s + ai] = np.linspace(1.0, 0.05, ai)
        if ri > 0:
            env[s + ai:s + ai + ri] = np.linspace(0.05, 1.0, ri)
    return env

sc = sidechain(KICK_TIMES_ALL, N, attack=0.002, release=0.20)
L *= sc
R *= sc


# =============================================================================
# OUTRO FADE
# =============================================================================
fs = int(OUTRO * SR)
fe = int(END * SR)
fn = fe - fs
if fn > 0:
    fenv = np.linspace(1, 0, fn)
    L[fs:fe] *= fenv
    R[fs:fe] *= fenv


# =============================================================================
# MIX & EXPORT
# =============================================================================
peak = max(np.max(np.abs(L)), np.max(np.abs(R)), 1e-9)
L = (L * 0.88 / peak).astype(np.float32)
R = (R * 0.88 / peak).astype(np.float32)

stereo = np.empty(N * 2, np.float32)
stereo[0::2] = L
stereo[1::2] = R

out_dir  = os.path.dirname(os.path.abspath(__file__))
wav_path = os.path.join(out_dir, "void.wav")
mp3_path = os.path.join(out_dir, "void.mp3")

s16 = (stereo * 32767).astype(np.int16)
with wave.open(wav_path, 'w') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(s16.tobytes())

kb  = os.path.getsize(wav_path) // 1024
dur = N / SR
print(f"WAV: {wav_path}  ({kb} KB, {dur:.1f}s, {BPM}BPM, D minor, stereo)")

try:
    from pydub import AudioSegment
    seg = AudioSegment.from_wav(wav_path)
    seg.export(mp3_path, format="mp3", bitrate="256k",
               tags={"title": "Void", "artist": "BespokeSynth MCP",
                     "genre": "Hardstyle Breakcore", "bpm": "180"})
    print(f"MP3: {mp3_path}  ({os.path.getsize(mp3_path)//1024} KB)")
except ImportError:
    print("pydub not installed -- WAV only")
