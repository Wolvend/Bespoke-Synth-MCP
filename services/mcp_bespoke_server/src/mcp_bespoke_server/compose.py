"""
bespoke.compose — Workflow render and track library tools.
Bridges the synth engine / workflow_composer into MCP tools.
Resolves paths relative to the repo root (3 levels above this file).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# ─── Path bootstrap ───────────────────────────────────────────────────────────
# repo_root = bespokesynth_mcp/
_REPO_ROOT = Path(__file__).resolve().parents[4]   # …/bespokesynth_mcp
_TRACKS_DIR    = _REPO_ROOT / "tracks"
_PRESETS_DIR   = _REPO_ROOT / "workflow_presets"

# Add repo root to path so we can import synth_engine / workflow_composer
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _ms() -> int:
    return int(time.time() * 1000)


# ─── Preset management ────────────────────────────────────────────────────────

def list_presets() -> dict:
    """
    List all workflow presets saved in workflow_presets/.

    Returns:
        {
          "ok": True,
          "presets": [{"name": "breakcore_brainworm", "bpm": 180, ...}, ...],
          "count": 1,
          "ts_ms": ...
        }
    """
    _PRESETS_DIR.mkdir(exist_ok=True)
    presets = []
    for f in sorted(_PRESETS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            presets.append({
                "name":        f.stem,
                "bpm":         data.get("bpm"),
                "description": data.get("description", ""),
                "steps":       len(data.get("steps", [])),
            })
        except Exception:
            presets.append({"name": f.stem, "error": "could not parse"})

    return {"ok": True, "presets": presets, "count": len(presets), "ts_ms": _ms()}


def get_preset(name: str) -> dict:
    """
    Return the full definition of a named workflow preset.
    """
    _PRESETS_DIR.mkdir(exist_ok=True)
    path = _PRESETS_DIR / f"{name}.json"
    if not path.exists():
        return {"ok": False, "error": f"preset {name!r} not found", "ts_ms": _ms()}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": True, "name": name, "preset": data, "ts_ms": _ms()}


# ─── Track library ────────────────────────────────────────────────────────────

def list_tracks(limit: int = 20) -> dict:
    """
    List recently generated MP3 tracks with their metadata.

    Returns:
        {
          "ok": True,
          "tracks": [
            {
              "file": "brainworm_protocol_20260320.mp3",
              "path": "C:\\...\\tracks\\...",
              "size_kb": 1374,
              "meta": {...}   # from companion .json if present
            },
            ...
          ],
          "count": N
        }
    """
    _TRACKS_DIR.mkdir(exist_ok=True)
    mp3s = sorted(_TRACKS_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime, reverse=True)
    tracks = []
    for mp3 in mp3s[:limit]:
        meta_path = mp3.with_suffix(".json")
        meta: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        tracks.append({
            "file":    mp3.name,
            "path":    str(mp3.absolute()),
            "size_kb": round(mp3.stat().st_size / 1024, 1),
            "meta":    meta,
        })

    return {"ok": True, "tracks": tracks, "count": len(tracks), "ts_ms": _ms()}


# ─── Render ───────────────────────────────────────────────────────────────────

def render_workflow(name: str, dry_run: bool = False) -> dict:
    """
    Load a workflow preset by name and render it to MP3.

    Args:
        name:    Preset name (without .json), e.g. "breakcore_brainworm".
        dry_run: If True, validate only — do not write audio.

    Returns:
        {
          "ok": True,
          "name": "breakcore_brainworm",
          "mp3_path": "C:\\...\\tracks\\breakcore_brainworm_20260320.mp3",
          "size_kb": 384,
          "duration_s": 9.75,
          "dry_run": False,
          "ts_ms": ...
        }
    """
    _PRESETS_DIR.mkdir(exist_ok=True)
    preset_path = _PRESETS_DIR / f"{name}.json"
    if not preset_path.exists():
        return {"ok": False, "error": f"preset {name!r} not found", "ts_ms": _ms()}

    if dry_run:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
        return {
            "ok": True, "name": name, "dry_run": True,
            "steps": len(data.get("steps", [])),
            "bpm": data.get("bpm"),
            "ts_ms": _ms(),
        }

    # Import lazily so the server starts even without scipy/pydub installed
    try:
        from workflow_composer import WorkflowPresetManager, WorkflowRenderer
    except ImportError as exc:
        return {"ok": False, "error": f"compose deps not installed: {exc}", "ts_ms": _ms()}

    try:
        manager  = WorkflowPresetManager(str(_PRESETS_DIR))
        workflow = manager.load_workflow(name)
        if workflow is None:
            return {"ok": False, "error": f"could not load workflow {name!r}", "ts_ms": _ms()}

        renderer = WorkflowRenderer()

        # Use synth_engine.save_audio_mp3 via renderer internals
        from synth_engine import SynthEngine, save_audio_mp3
        import datetime as _dt

        engine  = SynthEngine()
        pattern = [(s.preset, s.duration_ms, s.delay_ms) for s in workflow.steps]
        audio   = engine.render_sequence(pattern)

        _TRACKS_DIR.mkdir(exist_ok=True)
        ts       = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        mp3_name = f"{name}_{ts}.mp3"
        mp3_path = _TRACKS_DIR / mp3_name
        save_audio_mp3(audio, str(mp3_path), sample_rate=44100)

        dur_s    = len(audio) / 44100
        size_kb  = round(mp3_path.stat().st_size / 1024, 1)

        # Save companion metadata
        meta = {
            "title":    name,
            "preset":   name,
            "rendered": _dt.datetime.now().isoformat(),
            "dur_s":    round(dur_s, 2),
            "size_kb":  size_kb,
            "file":     mp3_name,
        }
        (mp3_path.with_suffix(".json")).write_text(json.dumps(meta, indent=2))

        return {
            "ok":        True,
            "name":      name,
            "mp3_path":  str(mp3_path.absolute()),
            "size_kb":   size_kb,
            "duration_s": round(dur_s, 2),
            "dry_run":   False,
            "ts_ms":     _ms(),
        }

    except Exception as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}


def save_preset(name: str, bpm: float, description: str, steps: list) -> dict:
    """Save a new workflow preset JSON to workflow_presets/."""
    _PRESETS_DIR.mkdir(exist_ok=True)
    path = _PRESETS_DIR / f"{name}.json"
    data = {"bpm": bpm, "description": description, "steps": steps}
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}
    return {"ok": True, "name": name, "path": str(path.absolute()), "steps_count": len(steps), "ts_ms": _ms()}


def delete_track(file: str) -> dict:
    """Delete an MP3 track and its companion JSON from the tracks directory."""
    if "/" in file or "\\" in file:
        return {"ok": False, "error": "file must be a filename, not a path", "ts_ms": _ms()}
    mp3_path = _TRACKS_DIR / file
    if not mp3_path.exists():
        return {"ok": False, "error": f"file {file!r} not found in tracks dir", "ts_ms": _ms()}
    deleted: list[str] = []
    try:
        mp3_path.unlink()
        deleted.append(str(mp3_path.absolute()))
        companion = mp3_path.with_suffix(".json")
        if companion.exists():
            companion.unlink()
            deleted.append(str(companion.absolute()))
    except OSError as exc:
        return {"ok": False, "file": file, "deleted": deleted, "error": str(exc), "ts_ms": _ms()}
    return {"ok": True, "file": file, "deleted": deleted, "ts_ms": _ms()}


def tag_track(file: str, tags: dict) -> dict:
    """Merge metadata tags into a track companion JSON (creates it if missing)."""
    if "/" in file or "\\" in file:
        return {"ok": False, "error": "file must be a filename, not a path", "ts_ms": _ms()}
    mp3_path = _TRACKS_DIR / file
    if not mp3_path.exists():
        return {"ok": False, "error": f"file {file!r} not found in tracks dir", "ts_ms": _ms()}
    companion = mp3_path.with_suffix(".json")
    existing: dict[str, Any] = {}
    if companion.exists():
        try:
            existing = json.loads(companion.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.update(tags)
    try:
        companion.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "file": file, "error": str(exc), "ts_ms": _ms()}
    return {"ok": True, "file": file, "meta": existing, "ts_ms": _ms()}


def export_midi(
    name: str | None = None,
    notes: list | None = None,
    bpm: float = 120.0,
    filename: str | None = None,
) -> dict:
    """Export a workflow preset or note list to a MIDI file.

    Mode 1 (name given): load preset, convert steps to MIDI events.
    Mode 2 (notes given): write note dicts directly.
      Each note dict: {pitch, velocity, at_ms, duration_ms}.
    Saves to tracks/ directory. Requires: mido.
    """
    if name is None and notes is None:
        return {"ok": False, "error": "provide name or notes", "ts_ms": _ms()}
    if name is not None and notes is not None:
        return {"ok": False, "error": "provide name OR notes, not both", "ts_ms": _ms()}
    try:
        import mido
    except ImportError:
        return {"ok": False, "error": "mido not installed (pip install mido)", "ts_ms": _ms()}

    note_events: list[dict[str, Any]] = []
    if name is not None:
        pr = get_preset(name)
        if not pr["ok"]:
            return {"ok": False, "error": pr.get("error", "preset not found"), "ts_ms": _ms()}
        ms_per_beat = 60_000.0 / bpm
        cursor = 0.0
        for step in pr["preset"].get("steps", []):
            dur = float(step.get("duration_ms", ms_per_beat))
            vel = int(min(127, float(step.get("velocity", 1.0)) * 100))
            note_events.append({"pitch": 60, "velocity": vel,
                                 "at_ms": int(cursor + float(step.get("delay_ms", 0))),
                                 "duration_ms": int(dur)})
            cursor += dur
    else:
        note_events = notes or []

    if not note_events:
        return {"ok": False, "error": "no note events to write", "ts_ms": _ms()}

    import datetime as _dt
    tpb = 480
    uspb = int(60_000_000 / bpm)
    mid = mido.MidiFile(ticks_per_beat=tpb)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=uspb, time=0))

    def _to_ticks(ms: float) -> int:
        return int((ms / 1000.0) * (bpm / 60.0) * tpb)

    events: list[tuple] = []
    for n in note_events:
        p, v = int(n.get("pitch", 60)), int(n.get("velocity", 100))
        on_tick  = _to_ticks(float(n.get("at_ms", 0)))
        off_tick = _to_ticks(float(n.get("at_ms", 0)) + float(n.get("duration_ms", 250)))
        events.append((on_tick,  "note_on",  p, v))
        events.append((off_tick, "note_off", p, 0))
    # note_off before note_on at same tick to prevent stuck notes
    events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))
    prev = 0
    for tick, mtype, pitch, vel in events:
        track.append(mido.Message(mtype, note=pitch, velocity=vel, time=tick - prev))
        prev = tick

    _TRACKS_DIR.mkdir(exist_ok=True)
    if filename is None:
        label = name if name else "notes"
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{label}_{ts}.mid"
    midi_path = _TRACKS_DIR / filename
    try:
        mid.save(str(midi_path))
    except OSError as exc:
        return {"ok": False, "error": str(exc), "ts_ms": _ms()}
    dur_s = round(max((n.get("at_ms", 0) + n.get("duration_ms", 0)) for n in note_events) / 1000.0, 3)
    return {"ok": True, "midi_path": str(midi_path.absolute()), "size_kb": round(midi_path.stat().st_size / 1024, 2),
            "note_count": len(note_events), "duration_s": dur_s, "ts_ms": _ms()}
