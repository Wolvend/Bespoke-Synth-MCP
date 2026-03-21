from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ScalarValue = float | int | str | bool


class ToolBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommonToolIn(ToolBaseModel):
    idempotency_key: str | None = Field(default=None, min_length=1)
    dry_run: bool = False
    request_ts_ms: int | None = Field(default=None, ge=0)
    session_id: str | None = None


class HealthOut(ToolBaseModel):
    ok: bool
    ts_ms: int
    server: str


class ListModulesIn(CommonToolIn):
    prefix: str | None = None


class ListModulesOut(ToolBaseModel):
    ok: bool
    modules: list[str]
    source: str
    ts_ms: int


class GetParamIn(CommonToolIn):
    path: str = Field(min_length=1, max_length=255)


class GetParamOut(ToolBaseModel):
    ok: bool
    path: str
    value: Any | None = None
    raw_reply: dict[str, Any] | None = None
    ts_ms: int


class SetParamIn(CommonToolIn):
    path: str = Field(min_length=1, max_length=255)
    value: ScalarValue
    mode: Literal["immediate", "ramp"] = "immediate"
    ramp_ms: int = Field(default=0, ge=0, le=60000)


class SetParamOut(ToolBaseModel):
    ok: bool
    applied: bool
    path: str
    value: ScalarValue
    raw_reply: dict[str, Any] | None = None
    ts_ms: int


class BatchSetItem(ToolBaseModel):
    path: str = Field(min_length=1, max_length=255)
    value: ScalarValue
    at_ms: int | None = Field(default=None, ge=0)


class BatchSetIn(CommonToolIn):
    ops: list[BatchSetItem] = Field(min_length=1, max_length=500)


class BatchSetOut(ToolBaseModel):
    ok: bool
    applied: bool
    count: int
    raw_reply: dict[str, Any] | None = None
    ts_ms: int


class PlayNoteIn(CommonToolIn):
    label: str = Field(min_length=1, max_length=128)
    pitch: int = Field(ge=0, le=127)
    velocity: int = Field(ge=0, le=127)
    duration_ms: int = Field(default=250, ge=1, le=60000)


class ScheduleNoteItem(ToolBaseModel):
    label: str = Field(min_length=1, max_length=128)
    pitch: int = Field(ge=0, le=127)
    velocity: int = Field(ge=0, le=127)
    at_ms: int = Field(ge=0)
    duration_ms: int = Field(default=250, ge=1, le=60000)


class ScheduleNotesIn(CommonToolIn):
    notes: list[ScheduleNoteItem] = Field(min_length=1, max_length=256)


class NoteOut(ToolBaseModel):
    ok: bool
    applied: bool
    count: int
    raw_reply: dict[str, Any] | None = None
    ts_ms: int


class TransportSetIn(CommonToolIn):
    playing: bool
    bpm: float | None = Field(default=None, gt=0, le=480)
    beat: int | None = Field(default=None, ge=0)


class SnapshotLoadIn(CommonToolIn):
    name: str = Field(min_length=1, max_length=128)


class TelemetryLastIn(CommonToolIn):
    limit: int = Field(default=20, ge=1, le=200)
    prefix: str | None = None


class TelemetryItem(ToolBaseModel):
    address: str
    args: list[Any]
    ts_ms: int


class TelemetryLastOut(ToolBaseModel):
    ok: bool
    items: list[TelemetryItem]
    ts_ms: int


class RawCommandIn(CommonToolIn):
    op: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("op")
    @classmethod
    def validate_op(cls, value: str) -> str:
        if value.startswith("bespoke.admin."):
            return value
        return value


class RawCommandOut(ToolBaseModel):
    ok: bool
    raw_reply: dict[str, Any] | None = None
    ts_ms: int


# ─── bespoke.theory schemas ───────────────────────────────────────────────────

class NoteInfo(ToolBaseModel):
    name: str
    midi: int
    freq_hz: float


class ScaleIn(ToolBaseModel):
    root: str = Field(min_length=1, max_length=4, description="Root note, e.g. 'C', 'F#', 'Bb'")
    mode: str = Field(default="major")
    octave: int = Field(default=4, ge=0, le=8)
    num_octaves: int = Field(default=1, ge=1, le=4)


class ScaleOut(ToolBaseModel):
    ok: bool
    root: str
    mode: str
    octave: int
    num_notes: int
    notes: list[NoteInfo]
    ts_ms: int


class ChordIn(ToolBaseModel):
    root: str = Field(min_length=1, max_length=4, description="Root note, e.g. 'C', 'F#', 'Bb'")
    chord_type: str = Field(default="maj")
    octave: int = Field(default=4, ge=0, le=8)
    inversion: int = Field(default=0, ge=0, le=3)


class ChordOut(ToolBaseModel):
    ok: bool
    root: str
    type: str
    octave: int
    inversion: int
    num_notes: int
    notes: list[NoteInfo]
    ts_ms: int


class TransposeIn(ToolBaseModel):
    notes: list[NoteInfo]
    semitones: int = Field(ge=-48, le=48)


class TransposeOut(ToolBaseModel):
    ok: bool
    semitones: int
    notes: list[NoteInfo]
    ts_ms: int


class TheoryInfoOut(ToolBaseModel):
    ok: bool
    modes: list[str]
    chord_types: list[str]
    ts_ms: int


# ─── bespoke.compose schemas ──────────────────────────────────────────────────

class PresetSummary(ToolBaseModel):
    name: str
    bpm: float | None = None
    description: str = ""
    steps: int = 0


class ListPresetsOut(ToolBaseModel):
    ok: bool
    presets: list[PresetSummary]
    count: int
    ts_ms: int


class TrackSummary(ToolBaseModel):
    file: str
    path: str
    size_kb: float
    meta: dict[str, Any] = Field(default_factory=dict)


class ListTracksOut(ToolBaseModel):
    ok: bool
    tracks: list[TrackSummary]
    count: int
    ts_ms: int


class RenderWorkflowIn(ToolBaseModel):
    name: str = Field(min_length=1, max_length=128, description="Workflow preset name")
    dry_run: bool = False


class RenderWorkflowOut(ToolBaseModel):
    ok: bool
    name: str
    mp3_path: str | None = None
    size_kb: float | None = None
    duration_s: float | None = None
    dry_run: bool = False
    error: str | None = None
    ts_ms: int


class GetPresetOut(ToolBaseModel):
    ok: bool
    name: str | None = None
    preset: dict[str, Any] | None = None
    error: str | None = None
    ts_ms: int



# ─── bespoke.theory.quantize schemas ──────────────────────────────────────────

class QuantizeIn(ToolBaseModel):
    freq_hz: float = Field(gt=0, description="Input frequency in Hz to snap to scale")
    root: str = Field(min_length=1, max_length=4)
    mode: str = Field(default="major")


class QuantizeOut(ToolBaseModel):
    ok: bool
    input_freq_hz: float
    quantized: NoteInfo
    cents_deviation: float
    ts_ms: int


# ─── bespoke.theory.progression schemas ───────────────────────────────────────

class ChordInfo(ToolBaseModel):
    degree: int
    roman: str
    root: str
    type: str
    notes: list[NoteInfo]


class ProgressionIn(ToolBaseModel):
    root: str = Field(min_length=1, max_length=4)
    mode: str = Field(default="major")
    pattern: str = Field(min_length=1, max_length=64, description="e.g. I-IV-V-I")
    octave: int = Field(default=4, ge=0, le=8)


class ProgressionOut(ToolBaseModel):
    ok: bool
    root: str
    mode: str
    pattern: str
    chords: list[ChordInfo]
    error: str | None = None
    ts_ms: int


# ─── bespoke.theory.arpeggiate schemas ────────────────────────────────────────

class ArpeggiateIn(ToolBaseModel):
    root: str = Field(min_length=1, max_length=4)
    chord_type: str = Field(default="maj")
    octave: int = Field(default=4, ge=0, le=8)
    pattern: Literal["up", "down", "updown", "random"] = "up"
    subdivision: Literal["8th", "16th", "triplet"] = "16th"
    bpm: float = Field(default=120.0, gt=0, le=480)
    bars: int = Field(default=1, ge=1, le=16)
    velocity: int = Field(default=100, ge=0, le=127)


class ArpeggiateOut(ToolBaseModel):
    ok: bool
    root: str
    chord_type: str
    pattern: str
    note_count: int
    notes: list[ScheduleNoteItem]
    error: str | None = None
    ts_ms: int


# ─── bespoke.compose.save_preset schemas ──────────────────────────────────────

class WorkflowStepIn(ToolBaseModel):
    preset: str = Field(min_length=1, max_length=128)
    duration_ms: float = Field(gt=0)
    delay_ms: float = Field(default=0.0, ge=0)
    velocity: float = Field(default=1.0, ge=0, le=2.0)


class SavePresetIn(ToolBaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[\w\-]+$")
    bpm: float = Field(gt=0, le=480)
    description: str = ""
    steps: list[WorkflowStepIn] = Field(min_length=1, max_length=256)


class SavePresetOut(ToolBaseModel):
    ok: bool
    name: str
    path: str
    steps_count: int
    error: str | None = None
    ts_ms: int


# ─── bespoke.compose.delete_track schemas ─────────────────────────────────────

class DeleteTrackIn(ToolBaseModel):
    file: str = Field(min_length=1, max_length=255)


class DeleteTrackOut(ToolBaseModel):
    ok: bool
    file: str
    deleted: list[str]
    error: str | None = None
    ts_ms: int


# ─── bespoke.compose.tag_track schemas ────────────────────────────────────────

class TagTrackIn(ToolBaseModel):
    file: str = Field(min_length=1, max_length=255)
    tags: dict[str, Any]


class TagTrackOut(ToolBaseModel):
    ok: bool
    file: str
    meta: dict[str, Any]
    error: str | None = None
    ts_ms: int


# ─── audio.analyze schemas ─────────────────────────────────────────────────────

class AudioAnalyzeIn(ToolBaseModel):
    file: str = Field(min_length=1, max_length=512)
    analyze_bpm: bool = True
    analyze_key: bool = True
    analyze_loudness: bool = True


class AudioAnalyzeOut(ToolBaseModel):
    ok: bool
    file: str
    duration_s: float | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None
    key: str | None = None
    key_confidence: float | None = None
    loudness_lufs: float | None = None
    error: str | None = None
    ts_ms: int


# ─── compose.export_midi schemas ───────────────────────────────────────────────

class ExportMidiIn(ToolBaseModel):
    name: str | None = Field(default=None, max_length=128)
    notes: list[dict[str, Any]] | None = None
    bpm: float = Field(default=120.0, gt=0, le=480)
    filename: str | None = Field(default=None, max_length=255)


class ExportMidiOut(ToolBaseModel):
    ok: bool
    midi_path: str | None = None
    size_kb: float | None = None
    note_count: int | None = None
    duration_s: float | None = None
    error: str | None = None
    ts_ms: int


# ─── bespoke.safe.automate schemas ────────────────────────────────────────────

class AutomatePoint(ToolBaseModel):
    value: ScalarValue
    at_ms: int = Field(ge=0)


class AutomateIn(CommonToolIn):
    path: str = Field(min_length=1, max_length=255)
    points: list[AutomatePoint] | None = Field(default=None, max_length=500)
    start_value: float | None = None
    end_value: float | None = None
    duration_ms: int | None = Field(default=None, ge=1, le=600000)
    steps: int = Field(default=16, ge=2, le=500)
    curve: Literal["linear", "exp", "log"] = "linear"


class AutomateOut(ToolBaseModel):
    ok: bool
    applied: bool
    path: str
    points_sent: int
    raw_reply: dict[str, Any] | None = None
    error: str | None = None
    ts_ms: int


# ─── audio.stems schemas ───────────────────────────────────────────────────────

class AudioStemsIn(ToolBaseModel):
    file: str = Field(min_length=1, max_length=512)
    stems: list[Literal["vocals", "drums", "bass", "other"]] = Field(
        default=["drums", "bass", "other", "vocals"]
    )


class AudioStemsOut(ToolBaseModel):
    ok: bool
    file: str
    stems: dict[str, str] = Field(default_factory=dict)
    model: str | None = None
    error: str | None = None
    ts_ms: int
