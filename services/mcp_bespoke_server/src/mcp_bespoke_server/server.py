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
    # --- new tools (30-44) ---
    AudioConvertIn,
    AudioConvertOut,
    AudioNormalizeIn,
    AudioNormalizeOut,
    AudioSpliceIn,
    AudioSpliceOut,
    AudioTrimIn,
    AudioTrimOut,
    DetectChordIn,
    DetectChordOut,
    ExportWavIn,
    ExportWavOut,
    GenerateSequenceIn,
    GenerateSequenceOut,
    GetAllParamsIn,
    GetAllParamsOut,
    HumanizeIn,
    HumanizeOut,
    ListSnapshotsOut,
    MidiCcIn,
    MidiCcOut,
    ModulateIn,
    ModulateOut,
    PivotChord,
    RhythmIn,
    RhythmOut,
    SaveSnapshotIn,
    VoiceLeadIn,
    VoiceLeadOut,
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




# ===========================================================================
# Tools 30-44 (new batch)
# ===========================================================================

# ---------------------------------------------------------------------------
# 30. bespoke.theory.detect_chord
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.theory.detect_chord")
def theory_detect_chord(pitches: list[int]) -> DetectChordOut:
    """
    Identify the most likely chord name from a list of MIDI pitch numbers.

    Args:
        pitches: 2-12 MIDI pitch values (e.g. [60, 64, 67] for C major).

    Returns root, chord_type, inversion, confidence score, and notes_matched.
    """
    inp = DetectChordIn(pitches=pitches)
    r = _theory.detect_chord(list(inp.pitches))
    return DetectChordOut(
        ok=r["ok"],
        root=r["root"],
        chord_type=r["chord_type"],
        inversion=r["inversion"],
        confidence=r["confidence"],
        notes_matched=r["notes_matched"],
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 31. bespoke.theory.rhythm
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.theory.rhythm")
def theory_rhythm(
    hits: int,
    steps: int,
    pitch: int = 60,
    velocity: int = 100,
    bpm: float = 120.0,
    subdivision: str = "16th",
    bars: int = 1,
    offset: int = 0,
) -> RhythmOut:
    """
    Generate a Euclidean rhythm pattern using the Bjorklund algorithm.

    Args:
        hits:        Number of hit events (1-64).
        steps:       Total steps in the cycle (2-64, must be >= hits).
        pitch:       MIDI pitch for each hit (0-127).
        velocity:    MIDI velocity (0-127).
        bpm:         Tempo in BPM.
        subdivision: Grid size -- "8th", "16th", or "triplet".
        bars:        Number of bars to generate (1-16).
        offset:      Rotate pattern start by N steps (0-63).

    Returns pattern string ("x"=hit, "."=rest), note list ready for
    bespoke.safe.schedule_notes, hit count, and step count.
    """
    inp = RhythmIn(
        hits=hits, steps=steps, pitch=pitch, velocity=velocity,
        bpm=bpm, subdivision=subdivision, bars=bars, offset=offset,
    )
    r = _theory.rhythm(
        inp.hits, inp.steps, inp.pitch, inp.velocity,
        inp.bpm, inp.subdivision, inp.bars, inp.offset,
    )
    return RhythmOut(
        ok=r["ok"],
        hits=r["hits"],
        steps=r["steps"],
        pattern=r["pattern"],
        note_count=r["note_count"],
        notes=[ScheduleNoteItem(**n) for n in r["notes"]],
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 32. bespoke.theory.voice_lead
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.theory.voice_lead")
def theory_voice_lead(
    from_notes: list[dict],
    to_root: str,
    to_chord_type: str = "maj",
) -> VoiceLeadOut:
    """
    Find the voicing of a target chord that minimises total semitone movement
    from the source chord notes.

    Args:
        from_notes:    List of {name, midi, freq_hz} dicts (source chord).
        to_root:       Root note of the target chord (e.g. "G").
        to_chord_type: Chord quality of the target (e.g. "maj", "min7").

    Returns from_notes, to_notes, and total_movement_semitones.
    """
    inp = VoiceLeadIn(
        from_notes=[NoteInfo(**n) for n in from_notes],
        to_root=to_root,
        to_chord_type=to_chord_type,
    )
    r = _theory.voice_lead(
        [n.model_dump() for n in inp.from_notes],
        inp.to_root,
        inp.to_chord_type,
    )
    return VoiceLeadOut(
        ok=r["ok"],
        from_notes=[NoteInfo(**n) for n in r["from_notes"]],
        to_notes=[NoteInfo(**n) for n in r["to_notes"]],
        total_movement_semitones=r["total_movement_semitones"],
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 33. bespoke.theory.modulate
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.theory.modulate")
def theory_modulate(
    from_root: str,
    from_mode: str = "major",
    to_root: str = "G",
    to_mode: str = "major",
) -> ModulateOut:
    """
    Find pivot chords shared between two diatonic keys to facilitate smooth
    modulation.

    Args:
        from_root: Root note of the source key (e.g. "C").
        from_mode: Mode of the source key (e.g. "major").
        to_root:   Root note of the target key (e.g. "G").
        to_mode:   Mode of the target key (e.g. "major").

    Returns a list of pivot chords with their Roman numeral label in each key.
    """
    inp = ModulateIn(
        from_root=from_root, from_mode=from_mode,
        to_root=to_root, to_mode=to_mode,
    )
    r = _theory.modulate(inp.from_root, inp.from_mode, inp.to_root, inp.to_mode)
    return ModulateOut(
        ok=r["ok"],
        from_key=r["from_key"],
        to_key=r["to_key"],
        pivot_chords=[PivotChord(**p) for p in r["pivot_chords"]],
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 34. compose.humanize
# ---------------------------------------------------------------------------

@mcp.tool(name="compose.humanize")
def compose_humanize(
    notes: list[dict],
    timing_ms: float = 10.0,
    velocity_pct: float = 0.05,
    seed: int | None = None,
) -> HumanizeOut:
    """
    Add random timing jitter and velocity variation to a note list to make it
    sound more human.

    Args:
        notes:        List of note dicts with at_ms and velocity fields.
        timing_ms:    Max timing shift in milliseconds (+/-), 0-100.
        velocity_pct: Max velocity change as a fraction (0-0.5).
        seed:         Optional random seed for reproducibility.

    Returns the modified note list with the same length as the input.
    """
    inp = HumanizeIn(
        notes=[ScheduleNoteItem(**n) for n in notes],
        timing_ms=timing_ms,
        velocity_pct=velocity_pct,
        seed=seed,
    )
    r = _compose.humanize(
        [n.model_dump() for n in inp.notes],
        inp.timing_ms,
        inp.velocity_pct,
        inp.seed,
    )
    return HumanizeOut(
        ok=r["ok"],
        note_count=r["note_count"],
        notes=[ScheduleNoteItem(**n) for n in r["notes"]],
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 35. compose.generate_sequence
# ---------------------------------------------------------------------------

@mcp.tool(name="compose.generate_sequence")
def compose_generate_sequence(
    root: str,
    mode: str = "major",
    octave: int = 4,
    num_octaves: int = 1,
    length: int = 16,
    bpm: float = 120.0,
    subdivision: str = "16th",
    velocity_min: int = 60,
    velocity_max: int = 100,
    rest_probability: float = 0.0,
    seed: int | None = None,
) -> GenerateSequenceOut:
    """
    Generate a random melodic sequence within a scale, ready for
    bespoke.safe.schedule_notes.

    Args:
        root:             Scale root note (e.g. "C").
        mode:             Scale mode (e.g. "major", "dorian").
        octave:           Starting octave (default 4).
        num_octaves:      Number of octaves to draw notes from (1-4).
        length:           Number of time slots (1-256).
        bpm:              Tempo.
        subdivision:      Note grid -- "8th", "16th", or "triplet".
        velocity_min:     Minimum MIDI velocity (0-127).
        velocity_max:     Maximum MIDI velocity (0-127).
        rest_probability: Probability each slot is a rest (0.0-1.0).
        seed:             Optional random seed.

    Returns root, mode, length, note_count, and notes list.
    """
    inp = GenerateSequenceIn(
        root=root, mode=mode, octave=octave, num_octaves=num_octaves,
        length=length, bpm=bpm, subdivision=subdivision,
        velocity_min=velocity_min, velocity_max=velocity_max,
        rest_probability=rest_probability, seed=seed,
    )
    r = _compose.generate_sequence(
        inp.root, inp.mode, inp.octave, inp.num_octaves,
        inp.length, inp.bpm, inp.subdivision,
        inp.velocity_min, inp.velocity_max, inp.rest_probability, inp.seed,
    )
    return GenerateSequenceOut(
        ok=r["ok"],
        root=r["root"],
        mode=r["mode"],
        length=r["length"],
        note_count=r["note_count"],
        notes=[ScheduleNoteItem(**n) for n in r["notes"]],
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 36. compose.export_wav
# ---------------------------------------------------------------------------

@mcp.tool(name="compose.export_wav")
def compose_export_wav(name: str, dry_run: bool = False) -> ExportWavOut:
    """
    Export a workflow preset to a lossless WAV file.

    Args:
        name:    Preset name (without .json extension).
        dry_run: Validate only, do not write audio.

    Returns wav_path, size_kb, and duration_s.
    Requires: soundfile, numpy.
    """
    inp = ExportWavIn(name=name, dry_run=dry_run)
    r = _compose.export_wav(inp.name, inp.dry_run)
    return ExportWavOut(
        ok=r["ok"],
        name=r.get("name", name),
        wav_path=r.get("wav_path"),
        size_kb=r.get("size_kb"),
        duration_s=r.get("duration_s"),
        dry_run=r.get("dry_run", dry_run),
        error=r.get("error"),
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 37. bespoke.safe.midi_cc
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.safe.midi_cc")
async def bespoke_midi_cc(
    cc: int,
    value: int,
    channel: int = 0,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
) -> MidiCcOut:
    """
    Send a MIDI Control Change (CC) message to BespokeSynth via OSC.

    Args:
        cc:      Controller number (0-127).
        value:   Controller value (0-127).
        channel: MIDI channel (0-15, default 0).

    Returns ok and applied status.
    """
    inp = MidiCcIn(
        cc=cc, value=value, channel=channel,
        idempotency_key=idempotency_key, dry_run=dry_run,
        request_ts_ms=request_ts_ms, session_id=session_id,
    )
    envelope = {"op": "midi_cc", "channel": inp.channel, "cc": inp.cc, "value": inp.value}
    result = await _send_with_cache(inp, envelope)
    return MidiCcOut(
        ok=result["ok"],
        applied=result.get("applied", False),
        raw_reply=result.get("raw_reply"),
        ts_ms=result.get("ts_ms", _ms()),
    )


# ---------------------------------------------------------------------------
# 38. bespoke.safe.save_snapshot
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.safe.save_snapshot")
async def bespoke_save_snapshot(
    name: str,
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
) -> RawCommandOut:
    """
    Save the current BespokeSynth state as a named snapshot via OSC.

    Args:
        name: Snapshot name (1-128 chars, alphanumeric/hyphens/underscores).

    Returns ok and applied status.
    """
    inp = SaveSnapshotIn(
        name=name,
        idempotency_key=idempotency_key, dry_run=dry_run,
        request_ts_ms=request_ts_ms, session_id=session_id,
    )
    envelope = {"op": "snapshot_save", "name": inp.name}
    result = await _send_with_cache(inp, envelope)
    return RawCommandOut(
        ok=result["ok"],
        raw_reply=result.get("raw_reply"),
        ts_ms=result.get("ts_ms", _ms()),
    )


# ---------------------------------------------------------------------------
# 39. bespoke.safe.list_snapshots
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.safe.list_snapshots")
def bespoke_list_snapshots() -> ListSnapshotsOut:
    """
    List available BespokeSynth snapshots (.bsk files) from the configured
    snapshots directory (BESPOKE_SNAPSHOTS_DIR env var).

    Returns a list of snapshot names (without extension) and total count.
    """
    import pathlib as _pl
    ts_ms = int(time.time() * 1000)
    snap_dir = settings.bespoke_snapshots_dir.strip()
    if not snap_dir:
        return ListSnapshotsOut(ok=True, snapshots=[], count=0,
                                error="BESPOKE_SNAPSHOTS_DIR not configured", ts_ms=ts_ms)
    p = _pl.Path(snap_dir)
    if not p.is_dir():
        return ListSnapshotsOut(ok=True, snapshots=[], count=0,
                                error=f"Directory not found: {snap_dir}", ts_ms=ts_ms)
    snaps = sorted(f.stem for f in p.glob("*.bsk"))
    return ListSnapshotsOut(ok=True, snapshots=snaps, count=len(snaps), ts_ms=ts_ms)


# ---------------------------------------------------------------------------
# 40. bespoke.safe.get_all_params
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.safe.get_all_params")
async def bespoke_get_all_params(
    paths: list[str],
    idempotency_key: str | None = None,
    dry_run: bool = False,
    request_ts_ms: int | None = None,
    session_id: str | None = None,
) -> GetAllParamsOut:
    """
    Read multiple module parameter values in a single batch request.

    Args:
        paths: List of 1-100 parameter paths (e.g. ["filter~cutoff", "osc~freq"]).

    Returns a params dict {path: value} and an errors dict {path: error_msg}.
    """
    inp = GetAllParamsIn(
        paths=paths,
        idempotency_key=idempotency_key, dry_run=dry_run,
        request_ts_ms=request_ts_ms, session_id=session_id,
    )
    ts_ms = int(time.time() * 1000)
    params: dict = {}
    errors: dict = {}
    for path in inp.paths:
        try:
            from .schemas import GetParamIn as _GPI
            sub_inp = _GPI(path=path)
            envelope = {"op": "get_param", "path": path}
            result = await _send_with_cache(sub_inp, envelope)
            if result.get("ok"):
                params[path] = result.get("value")
            else:
                errors[path] = result.get("error", "unknown error")
        except Exception as exc:
            errors[path] = str(exc)
    return GetAllParamsOut(ok=True, params=params, errors=errors, ts_ms=ts_ms)


# ---------------------------------------------------------------------------
# 41. audio.normalize
# ---------------------------------------------------------------------------

@mcp.tool(name="audio.normalize")
def audio_normalize(
    file: str,
    target_lufs: float = -14.0,
    output_file: str | None = None,
) -> AudioNormalizeOut:
    """
    Normalize an audio file to a target loudness (LUFS) using pyloudnorm.

    Args:
        file:        Filename in tracks/ dir or absolute path.
        target_lufs: Target integrated loudness in LUFS (-60 to -1, default -14).
        output_file: Output filename (auto-generated if omitted).

    Returns input_lufs, gain_db, and output path.
    Requires: pyloudnorm, soundfile, pydub.
    """
    inp = AudioNormalizeIn(file=file, target_lufs=target_lufs, output_file=output_file)
    r = _audio.normalize(inp.file, inp.target_lufs, inp.output_file)
    return AudioNormalizeOut(
        ok=r["ok"],
        file=r.get("file"),
        input_lufs=r.get("input_lufs"),
        target_lufs=r.get("target_lufs"),
        gain_db=r.get("gain_db"),
        error=r.get("error"),
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 42. audio.trim
# ---------------------------------------------------------------------------

@mcp.tool(name="audio.trim")
def audio_trim(
    file: str,
    silence_thresh_db: float = -40.0,
    padding_ms: int = 100,
    output_file: str | None = None,
) -> AudioTrimOut:
    """
    Trim leading and trailing silence from an audio file.

    Args:
        file:               Filename in tracks/ dir or absolute path.
        silence_thresh_db:  Silence threshold in dBFS (-80 to -10, default -40).
        padding_ms:         Silence padding to keep at each end (0-2000 ms).
        output_file:        Output filename (auto-generated if omitted).

    Returns original_duration_s, trimmed_duration_s, and removed_ms.
    Requires: pydub.
    """
    inp = AudioTrimIn(
        file=file, silence_thresh_db=silence_thresh_db,
        padding_ms=padding_ms, output_file=output_file,
    )
    r = _audio.trim(inp.file, inp.silence_thresh_db, inp.padding_ms, inp.output_file)
    return AudioTrimOut(
        ok=r["ok"],
        file=r.get("file"),
        original_duration_s=r.get("original_duration_s"),
        trimmed_duration_s=r.get("trimmed_duration_s"),
        removed_ms=r.get("removed_ms"),
        error=r.get("error"),
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 43. audio.splice
# ---------------------------------------------------------------------------

@mcp.tool(name="audio.splice")
def audio_splice(
    file: str,
    start_ms: int,
    end_ms: int,
    output_file: str | None = None,
) -> AudioSpliceOut:
    """
    Extract a time region from an audio file.

    Args:
        file:        Filename in tracks/ dir or absolute path.
        start_ms:    Start time in milliseconds (>= 0).
        end_ms:      End time in milliseconds (must be > start_ms).
        output_file: Output filename (auto-generated if omitted).

    Returns start_ms, end_ms, duration_ms, and output path.
    Requires: pydub.
    """
    inp = AudioSpliceIn(file=file, start_ms=start_ms, end_ms=end_ms, output_file=output_file)
    r = _audio.splice(inp.file, inp.start_ms, inp.end_ms, inp.output_file)
    return AudioSpliceOut(
        ok=r["ok"],
        file=r.get("file"),
        start_ms=r.get("start_ms"),
        end_ms=r.get("end_ms"),
        duration_ms=r.get("duration_ms"),
        error=r.get("error"),
        ts_ms=r["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 44. audio.convert
# ---------------------------------------------------------------------------

@mcp.tool(name="audio.convert")
def audio_convert(
    file: str,
    format: str = "wav",
    output_file: str | None = None,
) -> AudioConvertOut:
    """
    Convert an audio file to a different format.

    Args:
        file:        Filename in tracks/ dir or absolute path.
        format:      Target format: "mp3", "wav", "flac", or "ogg".
        output_file: Output filename (auto-generated if omitted).

    Returns format, size_kb, and output path.
    Requires: pydub.
    """
    inp = AudioConvertIn(file=file, format=format, output_file=output_file)  # type: ignore[arg-type]
    r = _audio.convert(inp.file, inp.format, inp.output_file)
    return AudioConvertOut(
        ok=r["ok"],
        file=r.get("file"),
        format=r.get("format"),
        size_kb=r.get("size_kb"),
        error=r.get("error"),
        ts_ms=r["ts_ms"],
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
