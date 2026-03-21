"""
render_sunrise.py  --  "SUNRISE"
152 BPM | E major | Uplifting happy hardstyle
Fun, consistent energy, major key, gentle dynamics.
No heavy sidechain. No breakcore chaos. Just a good time.
"""
import numpy as np, wave, os, sys
sys.path.insert(0, os.path.dirname(__file__))

SR   = 44100
BPM  = 152.0
BEAT = 60.0 / BPM
BAR  = BEAT * 4
S8   = BEAT / 2      # 8th note
S16  = BEAT / 4      # 16th note

def mhz(m): return 440.0 * 2 ** ((m - 69) / 12.0)
rng = np.random.default_rng(7)

# -- song map (bars) --
INTRO  = 0
VERSE1 = 4  * BAR
CHORUS1= 12 * BAR
VERSE2 = 20 * BAR
CHORUS2= 28 * BAR
OUTRO  = 36 * BAR
END    = 40 * BAR

N = int(END * SR) + SR
L = np.zeros(N, np.float64)
R = np.zeros(N, np.float64)

def place(ch, sig, t, amp=1.0):
    s = int(t * SR)
    if s >= len(ch): return
    e = min(len(ch), s + len(sig))
    ch[s:e] += sig[:e-s] * amp

def ar(n, a_s=0.005, r_s=0.08):
    env = np.ones(n, np.float64)
    ai = int(a_s * SR); ri = int(r_s * SR)
    if ai > 0 and ai < n: env[:ai] = np.linspace(0, 1, ai)
    if ri > 0 and ri < n: env[-ri:] = np.linspace(1, 0, ri)
    return env

# =============================================================================
# DRUMS  --  clean 4-on-floor, not complicated
# =============================================================================

def kick():
    dur = 0.50; n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    # Warm pitch sweep: 160 -> 50 Hz (not as extreme as before)
    freq = 50 + (160 - 50) * np.exp(-t / 0.045)
    ph   = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(ph) * (np.exp(-t * 7) + np.exp(-t * 2) * 0.4)
    click_n = int(0.003 * SR)
    click   = np.zeros(n)
    click[:click_n] = rng.standard_normal(click_n) * np.linspace(0.7, 0, click_n)
    sig = (body + click).astype(np.float64)
    sig /= max(np.max(np.abs(sig)), 1e-9)
    # Add a pure 45Hz sub thump for warmth in the 20-80Hz band
    sub_f = 45.0
    sub   = np.sin(2*np.pi*sub_f*t) * np.exp(-t * 3.5) * 0.40
    sig   = sig * 0.78 + sub * 0.22
    sig  /= max(np.max(np.abs(sig)), 1e-9)
    return sig * 0.92

def snare():
    dur = 0.20; n = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    tone  = np.sin(2*np.pi*(180*np.exp(-t*18)+100)*t) * np.exp(-t*30) * 0.45
    noise = rng.standard_normal(n) * np.exp(-t*22) * 0.65
    return ((tone + noise) * 0.72).astype(np.float64)

def hat(open_=False):
    dur = 0.12 if open_ else 0.028
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n) * np.exp(-t * (12 if open_ else 110))
    ring  = np.sin(2*np.pi*7500*t) * np.exp(-t * (15 if open_ else 100)) * 0.25
    amp   = 0.14 if open_ else 0.16
    return ((noise + ring) * amp).astype(np.float64)

def clap():
    dur = 0.10; n = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n) * np.exp(-t * 35) * 0.55
    body  = np.sin(2*np.pi*900*t) * np.exp(-t*40) * 0.20
    return ((noise + body) * 0.65).astype(np.float64)

# Kick: 4-on-floor every beat
# Snare: beat 2 & 4 + clap layer
# Hats: 8th notes, open hat on upbeats
# Ghost snare on 16th note offbeats (quietly)

def add_drums(t_start, n_bars, kick_amp=1.0, snare_amp=1.0, hat_amp=1.0, ghost=True):
    k = kick() * kick_amp
    s = snare() * snare_amp
    cl = clap() * snare_amp * 0.6
    hc = hat(False) * hat_amp
    ho = hat(True)  * hat_amp * 0.85

    for b in range(n_bars):
        t0 = t_start + b * BAR
        # 4-on-floor kick
        for beat in range(4):
            place(L, k, t0 + beat*BEAT); place(R, k, t0 + beat*BEAT)
        # Snare on 2 & 4
        for beat in [1, 3]:
            place(L, s,  t0 + beat*BEAT); place(R, s,  t0 + beat*BEAT)
            place(L, cl, t0 + beat*BEAT + 0.004); place(R, cl, t0 + beat*BEAT + 0.004)
        # 8th-note closed hats
        for i in range(8):
            place(L, hc, t0 + i*S8, 0.85); place(R, hc, t0 + i*S8, 0.85)
        # Open hat on every upbeat (the "&" of each beat)
        for i in [1, 3, 5, 7]:
            place(L, ho, t0 + i*S8, 0.80); place(R, ho, t0 + i*S8, 0.80)
        # Ghost snare (very quiet, on 16th offbeats)
        if ghost:
            for i in [2, 6, 10, 14]:
                g = snare() * 0.12
                place(L, g, t0 + i*S16); place(R, g, t0 + i*S16)

add_drums(INTRO,   4,  kick_amp=0.70, snare_amp=0.60, hat_amp=0.65, ghost=False)
add_drums(VERSE1,  8,  kick_amp=0.88, snare_amp=0.85, hat_amp=0.85, ghost=True)
add_drums(CHORUS1, 8,  kick_amp=1.00, snare_amp=1.00, hat_amp=1.00, ghost=True)
add_drums(VERSE2,  8,  kick_amp=0.88, snare_amp=0.85, hat_amp=0.85, ghost=True)
add_drums(CHORUS2, 8,  kick_amp=1.00, snare_amp=1.00, hat_amp=1.00, ghost=True)
add_drums(OUTRO,   4,  kick_amp=0.70, snare_amp=0.65, hat_amp=0.65, ghost=False)

# =============================================================================
# BASS  --  punchy, melodic, follows chord roots
# E major: I=E(40), IV=A(45), V=B(47), vi=C#(49) — octave 2
# Progression: I I IV V  (repeating 2-bar loop)
# =============================================================================
CHORD_ROOTS = [40, 40, 45, 47]   # E2, E2, A2, B2  (midi)
CHORD_PATTERN = [0, 0, 1, 2]     # index into CHORD_ROOTS per bar

def bass_note(midi, dur, amp=0.62):
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    f   = mhz(midi)
    # Sine fundamental + small 2nd harmonic for presence
    sig = np.sin(2*np.pi*f*t) * 0.80 + np.sin(2*np.pi*f*2*t) * 0.18
    e   = ar(n, a_s=0.008, r_s=0.06)
    return (sig * e * amp).astype(np.float64)

# Bouncy bass pattern: root on beat 1, octave-up stab on beat 3-and
BASS_OFFSETS = [
    (0.0,  0, 0.9),   # beat 1, root
    (0.75, 0, 0.6),   # beat 1-and-a, echo
    (1.0,  0, 0.8),   # beat 2, root
    (2.0,  0, 0.9),   # beat 3, root
    (2.5, 12, 0.55),  # beat 3-and, octave up stab
    (3.0,  0, 0.8),   # beat 4, root
    (3.75, 0, 0.5),   # beat 4-and-a, pick up
]

def add_bass(t_start, n_bars, amp=0.62):
    for b in range(n_bars):
        t0   = t_start + b * BAR
        root = CHORD_ROOTS[b % len(CHORD_ROOTS)]
        for beat_frac, semis, vel in BASS_OFFSETS:
            t   = t0 + beat_frac * BEAT
            dur = BEAT * 0.42
            sig = bass_note(root + semis, dur, amp * vel)
            place(L, sig, t); place(R, sig, t)

add_bass(VERSE1,  8,  amp=0.60)
add_bass(CHORUS1, 8,  amp=0.70)
add_bass(VERSE2,  8,  amp=0.60)
add_bass(CHORUS2, 8,  amp=0.72)
add_bass(OUTRO,   4,  amp=0.45)

# =============================================================================
# PADS  --  warm, sustained chords (no buzzing, just sines)
# I - IV - V - I in E major, 2 bars each
# =============================================================================
PAD_CHORDS = [
    [52, 56, 59],   # E3 G#3 B3  (I)
    [57, 61, 64],   # A3 C#4 E4  (IV)
    [59, 63, 66],   # B3 D#4 F#4 (V)
    [52, 56, 59],   # E3 G#3 B3  (I)
]

def pad_note(freq, dur, amp=0.12, detune=0.002):
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, endpoint=False)
    sig = (np.sin(2*np.pi*freq*(1-detune)*t) +
           np.sin(2*np.pi*freq*(1+detune)*t)) * 0.5
    # Slow attack, slow release — smooth sustain
    ai = int(0.18 * SR); ri = int(0.25 * SR)
    env = np.ones(n)
    if ai < n: env[:ai] = np.linspace(0, 1, ai)
    if ri < n: env[-ri:] = np.linspace(1, 0, ri)
    return (sig * env * amp).astype(np.float64)

def add_pads(t_start, n_bars, amp=0.12):
    chord_dur = BAR * 2  # each chord lasts 2 bars
    n_chords  = n_bars // 2
    for i in range(n_chords):
        chord = PAD_CHORDS[i % len(PAD_CHORDS)]
        t0    = t_start + i * chord_dur
        for mi, m in enumerate(chord):
            f   = mhz(m)
            sl  = pad_note(f, chord_dur + 0.3, amp)
            sr_ = pad_note(f, chord_dur + 0.3, amp, detune=0.0025)
            place(L, sl, t0)
            place(R, sr_, t0)

add_pads(INTRO,   4,  amp=0.09)
add_pads(VERSE1,  8,  amp=0.11)
add_pads(CHORUS1, 8,  amp=0.14)
add_pads(VERSE2,  8,  amp=0.11)
add_pads(CHORUS2, 8,  amp=0.15)
add_pads(OUTRO,   4,  amp=0.08)

# =============================================================================
# LEAD MELODY  --  catchy, E major, sits at 330-660Hz (warm mid range)
# Motif: E4-G#4-B4-E5 rise, then D#5-C#5-B4-A4 fall
# Plays every 2 bars, slightly different each time
# =============================================================================
# (step in 16ths, midi, dur in 16ths)
MOTIF_A = [
    (0,  64, 2), (2,  68, 2), (4,  71, 2), (6,  76, 3),
    (9,  75, 1), (10, 73, 2), (12, 71, 2), (14, 69, 2),
    # bar 2
    (16, 68, 2), (18, 71, 2), (20, 73, 2), (22, 76, 4),
    (26, 73, 2), (28, 71, 2), (30, 68, 2),
]
MOTIF_B = [
    (0,  76, 3), (3,  75, 1), (4,  73, 2), (6,  71, 2),
    (8,  73, 2), (10, 76, 2), (12, 78, 3), (15, 76, 1),
    (16, 73, 2), (18, 71, 2), (20, 69, 2), (22, 68, 4),
    (26, 71, 2), (28, 73, 2), (30, 76, 2),
]

def lead_note(midi, dur_s, amp=0.32):
    n   = int(dur_s * SR)
    t   = np.linspace(0, dur_s, n, endpoint=False)
    f   = mhz(midi)
    # Two slightly detuned sines = warm, not buzzy
    sig = (np.sin(2*np.pi*f*0.9985*t) * 0.55 +
           np.sin(2*np.pi*f*1.0015*t) * 0.55)
    # Small 3rd harmonic for presence without harshness
    sig += np.sin(2*np.pi*f*3*t) * 0.06
    e   = ar(n, a_s=0.010, r_s=0.05)
    return (sig * e * amp).astype(np.float64)

def add_lead(t_start, n_bars, amp=0.32, motif=MOTIF_A):
    steps_per_phrase = 32  # 2 bars of 16ths
    for b in range(0, n_bars, 2):
        t0 = t_start + b * BAR
        for (step, midi, dur_16) in motif:
            at  = t0 + step * S16
            dur = dur_16 * S16 * 0.82
            sig = lead_note(midi, dur, amp)
            place(L, sig, at,       amp=1.0)
            place(R, sig, at+0.005, amp=1.0)  # tiny stereo offset

def add_lead_alternating(t_start, n_bars, amp=0.32):
    for phrase in range(n_bars // 2):
        motif = MOTIF_A if phrase % 2 == 0 else MOTIF_B
        t0    = t_start + phrase * 2 * BAR
        for (step, midi, dur_16) in motif:
            at  = t0 + step * S16
            dur = dur_16 * S16 * 0.82
            sig = lead_note(midi, dur, amp)
            place(L, sig, at,       amp=1.0)
            place(R, sig, at+0.005, amp=1.0)

add_lead(VERSE1,  8, amp=0.28, motif=MOTIF_A)
add_lead_alternating(CHORUS1, 8, amp=0.36)
add_lead(VERSE2,  8, amp=0.28, motif=MOTIF_B)
add_lead_alternating(CHORUS2, 8, amp=0.38)

# =============================================================================
# ARP  --  E major arpeggio on 8th notes (from MCP arpeggiate result)
# E4(64) G#4(68) B4(71) cycling upward, high register, sparkly
# =============================================================================
ARP_PITCHES = [76, 78, 81, 83, 81, 78, 76, 73,   # E5 F#5 A5 B5 down
               71, 73, 76, 78, 76, 73, 71, 68]    # B4 C#5 E5 F#5 down

def arp_note(midi, dur, amp=0.16):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    f = mhz(midi)
    sig = np.sin(2*np.pi*f*t) * 0.7 + np.sin(2*np.pi*f*2*t) * 0.22
    e   = ar(n, a_s=0.003, r_s=0.04)
    return (sig * e * amp).astype(np.float64)

def add_arp(t_start, n_bars, amp=0.16):
    for b in range(n_bars):
        t0 = t_start + b * BAR
        for i in range(8):
            midi = ARP_PITCHES[(b * 8 + i) % len(ARP_PITCHES)]
            sig  = arp_note(midi, S8 * 0.78, amp)
            pan  = 0.3 + 0.4 * (i / 7)   # gentle pan sweep
            place(L, sig, t0 + i*S8, amp=(1 - pan*0.4))
            place(R, sig, t0 + i*S8, amp=(0.6 + pan*0.4))

add_arp(CHORUS1, 8, amp=0.16)
add_arp(CHORUS2, 8, amp=0.18)

# =============================================================================
# INTRO SWELL  --  gentle filter sweep to start things off
# =============================================================================
def add_swell(t_start, dur_s, amp=0.08):
    n = int(dur_s * SR)
    t = np.linspace(0, dur_s, n, endpoint=False)
    # Rising chord: E3 G#3 B3 with slow attack
    sig = np.zeros(n, np.float64)
    for m in [52, 56, 59, 64]:
        f = mhz(m)
        sig += np.sin(2*np.pi*f*t) * 0.25
    env = (t / dur_s) ** 1.5
    sig = sig * env * amp
    place(L, sig, t_start); place(R, sig, t_start)

add_swell(INTRO, 4 * BAR, amp=0.10)

# =============================================================================
# OUTRO FADE
# =============================================================================
fs = int(OUTRO * SR); fe = int(END * SR); fn = fe - fs
if fn > 0:
    fenv = np.linspace(1.0, 0.0, fn)
    L[fs:fe] *= fenv; R[fs:fe] *= fenv

# =============================================================================
# MIX & EXPORT  --  normalize to -1 dBFS
# =============================================================================
peak = max(np.max(np.abs(L)), np.max(np.abs(R)), 1e-9)
L = (L * 0.89 / peak).astype(np.float32)
R = (R * 0.89 / peak).astype(np.float32)

stereo = np.empty(N * 2, np.float32)
stereo[0::2] = L; stereo[1::2] = R
s16 = (stereo * 32767).astype(np.int16)

out = os.path.dirname(os.path.abspath(__file__))
wp  = os.path.join(out, "tracks", "sunrise.wav")
os.makedirs(os.path.dirname(wp), exist_ok=True)

with wave.open(wp, 'w') as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes(s16.tobytes())
print(f"WAV: {wp}  ({os.path.getsize(wp)//1024} KB, {N/SR:.1f}s, {BPM}BPM, E major)")

try:
    from pydub import AudioSegment
    seg = AudioSegment.from_wav(wp)
    mp  = wp.replace('.wav', '.mp3')
    seg.export(mp, format='mp3', bitrate='256k',
               tags={"title":"Sunrise","artist":"BespokeSynth MCP",
                     "genre":"Uplifting Hardstyle","bpm":"152"})
    print(f"MP3: {mp}  ({os.path.getsize(mp)//1024} KB)")
except ImportError:
    print("no pydub -- wav only")
