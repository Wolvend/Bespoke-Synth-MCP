#!/usr/bin/env python
"""
TUNNEL FEVER - Dig Dug Underground Breakcore
=============================================
Chip-tune square waves + triangle bass + pump sounds + drill rhythms
+ hardstyle kicks. Like Dig Dug found a rave underground.
Key: G Major  |  BPM: 168  |  Chip-tune + Hardstyle + Breakcore
"""

import numpy as np
from scipy import signal
from pydub import AudioSegment
from pedalboard import (
    Pedalboard, Reverb, Delay, Compressor, HighpassFilter,
    LowpassFilter, Chorus, Limiter, Distortion, Bitcrush
)
from pathlib import Path
from datetime import datetime
import json

SR   = 44100
BPM  = 168
BEAT = 60.0 / BPM        # 0.357s
BAR  = BEAT * 4           # 1.429s
S8   = BEAT / 2
S16  = BEAT / 4
S32  = BEAT / 8

# G Major + chromatic neighbours
FREQ = {
    "G2": 98.0,  "A2":110.0, "B2":123.5, "D3":146.8,
    "G3":196.0,  "A3":220.0, "B3":246.9, "C4":261.6, "D4":293.7,
    "E4":329.6,  "F4":349.2, "F#4":370.0,"G4":392.0, "A4":440.0,
    "B4":493.9,  "C5":523.3, "D5":587.3, "E5":659.3, "F#5":740.0,
    "G5":784.0,  "A5":880.0, "B5":987.8, "C6":1046.5,"D6":1174.7,
    "E6":1318.5, "F#6":1480.0,"G6":1568.0,
    "Bb4":466.2, "Eb5":622.3,
}

# ─── Utility ──────────────────────────────────────────────────────────────────

def adsr(n, a, d, s, r, sr=SR):
    env = np.ones(n, np.float32)
    ai=int(a*sr); di=int(d*sr); ri=int(r*sr)
    if ai: env[:ai] = np.linspace(0,1,ai)
    de=min(ai+di,n)
    if de>ai: env[ai:de] = np.linspace(1,s,de-ai)
    rs=max(0,n-ri)
    if rs<n: env[rs:] = np.linspace(s,0,n-rs)
    return env

def norm(x, h=1.05):
    p=np.max(np.abs(x)); return (x/(p*h) if p>0 else x).astype(np.float32)

def clip(x, d=1.0): return np.tanh(x*d).astype(np.float32)

def stereo(l, r=None):
    if r is None: r=l
    return np.stack([l,r],-1).astype(np.float32)

# ─── Mixer ────────────────────────────────────────────────────────────────────

class Mixer:
    def __init__(self, dur_s):
        self.n   = int(dur_s*SR)
        self.buf = np.zeros((self.n,2),np.float32)

    def place(self, audio, pos_s, gain=1.0, pan=0.0):
        s=int(pos_s*SR)
        if s>=self.n: return
        if audio.ndim==1: audio=stereo(audio)
        ln=min(len(audio),self.n-s)
        lv=gain*np.cos((pan+1)*np.pi/4)
        rv=gain*np.sin((pan+1)*np.pi/4)
        self.buf[s:s+ln,0]+=audio[:ln,0]*lv
        self.buf[s:s+ln,1]+=audio[:ln,1]*rv

    def export_mp3(self, path, bitrate="320k"):
        audio=norm(self.buf)
        board=Pedalboard([Limiter(threshold_db=-0.3,release_ms=80)])
        audio=board(audio.T.copy(),SR).T
        pcm=(np.clip(audio,-1,1)*32767).astype(np.int16)
        seg=AudioSegment(pcm.flatten().tobytes(),frame_rate=SR,sample_width=2,channels=2)
        seg.export(str(path),format="mp3",bitrate=bitrate)


# ─── Chip-tune Synths ─────────────────────────────────────────────────────────

def square(freq, dur_s, duty=0.5, vel=1.0):
    """50% square wave — pure NES/arcade chip sound."""
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    phase = (freq*t) % 1.0
    osc = np.where(phase < duty, 1.0, -1.0).astype(np.float32)
    # Soften the brutal square just slightly (RC filter simulation)
    b,a = signal.butter(1, min(freq*6, 8000), fs=SR, btype='low')
    osc = signal.lfilter(b,a,osc)
    env = adsr(n, 0.002, dur_s*0.15, 0.75, dur_s*0.2)
    return norm(osc*env)*vel

def pulse(freq, dur_s, duty=0.25, vel=1.0):
    """Narrow pulse wave — that scratchy Dig Dug lead timbre."""
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    phase = (freq*t) % 1.0
    osc = np.where(phase < duty, 1.0, -1.0).astype(np.float32)
    b,a = signal.butter(1, min(freq*8, 10000), fs=SR, btype='low')
    osc = signal.lfilter(b,a,osc)
    env = adsr(n, 0.001, dur_s*0.1, 0.7, dur_s*0.15)
    return norm(osc*env)*vel

def triangle_bass(freq, dur_s, vel=1.0):
    """Triangle wave bass — classic NES bass channel warmth."""
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    phase = (freq*t) % 1.0
    osc = (2*np.abs(2*(phase-np.floor(phase+0.5)))-1).astype(np.float32)
    env = adsr(n, 0.003, 0.06, 0.65, 0.08)
    return norm(osc*env)*vel

def noise_channel(dur_s=0.05, lp=8000, vel=1.0):
    """NES noise channel — for percussion."""
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    noise = np.random.uniform(-1,1,n).astype(np.float32)
    b,a = signal.butter(2, lp, fs=SR, btype='low')
    noise = signal.lfilter(b,a,noise)
    env = np.exp(-t*60)
    return norm(noise*env)*vel

def pump_sfx(vel=1.0):
    """The Dig Dug PUMP: rapid ascending chirp — bwip bwip bwip."""
    pulses = []
    freqs  = [FREQ["G4"], FREQ["B4"], FREQ["D5"], FREQ["G5"]]
    for f in freqs:
        p = pulse(f, 0.045, duty=0.3, vel=vel)
        silence = np.zeros(int(0.01*SR), np.float32)
        pulses.extend([p, silence])
    return np.concatenate(pulses)

def drill_burst(dur_s=0.12, vel=1.0):
    """Drilling sound: amplitude-modulated bandpass noise."""
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    noise = np.random.uniform(-1,1,n).astype(np.float32)
    # Bandpass for metallic drill character
    b,a = signal.butter(3,[400,2000],fs=SR,btype='bandpass')
    noise = signal.lfilter(b,a,noise)
    # Rapid amplitude tremolo (simulate drill rotation)
    tremolo = 0.5 + 0.5*np.sin(2*np.pi*60*t)
    env = adsr(n, 0.005, 0.07, 0.3, 0.04)
    return norm(noise*tremolo*env)*vel

def enemy_pop(vel=1.0):
    """Enemy inflated and popped: descending pitch burst."""
    dur_s = 0.15
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    # Descending chirp (inflate → pop)
    f_start, f_end = 800, 100
    pitch = f_end + (f_start-f_end)*np.exp(-t*25)
    phase = 2*np.pi*np.cumsum(pitch)/SR
    chirp = np.sin(phase)
    noise = np.random.uniform(-1,1,n)*0.5
    env   = adsr(n, 0.001, 0.08, 0.1, 0.05)
    audio = (chirp*0.6 + noise*0.4)*env
    return norm(audio)*vel

def underground_rumble(dur_s=BAR, vel=1.0):
    """Deep sub-bass rumble — you're underground."""
    n = int(dur_s*SR)
    t = np.arange(n)/SR
    sub = np.sin(2*np.pi*38*t) + 0.4*np.sin(2*np.pi*55*t)
    lfo = 0.7 + 0.3*np.sin(2*np.pi*0.5*t)
    env = np.ones(n)*0.85
    env[:int(0.1*SR)] = np.linspace(0,0.85,int(0.1*SR))
    env[-int(0.2*SR):] = np.linspace(0.85,0,int(0.2*SR))
    b,a = signal.butter(2, 120, fs=SR, btype='low')
    audio = signal.lfilter(b,a, sub*lfo*env)
    return norm(audio)*vel

def hardstyle_kick(vel=1.0):
    """Hard kick with sub layer."""
    dur_s=0.65; n=int(dur_s*SR); t=np.arange(n)/SR
    pitch = 55 + (200-55)*np.exp(-t*35)
    phase = 2*np.pi*np.cumsum(pitch)/SR
    body  = np.sin(phase)
    ck    = int(0.004*SR)
    click = np.random.uniform(-1,1,ck)*np.exp(-np.arange(ck)/SR*800)
    amp   = np.exp(-t*8); amp[:int(0.002*SR)]=1.0
    audio = body*amp; audio[:ck]+=click*0.5
    audio = clip(audio*3.5)*0.7
    sub   = np.sin(2*np.pi*42*t)*np.exp(-t*5)
    audio += sub*0.35
    return norm(audio)*vel

def chip_snare(vel=1.0):
    """NES-style snare: very short noise burst, no sustain."""
    dur_s=0.12; n=int(dur_s*SR); t=np.arange(n)/SR
    noise=np.random.uniform(-1,1,n).astype(np.float32)
    b,a=signal.butter(2,[500,8000],fs=SR,btype='bandpass')
    noise=signal.lfilter(b,a,noise)
    tone=np.sin(2*np.pi*180*t)
    env=adsr(n,0.001,0.06,0.0,0.02)
    return norm((noise*0.75+tone*0.25)*env)*vel

def chip_hat(vel=0.6, open_=False):
    dur_s=0.18 if open_ else 0.018
    n=int(dur_s*SR); t=np.arange(n)/SR
    noise=np.random.uniform(-1,1,n).astype(np.float32)
    b,a=signal.butter(4,10000,fs=SR,btype='high')
    noise=signal.lfilter(b,a,noise)
    amp=np.exp(-t*(4 if open_ else 300))
    return norm(noise*amp)*vel


# ─── FX Boards ────────────────────────────────────────────────────────────────

def apply(raw, board):
    s = stereo(raw) if raw.ndim==1 else raw
    return board(s.T.copy(),SR).T

# Dry chip lead — minimal processing to preserve 8-bit feel
BOARD_CHIP = Pedalboard([
    Compressor(threshold_db=-10, ratio=2),
    Reverb(room_size=0.15, damping=0.8, wet_level=0.08, dry_level=0.92),
])
# Chip lead in chorus sections — wider
BOARD_CHIP_WIDE = Pedalboard([
    Chorus(rate_hz=3.0, depth=0.2, centre_delay_ms=5, mix=0.25),
    Delay(delay_seconds=S16*2, feedback=0.15, mix=0.12),
    Reverb(room_size=0.25, wet_level=0.18, dry_level=0.82),
])
# Triangle bass — warm, simple
BOARD_TRI = Pedalboard([
    LowpassFilter(cutoff_frequency_hz=600),
    Compressor(threshold_db=-10, ratio=3),
])
# Kick
BOARD_KICK = Pedalboard([
    Compressor(threshold_db=-6, ratio=6, attack_ms=0.5, release_ms=60),
])
# Snare
BOARD_SNARE = Pedalboard([
    Reverb(room_size=0.18, wet_level=0.12, dry_level=0.88),
])
# Pump SFX — keep bright and fun
BOARD_PUMP = Pedalboard([
    Reverb(room_size=0.1, wet_level=0.08),
])
# Enemy pop
BOARD_POP = Pedalboard([
    HighpassFilter(cutoff_frequency_hz=150),
    Reverb(room_size=0.2, wet_level=0.15),
])


# ─── DIG DUG Melody ──────────────────────────────────────────────────────────
# Main hook: ascending march, triadic arpeggio feel
# 8th note grid at 168 BPM
HOOK_A = [   # 2 bars, 8th notes: tunnel theme main phrase
    ("G5",0),("B5",1),("D6",2),("B5",3),
    ("G5",4),("A5",5),("B5",6),("D6",7),
]
HOOK_B = [   # 2 bars, counter phrase: descent + bounce
    ("C6",0),("B5",1),("A5",2),("G5",3),
    ("F#5",4),("G5",5),("A5",6),("B5",7),
]
HOOK_FAST = [  # 1 bar, 16th notes — chaos run
    "G5","B5","D6","B5","G5","A5","B5","G5",
    "F#5","G5","A5","B5","C6","B5","A5","G5",
]
BASS_HOOK = [  # Bass arpeggio matching melody
    ("G3",0),("D3",1),("G3",2),("B3",3),
    ("A3",4),("D3",5),("G3",6),("D3",7),
]

def place_hook(mix, bar, speed=1, vel=1.0, wide=False):
    board = BOARD_CHIP_WIDE if wide else BOARD_CHIP
    src_a = HOOK_A
    src_b = HOOK_B
    if speed == 1:   # quarter + 8th feel
        step = S8
        src  = src_a if bar%4 < 2 else src_b
        for note, i in src:
            t   = bar*BAR + i*step
            dur = step * 0.80
            raw = pulse(FREQ[note], dur, duty=0.25, vel=vel)
            fxd = apply(raw, board)
            mix.place(fxd, t, gain=0.52, pan=np.random.uniform(-0.06,0.06))
    elif speed == 2:  # 16th note runs
        step = S16
        for i, note in enumerate(HOOK_FAST):
            t   = bar*BAR + i*step
            dur = step * 0.75
            raw = pulse(FREQ[note], dur, duty=0.3, vel=vel*0.88)
            fxd = apply(raw, BOARD_CHIP_WIDE)
            mix.place(fxd, t, gain=0.50, pan=np.sin(i*0.4)*0.2)
    elif speed == 0.5:  # half-speed (title screen feel)
        step = BEAT
        src  = src_a
        for note, i in src[:4]:   # just first 4 notes, slowly
            t   = bar*BAR + i*step
            dur = BEAT * 0.88
            raw = square(FREQ[note], dur, vel=vel*0.7)
            fxd = apply(raw, board)
            mix.place(fxd, t, gain=0.45, pan=0.0)

def place_bass(mix, bar, vel=1.0):
    step = S8
    for note, i in BASS_HOOK:
        t   = bar*BAR + i*step
        dur = step * 0.78
        raw = triangle_bass(FREQ[note], dur, vel)
        fxd = apply(raw, BOARD_TRI)
        mix.place(fxd, t, gain=0.42, pan=0.0)


# ─── Drum patterns ────────────────────────────────────────────────────────────

def place_drums(mix, bar, section="level"):
    b = bar*BAR

    def k(pos,v=1.0):  mix.place(apply(hardstyle_kick(v),BOARD_KICK), pos, gain=0.70)
    def sn(pos,v=1.0): mix.place(apply(chip_snare(v),BOARD_SNARE), pos, gain=0.55, pan=0.05)
    def hh(pos,v=0.5,op=False): mix.place(stereo(chip_hat(v,op)), pos, gain=0.25, pan=-0.2)
    def dr(pos,v=0.7): mix.place(stereo(drill_burst(vel=v)), pos, gain=0.28, pan=0.15)

    if section == "title":
        # Just a light kick + snare, staying out of the way of the melody
        k(b); sn(b+2*BEAT)
        for i in range(8): hh(b+i*S8, 0.25)

    elif section == "level":
        # Hardstyle kick on 1, 2.5, 3 + chip snare on 2, 4
        for pos in [0, 1.5, 2]:
            k(b+pos*BEAT, 0.85+0.1*np.random.random())
        for pos in [1, 3]:
            sn(b+pos*BEAT)
        for i in range(16):
            v = 0.2 + 0.3*(i%4==0) + 0.2*(i%2==0) + 0.1*np.random.random()
            hh(b+i*S16, v, op=(i==8))
        # Drilling sound on the upbeats
        for pos in [0.5, 2.5]: dr(b+pos*BEAT)

    elif section == "boss":
        # Syncopated chaos
        for pos in [0, 0.75, 1.5, 2, 2.75, 3, 3.5]:
            k(b+pos*BEAT, 0.88+0.1*np.random.random())
        for pos in [1, 2.5, 3, 3.75]:
            sn(b+pos*BEAT, 0.85+0.1*np.random.random())
        for i in range(16):
            v = 0.15 + 0.4*(i%4==0) + 0.25*(i%2==0) + 0.15*np.random.random()
            hh(b+i*S16, v, op=(i in (4,8,12)))
        # Drill on every beat
        for beat in range(4): dr(b+beat*BEAT+S8, 0.6)

    elif section == "victory":
        # Celebratory: kick 1+3, snare 2+4, hats 8th
        for pos in [0, 2]: k(b+pos*BEAT, 0.8)
        for pos in [1, 3]: sn(b+pos*BEAT, 0.75)
        for i in range(8): hh(b+i*S8, 0.3)


# ─── Song ─────────────────────────────────────────────────────────────────────
SONG_BARS = 34
mix = Mixer(SONG_BARS*BAR + 2.5)
np.random.seed(99)

print("\n" + "="*70)
print("  TUNNEL FEVER  |  168 BPM  |  G Major  |  Dig Dug Underground Breakcore")
print("="*70)

# ── Underground rumble pad throughout ─────────────────────────────────────────
for b in range(0, SONG_BARS, 4):
    gain = 0.18 if b < 4 else (0.28 if b < 28 else max(0.05, 0.28-(b-28)*0.07))
    raw  = underground_rumble(BAR*4)
    mix.place(stereo(raw), b*BAR, gain=gain)

# ── TITLE SCREEN (0-3): Melody materialises, no drums ────────────────────────
print("[TITLE]   bars 0–3   — 8-bit hook emerges from underground silence")
for b in range(0, 4):
    place_hook(mix, b, speed=0.5, vel=0.75)
    place_drums(mix, b, "title")

# Pump sound every 2 bars (BWIP BWIP BWIP)
for b in [1, 3]:
    raw = pump_sfx(vel=0.8)
    mix.place(apply(raw, BOARD_PUMP), b*BAR+3*BEAT, gain=0.42, pan=0.3)

# ── LEVEL 1 (4-11): Full beat drops, Dig Dug starts digging ─────────────────
print("[LEVEL 1] bars 4–11  — KICK DROP: dig dig dig, 8-bit melody rages")
for b in range(4, 12):
    place_hook(mix, b, speed=1, vel=0.95, wide=(b>=8))
    place_bass(mix, b, vel=0.9)
    place_drums(mix, b, "level")
    # Pump sound on beat 4 every 2 bars
    if b % 2 == 1:
        raw = pump_sfx(vel=0.7)
        mix.place(apply(raw, BOARD_PUMP), b*BAR+3*BEAT, gain=0.38, pan=0.35)

# Enemy pop accents
for b in [5, 7, 9, 11]:
    raw = enemy_pop(vel=0.8)
    mix.place(apply(raw, BOARD_POP), b*BAR+1.5*BEAT, gain=0.35, pan=-0.3)

# ── BOSS ENCOUNTER (12-15): Chaos increases, stabs enter ─────────────────────
print("[BOSS]    bars 12–15 — FYGAR APPROACHES: maximum drum chaos")
for b in range(12, 16):
    place_hook(mix, b, speed=1, vel=1.0, wide=True)
    place_bass(mix, b, vel=0.95)
    place_drums(mix, b, "boss")
    # Extra square arpeggio punches
    for beat in range(4):
        t   = b*BAR + beat*BEAT
        raw = square(FREQ["G4"] * (1 + beat*0.25), 0.05, vel=0.7)
        mix.place(apply(raw, BOARD_CHIP), t, gain=0.30, pan=beat*0.15-0.2)

# Alarm pump before break
for i in range(8):
    raw = pump_sfx(vel=0.55+i*0.05)
    mix.place(apply(raw, BOARD_PUMP), 15*BAR + i*S8, gain=0.35, pan=np.sin(i)*0.4)

# ── TUNNEL BREAK (16-19): Just melody + bass, drilling ───────────────────────
print("[TUNNEL]  bars 16–19 — deep underground: melody echoes in the dark")
for b in range(16, 20):
    place_hook(mix, b, speed=1, vel=0.85, wide=True)
    place_bass(mix, b, vel=0.75)
    # Just drill sounds and hats
    for i in range(8):
        t   = b*BAR + i*S8
        raw = drill_burst(dur_s=0.09, vel=0.5)
        mix.place(stereo(raw), t, gain=0.22, pan=np.sin(i*0.8)*0.4)
    # Kick on 1 only
    mix.place(apply(hardstyle_kick(0.65), BOARD_KICK), b*BAR, gain=0.55)

# Pump build-up into final drop
for i in range(16):
    raw  = pump_sfx(vel=min(1.0, 0.4+i*0.04))
    size = 0.3+i*0.045
    mix.place(apply(raw, BOARD_PUMP), 19*BAR+2*BEAT+i*S16*1.2, gain=size, pan=np.cos(i)*0.5)

# ── FINAL DIG (20-29): 16th-note melody madness, everything at once ──────────
print("[FINAL]   bars 20–29 — MAXIMUM DIG: 16th note melody + full chaos")
for b in range(20, 30):
    place_hook(mix, b, speed=2, vel=1.0)
    place_bass(mix, b, vel=0.98)
    place_drums(mix, b, "boss")
    # Pump sound every half-bar
    for half in range(2):
        raw = pump_sfx(vel=0.65)
        mix.place(apply(raw, BOARD_PUMP), b*BAR+half*BEAT*2+BEAT*1.5, gain=0.40, pan=half*0.4-0.2)
    # Enemy pops scatter
    if b % 2 == 0:
        for i in range(3):
            raw = enemy_pop(vel=0.7)
            mix.place(apply(raw, BOARD_POP), b*BAR+i*BEAT*1.3, gain=0.30,
                      pan=np.random.uniform(-0.5,0.5))

# ── VICTORY (30-33): Celebration — pump fanfare, jingle out ──────────────────
print("[VICTORY] bars 30–33 — YOU WIN: pump fanfare, melody celebration")
for b in range(30, 34):
    fade = max(0.1, 1.0-(b-30)*0.22)
    place_hook(mix, b, speed=1, vel=fade*0.9, wide=True)
    place_drums(mix, b, "victory")
    if b < 33: place_bass(mix, b, vel=fade*0.8)

# Victory pump fanfare: ascending pump sounds every beat
for b in [30, 31]:
    for beat in range(4):
        raw = pump_sfx(vel=0.8-beat*0.05)
        mix.place(apply(raw, BOARD_PUMP), b*BAR+beat*BEAT, gain=0.45,
                  pan=(beat-1.5)*0.3)

# Final jingle: ascending G major scale
scale = ["G5","A5","B5","C6","D6","E6","F#6","G6"]
for i, note in enumerate(scale):
    t   = 33*BAR + i*S16*1.5
    raw = pulse(FREQ[note], S8*0.85, duty=0.25, vel=0.85-i*0.02)
    mix.place(apply(raw, BOARD_CHIP_WIDE), t, gain=0.5, pan=i*0.1-0.35)

# Final enemy pop + silence
mix.place(apply(enemy_pop(1.0), BOARD_POP), 33*BAR+4*S16*1.5+0.1, gain=0.6)

# ─── Export ───────────────────────────────────────────────────────────────────
tracks_dir = Path(__file__).parent / "tracks"
tracks_dir.mkdir(exist_ok=True)
ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
mp3_name = f"tunnel_fever_{ts}.mp3"
mp3_path = tracks_dir / mp3_name

dur_s = SONG_BARS*BAR + 2.5
print(f"\n[RENDER]  Exporting {dur_s:.1f}s stereo 320 kbps ...")
mix.export_mp3(mp3_path)

size_kb = mp3_path.stat().st_size/1024
(tracks_dir/f"tunnel_fever_{ts}.json").write_text(json.dumps({
    "title":"TUNNEL FEVER","bpm":BPM,"key":"G Major",
    "bars":SONG_BARS,"dur_s":round(dur_s,2),"sr":SR,
    "channels":2,"bitrate":"320k",
    "synths":["pulse_wave (25% duty, Dig Dug lead)","square_wave",
              "triangle_bass (NES-style)","noise_channel",
              "pump_sfx (Dig Dug pump)","drill_burst",
              "enemy_pop (inflate+pop)","underground_rumble",
              "hardstyle_kick","chip_snare","chip_hat"],
    "sections":["Title Screen","Level 1","Boss Encounter",
                "Tunnel Break","Final Dig","Victory"],
    "file":mp3_name,
},indent=2))

print("\n"+"="*70)
print("  TUNNEL FEVER -- COMPLETE")
print("="*70)
print(f"  File:      {mp3_name}")
print(f"  Location:  {mp3_path.absolute()}")
print(f"  Size:      {size_kb:.0f} KB")
print(f"  Duration:  {dur_s:.1f}s  ({SONG_BARS} bars at {BPM} BPM)")
print(f"  Synths:    11 voices  (pulse, square, triangle, noise, pump, drill...)")
print(f"  Sections:  Title > Level1 > Boss > Tunnel > Final Dig > Victory")
print("="*70)
print(f"\n  -> {mp3_path.absolute()}\n")
