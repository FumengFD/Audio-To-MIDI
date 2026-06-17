"""MIDI 合并 — 各轨合入总谱，统一速度和节拍网格"""

import numpy as np
import pretty_midi

from ..transcription.base import StemType

# 各轨 → GM program
STEM_PROGRAM = {
    StemType.DRUMS: 0,
    StemType.BASS: 34,
    StemType.VOCALS: 54,
    StemType.GUITAR: 25,
    StemType.PIANO: 0,
    StemType.OTHER: 49,
}


def merge_midi(
    track_results: list,
    output_path,
    bpm: float | None = None,
    snap_ratio: float = 0.3,
) -> pretty_midi.PrettyMIDI:
    """合并多轨 MIDI 为总谱，按节拍网格对齐

    Args:
        track_results: 各轨 TrackResult
        output_path: 输出路径
        bpm: 统一 BPM，None 则取各轨中位数
        snap_ratio: 量化阈值（拍间距的比例）
    """
    # 加载各轨 MIDI
    tracks = []
    for tr in track_results:
        if tr.midi_path and tr.midi_path.exists():
            tracks.append((tr.stem_type, tr.midi_path))

    if not tracks:
        return pretty_midi.PrettyMIDI()

    # 读取各轨
    all_stems = []
    for stem_type, midi_path in tracks:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
        all_stems.append((stem_type, pm))

    # 确定统一 BPM
    if bpm:
        target_bpm = bpm
    else:
        tempos = []
        for _, pm in all_stems:
            t, _ = pm.get_tempo_changes()
            if len(t) > 0:
                tempos.extend(t.tolist())
        target_bpm = float(np.median(tempos)) if tempos else 120.0

    # 构建拍点网格
    max_time = max(pm.get_end_time() for _, pm in all_stems)
    beat_interval = 60.0 / target_bpm
    beats = np.arange(0, max_time + beat_interval, beat_interval)
    beat_spacing = float(np.median(np.diff(beats))) if len(beats) > 1 else beat_interval
    max_dist = beat_spacing * snap_ratio

    # 合并
    merged = pretty_midi.PrettyMIDI(initial_tempo=target_bpm)

    for stem_type, pm in all_stems:
        if stem_type == StemType.DRUMS:
            inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
        else:
            program = STEM_PROGRAM.get(stem_type, 0)
            inst = pretty_midi.Instrument(
                program=program,
                name=stem_type.value.capitalize(),
            )

        for old_inst in pm.instruments:
            for note in old_inst.notes:
                # 对齐起始时间
                snapped = _nearest_beat(note.start, beats, max_dist)
                start = snapped if snapped is not None else note.start
                shift = start - note.start
                new_note = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=start,
                    end=note.end + shift,
                )
                inst.notes.append(new_note)

        merged.instruments.append(inst)

    merged.write(str(output_path))
    return merged


def _nearest_beat(time: float, beats: np.ndarray, max_dist: float) -> float | None:
    idx = np.searchsorted(beats, time)
    candidates = []
    if idx > 0:
        candidates.append(beats[idx - 1])
    if idx < len(beats):
        candidates.append(beats[idx])
    if not candidates:
        return None
    closest = min(candidates, key=lambda b: abs(time - b))
    if abs(time - closest) <= max_dist:
        return float(closest)
    return None
