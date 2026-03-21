"""
check_audio.py  --  Audio QC before delivery
Run: python check_audio.py tracks/void2.wav

Checks:
  - Clipping / NaN / Inf
  - Silence ratio (too much empty space)
  - Frequency band energy balance (sub / bass / mid / high)
  - Sidechain over-pumping (is content constantly ducked?)
  - RMS per section (are any sections dead?)
  - Stereo width
  - Dynamic range (are drums audible vs synths?)

Prints PASS/FAIL with numbers for every check.
"""

import sys, os
import numpy as np
import wave
from scipy import signal as sp_signal

FAIL = "\033[91m[FAIL]\033[0m"
PASS = "\033[92m[PASS]\033[0m"
WARN = "\033[93m[WARN]\033[0m"

def load_wav(path):
    with wave.open(path, 'r') as wf:
        sr  = wf.getframerate()
        ch  = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    s = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        L = s[0::2]; R = s[1::2]
    else:
        L = R = s
    return L, R, sr

def band_rms(sig, sr, lo, hi):
    """RMS energy in a frequency band via FFT power sum."""
    n    = len(sig)
    fft  = np.fft.rfft(sig.astype(np.float64))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    mask = (freqs >= lo) & (freqs < hi)
    power = np.sum(np.abs(fft[mask])**2) / (n * n)
    return float(np.sqrt(max(power, 0.0)))

def rms_db(x):
    r = np.sqrt(np.mean(x**2))
    return 20 * np.log10(r + 1e-9)

def check(path):
    print(f"\n{'='*60}")
    print(f"  Audio QC: {os.path.basename(path)}")
    print(f"{'='*60}")

    if not os.path.exists(path):
        print(f"{FAIL} File not found: {path}")
        return

    L, R, sr = load_wav(path)
    mono = (L + R) / 2
    dur  = len(mono) / sr
    issues = []

    print(f"  Duration: {dur:.1f}s  |  SR: {sr}Hz  |  Stereo: {len(L)==len(R)}\n")

    # ------------------------------------------------------------------
    # 1. Clipping / NaN / Inf
    # ------------------------------------------------------------------
    nan_count = int(np.sum(np.isnan(mono)) + np.sum(np.isinf(mono)))
    clip_count = int(np.sum(np.abs(mono) >= 0.999))
    if nan_count > 0:
        print(f"  {FAIL} NaN/Inf samples: {nan_count}  -> render overflow, check arithmetic")
        issues.append("NaN/Inf")
    else:
        print(f"  {PASS} No NaN/Inf")

    if clip_count > 100:
        print(f"  {FAIL} Clipping: {clip_count} samples ({clip_count/len(mono)*100:.2f}%)  -> reduce gain")
        issues.append("clipping")
    elif clip_count > 0:
        print(f"  {WARN} Light clipping: {clip_count} samples")
    else:
        print(f"  {PASS} No clipping")

    # ------------------------------------------------------------------
    # 2. Silence ratio
    # ------------------------------------------------------------------
    silence_thresh = 0.01
    silent_samples = np.sum(np.abs(mono) < silence_thresh)
    silence_pct    = silent_samples / len(mono) * 100
    if silence_pct > 60:
        print(f"  {FAIL} Silence: {silence_pct:.1f}% of track is near-silent  -> too many gaps, sidechain too deep, or content too quiet")
        issues.append("too-silent")
    elif silence_pct > 40:
        print(f"  {WARN} Silence: {silence_pct:.1f}%  -> may sound sparse")
    else:
        print(f"  {PASS} Silence: {silence_pct:.1f}%")

    # ------------------------------------------------------------------
    # 3. Frequency band balance
    # ------------------------------------------------------------------
    print()
    print("  Frequency balance:")
    bands = [
        ("sub    20-80Hz ",  20,   80,  -34, -10),
        ("bass  80-250Hz ", 80,  250,  -35, -12),
        ("mid  250-2kHz  ", 250, 2000, -40, -15),
        ("high  2k-8kHz  ", 2000, 8000, -55, -25),
    ]
    band_levels = {}
    for label, lo, hi, warn_lo, warn_hi in bands:
        rms = band_rms(mono, sr, lo, hi)
        db  = 20 * np.log10(rms + 1e-9)
        band_levels[label] = db
        if db < warn_lo:
            tag = FAIL; msg = f"-> {label.strip()} almost inaudible"
            issues.append(f"low-{label.strip()}")
        elif db > warn_hi:
            tag = WARN; msg = f"-> {label.strip()} may be too loud"
        else:
            tag = PASS; msg = ""
        bar_len = max(0, int((db + 70) * 0.6))
        bar = "#" * bar_len
        print(f"  {tag} {label}  {db:6.1f} dBFS  {bar}  {msg}")

    # Check for missing mids (main symptom of "busted" tracks)
    sub_db  = band_levels["sub    20-80Hz "]
    mid_db  = band_levels["mid  250-2kHz  "]
    if sub_db - mid_db > 25:
        print(f"\n  {FAIL} Mid-range {sub_db-mid_db:.0f}dB below sub -> stabs/lead likely buried or wrong octave")
        issues.append("missing-mids")
    else:
        print(f"\n  {PASS} Mid/Sub balance OK (gap: {sub_db-mid_db:.0f}dB)")

    # ------------------------------------------------------------------
    # 4. Sidechain over-pumping  (measure RMS in 50ms windows)
    # ------------------------------------------------------------------
    print()
    win = int(0.05 * sr)
    windows = [mono[i:i+win] for i in range(0, len(mono)-win, win)]
    rms_vals = np.array([np.sqrt(np.mean(w**2)) for w in windows])
    pct_dead = np.sum(rms_vals < 0.005) / len(rms_vals) * 100
    rms_var   = float(np.std(rms_vals) / (np.mean(rms_vals) + 1e-9))
    if pct_dead > 40:
        print(f"  {FAIL} Sidechain: {pct_dead:.0f}% of 50ms windows are near-silent -> sidechain release too long or too deep")
        issues.append("over-pumping")
    else:
        print(f"  {PASS} Sidechain: {pct_dead:.0f}% near-silent windows (OK)")

    if rms_var > 2.5:
        print(f"  {WARN} Dynamics very spiky (RMS var={rms_var:.1f}) -> may sound choppy")
    else:
        print(f"  {PASS} RMS variance OK ({rms_var:.1f})")

    # ------------------------------------------------------------------
    # 5. Section RMS (dead sections?)
    # ------------------------------------------------------------------
    print()
    print("  Section energy:")
    n_sections = 8
    sec_len = len(mono) // n_sections
    all_dead = True
    for i in range(n_sections):
        sec = mono[i*sec_len:(i+1)*sec_len]
        db  = rms_db(sec)
        t0  = i * dur / n_sections
        t1  = (i+1) * dur / n_sections
        if db < -40:
            tag = FAIL
            issues.append(f"dead-section-{i}")
        elif db < -28:
            tag = WARN
        else:
            tag = PASS; all_dead = False
        print(f"  {tag} {t0:4.0f}s-{t1:4.0f}s  {db:6.1f} dBFS")

    # ------------------------------------------------------------------
    # 6. Stereo width
    # ------------------------------------------------------------------
    print()
    mid_sig = (L + R) / 2
    side_sig = (L - R) / 2
    width = rms_db(side_sig) - rms_db(mid_sig)
    if width < -20:
        print(f"  {WARN} Stereo width: {width:.1f}dB (very mono)")
    elif width < -10:
        print(f"  {PASS} Stereo width: {width:.1f}dB (moderate)")
    else:
        print(f"  {PASS} Stereo width: {width:.1f}dB (wide)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print(f"{'='*60}")
    if issues:
        print(f"  {FAIL} {len(issues)} issue(s): {', '.join(issues)}")
    else:
        print(f"  {PASS} All checks passed — ready to deliver")
    print(f"{'='*60}\n")
    return issues

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "tracks/void2.wav"
    check(path)
