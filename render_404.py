"""
404: Melody Not Found
A dial-up modem attempts Fur Elise. It does not succeed.

Structure:
  0:00 - 0:08  False Confidence: clean robotic Fur Elise opening
  0:08 - 0:12  First Corruption: 5th note holds forever, packet drop silence
  0:12 - 0:20  Dial-up Handshake: modem chirp tones interrupt
  0:20 - 0:36  Tempo Disintegration: melody accelerates into smear, hard stop
  0:36 - 0:40  Reboot: 56k screech + Windows XP chord
  0:40 - 1:10  Worse: wrong key, confident, bit-flip glitches throughout
"""

import numpy as np
import struct, wave, sys
from pathlib import Path

SR = 44100
OUT = Path("tracks/404_melody_not_found.wav")

def sine(freq, dur, amp=0.4, phase=0.0):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return amp * np.sin(2 * np.pi * freq * t + phase).astype(np.float32)

def silence(dur):
    return np.zeros(int(SR * dur), dtype=np.float32)

def midi_to_hz(midi):
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))

# Fur Elise melody: A4, G#4, A4, G#4, A4, E4, D5, C5, A4...
# MIDI: 69, 68, 69, 68, 69, 64, 74, 72, 69
FUR_ELISE = [69, 68, 69, 68, 69, 64, 74, 72, 69]
FUR_ELISE_WRONG = [71, 70, 71, 70, 71, 66, 76, 74, 71]  # shifted up 2 semitones (wrong key)

def note(midi, dur, amp=0.35, detune=0.0):
    """Mechanical sine note — zero vibrato, square envelope (uncanny)."""
    freq = midi_to_hz(midi) + detune
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    # Hard rectangular envelope: instant on, instant off — robotic
    env = np.ones(n, dtype=np.float32)
    env[:100] = np.linspace(0, 1, 100)   # tiny 2ms click prevention
    env[-100:] = np.linspace(1, 0, 100)
    return (amp * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)

def modem_chirp(dur=0.4):
    """Classic dial-up modem handshake burst: rapid freq sweeps 300→3400Hz."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    # Alternating fast sweeps between 300 and 3400 Hz
    chirp_rate = 1200  # sweeps per second
    phase_acc = 0.0
    out = np.zeros(n, dtype=np.float32)
    freq_lo, freq_hi = 300.0, 3400.0
    for i in range(n):
        tt = i / SR
        # Sawtooth modulation for freq sweep
        sweep_t = (tt * chirp_rate) % 1.0
        if int(tt * chirp_rate) % 2 == 0:
            freq = freq_lo + (freq_hi - freq_lo) * sweep_t
        else:
            freq = freq_hi - (freq_hi - freq_lo) * sweep_t
        phase_acc += 2 * np.pi * freq / SR
        out[i] = 0.3 * np.sin(phase_acc)
    # Add some amplitude modulation noise for extra modem flavour
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 8.0 * t)
    return (out * mod.astype(np.float32))

def screech_56k(dur=0.8):
    """56k modem connection screech: descending glissando 1200→300Hz."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    freq = np.linspace(1200, 300, n)
    phase = np.cumsum(2 * np.pi * freq / SR)
    env = np.linspace(0.4, 0.05, n)
    # Add harmonics for that truly horrible sound
    sig = (env * (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.3 * np.sin(3 * phase))).astype(np.float32)
    return sig

def winxp_chord():
    """The Windows XP startup chord: C5-E5-G5-B5 arpeggio, dead serious."""
    notes_midi = [72, 76, 79, 83]
    chord = []
    for i, m in enumerate(notes_midi):
        n = note(m, 0.18, amp=0.25)
        pad = silence(i * 0.09)
        chord.append(np.concatenate([pad, n]))
    max_len = max(len(c) for c in chord)
    mix = np.zeros(max_len, dtype=np.float32)
    for c in chord:
        mix[:len(c)] += c
    # Hold the chord
    sustain = note(notes_midi[-1], 0.6, amp=0.0)  # silent sustain
    return np.concatenate([mix, sustain])

def bit_flip_glitch(dur=0.06):
    """A single random tone glitch — bit flip in the melody buffer."""
    import random
    glitch_midi = random.choice([40, 80, 55, 90, 35, 75])  # out of range notes
    return note(glitch_midi, dur, amp=0.2)

# ─────────────────────────────────────────────────────────────────────────────
# BUILD THE SONG
# ─────────────────────────────────────────────────────────────────────────────

sections = []

# ── SECTION 1: False Confidence ───────────────────────────────────────────
# BPM 120 → 8th notes at 250ms each
# First 4 notes of Fur Elise: A, G#, A, G# — mechanical and perfect
beat = 0.25  # 8th note at 120 BPM

section1 = np.concatenate([
    note(69, beat),  # A4
    note(68, beat),  # G#4
    note(69, beat),  # A4
    note(68, beat),  # G#4
    note(69, beat),  # A4
    note(64, beat),  # E4
    note(74, beat),  # D5
    note(72, beat),  # C5
    note(69, beat),  # A4 — perfect. you almost trust it.
    silence(beat * 2),  # rest
    # repeat the opening motif
    note(69, beat),
    note(68, beat),
    note(69, beat),
    note(68, beat),
])
sections.append(section1)

# ── SECTION 2: First Corruption ───────────────────────────────────────────
# 5th note (A4) plays at 3x duration then cuts off. Silence. One beat.
held = note(69, beat * 3.5, amp=0.35)   # starts to hold...
# abrupt cut (already short attack/release handles this)
section2 = np.concatenate([
    held,
    silence(beat),   # packet dropped. nothing.
])
sections.append(section2)

# ── SECTION 3: Dial-up Interruption ──────────────────────────────────────
# 2 beats of modem handshake, then snaps back to melody as if nothing happened
section3 = np.concatenate([
    modem_chirp(beat * 2),       # the handshake
    silence(beat * 0.5),         # reconnecting...
    note(69, beat),              # right. where were we. A4.
    note(68, beat),              # G#4
    note(69, beat),              # A4. yes.
    silence(beat),
])
sections.append(section3)

# ── SECTION 4: Tempo Disintegration ──────────────────────────────────────
# Restarts melody but each note slightly shorter than the last
# until it's a blur, then hard stop
melody = [69, 68, 69, 68, 69, 64, 74, 72, 69, 68, 69, 68, 69, 64, 74, 72]
accum = []
dur = beat * 1.2
for m in melody:
    accum.append(note(m, max(dur, 0.02), amp=0.35))
    dur *= 0.82  # each note 18% shorter — acceleration
    if dur < 0.03:
        dur = 0.03
section4 = np.concatenate(accum + [silence(beat)])  # hard stop
sections.append(section4)

# ── SECTION 5: The Reboot ──────────────────────────────────────────────────
section5 = np.concatenate([
    silence(beat * 0.5),
    screech_56k(0.7),           # 56k modem connection screech
    silence(beat),
    winxp_chord(),              # Windows XP startup. Dead serious.
    silence(beat * 1.5),
])
sections.append(section5)

# ── SECTION 6: Worse ──────────────────────────────────────────────────────
# Wrong key (up 2 semitones). Confident. Bit-flip glitch every ~3 notes.
import random
random.seed(404)
worse = []
glitch_counter = 0
full_melody_wrong = FUR_ELISE_WRONG * 3  # repeat 3 times
for i, m in enumerate(full_melody_wrong):
    worse.append(note(m, beat, amp=0.35))
    glitch_counter += 1
    if glitch_counter >= 3 and random.random() < 0.45:
        worse.append(bit_flip_glitch())
        glitch_counter = 0
    # occasionally a modem chirp hiccup mid-phrase
    if i == 8:
        worse.append(modem_chirp(0.12))
    if i == 17:
        worse.append(modem_chirp(0.08))
    if i == 22:
        worse.append(silence(beat * 0.4))  # buffer stall

# Fade out mid-phrase (song just... gives up)
section6 = np.concatenate(worse)
# Apply fade-out on last 20%
fade_start = int(len(section6) * 0.75)
fade_len = len(section6) - fade_start
section6[fade_start:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
sections.append(section6)

# ─────────────────────────────────────────────────────────────────────────────
# MIX + MASTER
# ─────────────────────────────────────────────────────────────────────────────

audio = np.concatenate(sections)

# Server room ambient hum: 60Hz mains + 120Hz harmonic (computer room energy)
t_full = np.linspace(0, len(audio) / SR, len(audio), endpoint=False)
hum = (0.06 * np.sin(2 * np.pi * 60.0 * t_full) +
       0.03 * np.sin(2 * np.pi * 120.0 * t_full) +
       0.015 * np.sin(2 * np.pi * 180.0 * t_full)).astype(np.float32)
audio = audio + hum

# Stereo: left = direct, right = 8ms delay (tiny room — like a server closet)
delay_samples = int(0.008 * SR)
left = audio.copy()
right = np.zeros_like(audio)
right[delay_samples:] = audio[:-delay_samples] * 0.92

stereo = np.stack([left, right], axis=1)

# Clip protection
peak = np.max(np.abs(stereo))
if peak > 0.9:
    stereo = stereo * (0.9 / peak)

# Write WAV
OUT.parent.mkdir(exist_ok=True)
with wave.open(str(OUT), 'w') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    pcm = (stereo * 32767).astype(np.int16)
    wf.writeframes(pcm.tobytes())

dur_s = len(audio) / SR
print(f"Rendered: {OUT}  ({dur_s:.1f}s)")
print("404: Melody Not Found — render complete.")
