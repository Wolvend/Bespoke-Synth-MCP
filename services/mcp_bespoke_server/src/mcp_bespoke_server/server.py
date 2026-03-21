from __future__ import annotations

import logging
import time
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from .config import Settings
from .idempotency import IdempotencyCache
from .osc_bridge import OscBridge
from .schemas import (
    ArpeggiateIn,
    ArpeggiateOut,
    AudioAnalyzeIn,
    AudioAnalyzeOut,
    AudioStemsIn,
    AudioStemsOut,
    AutomateIn,
    AutomateOut,
    AutomatePoint,
    BatchSetItem,
    BatchSetIn,
    BatchSetOut,
    ChordIn,
    ChordInfo,
    ChordOut,
    DeleteTrackIn,
    DeleteTrackOut,
    ExportMidiIn,
    ExportMidiOut,
    GetParamIn,
    GetParamOut,
    GetPresetOut,
    HealthOut,
    ListModulesIn,
    ListModulesOut,
    ListPresetsOut,
    ListTracksOut,
    NoteInfo,
    NoteOut,
    PlayNoteIn,
    PresetSummary,
    ProgressionIn,
    ProgressionOut,
    QuantizeIn,
    QuantizeOut,
    RawCommandIn,
    RawCommandOut,
    RenderWorkflowIn,
    RenderWorkflowOut,
    SavePresetIn,
    SavePresetOut,
    ScaleIn,
    ScaleOut,
    ScheduleNoteItem,
    ScheduleNotesIn,
    SetParamIn,
    SetParamOut,
    SnapshotLoadIn,
    TagTrackIn,
    TagTrackOut,
    TelemetryItem,
    TelemetryLastIn,
    TelemetryLastOut,
    TheoryInfoOut,
    TrackSummary,
    TransposeIn,
    TransposeOut,
    TransportSetIn,
    WorkflowStepIn,
)
from . import audio as _audio
from . import compose as _compose
from . import theory as _theory


settings = Settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

mcp = FastMCP("bespokesynth_mcp", stateless_http=True, json_response=True)
osc = OscBridge(
    cmd_host=settings.bespoke_cmd_host,
    cmd_port=settings.bespoke_cmd_port,
    reply_listen_host=settings.reply_listen_host,
    reply_listen_port=settings.reply_listen_port,
    telemetry_listen_host=settings.telemetry_listen_host,
    telemetry_listen_port=settings.telemetry_listen_port,
)
idem: IdempotencyCache[Any] = IdempotencyCache(ttl_seconds=settings.idempotency_ttl_s)


@mcp.custom_route("/healthz", methods=["GET"])  # type: ignore[untyped-decorator]
async def http_healthz(request: Any) -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "service": "bespokesynth_mcp",
            "transport": settings.mcp_transport,
            "ts_ms": _ms(),
        }
    )


@mcp.custom_route("/readyz", methods=["GET"])  # type: ignore[untyped-decorator]
async def http_readyz(request: Any) -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "service": "bespokesynth_mcp",
            "reply_listen_port": settings.reply_listen_port,
            "telemetry_listen_port": settings.telemetry_listen_port,
            "ts_ms": _ms(),
        }
    )


def _ms() -> int:
    return int(time.time() * 1000)


async def _send_with_cache(inp: Any, envelope: dict[str, Any]) -> dict[str, Any]:
    cached = idem.get(getattr(inp, "idempotency_key", None))
    if cached is not None:
        return cast(dict[str, Any], cached)
    if getattr(inp, "dry_run", False):
        reply = {"ok": True, "dry_run": True, "correlation_id": envelope.get("correlation_id")}
    else:
        reply = await osc.send_cmd_and_wait_reply(
            envelope=envelope,
            timeout_ms=settings.osc_reply_timeout_ms,
        )
    idem.put(getattr(inp, "idempotency_key", None), reply)
    return reply


@mcp.tool(name="bespoke.safe.health")
def bespoke_safe_health(ctx: Any = None) -> HealthOut:
    return HealthOut(ok=True, ts_ms=_ms(), server="bespokesynth_mcp")


@mcp.tool(name="bespoke.safe.list_modules")
def bespoke_safe_list_modules(
    prefix: str | None = None,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> ListModulesOut:
    inp = ListModulesIn(
        prefix=prefix,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    modules = settings.known_modules
    if inp.prefix:
        modules = [module for module in modules if module.startswith(inp.prefix)]
    return ListModulesOut(ok=True, modules=modules, source="config", ts_ms=_ms())


@mcp.tool(name="bespoke.safe.get_param")
async def bespoke_safe_get_param(
    path: str,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> GetParamOut:
    inp = GetParamIn(
        path=path,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "get",
            "path": inp.path,
            "idempotency_key": inp.idempotency_key,
        },
    )
    return GetParamOut(
        ok=bool(reply.get("ok")),
        path=inp.path,
        value=reply.get("value"),
        raw_reply=reply,
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.safe.set_param")
async def bespoke_safe_set_param(
    path: str,
    value: Any,
    mode: Literal["immediate", "ramp"] = "immediate",
    ramp_ms: int = 0,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> SetParamOut:
    inp = SetParamIn(
        path=path,
        value=value,
        mode=mode,
        ramp_ms=ramp_ms,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "set",
            "path": inp.path,
            "value": inp.value,
            "mode": inp.mode,
            "ramp_ms": inp.ramp_ms,
            "idempotency_key": inp.idempotency_key,
        },
    )
    return SetParamOut(
        ok=bool(reply.get("ok")),
        applied=bool(reply.get("ok")) and not inp.dry_run,
        path=inp.path,
        value=inp.value,
        raw_reply=reply,
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.safe.batch_set_params")
async def bespoke_safe_batch_set_params(
    ops: list[dict[str, Any]],
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> BatchSetOut:
    inp = BatchSetIn(
        ops=[BatchSetItem.model_validate(op) for op in ops],
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "batch_set",
            "ops": [op.model_dump(exclude_none=True) for op in inp.ops],
            "idempotency_key": inp.idempotency_key,
        },
    )
    return BatchSetOut(
        ok=bool(reply.get("ok")),
        applied=bool(reply.get("ok")) and not inp.dry_run,
        count=len(inp.ops),
        raw_reply=reply,
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.safe.play_note")
async def bespoke_safe_play_note(
    label: str,
    pitch: int,
    velocity: int,
    duration_ms: int = 250,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> NoteOut:
    inp = PlayNoteIn(
        label=label,
        pitch=pitch,
        velocity=velocity,
        duration_ms=duration_ms,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "play_note",
            "label": inp.label,
            "pitch": inp.pitch,
            "velocity": inp.velocity,
            "duration_ms": inp.duration_ms,
            "idempotency_key": inp.idempotency_key,
        },
    )
    return NoteOut(
        ok=bool(reply.get("ok")),
        applied=bool(reply.get("ok")) and not inp.dry_run,
        count=1,
        raw_reply=reply,
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.safe.schedule_notes")
async def bespoke_safe_schedule_notes(
    notes: list[dict[str, Any]],
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> NoteOut:
    inp = ScheduleNotesIn(
        notes=[ScheduleNoteItem.model_validate(note) for note in notes],
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "schedule_notes",
            "notes": [note.model_dump() for note in inp.notes],
            "idempotency_key": inp.idempotency_key,
        },
    )
    return NoteOut(
        ok=bool(reply.get("ok")),
        applied=bool(reply.get("ok")) and not inp.dry_run,
        count=len(inp.notes),
        raw_reply=reply,
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.safe.transport_set")
async def bespoke_safe_transport_set(
    playing: bool,
    bpm: float | None = None,
    beat: int | None = None,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> RawCommandOut:
    inp = TransportSetIn(
        playing=playing,
        bpm=bpm,
        beat=beat,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "transport_set",
            "playing": inp.playing,
            "bpm": inp.bpm,
            "beat": inp.beat,
            "idempotency_key": inp.idempotency_key,
        },
    )
    return RawCommandOut(ok=bool(reply.get("ok")), raw_reply=reply, ts_ms=_ms())


@mcp.tool(name="bespoke.safe.snapshot_load")
async def bespoke_safe_snapshot_load(
    name: str,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> RawCommandOut:
    inp = SnapshotLoadIn(
        name=name,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    reply = await _send_with_cache(
        inp,
        {
            "op": "snapshot_load",
            "name": inp.name,
            "idempotency_key": inp.idempotency_key,
        },
    )
    return RawCommandOut(ok=bool(reply.get("ok")), raw_reply=reply, ts_ms=_ms())


@mcp.tool(name="bespoke.safe.telemetry_last")
def bespoke_safe_telemetry_last(
    limit: int = 20,
    prefix: str | None = None,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> TelemetryLastOut:
    inp = TelemetryLastIn(
        limit=limit,
        prefix=prefix,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    items = [
        TelemetryItem.model_validate(item)
        for item in osc.telemetry_last(limit=inp.limit, prefix=inp.prefix)
    ]
    return TelemetryLastOut(ok=True, items=items, ts_ms=_ms())


@mcp.tool(name="bespoke.admin.raw_command")
async def bespoke_admin_raw_command(
    op: str,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> RawCommandOut:
    inp = RawCommandIn(
        op=op,
        payload=payload or {},
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )
    if not settings.allow_admin_tools:
        raise ValueError("Admin tools are disabled. Set ALLOW_ADMIN_TOOLS=true to enable them.")
    reply = await _send_with_cache(
        inp,
        {
            "op": inp.op,
            **inp.payload,
            "idempotency_key": inp.idempotency_key,
        },
    )
    return RawCommandOut(ok=bool(reply.get("ok")), raw_reply=reply, ts_ms=_ms())


# ─── bespoke.theory tools ─────────────────────────────────────────────────────

@mcp.tool(name="bespoke.theory.info")
def bespoke_theory_info(ctx: Any = None) -> TheoryInfoOut:
    """List all available scale modes and chord types."""
    return TheoryInfoOut(
        ok=True,
        modes=_theory.list_modes(),
        chord_types=_theory.list_chord_types(),
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.theory.scale")
def bespoke_theory_scale(
    root: str,
    mode: str = "major",
    octave: int = 4,
    num_octaves: int = 1,
    ctx: Any = None,
) -> ScaleOut:
    """
    Return every note in a scale with MIDI numbers and frequencies.

    Example: root="G", mode="major" → G4 A4 B4 C5 D5 E5 F#5 G5
    Supported modes: major, minor, dorian, phrygian, lydian, mixolydian,
      locrian, harmonic_minor, melodic_minor, pentatonic_major,
      pentatonic_minor, blues, whole_tone, diminished, chromatic.
    """
    inp = ScaleIn(root=root, mode=mode, octave=octave, num_octaves=num_octaves)
    try:
        result = _theory.get_scale(inp.root, inp.mode, inp.octave, inp.num_octaves)  # type: ignore[arg-type]
    except (ValueError, KeyError) as exc:
        return ScaleOut(ok=False, root=root, mode=mode, octave=octave,
                        num_notes=0, notes=[], ts_ms=_ms())
    return ScaleOut(
        ok=True,
        root=result["root"],
        mode=result["mode"],
        octave=result["octave"],
        num_notes=result["num_notes"],
        notes=[NoteInfo(**n) for n in result["notes"]],
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.theory.chord")
def bespoke_theory_chord(
    root: str,
    chord_type: str = "maj",
    octave: int = 4,
    inversion: int = 0,
    ctx: Any = None,
) -> ChordOut:
    """
    Return the notes in a chord voicing with MIDI numbers and frequencies.

    Example: root="C", chord_type="maj7", octave=4 → C4 E4 G4 B4
    Supported types: maj, min, dim, aug, maj7, min7, dom7, dim7,
      half_dim7, sus2, sus4, add9, maj9, min9.
    """
    inp = ChordIn(root=root, chord_type=chord_type, octave=octave, inversion=inversion)
    try:
        result = _theory.get_chord(inp.root, inp.chord_type, inp.octave, inp.inversion)  # type: ignore[arg-type]
    except (ValueError, KeyError):
        return ChordOut(ok=False, root=root, type=chord_type, octave=octave,
                        inversion=inversion, num_notes=0, notes=[], ts_ms=_ms())
    return ChordOut(
        ok=True,
        root=result["root"],
        type=result["type"],
        octave=result["octave"],
        inversion=result["inversion"],
        num_notes=result["num_notes"],
        notes=[NoteInfo(**n) for n in result["notes"]],
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.theory.transpose")
def bespoke_theory_transpose(
    notes: list[dict[str, Any]],
    semitones: int,
    ctx: Any = None,
) -> TransposeOut:
    """
    Shift a list of notes up or down by semitones.

    notes: list of {name, midi, freq_hz} dicts (e.g. from bespoke.theory.scale).
    semitones: +12 = up one octave, -12 = down one octave.
    """
    inp = TransposeIn(notes=[NoteInfo(**n) for n in notes], semitones=semitones)
    shifted = _theory.transpose([n.model_dump() for n in inp.notes], inp.semitones)
    return TransposeOut(
        ok=True,
        semitones=inp.semitones,
        notes=[NoteInfo(**n) for n in shifted],
        ts_ms=_ms(),
    )


# ─── bespoke.compose tools ────────────────────────────────────────────────────

@mcp.tool(name="bespoke.compose.list_presets")
def bespoke_compose_list_presets(ctx: Any = None) -> ListPresetsOut:
    """List all saved workflow presets available to render."""
    result = _compose.list_presets()
    return ListPresetsOut(
        ok=result["ok"],
        presets=[PresetSummary(**p) for p in result["presets"]],
        count=result["count"],
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="bespoke.compose.get_preset")
def bespoke_compose_get_preset(
    name: str,
    ctx: Any = None,
) -> GetPresetOut:
    """Return the full step-by-step definition of a named workflow preset."""
    result = _compose.get_preset(name)
    return GetPresetOut(
        ok=result["ok"],
        name=result.get("name"),
        preset=result.get("preset"),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="bespoke.compose.list_tracks")
def bespoke_compose_list_tracks(
    limit: int = 20,
    ctx: Any = None,
) -> ListTracksOut:
    """List recently generated MP3 tracks with file paths and metadata."""
    result = _compose.list_tracks(limit=limit)
    return ListTracksOut(
        ok=result["ok"],
        tracks=[TrackSummary(**t) for t in result["tracks"]],
        count=result["count"],
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="bespoke.compose.render_workflow")
def bespoke_compose_render_workflow(
    name: str,
    dry_run: bool = False,
    ctx: Any = None,
) -> RenderWorkflowOut:
    """
    Render a saved workflow preset to an MP3 file.

    Args:
        name:    Preset name, e.g. "breakcore_brainworm". Use
                 bespoke.compose.list_presets to see available names.
        dry_run: Validate only — do not write audio.

    Returns the absolute path to the generated MP3 and its duration.
    """
    inp = RenderWorkflowIn(name=name, dry_run=dry_run)
    result = _compose.render_workflow(inp.name, inp.dry_run)
    return RenderWorkflowOut(
        ok=result["ok"],
        name=inp.name,
        mp3_path=result.get("mp3_path"),
        size_kb=result.get("size_kb"),
        duration_s=result.get("duration_s"),
        dry_run=result.get("dry_run", False),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


# ─── bespoke.theory extension tools ──────────────────────────────────────────

@mcp.tool(name="bespoke.theory.quantize")
def bespoke_theory_quantize(
    freq_hz: float,
    root: str,
    mode: str = "major",
    ctx: Any = None,
) -> QuantizeOut:
    """
    Snap a free frequency to the nearest note in a scale.

    Args:
        freq_hz: Input frequency in Hz to quantize.
        root: Scale root note, e.g. "C", "F#", "Bb".
        mode: Scale mode (default: major).

    Returns the closest scale note and how many cents off the input was.
    """
    inp = QuantizeIn(freq_hz=freq_hz, root=root, mode=mode)
    try:
        result = _theory.quantize_to_scale(inp.freq_hz, inp.root, inp.mode)  # type: ignore[arg-type]
    except (ValueError, KeyError) as exc:
        return QuantizeOut(
            ok=False,
            input_freq_hz=inp.freq_hz,
            quantized=NoteInfo(name="", midi=0, freq_hz=0.0),
            cents_deviation=0.0,
            ts_ms=_ms(),
        )
    return QuantizeOut(
        ok=True,
        input_freq_hz=result["input_freq_hz"],
        quantized=NoteInfo(**result["quantized"]),
        cents_deviation=result["cents_deviation"],
        ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.theory.progression")
def bespoke_theory_progression(
    root: str,
    mode: str = "major",
    pattern: str = "I-IV-V-I",
    octave: int = 4,
    ctx: Any = None,
) -> ProgressionOut:
    """
    Generate a chord progression from Roman numeral notation.

    Args:
        root: Root note, e.g. "C", "F#", "Bb".
        mode: Diatonic mode (major, minor, dorian, phrygian, lydian,
              mixolydian, locrian, harmonic_minor, melodic_minor).
        pattern: Dash-separated Roman numerals, e.g. "I-IV-V-I", "ii-V-I".
        octave: Octave for chord voicing.

    Returns each chord's root, type, and MIDI notes.
    """
    inp = ProgressionIn(root=root, mode=mode, pattern=pattern, octave=octave)
    try:
        result = _theory.progression(inp.root, inp.mode, inp.pattern, inp.octave)
    except (ValueError, KeyError) as exc:
        return ProgressionOut(
            ok=False, root=root, mode=mode, pattern=pattern,
            chords=[], error=str(exc), ts_ms=_ms(),
        )
    chords = [
        ChordInfo(
            degree=c["degree"],
            roman=c["roman"],
            root=c["root"],
            type=c["type"],
            notes=[NoteInfo(**n) for n in c["notes"]],
        )
        for c in result["chords"]
    ]
    return ProgressionOut(
        ok=True, root=result["root"], mode=result["mode"],
        pattern=result["pattern"], chords=chords, ts_ms=_ms(),
    )


@mcp.tool(name="bespoke.theory.arpeggiate")
def bespoke_theory_arpeggiate(
    root: str,
    chord_type: str = "maj",
    octave: int = 4,
    pattern: str = "up",
    subdivision: str = "16th",
    bpm: float = 120.0,
    bars: int = 1,
    velocity: int = 100,
    ctx: Any = None,
) -> ArpeggiateOut:
    """
    Expand a chord into a timed note sequence ready for bespoke.safe.schedule_notes.

    Args:
        root: Root note name.
        chord_type: Chord quality (maj, min, dim, aug, etc.).
        octave: Root octave.
        pattern: up | down | updown | random
        subdivision: 8th | 16th | triplet
        bpm: Beats per minute.
        bars: Number of bars (4/4 time).
        velocity: MIDI velocity 0-127.

    Returns a list of timed note dicts with label, pitch, velocity, at_ms, duration_ms.
    """
    inp = ArpeggiateIn(
        root=root, chord_type=chord_type, octave=octave, pattern=pattern,  # type: ignore[arg-type]
        subdivision=subdivision, bpm=bpm, bars=bars, velocity=velocity,  # type: ignore[arg-type]
    )
    try:
        result = _theory.arpeggiate(
            inp.root, inp.chord_type, inp.octave, inp.pattern,
            inp.subdivision, inp.bpm, inp.bars, inp.velocity,
        )
    except (ValueError, KeyError) as exc:
        return ArpeggiateOut(
            ok=False, root=root, chord_type=chord_type, pattern=pattern,
            note_count=0, notes=[], error=str(exc), ts_ms=_ms(),
        )
    return ArpeggiateOut(
        ok=True,
        root=result["root"],
        chord_type=result["chord_type"],
        pattern=result["pattern"],
        note_count=result["note_count"],
        notes=[ScheduleNoteItem(**n) for n in result["notes"]],
        ts_ms=_ms(),
    )


# ─── bespoke.compose management tools ────────────────────────────────────────

@mcp.tool(name="bespoke.compose.save_preset")
def bespoke_compose_save_preset(
    name: str,
    bpm: float,
    steps: list[dict[str, Any]],
    description: str = "",
    ctx: Any = None,
) -> SavePresetOut:
    """
    Save a new workflow preset to workflow_presets/.

    Args:
        name: Preset name (alphanumeric + hyphens/underscores).
        bpm: Tempo for the workflow.
        steps: List of step dicts with keys: preset, duration_ms, delay_ms, velocity.
        description: Optional human-readable description.
    """
    inp = SavePresetIn(
        name=name, bpm=bpm, description=description,
        steps=[WorkflowStepIn.model_validate(s) for s in steps],
    )
    result = _compose.save_preset(
        inp.name, inp.bpm, inp.description,
        [s.model_dump() for s in inp.steps],
    )
    return SavePresetOut(
        ok=result["ok"],
        name=result.get("name", name),
        path=result.get("path", ""),
        steps_count=result.get("steps_count", 0),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="bespoke.compose.delete_track")
def bespoke_compose_delete_track(
    file: str,
    ctx: Any = None,
) -> DeleteTrackOut:
    """
    Delete an MP3 track (and its companion JSON) from the tracks directory.

    Args:
        file: Filename only (no path separators), e.g. "track_20260320.mp3".
    """
    inp = DeleteTrackIn(file=file)
    result = _compose.delete_track(inp.file)
    return DeleteTrackOut(
        ok=result["ok"],
        file=result.get("file", file),
        deleted=result.get("deleted", []),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="bespoke.compose.tag_track")
def bespoke_compose_tag_track(
    file: str,
    tags: dict[str, Any],
    ctx: Any = None,
) -> TagTrackOut:
    """
    Merge metadata tags into a track's companion JSON file.

    Args:
        file: Filename only (no path separators), e.g. "track_20260320.mp3".
        tags: Key-value pairs to merge into the companion JSON (shallow merge).
    """
    inp = TagTrackIn(file=file, tags=tags)
    result = _compose.tag_track(inp.file, inp.tags)
    return TagTrackOut(
        ok=result["ok"],
        file=result.get("file", file),
        meta=result.get("meta", {}),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="compose.export_midi")
def compose_export_midi(
    name: str | None = None,
    notes: list[dict[str, Any]] | None = None,
    bpm: float = 120.0,
    filename: str | None = None,
    ctx: Any = None,
) -> ExportMidiOut:
    """
    Export a workflow preset or note list to a MIDI file.

    Mode 1 — preset: provide name, omit notes.
    Mode 2 — notes: provide notes list, omit name.
      Each note dict: {pitch, velocity, at_ms, duration_ms}.

    Args:
        name:     Preset name to convert to MIDI.
        notes:    Direct note list (alternative to name).
        bpm:      Tempo (used for ticks-per-beat calculation).
        filename: Output filename (auto-generated if omitted).

    Requires: mido (pip install mido).
    """
    inp = ExportMidiIn(name=name, notes=notes, bpm=bpm, filename=filename)
    result = _compose.export_midi(inp.name, inp.notes, inp.bpm, inp.filename)
    return ExportMidiOut(
        ok=result["ok"],
        midi_path=result.get("midi_path"),
        size_kb=result.get("size_kb"),
        note_count=result.get("note_count"),
        duration_s=result.get("duration_s"),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


# ─── bespoke.safe.automate tool ───────────────────────────────────────────────

@mcp.tool(name="bespoke.safe.automate")
async def bespoke_safe_automate(
    path: str,
    start_value: float | None = None,
    end_value: float | None = None,
    duration_ms: int | None = None,
    steps: int = 16,
    curve: str = "linear",
    points: list[dict[str, Any]] | None = None,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
    ctx: Any = None,
) -> AutomateOut:
    """
    Automate a parameter by sending a batch of interpolated set-param messages.

    Two modes:
    - Linear/exp/log ramp: provide start_value, end_value, duration_ms.
    - Explicit points:     provide points=[{value, at_ms}, ...].

    Args:
        path:         Module parameter path (e.g. "synth/oscVolume").
        start_value:  Start value for ramp mode.
        end_value:    End value for ramp mode.
        duration_ms:  Total ramp duration in ms.
        steps:        Number of interpolation steps (default 16).
        curve:        linear | exp | log
        points:       Explicit list of {value, at_ms} dicts.
        dry_run:      Validate only — do not send OSC commands.
    """
    import math as _math
    inp = AutomateIn(
        path=path,
        start_value=start_value,
        end_value=end_value,
        duration_ms=duration_ms,
        steps=steps,
        curve=curve,  # type: ignore[arg-type]
        points=[AutomatePoint.model_validate(p) for p in points] if points else None,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        request_ts_ms=request_ts_ms,
        session_id=session_id,
    )

    # Build point list
    if inp.points is not None:
        pt_list = inp.points
    elif inp.start_value is not None and inp.end_value is not None and inp.duration_ms is not None:
        pt_list = []
        for i in range(inp.steps):
            t = i / (inp.steps - 1)
            if inp.curve == "exp":
                t = t ** 2
            elif inp.curve == "log":
                t = _math.log1p(t * (2.718281828 - 1)) / 1.0
            val = inp.start_value + t * (inp.end_value - inp.start_value)
            at_ms = int(i * inp.duration_ms / (inp.steps - 1))
            pt_list.append(AutomatePoint(value=round(val, 6), at_ms=at_ms))
    else:
        return AutomateOut(
            ok=False, applied=False, path=path, points_sent=0,
            error="Provide either points or (start_value, end_value, duration_ms)",
            ts_ms=_ms(),
        )

    ops = [BatchSetItem(path=inp.path, value=pt.value, at_ms=pt.at_ms) for pt in pt_list]
    batch_inp = BatchSetIn(
        ops=ops,
        idempotency_key=inp.idempotency_key,
        dry_run=inp.dry_run,
        request_ts_ms=inp.request_ts_ms,
        session_id=inp.session_id,
    )
    reply = await _send_with_cache(
        batch_inp,
        {
            "op": "batch_set",
            "ops": [op.model_dump(exclude_none=True) for op in ops],
            "idempotency_key": inp.idempotency_key,
        },
    )
    return AutomateOut(
        ok=bool(reply.get("ok")),
        applied=bool(reply.get("ok")) and not inp.dry_run,
        path=inp.path,
        points_sent=len(pt_list),
        raw_reply=reply,
        ts_ms=_ms(),
    )


# ─── audio tools ──────────────────────────────────────────────────────────────

@mcp.tool(name="audio.analyze")
def audio_analyze(
    file: str,
    analyze_bpm: bool = True,
    analyze_key: bool = True,
    analyze_loudness: bool = True,
    ctx: Any = None,
) -> AudioAnalyzeOut:
    """
    Analyze an audio file for BPM, musical key, and integrated loudness (LUFS).

    Args:
        file:             Filename in tracks/ dir OR absolute path.
        analyze_bpm:      Detect tempo via onset autocorrelation.
        analyze_key:      Detect key via Krumhansl-Schmuckler chromagram.
        analyze_loudness: Measure LUFS (requires pyloudnorm + soundfile).

    Returns bpm, bpm_confidence, key, key_confidence, loudness_lufs, duration_s.
    Requires: scipy, pydub (BPM/key); pyloudnorm, soundfile (LUFS).
    """
    inp = AudioAnalyzeIn(
        file=file, analyze_bpm=analyze_bpm,
        analyze_key=analyze_key, analyze_loudness=analyze_loudness,
    )
    result = _audio.analyze(inp.file, inp.analyze_bpm, inp.analyze_key, inp.analyze_loudness)
    return AudioAnalyzeOut(
        ok=result["ok"],
        file=result.get("file", file),
        duration_s=result.get("duration_s"),
        bpm=result.get("bpm"),
        bpm_confidence=result.get("bpm_confidence"),
        key=result.get("key"),
        key_confidence=result.get("key_confidence"),
        loudness_lufs=result.get("loudness_lufs"),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


@mcp.tool(name="audio.stems")
def audio_stems(
    file: str,
    stems: list[str] | None = None,
    ctx: Any = None,
) -> AudioStemsOut:
    """
    Separate an audio file into instrument stems using demucs (htdemucs model).

    Args:
        file:  Filename in tracks/ dir OR absolute path.
        stems: Subset of ["vocals", "drums", "bass", "other"]. Default: all four.

    Returns paths to each separated WAV file under tracks/stems/<trackname>/.
    NOTE: Slow on CPU (minutes). Downloads ~2GB htdemucs model on first call.
    Requires: demucs, torch, torchaudio.
    """
    stem_types = stems if stems is not None else ["vocals", "drums", "bass", "other"]
    inp = AudioStemsIn(file=file, stems=stem_types)  # type: ignore[arg-type]
    result = _audio.stems(inp.file, list(inp.stems))
    return AudioStemsOut(
        ok=result["ok"],
        file=result.get("file", file),
        stems=result.get("stems", {}),
        model=result.get("model"),
        error=result.get("error"),
        ts_ms=result["ts_ms"],
    )


def create_http_app() -> Any:
    app = mcp.streamable_http_app()
    return app


def main_stdio() -> None:
    mcp.run()


def main_http() -> None:
    import uvicorn

    uvicorn.run(
        create_http_app(),
        host=settings.mcp_http_host,
        port=settings.mcp_http_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    if settings.mcp_transport == "streamable-http":
        main_http()
    else:
        main_stdio()
