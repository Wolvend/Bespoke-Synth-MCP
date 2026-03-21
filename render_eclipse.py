"""
render_eclipse.py  --  "ECLIPSE"
174 BPM | D minor | Rawstyle/Hardstyle
Much cooler than Starfall: supersaw, distorted kick, sidechain pump, reverb.

Run: python render_eclipse.py
Needs: numpy, scipy   (pip install numpy scipy)
Needs: pydub + ffmpeg for MP3 export
"""

import numpy as np
import wave, os

SR   = 44100
BPM  = 174.0
BEAT = 60.0 / BPM        # 0.3448 s
BAR  = BEAT * 4           # 1.379 s
STEP = BEAT / 4           # 16th note = 0.0862 s

def hz(midi): return 440.0 * 2 ** ((midi - 69) / 12.0)

# ---- sections (bars) --------------------------------------------------------
INTRO      = 0
BUILD      = 4  * BAR
DROP1      = 8  * BAR
BREAK      = 16 * BAR
BUILD2     = 20 * BAR
DROP2      = 24 * BAR
OUTRO      = 32 * BAR
END        = 36 * BAR

N = int(END * SR) + SR
L = np.zeros(N, np.float64)   # left  (float64 to avoid overflow)
R = np.zeros(N, np.float64)   # right

rng = np.random.default_rng(99)

# ---- helpers ----------------------------------------------------------------
def place(ch, sig, t):
    s = int(t * SR)
    if s >= len(ch): return
    e = min(len(ch), s + len(sig))
    ch[s:e] += sig[:e - s]

def env_ar(n, a=0.004, r=0.08):
    e = np.ones(n, np.float32)
    ai = int(a * SR); ri = int(r * SR)
    if ai > 0 and ai <= n: e[:ai] = np.linspace(0, 1, ai)
    if ri > 0 and ri <= n: e[-ri:] = np.linspace(1, 0, ri)
    return e

def softclip(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)

def simple_reverb(sig, rt60=0.4, mix=0.25):
    """Schroeder-ish reverb: comb + allpass via delays."""
    delay_s = [0.0297, 0.0371, 0.0411, 0.0437]
    out = sig.copy().astype(np.float64)
    g = 0.84
    for d in delay_s:
        dly = int(d * SR)
        buf = np.zeros(len(sig) + dly, np.float64)
        buf[:len(sig)] += sig
        for i in range(dly, len(buf)):
            buf[i] += g * buf[i - dly]
        out += buf[:len(sig)] * 0.3
    # allpass
    ap = int(0.005 * SR)
    result = np.zeros_like(out)
    fb = 0.7
    for i in range(len(out)):
        delayed = result[i - ap] if i >= ap else 0
        result[i] = -fb * out[i] + delayed + fb * result[i - ap] if i >= ap else out[i]
    dry = sig.astype(np.float64)
    wet = result[:len(sig)]
    out = dry * (1 - mix) + wet * mix
    np.clip(out, -4.0, 4.0, out=out)   # prevent overflow
    return out.astype(np.float32)

# ============================================================
# DRUM SYNTHESIS
# ============================================================

def make_kick(dur=0.55):
    """Hardstyle kick: heavy pitch sweep 240->42 Hz, dist, click."""
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    # Pitch envelope: fast exponential sweep
    f0, f1 = 240.0, 42.0
    tau = 0.045
    freq = f1 + (f0 - f1) * np.exp(-t / tau)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase)
    # Amplitude envelope
    amp_env = np.exp(-t * 6.5) * 1.0 + np.exp(-t * 2.0) * 0.4
    # Click transient (1ms of noise)
    click = np.zeros(n, np.float32)
    click_len = int(0.003 * SR)
    click[:click_len] = rng.standard_normal(click_len) * 0.9 * np.linspace(1, 0, click_len)
    # Combine + saturate
    sig = (body * amp_env + click).astype(np.float32)
    sig = softclip(sig, drive=3.5)
    sig = sig * (0.95 / np.max(np.abs(sig) + 1e-9))
    return sig

def make_snare(dur=0.22):
    """Punchy snare: tonal body + noise burst."""
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    # Tonal part: 200Hz pitch drop
    freq = 200 * np.exp(-t * 18) + 100
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(phase) * np.exp(-t * 28) * 0.55
    # Noise burst
    noise = rng.standard_normal(n).astype(np.float32) * np.exp(-t * 22) * 0.65
    # Extra snap
    snap = np.zeros(n, np.float32)
    snap[:int(0.004 * SR)] = rng.standard_normal(int(0.004 * SR)) * np.linspace(1, 0, int(0.004 * SR))
    sig = (tone + noise + snap * 0.4).astype(np.float32)
    return sig * 0.85

def make_hat_closed(dur=0.04, amp=0.18):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n).astype(np.float32)
    # High-pass style: emphasize high freqs with harmonics
    for k in [2, 3, 5, 7, 11, 13]:
        noise += 0.15 * np.sin(2 * np.pi * k * 3000 * t)
    env = np.exp(-t * 120)
    return amp * env * noise

def make_hat_open(dur=0.18, amp=0.14):
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n).astype(np.float32)
    env = np.exp(-t * 18)
    return amp * env * noise

# ============================================================
# MELODIC SYNTHESIS
# ============================================================

def supersaw_stereo(freq, dur, amp=0.14, detune=0.005, voices=5):
    """5-oscillator supersaw — smoothed, fewer harmonics to reduce buzz."""
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    sl = np.zeros(n, np.float64)
    sr = np.zeros(n, np.float64)
    offsets = np.linspace(-detune, detune, voices)
    for i, d in enumerate(offsets):
        f = freq * (1 + d)
        ph = 2 * np.pi * f * t
        osc = np.zeros(n, np.float64)
        # Only 4 harmonics — keeps it warm not buzzy
        for k in range(1, 5):
            osc += ((-1) ** (k + 1)) / k * np.sin(k * ph)
        osc *= (2 / np.pi)
        # Smooth with light low-pass via running average
        from numpy import convolve
        kernel_len = int(SR / (freq * 6)) + 1
        if kernel_len > 1:
            kernel = np.ones(kernel_len) / kernel_len
            osc = np.convolve(osc, kernel, mode='same')
        pan = i / (voices - 1)
        sl += osc * (1 - pan * 0.4)
        sr += osc * (0.6 + pan * 0.4)
    sl = (sl * amp / voices).astype(np.float32)
    sr = (sr * amp / voices).astype(np.float32)
    return sl, sr

def distbass(midi, dur, amp=0.45, drive=1.8):
    """Sub-bass: clean sine with mild saturation — punchy not buzzy."""
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    f = hz(midi)
    sub  = np.sin(2 * np.pi * f * t)
    # Just a touch of second harmonic for body
    sig = (sub * 0.88 + np.sin(4 * np.pi * f * t) * 0.12).astype(np.float32)
    sig = softclip(sig, drive=drive)
    e = env_ar(n, a=0.008, r=0.10)
    return sig * e * amp

def pluck(midi, dur, amp=0.3):
    """Plucky synth: karplus-strong inspired."""
    n = int(dur * SR)
    f = hz(midi)
    # Simple decaying sine + harmonics with fast envelope
    t = np.linspace(0, dur, n, endpoint=False)
    sig = np.zeros(n, np.float32)
    for k, a in [(1, 1.0), (2, 0.4), (3, 0.2), (4, 0.08)]:
        sig += a * np.sin(2 * np.pi * f * k * t).astype(np.float32)
    e = np.exp(-t * (8 + f * 0.008)).astype(np.float32)
    return sig * e * amp

def pad(midi_notes, dur, amp=0.10):
    """Lush pad: detuned saws with slow attack."""
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    sig = np.zeros(n, np.float32)
    for m in midi_notes:
        for d in [-0.003, 0, 0.003]:
            f = hz(m) * (1 + d)
            ph = 2 * np.pi * f * t
            for k in range(1, 6):
                sig += (amp * 0.2 / k) * np.sin(k * ph).astype(np.float32)
    # Slow attack + long release
    ai = int(0.15 * SR); ri = int(0.3 * SR)
    e = np.ones(n, np.float32)
    if ai < n: e[:ai] = np.linspace(0, 1, ai)
    if ri < n: e[-ri:] = np.linspace(1, 0, ri)
    return sig * e

# ============================================================
# SIDECHAIN: duck on every kick hit
# ============================================================
KICK_TIMES = []   # populated when placing kicks

def build_sidechain(kick_times, total_n, attack=0.003, release=0.18):
    """Gain envelope: dips to 0 on kick, recovers over release_s."""
    env = np.ones(total_n, np.float32)
    a = int(attack * SR); r = int(release * SR)
    for t in kick_times:
        s = int(t * SR)
        if s >= total_n: continue
        dip = min(total_n - s, a + r)
        ramp_d = min(a, dip)
        ramp_r = min(r, dip - ramp_d)
        env[s:s + ramp_d] = np.linspace(1, 0.08, ramp_d)
        if ramp_r > 0:
            env[s + ramp_d:s + ramp_d + ramp_r] = np.linspace(0.08, 1, ramp_r)
    return env

# ============================================================
# DRUM PATTERNS  (174 BPM, 16th-note grid)
# Euclidean patterns from MCP theory.rhythm:
#   kick:  4/16  -> x...x...x...x...
#   snare: 2/16  -> ....x.......x...
#   hat-c: 7/16  -> x.x.x..x.x.x.x..
#   hat-o: 3/16  -> x....x....x.....
#   perc:  5/16  -> x..x..x..x..x...  (on off-beats)
# Drop gets harder kick: 5/16 pattern
# ============================================================

KICK4  = "x...x...x...x..."
KICK5  = "x...x..x...x..x."   # hardstyle rolling
SNARE  = "....x.......x..."
HATC   = "x.x.x.x.x.x.x.x."  # 8ths
HATO   = "x....x....x....."
PERC5  = "x..x..x..x..x..."   # 5/16 euclidean from MCP

def add_drums(bars_start, num_bars, kick_pat, snare_pat, hat_c, hat_o,
              perc_pat=None, kick_amp=1.0, snare_amp=1.0, hat_amp=1.0):
    kick_sig  = make_kick()
    snare_sig = make_snare()
    for b in range(num_bars):
        t0 = bars_start + b * BAR
        for i, ch in enumerate(kick_pat[:16]):
            if ch == 'x':
                t = t0 + i * STEP
                KICK_TIMES.append(t)
                place(L, kick_sig * kick_amp, t)
                place(R, kick_sig * kick_amp, t)
        for i, ch in enumerate(snare_pat[:16]):
            if ch == 'x':
                t = t0 + i * STEP
                s = snare_sig * snare_amp
                # slight reverb on snare
                s_rev = simple_reverb(s, rt60=0.3, mix=0.35)
                place(L, s_rev, t)
                place(R, s_rev, t)
        for i, ch in enumerate(hat_c[:16]):
            if ch == 'x':
                t = t0 + i * STEP
                amp = 0.20 if i % 4 == 0 else 0.13
                hc = make_hat_closed(amp=amp * hat_amp)
                place(L, hc * 0.7, t)
                place(R, hc * 0.7, t)
        for i, ch in enumerate(hat_o[:16]):
            if ch == 'x':
                t = t0 + i * STEP
                ho = make_hat_open(amp=0.14 * hat_amp)
                place(L, ho * 0.6, t)
                place(R, ho * 0.6, t)
        if perc_pat:
            for i, ch in enumerate(perc_pat[:16]):
                if ch == 'x':
                    t = t0 + i * STEP
                    pc = make_hat_closed(dur=0.025, amp=0.09 * hat_amp)
                    place(L, pc, t + 0.01)  # micro-offset for texture
                    place(R, pc, t - 0.01)

# Intro: light hats + build atmosphere
add_drums(INTRO,  4, KICK4, "................", HATC, "................", hat_amp=0.55)
# Build: full kick + hats, no snare yet
add_drums(BUILD,  4, KICK4, "................", HATC, HATO, hat_amp=0.8, kick_amp=0.85)
# Drop 1: FULL — rolling hardstyle kick, snare, hats, percussion
add_drums(DROP1,  8, KICK5, SNARE, HATC, HATO, PERC5, kick_amp=1.0, snare_amp=1.0, hat_amp=1.0)
# Break: just kick and hat ghost notes
add_drums(BREAK,  4, KICK4, "................", "....x.......x...", "................", hat_amp=0.4, kick_amp=0.7)
# Build 2: rolling kick, escalating
add_drums(BUILD2, 4, KICK5, "................", HATC, HATO, hat_amp=0.9, kick_amp=0.95)
# Drop 2: same but louder
add_drums(DROP2,  8, KICK5, SNARE, HATC, HATO, PERC5, kick_amp=1.05, snare_amp=1.05, hat_amp=1.05)
# Outro: kick + hat decay
add_drums(OUTRO,  4, KICK4, "....x....x....x.", "x...x...x...x...", "................", kick_amp=0.7, hat_amp=0.6)

# ============================================================
# BASS LINE  (D minor: D2=38, F2=41, A2=45, C3=48, D3=50)
# Pattern: root-based groove from MCP bassline sequence (transposed -24)
# ============================================================
# MCP sequence (transposed down 2 octaves to bass register):
BASS_LINE = [
    # (bar_frac, midi, dur_beats)
    (0.00, 38, 0.75), (0.25, 38, 0.25), (0.50, 41, 0.5),  (0.75, 45, 0.5),
    (1.00, 38, 0.75), (1.25, 40, 0.25), (1.50, 41, 0.5),  (1.75, 43, 0.5),
    (2.00, 38, 0.75), (2.25, 38, 0.25), (2.50, 45, 0.5),  (2.75, 48, 0.5),
    (3.00, 38, 0.75), (3.25, 36, 0.25), (3.50, 38, 0.5),  (3.75, 41, 0.5),
]

def add_bass(start, num_bars, amp=0.55, drive=4.0):
    for b in range(num_bars):
        t0 = start + b * BAR
        for (frac, midi, dur_b) in BASS_LINE:
            t   = t0 + frac * BEAT
            dur = dur_b * BEAT + 0.03
            sig = distbass(midi, dur, amp=amp, drive=drive)
            place(L, sig, t)
            place(R, sig, t)

add_bass(DROP1,  8, amp=0.42, drive=1.6)
add_bass(DROP2,  8, amp=0.48, drive=2.0)
add_bass(BUILD2, 4, amp=0.32, drive=1.4)

# ============================================================
# SUPERSAW LEAD (D minor: D4=62, F4=65, A4=69, C5=72, D5=74)
# Sequence from MCP generate_sequence + humanize, mapped to D minor
# ============================================================
# MCP melodic sequence (32 notes), remapped to D minor pitches
DMIN_MAP = {62:62, 64:64, 66:65, 67:67, 69:69, 71:70, 73:72, 74:74, 71:70}

LEAD_SEQ = [
    # 2 bars of lead motif, repeated
    (0, 74, 0.5), (1, 72, 0.5), (2, 69, 0.5), (3, 67, 0.5),
    (4, 65, 0.5), (5, 67, 0.5), (6, 69, 0.5), (7, 72, 0.5),
    (8, 74, 1.0),               (10,72, 0.5), (11,69, 0.5),
    (12,72, 0.5),(13,74, 0.5), (14,76, 0.5), (15,77, 0.5),
    # bar 3-4 variation
    (16,79, 1.0),               (18,77, 0.5), (19,76, 0.5),
    (20,74, 0.5),(21,72, 0.5), (22,69, 0.5), (23,67, 0.5),
    (24,65, 0.5),(25,67, 0.5), (26,69, 0.5), (27,72, 0.5),
    (28,74, 0.5),(29,72, 0.5), (30,69, 1.0),
]

def add_lead(start, num_bars, amp=0.32):
    steps_per_bar = 16
    for b in range(num_bars):
        t0 = start + b * BAR
        for (step, midi, dur_beats) in LEAD_SEQ:
            bar_off = step // steps_per_bar
            if bar_off != (b % (num_bars)):
                continue
            if bar_off >= num_bars: break
            at  = t0 + (step % steps_per_bar) * STEP
            dur = dur_beats * STEP
            sl, sr = supersaw_stereo(hz(midi), dur + 0.06, amp=amp, detune=0.007)
            e = env_ar(len(sl), a=0.006, r=0.05)
            # reverb on lead
            sl_r = simple_reverb(sl * e, rt60=0.35, mix=0.22)
            sr_r = simple_reverb(sr * e, rt60=0.35, mix=0.22)
            place(L, sl_r, at)
            place(R, sr_r, at)

add_lead(DROP1, 8,  amp=0.13)
add_lead(DROP2, 8,  amp=0.16)

# ============================================================
# CHORDS / PAD  (D minor: i-VI-III-VII)
# D min, Bb maj, F maj, C maj
# ============================================================
CHORD_PROG = [
    ([62, 65, 69], 2 * BAR),   # Dm
    ([58, 62, 65], 2 * BAR),   # Bb
    ([53, 57, 60], 2 * BAR),   # F
    ([60, 64, 67], 2 * BAR),   # C
]

def add_pads(start, chord_list, amp=0.09):
    t0 = start
    for (notes, dur) in chord_list:
        sig_l = pad(notes, dur, amp=amp)
        sig_r = pad([n + 12 for n in notes], dur, amp=amp * 0.5)
        rv_l = simple_reverb(sig_l, rt60=0.4, mix=0.22)
        rv_r = simple_reverb(sig_r, rt60=0.4, mix=0.22)
        place(L, rv_l, t0)
        place(R, rv_r, t0)
        t0 += dur

add_pads(INTRO,  CHORD_PROG, amp=0.055)
add_pads(BUILD,  CHORD_PROG, amp=0.065)
add_pads(BREAK,  CHORD_PROG, amp=0.060)
add_pads(OUTRO,  CHORD_PROG, amp=0.040)

# ============================================================
# PLUCK ARP  (from MCP arpeggiate result: D4 F#4 A4 pattern)
# Use during break/build
# ============================================================
PLUCK_PITCHES = [62, 65, 69, 74, 72, 69, 65, 62,
                 65, 69, 74, 77, 76, 74, 72, 69]

def add_plucks(start, num_bars, amp=0.22):
    for b in range(num_bars):
        t0 = start + b * BAR
        for i, midi in enumerate(PLUCK_PITCHES):
            t = t0 + i * STEP
            sig = pluck(midi, STEP * 0.9, amp=amp)
            rv  = simple_reverb(sig, rt60=0.25, mix=0.3)
            place(L, rv, t)
            place(R, rv, t + 0.003)   # tiny stereo delay

add_plucks(INTRO,  4, amp=0.18)
add_plucks(BUILD,  4, amp=0.22)
add_plucks(BREAK,  4, amp=0.20)
add_plucks(BUILD2, 4, amp=0.25)
add_plucks(OUTRO,  4, amp=0.14)

# ============================================================
# RISER / SWEEP
# ============================================================
def add_riser(start_s, dur_s, f0=60, f1=4000, amp=0.12):
    n = int(dur_s * SR)
    t = np.linspace(0, dur_s, n, endpoint=False)
    freqs = f0 * (f1 / f0) ** (t / dur_s)   # exponential sweep
    phase = 2 * np.pi * np.cumsum(freqs) / SR
    noise = rng.standard_normal(n).astype(np.float32) * 0.3
    tone  = np.sin(phase).astype(np.float32)
    env   = (t / dur_s) ** 2
    sig   = ((tone + noise) * env * amp).astype(np.float32)
    place(L, sig, start_s)
    place(R, sig, start_s)

add_riser(BUILD, 4 * BAR, f0=55, f1=6000, amp=0.14)
add_riser(BUILD2, 4 * BAR, f0=40, f1=8000, amp=0.16)

# ============================================================
# SIDECHAIN PUMPING  (apply to L+R after all elements placed)
# ============================================================
sc = build_sidechain(KICK_TIMES, N, attack=0.003, release=0.20)
# Apply sidechain only during drops (not to the kick itself)
# We do a simplified approach: multiply the whole mix by sidechain
# (this is how hardware sidechain works in live context)
L *= sc
R *= sc

# ============================================================
# OUTRO FADE
# ============================================================
fade_s = int(OUTRO * SR)
fade_e = int(END * SR)
fade_n = fade_e - fade_s
if fade_n > 0:
    fenv = np.linspace(1, 0, fade_n, dtype=np.float32)
    L[fade_s:fade_e] *= fenv
    R[fade_s:fade_e] *= fenv

# ============================================================
# MIX & EXPORT
# ============================================================
# Normalize channels before interleaving
peak = max(np.max(np.abs(L)), np.max(np.abs(R)), 1e-9)
L = L * (0.88 / peak)
R = R * (0.88 / peak)

# Interleave L+R
stereo = np.empty(N * 2, np.float64)
stereo[0::2] = L
stereo[1::2] = R

out_dir = os.path.dirname(os.path.abspath(__file__))
wav_path = os.path.join(out_dir, "eclipse.wav")
mp3_path = os.path.join(out_dir, "eclipse.mp3")

# Write stereo WAV
s16 = (stereo * 32767).astype(np.int16)
with wave.open(wav_path, 'w') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(s16.tobytes())

kb = os.path.getsize(wav_path) // 1024
dur = N / SR
print(f"WAV: {wav_path}  ({kb} KB, {dur:.1f}s, {BPM}BPM, D minor, stereo)")

try:
    from pydub import AudioSegment
    seg = AudioSegment.from_wav(wav_path)
    seg.export(mp3_path, format="mp3", bitrate="256k",
               tags={"title": "Eclipse", "artist": "BespokeSynth MCP",
                     "genre": "Rawstyle/Hardstyle", "bpm": "174"})
    kb2 = os.path.getsize(mp3_path) // 1024
    print(f"MP3: {mp3_path}  ({kb2} KB)")
except ImportError:
    print("pydub not installed -- WAV only. pip install pydub")
