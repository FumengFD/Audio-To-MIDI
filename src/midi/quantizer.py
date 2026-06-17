"""MIDI 保守量化 — 只对齐起始时间，保留原曲结构"""

import numpy as np
import pretty_midi


def quantize_midi(
    midi: pretty_midi.PrettyMIDI,
    bpm: float | None = None,
    snap_ratio: float = 0.3,
) -> pretty_midi.PrettyMIDI:
    """保守量化：只把接近拍点的起始时间对齐，保留原有时值和力度

    Args:
        midi: 输入 MIDI
        bpm: 手动 BPM，None 则自动检测
        snap_ratio: 对齐阈值（占拍间距的比例），默认 0.3 = 拍间距 30% 以内的音符才对齐
    """
    if bpm:
        beats = np.arange(0, midi.get_end_time() + 60 / bpm, 60 / bpm)
    else:
        beats = midi.get_beats()

    if len(beats) < 2:
        return midi

    beat_spacing = float(np.median(np.diff(beats)))
    max_dist = beat_spacing * snap_ratio

    for inst in midi.instruments:
        for note in inst.notes:
            target = _nearest_beat(note.start, beats, max_dist)
            if target is not None:
                shift = target - note.start
                note.start = target
                note.end += shift  # 等量平移，时值不变

    return midi


def _nearest_beat(time: float, beats: np.ndarray, max_dist: float) -> float | None:
    """找最近的拍点，距离超过 max_dist 则返回 None（不动）"""
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
