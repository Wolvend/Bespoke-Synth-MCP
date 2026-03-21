"""
audio — Audio analysis and stem separation tools.
Uses scipy + pydub for BPM/key detection (no librosa dependency).
All heavy imports are lazy — server starts cleanly without optional deps.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

_REPO_ROOT  = Path(__file__).resolve().parents[4]
_TRACKS_DIR = _REPO_ROOT / "tracks"
_STEMS_DIR  = _TRACKS_DIR / "stems"


def _ms() -> int:
    return int(time.time() * 1000)


def _resolve(file: str) -> Path:
    """Resolve filename to absolute path: try tracks dir first, then as absolute."""
    p = Path(file)
    if p.is_absolute() and p.exists():
        return p
    candidate = _TRACKS_DIR / file
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Audio file not found: {file!r}")


def _load_audio_np(audio_path: Path):
    """Load audio file to mono float32 numpy array. Returns (samples, sample_rate)."""
    import numpy as np
    from pydub import AudioSegment

    seg = AudioSegment.from_file(str(audio_path))
    sr  = seg.frame_rate
    # Convert to mono float32 in [-1, 1]
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
    if seg.channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)
    peak = np.max(np.abs(samples))
    if peak > 0:
        samples /= peak
    return samples, sr


def _detect_bpm(samples, sr) -> tuple[float, float]:
    """Estimate BPM via onset strength autocorrelation. Returns (bpm, confidence)."""
    import numpy as np
    from scipy import signal

    # Compute energy envelope: downsample to ~100 fps
    hop = sr // 100
    frames = len(samples) // hop
    energy = np.array([
        np.sqrt(np.mean(samples[i * hop:(i + 1) * hop] ** 2))
        for i in range(frames)
    ])

    # Onset strength: positive energy flux
    onset_env = np.diff(energy, prepend=energy[0])
    onset_env = np.maximum(onset_env, 0)

    # Autocorrelation of onset envelope to find period
    fps = sr / hop
    min_lag = int(fps * 60.0 / 240)  # 240 BPM max
    max_lag = int(fps * 60.0 / 40)   # 40 BPM min
    max_lag = min(max_lag, len(onset_env) - 1)

    if max_lag <= min_lag:
        return 120.0, 0.0

    corr = np.correlate(onset_env, onset_env, mode="full")
    corr = corr[len(corr) // 2:]  # positive lags only
    corr_window = corr[min_lag:max_lag]

    if len(corr_window) == 0:
        return 120.0, 0.0

    best_lag = np.argmax(corr_window) + min_lag
    bpm = fps * 60.0 / best_lag

    # Confidence: peak correlation / mean (signal-to-noise-ish)
    mean_corr = np.mean(corr_window)
    confidence = round(float(corr_window[best_lag - min_lag] / (mean_corr + 1e-6)), 3)
    confidence = min(confidence, 10.0)  # cap

    return round(float(bpm), 2), confidence


def _detect_key(samples, sr) -> tuple[str, float]:
    """Detect musical key via chromagram correlation (Krumhansl-Schmuckler)."""
    import numpy as np
    from scipy.signal import stft

    # Short-time Fourier transform
    nperseg = min(4096, len(samples) // 4)
    freqs, _, Zxx = stft(samples, fs=sr, nperseg=nperseg)

    power = np.abs(Zxx) ** 2

    # Map STFT bins to 12 chroma bins
    chroma = np.zeros(12)
    for i, f in enumerate(freqs):
        if f < 20 or f > 5000:
            continue
        midi = 69 + 12 * np.log2(f / 440.0)
        chroma_bin = int(round(midi)) % 12
        chroma[chroma_bin] += np.mean(power[i])

    chroma_mean = chroma / (chroma.sum() + 1e-9)

    note_names   = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    maj_profile  = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    min_profile  = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    best_corr, best_key, best_conf = -999.0, "C major", 0.0
    for shift in range(12):
        rot = np.roll(chroma_mean, -shift)
        for profile, suffix in [(maj_profile, "major"), (min_profile, "minor")]:
            corr = float(np.corrcoef(rot, profile)[0, 1])
            if corr > best_corr:
                best_corr = corr
                best_key  = f"{note_names[shift]} {suffix}"
                best_conf = corr

    return best_key, round(best_conf, 3)


def analyze(
    file: str,
    analyze_bpm: bool = True,
    analyze_key: bool = True,
    analyze_loudness: bool = True,
) -> dict:
    """
    Analyze an audio file for BPM, musical key, and integrated loudness (LUFS).

    Args:
        file: Filename in tracks/ dir OR absolute path.
        analyze_bpm: Detect BPM via onset autocorrelation.
        analyze_key: Detect key via Krumhansl-Schmuckler chromagram.
        analyze_loudness: Measure LUFS via pyloudnorm + soundfile.

    Returns:
        {ok, file, duration_s, bpm, bpm_confidence, key, key_confidence, loudness_lufs, ts_ms}
    """
    try:
        audio_path = _resolve(file)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    result: dict[str, Any] = {"ok": True, "file": str(audio_path)}

    try:
        import numpy as np
        samples, sr = _load_audio_np(audio_path)
        result["duration_s"] = round(float(len(samples) / sr), 3)

        if analyze_bpm:
            bpm, conf = _detect_bpm(samples, sr)
            result["bpm"]            = bpm
            result["bpm_confidence"] = conf

        if analyze_key:
            key, conf = _detect_key(samples, sr)
            result["key"]            = key
            result["key_confidence"] = conf

    except ImportError as exc:
        return {"ok": False, "error": f"scipy/pydub not available: {exc}", "ts_ms": _ms()}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    if analyze_loudness:
        try:
            import pyloudnorm as pyln   # lazy
            import soundfile as sf      # lazy

            data, sr_sf = sf.read(str(audio_path), always_2d=True)
            meter = pyln.Meter(sr_sf)
            lufs  = meter.integrated_loudness(data.astype("float32"))
            result["loudness_lufs"] = round(float(lufs), 2)
        except ImportError:
            result["loudness_lufs"] = None
        except Exception:
            result["loudness_lufs"] = None

    result["ts_ms"] = _ms()
    return result


def stems(
    file: str,
    stem_types: list[str] | None = None,
) -> dict:
    """
    Separate an audio file into instrument stems using demucs (htdemucs model).

    Args:
        file: Filename in tracks/ dir OR absolute path.
        stem_types: Subset of ["vocals", "drums", "bass", "other"]. Default: all four.

    Returns:
        {ok, file, stems: {name: path}, model, ts_ms}

    NOTE: Slow — minutes on CPU, seconds on GPU.
    demucs downloads htdemucs model (~2GB) on first call.
    Requires: demucs, torch, torchaudio.
    """
    if stem_types is None:
        stem_types = ["vocals", "drums", "bass", "other"]
    invalid = set(stem_types) - {"vocals", "drums", "bass", "other"}
    if invalid:
        return {"ok": False, "error": f"Invalid stem types: {invalid}", "ts_ms": _ms()}

    try:
        audio_path = _resolve(file)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    try:
        import torch                            # lazy
        from demucs.apply import apply_model    # lazy
        from demucs.pretrained import get_model # lazy
        import torchaudio                       # lazy
    except ImportError as exc:
        return {"ok": False, "error": f"demucs not installed: {exc}", "ts_ms": _ms()}

    try:
        model_name = "htdemucs"
        model = get_model(model_name)
        model.train(False)  # inference mode

        waveform, sr = torchaudio.load(str(audio_path))
        if sr != model.samplerate:
            waveform = torchaudio.functional.resample(waveform, sr, model.samplerate)
        if waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)
        mix = waveform.unsqueeze(0)

        with torch.no_grad():
            sources = apply_model(model, mix)   # (1, n_sources, 2, samples)

        out_dir = _STEMS_DIR / audio_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        stem_paths: dict[str, str] = {}
        for idx, src in enumerate(model.sources):
            if src not in stem_types:
                continue
            out_p = out_dir / f"{src}.wav"
            torchaudio.save(str(out_p), sources[0, idx], model.samplerate)
            stem_paths[src] = str(out_p.absolute())

        return {
            "ok":    True,
            "file":  str(audio_path),
            "stems": stem_paths,
            "model": model_name,
            "ts_ms": _ms(),
        }

    except Exception as exc:
        return {"ok": False, "file": str(audio_path), "error": str(exc), "ts_ms": _ms()}
