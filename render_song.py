"""
render_song.py
==============
Full hardstyle / techno / breakcore + chibi cute track — software synthesizer.

160 BPM  |  F# minor  |  ~4:00  |  160 bars
Instruments: pitched-sweep kick, multi-band snare, reese bass, 7-voice supersaw
             stabs, bell-FM chibi lead, lush breakdown pad, industrial noise.
Processing:  convolution reverb (plate / hall / room), sidechain compression,
             swept LP filter on builds, stereo widening, soft-knee limiter.

Run:  python render_song.py
Out:  tracks/hardstyle_chibi_full.mp3
"""

import pathlib, time
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR   = 44100
BPM  = 160.0
SPB  = SR * 60 / BPM        # samples per beat  = 16537.5
S16  = SPB / 4               # samples per 16th  = 4134.4
SBAR = SPB * 4               # samples per bar   = 66150

RNG    = np.random.default_rng(77)
TRACKS = pathlib.Path(__file__).parent / "tracks"
TRACKS.mkdir(exist_ok=True)

# ── timing helpers ────────────────────────────────────────────────────────────

def bs(bar):           return int(bar * SBAR)           # bar  → sample
def bss(bar, step16):  return int(bar*SBAR + step16*S16) # bar+step → sample
def hz(m):             return 440.0 * 2.0**((m-69)/12)

# ── filters ───────────────────────────────────────────────────────────────────

def lpf(x, f, order=4):
    f = float(np.clip(f, 10, SR/2 - 100))
    return sosfilt(butter(order, f/(SR/2), btype='low',  output='sos'), x)

def hpf(x, f, order=2):
    f = float(np.clip(f, 1,  SR/2 - 100))
    return sosfilt(butter(order, f/(SR/2), btype='high', output='sos'), x)

def bpf(x, lo, hi, order=2):
    lo = float(np.clip(lo, 1,    SR/2*0.97))
    hi = float(np.clip(hi, lo+1, SR/2*0.99))
    return sosfilt(butter(order, [lo/(SR/2), hi/(SR/2)], btype='band', output='sos'), x)

def swept_lpf(sig, f0, f1):
    """Crossfade between two LP-filtered copies — simulates a filter sweep."""
    a = lpf(sig, f0)
    b = lpf(sig, f1)
    r = np.linspace(0, 1, len(sig)) ** 1.4
    return a*(1-r) + b*r

# ── envelope ─────────────────────────────────────────────────────────────────

def adsr(n, atk, dec, sus, rel):
    """ADSR envelope. All times in seconds. Scales down gracefully for short n."""
    if n <= 0:
        return np.zeros(n)
    # Scale segments to fit n proportionally if they'd overflow
    a_f = atk * SR
    d_f = dec * SR
    r_f = rel * SR
    total = a_f + d_f + r_f
    if total >= n:
        scale = n / (total + 1)
        a_f, d_f, r_f = a_f*scale, d_f*scale, r_f*scale
    a, d, r = int(a_f), int(d_f), int(r_f)
    s = max(0, n - a - d - r)
    env = np.zeros(n)
    if a: env[:a]              = np.linspace(0, 1,   a)
    if d: env[a:a+d]           = np.linspace(1, sus,  d)
    if s: env[a+d:a+d+s]       = sus
    if r: env[a+d+s:a+d+s+r]   = np.linspace(sus, 0, min(r, n-a-d-s))
    return env

# ── oscillators ───────────────────────────────────────────────────────────────

def saw_bl(freq, n):
    """Band-limited sawtooth — additive synthesis, harmonics capped at Nyquist."""
    t     = np.arange(n) / SR
    kmax  = max(1, int(SR / 2 / freq * 0.88))
    wave  = np.zeros(n)
    for k in range(1, min(kmax+1, 64)):
        wave += ((-1)**(k+1)) * np.sin(2*np.pi*freq*k*t) / k
    return wave * (2/np.pi)

def unison_saw(freq, n, voices=7, spread=0.16):
    """Detuned unison sawtooth (supersaw-style)."""
    wave = np.zeros(n)
    for i, d in enumerate(np.linspace(-spread, spread, voices)):
        wave += saw_bl(freq * 2**(d/12), n)
    return wave / voices

def sine_stack(freq, n, ratios, amps):
    """Additive sine stack at given frequency ratios and amplitudes."""
    t    = np.arange(n) / SR
    wave = np.zeros(n)
    for r, a in zip(ratios, amps):
        wave += a * np.sin(2*np.pi * freq * r * t)
    return wave

# ── reverb (convolution with synthetic impulse response) ─────────────────────

def _make_ir(dur_s, decay_s, hi_cut, pre_ms=8):
    n   = int(dur_s * SR)
    ir  = RNG.standard_normal(n).astype(np.float64)
    t   = np.arange(n) / SR
    ir *= np.exp(-t / decay_s)
    ir[:int(pre_ms*SR/1000)] = 0      # pre-delay
    ir  = lpf(ir, hi_cut)
    ir /= np.abs(ir).max() * 25
    return ir.astype(np.float32)

_PLATE = _make_ir(2.2, 1.0, 7000, pre_ms=12)
_ROOM  = _make_ir(0.6, 0.25, 5000, pre_ms=4)
_HALL  = _make_ir(4.0, 1.8, 5500, pre_ms=20)

def reverb(sig, ir, wet=0.35):
    tail = fftconvolve(sig, ir)[:len(sig)]
    return sig*(1-wet) + tail*wet

# ── sidechain (kick ducts bass / chords) ─────────────────────────────────────

def make_sc_env(kick_samps, total_n, release_s=0.14):
    env  = np.ones(total_n, dtype=np.float32)
    r_n  = int(release_s * SR)
    ramp = np.linspace(0.10, 1.0, r_n)
    for pos in kick_samps:
        a = pos; b = min(pos + r_n, total_n)
        env[a:b] = np.minimum(env[a:b], ramp[:b-a])
    return env

# ── stamp helper ─────────────────────────────────────────────────────────────

def stamp(buf, sig, start):
    end = min(start + len(sig), len(buf))
    if end > start >= 0:
        buf[start:end] += sig[:end-start]

# ══════════════════════════════════════════════════════════════════════════════
#  INSTRUMENTS
# ══════════════════════════════════════════════════════════════════════════════

def mk_kick():
    n = samp_ms(680)
    t = np.arange(n) / SR
    # Sub: sustained 42 Hz
    sub   = np.sin(2*np.pi*42*t) * np.exp(-t*3.2)
    # Body: fast pitch sweep 195→42 Hz
    f_env = 42 + (195-42)*np.exp(-t*20)
    body  = np.sin(np.cumsum(2*np.pi*f_env/SR)) * np.exp(-t*6)
    # Mid punch 80 Hz
    punch = np.sin(2*np.pi*80*t) * np.exp(-t*30)
    # Transient click
    noise = hpf(RNG.uniform(-1,1,n), 3000) * np.exp(-np.arange(n)*380/SR)
    noise[samp_ms(18):] = 0
    raw   = sub*0.38 + body*0.44 + punch*0.18 + noise*0.32
    # Warm asymmetric saturation (adds 2nd harmonic)
    raw   = (np.tanh(raw*2.6 + 0.10) - np.tanh(0.10)) / np.tanh(2.6)
    return hpf(raw, 28).astype(np.float32)

def mk_snare(vel=1.0, ghost=False):
    n    = samp_ms(200 if not ghost else 120)
    t    = np.arange(n) / SR
    body = bpf(RNG.uniform(-1,1,n), 150, 1000) * np.exp(-t*20)
    air  = hpf(RNG.uniform(-1,1,n), 4500)      * np.exp(-t*38)
    tone = (np.sin(2*np.pi*195*t)*0.6 + np.sin(2*np.pi*320*t)*0.4) * np.exp(-t*45)
    raw  = body*0.50 + air*0.32 + tone*0.25
    raw  = np.tanh(raw*1.6) / np.tanh(1.6)
    return (raw * vel * (0.72 if not ghost else 0.32)).astype(np.float32)

def mk_chh(open_frac=0.0, vel=1.0):
    ms  = 30 + int(open_frac * 280)
    n   = samp_ms(ms)
    t   = np.arange(n) / SR
    sig = hpf(RNG.uniform(-1,1,n), 8000 - open_frac*2500)
    sig+= hpf(RNG.uniform(-1,1,n), 11000) * 0.35
    env = np.exp(-t * (65 - open_frac*48))
    return (sig * env * vel * 0.40).astype(np.float32)

def mk_crash():
    n   = samp_ms(1100)
    t   = np.arange(n) / SR
    lo  = hpf(RNG.uniform(-1,1,n), 1200)
    hi  = hpf(RNG.uniform(-1,1,n), 5000)
    mid = bpf(RNG.uniform(-1,1,n), 600, 3000)
    env = np.exp(-t*3.2)
    return ((lo*0.45 + hi*0.35 + mid*0.20) * env * 0.55).astype(np.float32)

def mk_clap():
    n  = samp_ms(300)
    t  = np.arange(n) / SR
    n1 = bpf(RNG.uniform(-1,1,n), 700, 3500) * np.exp(-t*28)
    n2 = hpf(RNG.uniform(-1,1,n), 2000)      * np.exp(-t*60)
    s  = n1*0.6 + n2*0.4
    return (s * 0.70).astype(np.float32)

def mk_bass(pitch, dur_ms, cutoff=800.0):
    f = hz(pitch)
    n = samp_ms(dur_ms)
    # 3-voice Reese (tight detune = warm chorus)
    w = (saw_bl(f*0.9975, n) + saw_bl(f, n) + saw_bl(f*1.0025, n)) / 3
    w = w * adsr(n, 0.005, 0.04, 0.80, 0.06)
    w = lpf(w, cutoff)
    w = np.tanh(w * 2.2) / np.tanh(2.2)
    return (w * 0.58).astype(np.float32)

def mk_stab(pitch, dur_ms, cutoff=5500.0, vel=0.80):
    f = hz(pitch)
    n = samp_ms(dur_ms)
    w = unison_saw(f, n, voices=7, spread=0.18)
    w = w * adsr(n, 0.007, 0.09, 0.38, 0.06)
    w = lpf(w, cutoff)
    return (w * vel * 0.30).astype(np.float32)

def mk_pad(pitch, dur_ms, cutoff=2400.0):
    """Lush chord pad: detuned saws + sine harmonics, slow attack."""
    f = hz(pitch)
    n = samp_ms(dur_ms)
    t = np.arange(n) / SR
    w = (unison_saw(f, n, voices=5, spread=0.12) * 0.50
         + np.sin(2*np.pi*f*1.0*t) * 0.22
         + np.sin(2*np.pi*f*1.5*t) * 0.15   # perfect 5th
         + np.sin(2*np.pi*f*2.0*t) * 0.08   # octave
         + np.sin(2*np.pi*f*0.5*t) * 0.10)  # sub octave
    w = w * adsr(n, 1.40, 0.80, 0.72, 1.60)
    w = lpf(w, cutoff)
    return (w * 0.26).astype(np.float32)

def mk_lead(pitch, dur_ms, vel=1.0, bright=1.0):
    """
    Chibi bell lead: FM carrier + inharmonic bell partials + vibrato.
    Sounds bell-like and sparkly, not thin/digital.
    """
    f  = hz(pitch)
    n  = samp_ms(dur_ms)
    t  = np.arange(n) / SR
    # FM component (mod ratio 2.007 — near-harmonic avoids harsh sidebands)
    mod_idx = (2.8 + vel * 0.8) * bright
    mod     = mod_idx * np.sin(2*np.pi * f * 2.007 * t)
    carrier = np.sin(2*np.pi * f * t + mod)
    # Inharmonic bell partials (physical bell ratios from Chowning 1973)
    p2 = np.sin(2*np.pi * f * 2.756 * t) * 0.24 * bright
    p3 = np.sin(2*np.pi * f * 5.404 * t) * 0.08
    p4 = np.sin(2*np.pi * f * 1.414 * t) * 0.18   # warm sub
    # Sparkle: triangle-approx at 4× freq
    p5 = (np.sin(2*np.pi*f*4*t) - np.sin(2*np.pi*f*12*t)/9) * 0.06
    # Vibrato ramp (kicks in at 20ms)
    vs  = samp_ms(20)
    vib = np.zeros(n)
    if n > vs:
        vt = np.arange(n-vs) / SR
        vib[vs:] = np.sin(2*np.pi*5.6*vt) * 0.0048*f * np.minimum(vt*12, 1.0)
    wave = (carrier*0.65 + p2 + p3 + p4 + p5) * np.cos(vib)
    # Bell envelope: instant attack, fast main decay, gentle sustain tail
    env  = adsr(n, 0.002, 0.14, 0.28, 0.10)
    wave = wave * env * vel
    return (wave * 0.42).astype(np.float32)

def mk_lead_hard(pitch, dur_ms, vel=1.0):
    """
    Hardstyle raw lead: heavily distorted supersaw — aggressive.
    Used in drop 2 for extra intensity.
    """
    f = hz(pitch)
    n = samp_ms(dur_ms)
    w = unison_saw(f, n, voices=5, spread=0.22)
    w = w * adsr(n, 0.004, 0.06, 0.60, 0.05)
    w = lpf(w, 4500)
    w = np.tanh(w * 3.5) / np.tanh(3.5)   # heavy distortion
    w = hpf(w, 120)                         # remove mud
    return (w * vel * 0.35).astype(np.float32)

def mk_sub_bass(pitch, dur_ms):
    """Pure sine sub — underpins the intro and breakdown sections."""
    f = hz(pitch)
    n = samp_ms(dur_ms)
    t = np.arange(n) / SR
    w = np.sin(2*np.pi*f*t) * adsr(n, 0.02, 0.1, 0.85, 0.2)
    return (w * 0.55).astype(np.float32)

def mk_noise_swell(dur_ms, f0=120, f1=9000):
    """Filtered noise swell: opens from f0 to f1 over dur_ms."""
    n    = samp_ms(dur_ms)
    sig  = RNG.uniform(-1, 1, n)
    out  = swept_lpf(sig, f0, f1)
    amp  = np.linspace(0, 0.45, n) ** 0.7
    return (out * amp).astype(np.float32)

def mk_riser(dur_ms, start_hz=50, end_hz=2000):
    """Pitched sine riser."""
    n    = samp_ms(dur_ms)
    t    = np.arange(n) / SR
    freq = np.geomspace(start_hz, end_hz, n)
    sig  = np.sin(np.cumsum(2*np.pi*freq/SR))
    amp  = np.linspace(0, 0.30, n) ** 0.6
    return (sig * amp).astype(np.float32)

def samp_ms(ms):
    return int(ms * SR / 1000)

# ══════════════════════════════════════════════════════════════════════════════
#  PATTERN GENERATORS
# ══════════════════════════════════════════════════════════════════════════════
# Each pattern is a list of (step, velocity_0_127) tuples — step is 0–15.

KICK_FLOOR  = [(0,127),(4,127),(8,127),(12,127)]
KICK_HARD   = [(0,127),(3,100),(4,127),(7,85),(8,127),(11,95),(12,127),(15,80)]
KICK_BC     = [(0,127),(2,95),(4,127),(5,85),(7,110),(8,127),(9,75),(11,100),
               (12,127),(13,80),(14,110),(15,75)]

SNARE_24    = [(4,100),(12,100)]
SNARE_HARD  = [(4,100),(10,55),(12,100),(14,60)]
SNARE_BC    = [(4,100),(6,55),(10,70),(12,100),(13,50),(15,65)]

HH_8TH      = [(i*2, 60+10*(i%4==0)+5*(i%2==0)) for i in range(8)]
HH_16TH     = [(i,   60+10*(i%4==0)+5*(i%2==0)) for i in range(16)]
HH_ROLL     = [(i,   55+15*(i%4==0)+8*(i%2==0)) for i in range(16)]  # denser
HH_OPEN_4   = [(2,80),(6,80),(10,80),(14,80)]   # open hat on off-beats

GHOST_PAT   = [(2,35),(6,35),(10,35),(14,35)]

# Bass patterns: (step, pitch_midi, velocity, dur_ms)
def bass_bar(root, pat):
    return [(s, p, v, d) for s,p,v,d in pat]

# Chord stab patterns: (step, [pitches], vel, dur_ms)
def stab_bar(steps, pitches, vel=78, dur=185):
    return [(s, pitches, vel, dur) for s in steps]

# ── scale / chord reference (F# minor) ───────────────────────────────────────
# F#2=42 G#2=44 A2=45 B2=47 C#3=49 D3=50 E3=52
# F#3=54 G#3=56 A3=57 B3=59 C#4=61 D4=62 E4=64
# F#4=66 G#4=68 A4=69 B4=71 C#5=73 D5=74 E5=76
# F#5=78 G#5=80 A5=81 B5=83 C#6=85 D6=86 E6=88 F#6=90

# ══════════════════════════════════════════════════════════════════════════════
#  SONG STRUCTURE  (160 bars = 4:00 at 160 BPM)
# ══════════════════════════════════════════════════════════════════════════════
#
#  INTRO       bars  0-15   (0:00-0:24)  kick + sub, darkness
#  BUILD 1     bars 16-31   (0:24-0:48)  + hats, bass, stabs (filtered)
#  PRE-DROP    bars 32-39   (0:48-1:00)  noise swell, riser, drum fill
#  DROP 1      bars 40-71   (1:00-1:48)  full energy, chibi lead melody A
#  BREAKDOWN   bars 72-87   (1:48-2:12)  pad, chibi melody B, no kick
#  BUILD 2     bars 88-95   (2:12-2:24)  kick returns, filter sweep, tension
#  DROP 2      bars 96-143  (2:24-3:36)  harder, breakcore drums, melody A+C
#  OUTRO       bars 144-159 (3:36-4:00)  elements drop, reverb tail, end
#
# ══════════════════════════════════════════════════════════════════════════════

def build_schedule(total_bars):
    """
    Returns a list of events:
      (sample_start, layer, *args)
    layer in: kick snare ghost chh ohh crash clap bass stab pad lead lead_hard
              sub noise riser
    """
    events = []

    def add(bar, step16, layer, *args):
        events.append((bss(bar, step16), layer, *args))

    def add_s(bar, step16, layer, *args):
        """Alias: add at sample = bss(bar, step16)."""
        add(bar, step16, layer, *args)

    def drums(bar, kick_pat=None, snare_pat=None, hh_pat=None,
              ohh_pat=None, ghost_pat=None, crash=False):
        if kick_pat:
            for s, v in kick_pat:
                add(bar, s, 'kick', v)
        if snare_pat:
            for s, v in snare_pat:
                add(bar, s, 'snare', v/127)
        if hh_pat:
            for s, v in hh_pat:
                add(bar, s, 'chh', 0.0, v/127)
        if ohh_pat:
            for s, v in ohh_pat:
                add(bar, s, 'ohh', v/127)
        if ghost_pat:
            for s, v in ghost_pat:
                add(bar, s, 'ghost')
        if crash:
            add(bar, 0, 'crash')

    def bass_line(bar, notes):
        # notes = [(step16, pitch_midi, vel, dur_ms)]
        for s, p, v, d in notes:
            add(bar, s, 'bass', p, d, 800.0)

    def stab_line(bar, notes, cutoff=5000.0):
        # notes = [(step16, [pitches], vel, dur_ms)]
        for s, pitches, v, d in notes:
            for p in pitches:
                add(bar, s, 'stab', p, d, cutoff, v/127)

    def lead_line(bar, notes, hard=False, bright=1.0):
        # notes = [(step16, pitch_midi, vel_0_127, dur_ms)]
        layer = 'lead_hard' if hard else 'lead'
        for s, p, v, d in notes:
            add(bar, s, layer, p, d, v/127, bright)

    def pad_line(bar, notes, cutoff=2400.0):
        for s, p, v, d in notes:
            add(bar, s, 'pad', p, d, cutoff)

    # ─────────────────────────────────────────────────────────────────────────
    # INTRO  bars 0-15   (darkness — kick + sub only)
    # ─────────────────────────────────────────────────────────────────────────
    for bar in range(0, 8):
        drums(bar, kick_pat=KICK_FLOOR, crash=(bar==0))

    # Sub bass throb (F#1 = 30)
    for bar in range(0, 8):
        add(bar, 0, 'sub', 30, 1500*4, )   # whole bar

    # Bars 8-15: kick + very sparse hi-hat, bass enters muffled
    for bar in range(8, 16):
        drums(bar, kick_pat=KICK_FLOOR,
              hh_pat=[(i*4, 55) for i in range(4)])   # quarter-note hh only

    # Filtered bass starts bar 8 (very low cutoff, muffled)
    bass_notes_intro = [
        (0,42,90,375),(4,42,75,375),(8,42,90,375),(12,42,75,375),
    ]
    for bar in range(8, 16):
        for s, p, v, d in bass_notes_intro:
            add(bar, s, 'bass', p, d, 220.0)   # very muffled

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD 1  bars 16-31  (things pile in, filter opens)
    # ─────────────────────────────────────────────────────────────────────────
    bass_notes_build = [
        (0,42,100,280), (2,42,80,180), (4,45,90,280), (6,42,80,180),
        (8,47,95,280),  (10,42,80,180),(12,45,90,280),(14,42,75,180),
    ]
    # Stabs: F#m and Bm, filter closed then opening
    stab_notes_build = [
        (0,  [54,57,61], 72, 185),    # F#m close voicing
        (8,  [59,62,66], 72, 185),    # Bm
    ]

    for bar in range(16, 32):
        progress = (bar - 16) / 16.0    # 0 → 1
        hh = HH_8TH if bar < 24 else HH_16TH
        drums(bar, kick_pat=KICK_FLOOR,
              snare_pat=SNARE_24 if bar >= 20 else None,
              hh_pat=hh,
              ohh_pat=HH_OPEN_4 if bar >= 24 else None,
              crash=(bar==16))
        # Bass cutoff opens: 220 → 900 Hz over 16 bars
        cutoff = 220 + (900-220) * progress
        for s, p, v, d in bass_notes_build:
            add(bar, s, 'bass', p, d, cutoff)
        # Stabs enter at bar 20, cutoff opens 400 → 4000 Hz
        if bar >= 20:
            sc = 400 + (4000-400) * ((bar-20)/12)
            stab_line(bar, stab_notes_build, cutoff=sc)

    # ─────────────────────────────────────────────────────────────────────────
    # PRE-DROP  bars 32-39  (tension: noise swell, riser, dense drums)
    # ─────────────────────────────────────────────────────────────────────────
    for bar in range(32, 40):
        drums(bar, kick_pat=KICK_HARD,
              snare_pat=SNARE_HARD,
              hh_pat=HH_16TH,
              ohh_pat=HH_OPEN_4,
              ghost_pat=GHOST_PAT,
              crash=(bar==32))

    add(32, 0, 'noise', 12000)   # 12-bar noise swell (covers bars 32-39 + a bit)
    add(36, 0, 'riser', 8000)    # riser in last 4 bars

    # Snare roll bars 38-39 (16th-note snare hits building to drop)
    for bar in (38, 39):
        for s in range(0, 16, 1):
            v = int(55 + s*4)
            add(bar, s, 'snare', min(v,100)/127)

    # ─────────────────────────────────────────────────────────────────────────
    # DROP 1  bars 40-71  (full energy, chibi lead)
    # ─────────────────────────────────────────────────────────────────────────

    # Bass line (F# minor pattern, repeating every 4 bars)
    bass_drop1 = [
        # bar A (F#m feel)
        (0,42,110,280), (2,42,85,140), (3,45,80,140), (4,42,105,280),
        (6,45,85,180),  (8,47,100,280),(10,47,80,140),(12,45,95,280),
        (14,42,85,140),
        # (continues per-bar below)
    ]
    # Chord stabs: 4-bar cycle  i - iv - VI - v  (F#m Bm D C#m)
    stab_cycle = [
        [(0,[54,57,61],80,185),(4,[54,57,61],78,185),(8,[54,57,61],75,185),(12,[54,57,61],78,185)],
        [(0,[59,62,66],80,185),(4,[59,62,66],78,185),(8,[59,62,66],75,185),(12,[59,62,66],78,185)],
        [(0,[62,66,69],80,185),(4,[62,66,69],78,185),(8,[62,66,69],75,185),(12,[62,66,69],78,185)],
        [(0,[61,64,68],80,185),(4,[61,64,68],78,185),(8,[61,64,68],75,185),(12,[61,64,68],78,185)],
    ]

    # Lead melody A — chibi sparkle ascending/descending across 4 bars
    lead_A = [
        # bar 0 of phrase: ascending arpeggio
        (0,78,95,80),(1,81,100,80),(2,85,105,80),(3,88,110,80),
        (4,85,100,80),(5,83,95,80),(6,81,90,80),(7,80,85,80),
        (8,81,95,80),(9,85,100,80),(10,88,105,80),(11,86,102,80),
        (12,85,100,80),(13,83,95,80),(14,81,90,80),(15,80,85,80),
        # bar 1: upper register run
        (16,90,110,80),(17,88,105,80),(18,85,100,80),(19,83,95,80),
        (20,81,90,80),(21,83,95,80),(22,85,100,80),(23,88,105,80),
        (24,90,110,80),(25,88,105,80),(26,85,100,80),(27,81,95,80),
        (28,80,90,80),(29,81,92,80),(30,83,95,80),(31,85,100,80),
        # bar 2: breakcore intensity — octave stutter
        (32,78,110,80),(33,90,110,80),(34,78,105,80),(35,90,105,80),
        (36,85,110,80),(37,83,105,80),(38,81,100,80),(39,80,95,80),
        (40,83,105,80),(41,85,108,80),(42,88,110,80),(43,85,105,80),
        (44,83,100,80),(45,81,95,80),(46,80,90,80),(47,78,85,80),
        # bar 3: resolution melody
        (48,85,100,80),(49,83,98,80),(50,81,95,80),(51,80,92,80),
        (52,78,95,80),(53,80,98,80),(54,83,102,80),(55,85,105,80),
        (56,88,108,80),(57,90,110,80),(58,88,105,80),(59,85,100,80),
        (60,83,95,80),(61,81,90,80),(62,80,88,80),(63,78,85,80),
    ]

    for bar in range(40, 72):
        cycle_bar = (bar - 40) % 4
        drums(bar,
              kick_pat=KICK_HARD,
              snare_pat=SNARE_HARD,
              hh_pat=HH_16TH,
              ohh_pat=HH_OPEN_4,
              ghost_pat=GHOST_PAT,
              crash=(bar % 8 == 0))
        stab_line(bar, stab_cycle[cycle_bar], cutoff=6000.0)
        # Bass repeating 4-bar pattern
        for s, p, v, d in bass_drop1:
            add(bar, s % 16, 'bass', p, d, 1000.0)

    # Lead A across bars 40-71 (repeating 4-bar phrase)
    for phrase_start in range(40, 72, 4):
        for idx, (rel_step, p, v, d) in enumerate(lead_A):
            bar_off = rel_step // 16
            step    = rel_step % 16
            add(phrase_start + bar_off, step, 'lead', p, d, v/127, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # BREAKDOWN  bars 72-87  (stripped back — pad + melody, atmospheric)
    # ─────────────────────────────────────────────────────────────────────────
    pad_notes_bd = [
        (0,  [54,57,61], 2),   # F#m pad
        (16, [59,62,66], 2),   # Bm pad
        (32, [62,66,69], 2),   # D pad
        (48, [61,64,68], 2),   # C#m pad
    ]

    # Soft hi-hats only (bars 72-79), snare clap on 2&4 (bars 80-87)
    for bar in range(72, 80):
        drums(bar, hh_pat=[(i*4, 42) for i in range(4)])   # quarter hats
    for bar in range(80, 88):
        drums(bar, kick_pat=[(0,80),(8,80)],                # soft kick
              snare_pat=SNARE_24,
              hh_pat=HH_8TH)

    # Pad enters: big lush chords over 4-bar blocks
    for bar in range(72, 88):
        cycle = (bar - 72) % 16
        for rel, pitches, _ in pad_notes_bd:
            if cycle == rel // 4:
                for p in pitches:
                    add(bar, 0, 'pad', p, 6000, 1800.0)

    # Chibi melody B: slower, more melodic, over the pad
    lead_B = [
        (0,83,85,200),(2,85,90,150),(4,88,95,300),(7,85,88,150),
        (8,83,85,200),(10,81,80,200),(12,85,90,300),(15,83,82,150),
        (16,88,95,300),(19,90,100,200),(20,88,95,150),(22,85,88,200),
        (24,83,82,300),(27,81,78,150),(28,83,85,200),(30,85,90,300),
        (32,81,85,200),(34,83,90,200),(36,85,95,300),(39,88,92,150),
        (40,85,88,200),(42,83,82,150),(44,81,78,200),(46,83,85,150),
        (48,85,90,300),(51,88,95,200),(52,85,88,150),(54,83,82,200),
        (56,81,78,300),(59,80,72,150),(60,81,78,200),(62,83,85,300),
    ]
    for bar in range(72, 88):
        phrase_bar = (bar - 72) % 16
        for rel_step, p, v, d in lead_B:
            b2  = rel_step // 16
            s2  = rel_step % 16
            if b2 == phrase_bar:
                add(bar, s2, 'lead', p, d, v/127, 0.85)

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD 2  bars 88-95  (kick returns, drums swell, filter sweep)
    # ─────────────────────────────────────────────────────────────────────────
    for bar in range(88, 96):
        progress = (bar - 88) / 8.0
        drums(bar,
              kick_pat=KICK_FLOOR if bar < 92 else KICK_HARD,
              snare_pat=SNARE_24 if bar >= 90 else None,
              hh_pat=HH_16TH if bar >= 90 else HH_8TH,
              ghost_pat=GHOST_PAT if bar >= 92 else None,
              crash=(bar==88))
        cutoff = 300 + (1100-300)*progress
        for s, p, v, d in bass_notes_build:
            add(bar, s, 'bass', p, d, cutoff)

    add(88, 0, 'noise', 12000)   # 12-bar swell
    add(92, 0, 'riser', 6000)    # 4-bar riser

    # ─────────────────────────────────────────────────────────────────────────
    # DROP 2  bars 96-143  (hardest section — breakcore drums, hard lead too)
    # ─────────────────────────────────────────────────────────────────────────

    # Bass variation — more movement
    bass_drop2 = [
        (0,42,115,240),(1,45,95,120),(2,47,105,240),(3,45,90,120),
        (4,42,110,240),(5,47,95,120),(6,50,100,240),(7,47,90,120),
        (8,42,115,240),(9,45,95,120),(10,47,105,240),(11,42,90,120),
        (12,45,110,240),(13,47,95,120),(14,42,100,240),(15,45,88,120),
    ]

    # Lead melody C — higher octave, more aggressive
    lead_C = [
        (0,90,110,75),(1,88,105,75),(2,85,100,75),(3,83,98,75),
        (4,85,105,75),(5,88,108,75),(6,90,110,75),(7,88,105,75),
        (8,85,100,75),(9,83,95,75),(10,81,90,75),(11,80,88,75),
        (12,83,98,75),(13,85,102,75),(14,88,105,75),(15,90,110,75),
        (16,90,112,75),(17,90,112,75),(18,88,108,75),(19,88,108,75),
        (20,85,105,75),(21,85,105,75),(22,83,100,75),(23,83,100,75),
        (24,81,95,75),(25,83,98,75),(26,85,102,75),(27,88,105,75),
        (28,90,110,75),(29,88,108,75),(30,85,104,75),(31,83,100,75),
        (32,78,110,75),(33,81,108,75),(34,85,110,75),(35,88,112,75),
        (36,90,115,75),(37,88,110,75),(38,85,105,75),(39,83,100,75),
        (40,88,110,75),(41,85,105,75),(42,83,100,75),(43,81,95,75),
        (44,83,100,75),(45,85,105,75),(46,88,108,75),(47,90,112,75),
        (48,90,115,75),(49,88,112,75),(50,85,108,75),(51,83,105,75),
        (52,81,100,75),(53,80,95,75),(54,81,100,75),(55,83,105,75),
        (56,85,108,75),(57,88,112,75),(58,90,115,75),(59,88,112,75),
        (60,85,108,75),(61,83,105,75),(62,81,100,75),(63,80,95,75),
    ]

    for bar in range(96, 144):
        # Alternate kick patterns: breakcore every other 4 bars
        kpat = KICK_BC if ((bar-96)//4) % 2 == 1 else KICK_HARD
        drums(bar,
              kick_pat=kpat,
              snare_pat=SNARE_BC,
              hh_pat=HH_ROLL,
              ohh_pat=HH_OPEN_4,
              ghost_pat=GHOST_PAT,
              crash=(bar % 8 == 0))
        stab_line(bar, stab_cycle[(bar-96)%4], cutoff=6500.0)
        for s, p, v, d in bass_drop2:
            add(bar, s, 'bass', p, d, 1100.0)

    # Lead A + C alternating by 4-bar phrase (A for verse, C for intensification)
    for phrase_start in range(96, 144, 4):
        phrase_idx = (phrase_start - 96) // 4
        melody = lead_A if phrase_idx % 2 == 0 else lead_C
        for rel_step, p, v, d in melody:
            b2  = rel_step // 16
            s2  = rel_step % 16
            add(phrase_start + b2, s2, 'lead', p, d, v/127, 1.2)  # slightly brighter

        # Add hard lead octave below on the C phrases for extra grit
        if phrase_idx % 2 == 1:
            hard_notes = [(s, max(p-12,30), v-10, d)
                          for s, p, v, d in lead_C[:16]]
            for rel_step, p, v, d in hard_notes:
                b2 = rel_step // 16
                s2 = rel_step % 16
                add(phrase_start + b2, s2, 'lead_hard', p, d, max(v,60)/127, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # OUTRO  bars 144-159  (gradual strip-down)
    # ─────────────────────────────────────────────────────────────────────────
    for bar in range(144, 160):
        progress = (bar - 144) / 16.0
        # Kick fades: full → floor → none
        if bar < 152:
            drums(bar, kick_pat=KICK_FLOOR,
                  snare_pat=SNARE_24 if bar < 148 else None,
                  hh_pat=HH_8TH if bar < 150 else None,
                  crash=(bar==144))
        else:
            drums(bar, kick_pat=[(0,max(30,int(127*(1-progress))),)])
        # Bass fades
        if bar < 152:
            cutoff = max(100, 1000 - (bar-144)*60)
            for s, p, v, d in bass_notes_intro:
                add(bar, s, 'bass', p, d, cutoff)
        # Sub fades in for final bars
        if bar >= 152:
            add(bar, 0, 'sub', 30, 1500*4)

    return events

# ══════════════════════════════════════════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render():
    TOTAL_BARS = 160
    total_n    = bs(TOTAL_BARS) + samp_ms(3000)   # +3s reverb tail

    print(f"Building schedule ({TOTAL_BARS} bars = {TOTAL_BARS*1.5:.0f}s)...")
    events = build_schedule(TOTAL_BARS)
    print(f"  {len(events)} events")

    # Pre-generate samples
    KICK_S  = mk_kick()
    CHH_S   = {0: mk_chh(0.0), 1: mk_chh(1.0)}
    CRASH_S = mk_crash()
    CLAP_S  = mk_clap()
    GHOST_S = mk_snare(ghost=True)

    # Separate buses
    kick_bus  = np.zeros(total_n, np.float32)
    snare_bus = np.zeros(total_n, np.float32)
    hat_bus   = np.zeros(total_n, np.float32)
    bass_bus  = np.zeros(total_n, np.float32)
    stab_bus  = np.zeros(total_n, np.float32)
    pad_bus   = np.zeros(total_n, np.float32)
    lead_bus  = np.zeros(total_n, np.float32)
    hard_bus  = np.zeros(total_n, np.float32)
    fx_bus    = np.zeros(total_n, np.float32)   # noise swells, risers

    print("Synthesizing...")
    kick_positions = []

    for start, layer, *args in events:
        if layer == 'kick':
            v = args[0] / 127 if args else 1.0
            stamp(kick_bus, KICK_S * v, start)
            kick_positions.append(start)
        elif layer == 'snare':
            v = args[0] if args else 1.0
            stamp(snare_bus, mk_snare(v), start)
        elif layer == 'ghost':
            stamp(snare_bus, GHOST_S, start)
        elif layer == 'chh':
            of, v = (args[0], args[1]) if len(args) >= 2 else (0.0, 0.8)
            stamp(hat_bus, CHH_S[int(of>0.5)] * v, start)
        elif layer == 'ohh':
            v = args[0] if args else 0.8
            stamp(hat_bus, mk_chh(1.0) * v, start)
        elif layer == 'crash':
            stamp(hat_bus, CRASH_S, start)
        elif layer == 'clap':
            stamp(snare_bus, CLAP_S, start)
        elif layer == 'bass':
            pitch, dur_ms, cutoff = args[0], args[1], args[2]
            stamp(bass_bus, mk_bass(pitch, dur_ms, cutoff), start)
        elif layer == 'stab':
            pitch, dur_ms, cutoff, vel = args[0], args[1], args[2], args[3]
            stamp(stab_bus, mk_stab(pitch, dur_ms, cutoff, vel), start)
        elif layer == 'pad':
            pitch, dur_ms, cutoff = args[0], args[1], args[2]
            stamp(pad_bus, mk_pad(pitch, dur_ms, cutoff), start)
        elif layer == 'lead':
            pitch, dur_ms, vel, bright = args[0], args[1], args[2], args[3]
            stamp(lead_bus, mk_lead(pitch, dur_ms, vel, bright), start)
        elif layer == 'lead_hard':
            pitch, dur_ms, vel, _ = args[0], args[1], args[2], args[3]
            stamp(hard_bus, mk_lead_hard(pitch, dur_ms, vel), start)
        elif layer == 'sub':
            pitch, dur_ms = args[0], args[1]
            stamp(bass_bus, mk_sub_bass(pitch, dur_ms), start)
        elif layer == 'noise':
            dur_ms = args[0]
            stamp(fx_bus, mk_noise_swell(dur_ms), start)
        elif layer == 'riser':
            dur_ms = args[0]
            stamp(fx_bus, mk_riser(dur_ms), start)

    print("Applying effects...")

    # Sidechain compression on bass, stabs, pad
    sc = make_sc_env(kick_positions, total_n, release_s=0.14)
    bass_bus  = bass_bus  * sc
    stab_bus  = stab_bus  * sc * 0.92
    pad_bus   = pad_bus   * (sc * 0.5 + 0.5)   # lighter duck on pad

    # Reverb buses
    snare_wet = reverb(snare_bus, _ROOM, wet=0.30)
    lead_wet  = reverb(lead_bus,  _PLATE, wet=0.50)
    pad_wet   = reverb(pad_bus,   _HALL,  wet=0.70)
    stab_wet  = reverb(stab_bus,  _ROOM,  wet=0.20)

    # Mix buses
    drums_mix = kick_bus*1.00 + snare_wet*0.88 + hat_bus*0.72
    synth_mix = bass_bus*0.85 + stab_wet*0.72 + pad_wet*0.78
    mel_mix   = lead_wet*0.95 + hard_bus*0.70 + fx_bus*0.55

    master = drums_mix*0.90 + synth_mix*0.82 + mel_mix*0.88

    # Stereo widening using M/S technique
    # Widen stabs and lead; keep kick/bass mono
    wide_src = stab_wet + lead_wet * 1.2
    t_arr    = np.arange(total_n) / SR
    # Slow panning LFO (0.08 Hz — one cycle every ~12.5s)
    lfo      = np.sin(2*np.pi*0.08*t_arr) * 0.12
    left     = (master + wide_src * lfo).astype(np.float32)
    right    = (master - wide_src * lfo).astype(np.float32)

    # High-pass to remove DC
    left  = hpf(left.astype(np.float64),  22).astype(np.float32)
    right = hpf(right.astype(np.float64), 22).astype(np.float32)

    # Soft-knee limiter
    def limit(x, thresh=0.90):
        mask  = np.abs(x) > thresh
        over  = np.abs(x[mask]) - thresh
        x[mask] = np.sign(x[mask]) * (thresh + np.tanh(over*3) * (1-thresh))
        return x

    peak = max(np.abs(left).max(), np.abs(right).max())
    if peak > 0:
        left  = left  / peak * 0.85
        right = right / peak * 0.85
    left  = limit(left)
    right = limit(right)

    stereo = np.stack([left, right], axis=-1)

    # ── export ────────────────────────────────────────────────────────────────
    print("Exporting...")
    wav_path = TRACKS / "hardstyle_chibi_full.wav"
    mp3_path = TRACKS / "hardstyle_chibi_full.mp3"

    import soundfile as sf
    sf.write(str(wav_path), stereo.astype(np.float32), SR, subtype='FLOAT')
    print(f"  WAV: {wav_path.name}  ({wav_path.stat().st_size//1024} KB)")

    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_wav(str(wav_path))
        seg.export(str(mp3_path), format="mp3", bitrate="320k",
                   tags={"title":  "Hardstyle Chibi Full",
                         "artist": "BespokeSynth MCP",
                         "genre":  "Hardstyle / Techno / Breakcore",
                         "bpm":    "160",
                         "key":    "F# minor"})
        dur  = len(stereo) / SR
        size = mp3_path.stat().st_size // 1024
        print(f"  MP3: {mp3_path.name}  ({size} KB  {dur:.1f}s  320kbps)")
        wav_path.unlink()
        return mp3_path, dur
    except Exception as exc:
        print(f"  MP3 failed ({exc}), keeping WAV.")
        return wav_path, len(stereo)/SR


if __name__ == "__main__":
    t0   = time.perf_counter()
    out, dur = render()
    mins = int(dur // 60)
    secs = dur % 60
    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s  ->  {out}  [{mins}:{secs:05.2f}]")
