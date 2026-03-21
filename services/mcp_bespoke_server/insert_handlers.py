"""Insert new tool handlers into server.py before create_http_app()."""
import pathlib

handlers = """

# ===========================================================================
# Tools 30-44 (new batch)
# ===========================================================================

# ---------------------------------------------------------------------------
# 30. bespoke.theory.detect_chord
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.theory.detect_chord")
def theory_detect_chord(pitches: list[int]) -> DetectChordOut:
    \"\"\"
    Identify the most likely chord name from a list of MIDI pitch numbers.

    Args:
        pitches: 2-12 MIDI pitch values (e.g. [60, 64, 67] for C major).

    Returns root, chord_type, inversion, confidence score, and notes_matched.
    \"\"\"
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
    \"\"\"
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
    \"\"\"
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
    \"\"\"
    Find the voicing of a target chord that minimises total semitone movement
    from the source chord notes.

    Args:
        from_notes:    List of {name, midi, freq_hz} dicts (source chord).
        to_root:       Root note of the target chord (e.g. "G").
        to_chord_type: Chord quality of the target (e.g. "maj", "min7").

    Returns from_notes, to_notes, and total_movement_semitones.
    \"\"\"
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
    \"\"\"
    Find pivot chords shared between two diatonic keys to facilitate smooth
    modulation.

    Args:
        from_root: Root note of the source key (e.g. "C").
        from_mode: Mode of the source key (e.g. "major").
        to_root:   Root note of the target key (e.g. "G").
        to_mode:   Mode of the target key (e.g. "major").

    Returns a list of pivot chords with their Roman numeral label in each key.
    \"\"\"
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
    \"\"\"
    Add random timing jitter and velocity variation to a note list to make it
    sound more human.

    Args:
        notes:        List of note dicts with at_ms and velocity fields.
        timing_ms:    Max timing shift in milliseconds (+/-), 0-100.
        velocity_pct: Max velocity change as a fraction (0-0.5).
        seed:         Optional random seed for reproducibility.

    Returns the modified note list with the same length as the input.
    \"\"\"
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
    \"\"\"
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
    \"\"\"
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
    \"\"\"
    Export a workflow preset to a lossless WAV file.

    Args:
        name:    Preset name (without .json extension).
        dry_run: Validate only, do not write audio.

    Returns wav_path, size_kb, and duration_s.
    Requires: soundfile, numpy.
    \"\"\"
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
    \"\"\"
    Send a MIDI Control Change (CC) message to BespokeSynth via OSC.

    Args:
        cc:      Controller number (0-127).
        value:   Controller value (0-127).
        channel: MIDI channel (0-15, default 0).

    Returns ok and applied status.
    \"\"\"
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
        ts_ms=result["ts_ms"],
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
    \"\"\"
    Save the current BespokeSynth state as a named snapshot via OSC.

    Args:
        name: Snapshot name (1-128 chars, alphanumeric/hyphens/underscores).

    Returns ok and applied status.
    \"\"\"
    inp = SaveSnapshotIn(
        name=name,
        idempotency_key=idempotency_key, dry_run=dry_run,
        request_ts_ms=request_ts_ms, session_id=session_id,
    )
    envelope = {"op": "snapshot_save", "name": inp.name}
    result = await _send_with_cache(inp, envelope)
    return RawCommandOut(
        ok=result["ok"],
        applied=result.get("applied", False),
        raw_reply=result.get("raw_reply"),
        ts_ms=result["ts_ms"],
    )


# ---------------------------------------------------------------------------
# 39. bespoke.safe.list_snapshots
# ---------------------------------------------------------------------------

@mcp.tool(name="bespoke.safe.list_snapshots")
def bespoke_list_snapshots() -> ListSnapshotsOut:
    \"\"\"
    List available BespokeSynth snapshots (.bsk files) from the configured
    snapshots directory (BESPOKE_SNAPSHOTS_DIR env var).

    Returns a list of snapshot names (without extension) and total count.
    \"\"\"
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
    \"\"\"
    Read multiple module parameter values in a single batch request.

    Args:
        paths: List of 1-100 parameter paths (e.g. ["filter~cutoff", "osc~freq"]).

    Returns a params dict {path: value} and an errors dict {path: error_msg}.
    \"\"\"
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
    \"\"\"
    Normalize an audio file to a target loudness (LUFS) using pyloudnorm.

    Args:
        file:        Filename in tracks/ dir or absolute path.
        target_lufs: Target integrated loudness in LUFS (-60 to -1, default -14).
        output_file: Output filename (auto-generated if omitted).

    Returns input_lufs, gain_db, and output path.
    Requires: pyloudnorm, soundfile, pydub.
    \"\"\"
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
    \"\"\"
    Trim leading and trailing silence from an audio file.

    Args:
        file:               Filename in tracks/ dir or absolute path.
        silence_thresh_db:  Silence threshold in dBFS (-80 to -10, default -40).
        padding_ms:         Silence padding to keep at each end (0-2000 ms).
        output_file:        Output filename (auto-generated if omitted).

    Returns original_duration_s, trimmed_duration_s, and removed_ms.
    Requires: pydub.
    \"\"\"
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
    \"\"\"
    Extract a time region from an audio file.

    Args:
        file:        Filename in tracks/ dir or absolute path.
        start_ms:    Start time in milliseconds (>= 0).
        end_ms:      End time in milliseconds (must be > start_ms).
        output_file: Output filename (auto-generated if omitted).

    Returns start_ms, end_ms, duration_ms, and output path.
    Requires: pydub.
    \"\"\"
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
    \"\"\"
    Convert an audio file to a different format.

    Args:
        file:        Filename in tracks/ dir or absolute path.
        format:      Target format: "mp3", "wav", "flac", or "ogg".
        output_file: Output filename (auto-generated if omitted).

    Returns format, size_kb, and output path.
    Requires: pydub.
    \"\"\"
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

"""

target = pathlib.Path(r"C:\Users\LIZ\Desktop\Claude\bespokesynth_mcp\services\mcp_bespoke_server\src\mcp_bespoke_server\server.py")
content = target.read_text(encoding="utf-8")

marker = "def create_http_app()"
idx = content.index(marker)
new_content = content[:idx] + handlers + "\n" + content[idx:]
target.write_text(new_content, encoding="utf-8")
print(f"server.py updated — total lines: {new_content.count(chr(10))}")
