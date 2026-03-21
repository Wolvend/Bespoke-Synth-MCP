"""Append normalize, trim, splice, convert to audio.py."""
import pathlib

code = """

# ---------------------------------------------------------------------------
# Tool 12: normalize
# ---------------------------------------------------------------------------

def normalize(file: str, target_lufs: float = -14.0, output_file: str | None = None) -> dict:
    \"\"\"Normalize audio to a target LUFS level.\"\"\"
    try:
        audio_path = _resolve(file)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    try:
        import pyloudnorm as _pln
        import soundfile as _sf
        import numpy as _np
    except ImportError as exc:
        return {"ok": False, "error": f"Missing dep: {exc} -- pip install pyloudnorm soundfile", "ts_ms": _ms()}

    try:
        from pydub import AudioSegment as _AS
    except ImportError:
        return {"ok": False, "error": "pydub not installed -- pip install pydub", "ts_ms": _ms()}

    try:
        data, sr = _sf.read(str(audio_path))
        meter = _pln.Meter(sr)
        loudness = meter.integrated_loudness(data)
        gain_db = target_lufs - loudness
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    try:
        seg = _AS.from_file(str(audio_path)).apply_gain(gain_db)
        stem = audio_path.stem
        if output_file:
            if "/" in output_file or "\\\\" in output_file:
                return {"ok": False, "error": "output_file must be filename only", "ts_ms": _ms()}
            out_name = output_file
        else:
            out_name = f"{stem}_normalized.mp3"
        _TRACKS_DIR.mkdir(exist_ok=True)
        out_path = _TRACKS_DIR / out_name
        seg.export(str(out_path), format="mp3")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    return {
        "ok": True,
        "file": str(out_path.absolute()),
        "input_lufs": round(loudness, 2),
        "target_lufs": target_lufs,
        "gain_db": round(gain_db, 2),
        "ts_ms": _ms(),
    }


# ---------------------------------------------------------------------------
# Tool 13: trim
# ---------------------------------------------------------------------------

def trim(
    file: str,
    silence_thresh_db: float = -40.0,
    padding_ms: int = 100,
    output_file: str | None = None,
) -> dict:
    \"\"\"Trim leading and trailing silence from an audio file.\"\"\"
    try:
        audio_path = _resolve(file)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    try:
        from pydub import AudioSegment as _AS
        from pydub.silence import detect_leading_silence as _dls
    except ImportError:
        return {"ok": False, "error": "pydub not installed -- pip install pydub", "ts_ms": _ms()}

    try:
        seg = _AS.from_file(str(audio_path))
        original_ms = len(seg)

        start_trim = _dls(seg, silence_threshold=silence_thresh_db)
        end_trim = _dls(seg.reverse(), silence_threshold=silence_thresh_db)

        start_ms = max(0, start_trim - padding_ms)
        end_ms = max(start_ms + 1, original_ms - end_trim + padding_ms)
        trimmed = seg[start_ms:end_ms]
        trimmed_ms = len(trimmed)

        stem = audio_path.stem
        if output_file:
            if "/" in output_file or "\\\\" in output_file:
                return {"ok": False, "error": "output_file must be filename only", "ts_ms": _ms()}
            out_name = output_file
        else:
            out_name = f"{stem}_trimmed.mp3"
        _TRACKS_DIR.mkdir(exist_ok=True)
        out_path = _TRACKS_DIR / out_name
        trimmed.export(str(out_path), format="mp3")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    return {
        "ok": True,
        "file": str(out_path.absolute()),
        "original_duration_s": round(original_ms / 1000.0, 3),
        "trimmed_duration_s": round(trimmed_ms / 1000.0, 3),
        "removed_ms": original_ms - trimmed_ms,
        "ts_ms": _ms(),
    }


# ---------------------------------------------------------------------------
# Tool 14: splice
# ---------------------------------------------------------------------------

def splice(
    file: str,
    start_ms: int,
    end_ms: int,
    output_file: str | None = None,
) -> dict:
    \"\"\"Extract a time region from an audio file.\"\"\"
    try:
        audio_path = _resolve(file)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    if end_ms <= start_ms:
        return {"ok": False, "error": "end_ms must be greater than start_ms", "ts_ms": _ms()}

    try:
        from pydub import AudioSegment as _AS
    except ImportError:
        return {"ok": False, "error": "pydub not installed -- pip install pydub", "ts_ms": _ms()}

    try:
        seg = _AS.from_file(str(audio_path))
        clip = seg[start_ms:end_ms]

        stem = audio_path.stem
        if output_file:
            if "/" in output_file or "\\\\" in output_file:
                return {"ok": False, "error": "output_file must be filename only", "ts_ms": _ms()}
            out_name = output_file
        else:
            out_name = f"{stem}_{start_ms}_{end_ms}.mp3"
        _TRACKS_DIR.mkdir(exist_ok=True)
        out_path = _TRACKS_DIR / out_name
        clip.export(str(out_path), format="mp3")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    duration_ms = end_ms - start_ms
    return {
        "ok": True,
        "file": str(out_path.absolute()),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "duration_ms": duration_ms,
        "ts_ms": _ms(),
    }


# ---------------------------------------------------------------------------
# Tool 15: convert
# ---------------------------------------------------------------------------

def convert(
    file: str,
    format: str = "wav",
    output_file: str | None = None,
) -> dict:
    \"\"\"Convert an audio file to a different format.\"\"\"
    valid_formats = {"mp3", "wav", "flac", "ogg"}
    if format not in valid_formats:
        return {"ok": False, "error": f"Invalid format '{format}'. Choose: {sorted(valid_formats)}", "ts_ms": _ms()}

    try:
        audio_path = _resolve(file)
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    try:
        from pydub import AudioSegment as _AS
    except ImportError:
        return {"ok": False, "error": "pydub not installed -- pip install pydub", "ts_ms": _ms()}

    try:
        seg = _AS.from_file(str(audio_path))
        stem = audio_path.stem
        if output_file:
            if "/" in output_file or "\\\\" in output_file:
                return {"ok": False, "error": "output_file must be filename only", "ts_ms": _ms()}
            out_name = output_file
        else:
            out_name = f"{stem}.{format}"
        _TRACKS_DIR.mkdir(exist_ok=True)
        out_path = _TRACKS_DIR / out_name
        seg.export(str(out_path), format=format)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}

    return {
        "ok": True,
        "file": str(out_path.absolute()),
        "format": format,
        "size_kb": round(out_path.stat().st_size / 1024, 2),
        "ts_ms": _ms(),
    }
"""

target = pathlib.Path(r"C:\Users\LIZ\Desktop\Claude\bespokesynth_mcp\services\mcp_bespoke_server\src\mcp_bespoke_server\audio.py")
with open(target, "a", encoding="utf-8") as f:
    f.write(code)
print(f"audio.py appended, total lines: {len(target.read_text(encoding='utf-8').splitlines())}")
