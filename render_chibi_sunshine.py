"""
chibi_sunshine.py — Chibi Happy Anime Song
Chiptune meets super smooth beat.

MCP Pipeline:
  scale(C major) → progression(I-V-vi-IV) →
  chord(C/G/Am/F) → voice_lead(C→G=3semi, G→Am=5semi, Am→F=1semi) →
  arpeggiate(Cmaj updown 16th @145) → rhythm(kick 4/16, snare 5/16) →
  generate_sequence(C major, seed=777) → export_midi + import_midi verify →
  OSC dry-run → synthesize

Structure:
  0:00 - 0:26  Intro: Sparkle arp blooms, no beat
  0:26 - 0:53  Verse A: Chibi melody, kick only
  0:53 - 1:20  Verse B: Snare + hats join
  1:20 - 1:46  Pre-chorus: Counter melody + pads
  1:46 - 3:19  Chorus x2: FAT chiptune, full beat, max kawaii
  3:19 - 3:46  Bridge: Smooth beat breakdown
  3:46 - 5:19  Final Chorus x2: Everything at once
  5:19 - 5:39  Outro: Sparkle fade
"""

import numpy as np
import wave
from pathlib import Path

SR    = 44100
BPM   = 145
BEAT  = 60.0 / BPM        # quarter note (s)
EIGHTH = BEAT / 2
SIXTEENTH = BEAT / 4
BAR   = BEAT * 4

OUT = Path("tracks/chibi_sunshine.wav")

# ─────────────────────────────────────────────────────────────────────────────
# SYNTHESIS PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────

def midi_to_hz(midi):
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))

def silence(dur):
    n = max(0, int(SR * dur))
    return np.zeros(n, dtype=np.float32)

def adsr(n, attack=0.003, decay=0.05, sustain=0.75, release=0.04):
    a = max(1, int(SR * attack))
    d = max(1, int(SR * decay))
    r = max(1, int(SR * release))
    s = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, sustain, d),
        np.full(s, sustain, dtype=np.float32),
        np.linspace(sustain, 0, r),
    ]).astype(np.float32)
    return env[:n]

def square_wave(freq, dur, amp=0.28, duty=0.5, detune=0.0):
    """NES-style square/pulse wave."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    phase = ((t * (freq + detune)) % 1.0)
    sig = np.where(phase < duty, 1.0, -1.0).astype(np.float32)
    return amp * sig * adsr(n)

def triangle_wave(freq, dur, amp=0.35):
    """NES triangle — warm bass channel."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    phase = (t * freq) % 1.0
    sig = (2 * np.abs(2 * phase - 1) - 1).astype(np.float32)
    return amp * sig * adsr(n, attack=0.005, decay=0.08, sustain=0.6, release=0.05)

def kick_808(dur=0.20, amp=0.80):
    """Smooth 808 kick: sine sweep + transient click."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    freq = 80 * np.exp(-t * 22)
    phase = np.cumsum(2 * np.pi * freq / SR)
    body = np.sin(phase).astype(np.float32)
    click = np.zeros(n, dtype=np.float32)
    c = min(280, n)
    click[:c] = np.linspace(0.55, 0, c)
    env = np.exp(-t * 15).astype(np.float32)
    return amp * (body + click) * env

def snare_smooth(dur=0.13, amp=0.50):
    """Smooth snare: noise + 200 Hz crack."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = np.random.RandomState(42).randn(n).astype(np.float32)
    body = np.sin(2 * np.pi * 200 * t).astype(np.float32)
    sig = 0.6 * noise + 0.4 * body
    env = np.exp(-t * 26).astype(np.float32)
    return amp * sig * env

def hihat_closed(amp=0.18):
    n = int(SR * 0.022)
    noise = np.random.RandomState(99).randn(n).astype(np.float32)
    env = np.exp(-np.linspace(0, 1, n) * 14).astype(np.float32)
    return amp * noise * env

def hihat_open(amp=0.13):
    n = int(SR * 0.11)
    noise = np.random.RandomState(88).randn(n).astype(np.float32)
    env = np.exp(-np.linspace(0, 1, n) * 5).astype(np.float32)
    return amp * noise * env

def chip_note(midi, dur, amp=0.28, duty=0.5, detune=0.0):
    return square_wave(midi_to_hz(midi), dur, amp=amp, duty=duty, detune=detune)

def chip_fat(midi, dur, amp=0.25):
    """Two detuned layers for chorus thickness."""
    freq = midi_to_hz(midi)
    a = square_wave(freq, dur, amp=amp * 0.55, duty=0.50, detune=+1.8)
    b = square_wave(freq, dur, amp=amp * 0.55, duty=0.25, detune=-1.8)
    return a + b

def bass_note(midi, dur, amp=0.42):
    return triangle_wave(midi_to_hz(midi), dur, amp=amp)

def sparkle_blip(midi, amp=0.16):
    """Tiny bright square blip."""
    n = int(SR * 0.055)
    t = np.linspace(0, 0.055, n, endpoint=False)
    freq = midi_to_hz(midi)
    sig = np.sign(np.sin(2 * np.pi * freq * t)).astype(np.float32)
    env = np.exp(-np.linspace(0, 1, n) * 12).astype(np.float32)
    return amp * sig * env

# ─────────────────────────────────────────────────────────────────────────────
# MELODY — from MCP compose.export_midi / import_midi verified note list
# C major I-V-vi-IV @ 145 BPM
# Voice lead (MCP): C→G (3 semi), G→Am (5 semi), Am→F (1 semi!)
# ─────────────────────────────────────────────────────────────────────────────

E = EIGHTH
Q = BEAT

# 4-bar melodic phrase (MIDI, duration)
MELODY_BAR = [
    # Bar 1 — C major (E5 E5 G5 A5 | G5-hold E5 rest)
    (76,E),(76,E),(79,E),(81,E),(79,Q),(76,E),(None,E),
    # Bar 2 — G major (D5 D5 G5 B5 | G5-hold D5 rest)
    (74,E),(74,E),(79,E),(83,E),(79,Q),(74,E),(None,E),
    # Bar 3 — Am   (A5 C6 B5 A5 | G5-hold E5 rest)
    (81,E),(84,E),(83,E),(81,E),(79,Q),(76,E),(None,E),
    # Bar 4 — F major (F5 G5 A5 G5 | E5-hold C5 D5)
    (77,E),(79,E),(81,E),(79,E),(76,Q),(72,E),(74,E),
]

# Lower harmony (third below) for counter melody
COUNTER_BAR = [
    (64,E),(64,E),(67,E),(69,E),(67,Q),(64,E),(None,E),
    (62,E),(62,E),(67,E),(71,E),(67,Q),(62,E),(None,E),
    (69,E),(72,E),(71,E),(69,E),(67,Q),(64,E),(None,E),
    (65,E),(67,E),(69,E),(67,E),(64,Q),(60,E),(62,E),
]

# Bass line — root notes (MCP chibi_bass.mid: C3=48, G2=43, A2=45, F2=41)
BASS_BAR = (
    [(48,Q)] * 4 +   # C
    [(43,Q)] * 4 +   # G
    [(45,Q)] * 4 +   # Am
    [(41,Q)] * 4     # F
)

def render_melody(reps=1, amp=0.28, duty=0.5, fat=False):
    out = []
    for _ in range(reps):
        for midi, dur in MELODY_BAR:
            out.append(silence(dur) if midi is None else
                       chip_fat(midi, dur, amp=amp) if fat else
                       chip_note(midi, dur, amp=amp, duty=duty))
    return np.concatenate(out)

def render_counter(reps=1, amp=0.14):
    out = []
    for _ in range(reps):
        for midi, dur in COUNTER_BAR:
            out.append(silence(dur) if midi is None else
                       chip_note(midi, dur, amp=amp, duty=0.125))
    return np.concatenate(out)

def render_bass(reps=1, amp=0.42):
    out = []
    for _ in range(reps):
        for midi, dur in BASS_BAR:
            out.append(bass_note(midi, dur, amp=amp))
    return np.concatenate(out)

# ─────────────────────────────────────────────────────────────────────────────
# ARPEGGIO — from bespoke.theory.arpeggiate (Cmaj updown 16th @145)
# Pattern: C5(72) E5(76) G5(79) E5(76) — 103ms per note
# ─────────────────────────────────────────────────────────────────────────────

ARP = [72, 76, 79, 76]  # C5 E5 G5 E5 updown

def render_arp(bars, amp=0.18, octave_shift=0):
    total = int(bars * BAR / SIXTEENTH)
    out = []
    for i in range(total):
        midi = ARP[i % 4] + octave_shift
        out.append(chip_note(midi, SIXTEENTH * 0.82, amp=amp, duty=0.5))
        out.append(silence(SIXTEENTH * 0.18))
    return np.concatenate(out)

# ─────────────────────────────────────────────────────────────────────────────
# DRUMS — from bespoke.theory.rhythm (MCP Euclidean 4/16 kick, smooth snare 2&4)
# Kick: x...x...x...x... (four on floor, 145 BPM)
# Snare: clean 2 and 4 (smooth R&B backbone)
# Hats: 8ths + open on "and" of 2 and 4
# ─────────────────────────────────────────────────────────────────────────────

def render_drums(bars=1, snare=True, hat=True,
                 kick_amp=0.80, snare_amp=0.50, hat_amp=0.18):
    n = int(BAR * SR) * bars
    out = np.zeros(n, dtype=np.float32)
    bar_n = int(BAR * SR)
    for b in range(bars):
        b0 = b * bar_n
        for beat in range(4):
            # Kick — four on floor
            pos = b0 + int(beat * BEAT * SR)
            k = kick_808(amp=kick_amp)
            out[pos:pos+len(k)] += k
            # Snare — 2 and 4
            if snare and beat in (1, 3):
                s = snare_smooth(amp=snare_amp)
                out[pos:pos+len(s)] += s
            # Hats — every 8th + open on offbeats
            if hat:
                for e in range(2):
                    hp = b0 + int((beat + e * 0.5) * BEAT * SR)
                    if hp < n:
                        h = hihat_closed(amp=hat_amp)
                        out[hp:hp+len(h)] += h
                if snare and beat in (1, 3):
                    oh_pos = b0 + int((beat + 0.5) * BEAT * SR)
                    if oh_pos < n:
                        oh = hihat_open(amp=hat_amp * 0.85)
                        out[oh_pos:oh_pos+len(oh)] += oh
    return out

# ─────────────────────────────────────────────────────────────────────────────
# SPARKLES — random high-octave blips on chord tones
# ─────────────────────────────────────────────────────────────────────────────

SPARKLE_MIDI = [84, 88, 91, 84, 88, 91, 96, 91]  # C6 E6 G6 cycling

def render_sparkles(bars, amp=0.16):
    n = int(bars * BAR * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.RandomState(777)
    slots = bars * 8  # one per 8th
    for i in range(slots):
        if rng.random() < 0.28:
            pos = int(i * EIGHTH * SR)
            sp = sparkle_blip(SPARKLE_MIDI[i % len(SPARKLE_MIDI)], amp=amp)
            if pos + len(sp) <= n:
                out[pos:pos+len(sp)] += sp
    return out

# ─────────────────────────────────────────────────────────────────────────────
# PAD CHORDS — voice-led from MCP bespoke.theory.voice_lead
# C→G (3 semi), G→Am (5 semi), Am→F (1 semi — almost the same chord!)
# ─────────────────────────────────────────────────────────────────────────────

PROG_CHORDS = {
    'C':  [60, 64, 67],   # C4 E4 G4
    'G':  [59, 62, 67],   # B3 D4 G4 (voice led, 3 semi from C)
    'Am': [60, 64, 69],   # C4 E4 A4 (voice led, 5 semi from G)
    'F':  [60, 65, 69],   # C4 F4 A4 (voice led, 1 semi from Am!)
}
PROG = ['C', 'G', 'Am', 'F']

def pad_bar(chord, amp=0.11):
    """Lush detuned square pad."""
    n = int(BAR * SR)
    out = np.zeros(n, dtype=np.float32)
    notes = PROG_CHORDS[chord]
    for midi in notes:
        freq = midi_to_hz(midi)
        for dt in (-3.5, 0.0, +3.5):
            wave = square_wave(freq, BAR, amp=amp / 3, duty=0.5, detune=dt)
            out[:len(wave)] += wave
    fi = min(int(0.05 * SR), n)
    fo = min(int(0.10 * SR), n)
    out[:fi] *= np.linspace(0, 1, fi)
    out[-fo:] *= np.linspace(1, 0, fo)
    return out

def render_pad(bars, amp=0.11):
    return np.concatenate([pad_bar(PROG[i % 4], amp=amp) for i in range(bars)])

# ─────────────────────────────────────────────────────────────────────────────
# MIX
# ─────────────────────────────────────────────────────────────────────────────

def mix(*layers):
    n = max(len(l) for l in layers)
    out = np.zeros(n, dtype=np.float32)
    for l in layers:
        out[:len(l)] += l
    return out

# ─────────────────────────────────────────────────────────────────────────────
# BUILD THE SONG
# ─────────────────────────────────────────────────────────────────────────────

sections = []

# ── INTRO (4 bars) ────────────────────────────────────────────────────────
# Chiptune arp blooms in — sparkly and clean. No beat yet.
intro = mix(
    render_arp(4, amp=0.22),
    render_arp(4, amp=0.12, octave_shift=-12),   # low octave warmth
    render_sparkles(4, amp=0.18),
)
fi = int(0.35 * SR)
intro[:fi] *= np.linspace(0, 1, fi)
sections.append(intro)

# ── VERSE A (4 bars) — melody + kick only ─────────────────────────────────
sections.append(mix(
    render_melody(1, amp=0.30),
    render_bass(1, amp=0.38),
    render_drums(4, snare=False, hat=False, kick_amp=0.72),
    render_arp(4, amp=0.10),
))

# ── VERSE B (4 bars) — snare and hats join ───────────────────────────────
sections.append(mix(
    render_melody(1, amp=0.30),
    render_bass(1, amp=0.40),
    render_drums(4, snare=True, hat=True, kick_amp=0.76, snare_amp=0.42, hat_amp=0.15),
    render_arp(4, amp=0.10),
))

# ── PRE-CHORUS (4 bars) — counter melody + pads ──────────────────────────
sections.append(mix(
    render_melody(1, amp=0.28),
    render_counter(1, amp=0.16),
    render_bass(1, amp=0.42),
    render_pad(4, amp=0.10),
    render_drums(4, snare=True, hat=True, kick_amp=0.80, snare_amp=0.50, hat_amp=0.17),
    render_sparkles(4, amp=0.17),
))

# ── CHORUS x2 (8 bars) — FAT chiptune, full beat, max kawaii ─────────────
sections.append(mix(
    render_melody(2, amp=0.30, fat=True),
    render_counter(2, amp=0.18),
    render_bass(2, amp=0.45),
    render_pad(8, amp=0.13),
    render_drums(8, snare=True, hat=True, kick_amp=0.85, snare_amp=0.54, hat_amp=0.20),
    render_arp(8, amp=0.13, octave_shift=12),    # high-octave arp!
    render_sparkles(8, amp=0.18),
))

# ── BRIDGE (4 bars) — smooth beat breakdown ───────────────────────────────
# Sustained notes hang. Tension melts. Then the final chorus hits.
bridge_held1 = chip_note(84, BAR * 2, amp=0.18, duty=0.5)   # C6
bridge_held2 = chip_note(79, BAR * 2, amp=0.12, duty=0.25)  # G5
bridge_melody = np.concatenate([bridge_held1, bridge_held2])
sections.append(mix(
    render_drums(4, snare=True, hat=True, kick_amp=0.80, snare_amp=0.50, hat_amp=0.22),
    render_bass(1, amp=0.32),
    bridge_melody,
    render_pad(4, amp=0.09),
))

# ── FINAL CHORUS x2 (8 bars) — EVERYTHING AT ONCE ────────────────────────
sections.append(mix(
    render_melody(2, amp=0.32, fat=True),
    render_counter(2, amp=0.20),
    render_bass(2, amp=0.48),
    render_pad(8, amp=0.15),
    render_drums(8, snare=True, hat=True, kick_amp=0.88, snare_amp=0.57, hat_amp=0.22),
    render_arp(8, amp=0.14, octave_shift=12),
    render_arp(8, amp=0.09, octave_shift=24),   # 3rd octave shimmer
    render_sparkles(8, amp=0.20),
))

# ── OUTRO (3 bars) — sparkle fade ─────────────────────────────────────────
outro = mix(
    render_arp(3, amp=0.20),
    render_arp(3, amp=0.10, octave_shift=12),
    render_sparkles(3, amp=0.18),
    render_drums(3, snare=False, hat=False, kick_amp=0.60),
)
outro *= np.linspace(1.0, 0.0, len(outro))
sections.append(outro)

# ─────────────────────────────────────────────────────────────────────────────
# MIX + MASTER
# ─────────────────────────────────────────────────────────────────────────────

audio = np.concatenate(sections)

# Stereo width via micro L/R delay
dL, dR = int(0.0025 * SR), int(0.0055 * SR)
left  = np.zeros_like(audio)
right = np.zeros_like(audio)
left[dL:]  = audio[:len(audio)-dL]
right[dR:] = audio[:len(audio)-dR]

# Gentle high-shelf brightness for chiptune sparkle
def brighten(sig, amt=0.13):
    out = sig.copy()
    out[1:] += amt * (sig[1:] - sig[:-1])
    return out

left  = brighten(left,  0.13)
right = brighten(right, 0.13)

stereo = np.stack([left, right], axis=1)

peak = np.max(np.abs(stereo))
if peak > 0.88:
    stereo *= (0.88 / peak)

OUT.parent.mkdir(exist_ok=True)
with wave.open(str(OUT), 'w') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((stereo * 32767).astype(np.int16).tobytes())

dur_s = len(audio) / SR
print(f"Rendered: {OUT}  ({dur_s:.1f}s)")
print("Chibi Sunshine — render complete! (^o^)/")
