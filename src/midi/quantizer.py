"""MIDI 量化 — 保守量化，保留原曲结构"""

import numpy as np
import pretty_midi


class MidiQuantizer:
    """保守量化：只把接近拍点的起始时间对齐，保留原有时值和力度"""

    def quantize(
        self,
        midi: pretty_midi.PrettyMIDI,
        bpm: float | None = None,
        snap_threshold: float = 0.3,  # 只对齐距网格点 30% 以内的音符
    ) -> pretty_midi.PrettyMIDI:
        """量化音符起始时间，保留原有时值和结构"""

        if bpm:
            end_time = midi.get_end_time()
            beat_interval = 60.0 / bpm
            beats = np.arange(0, end_time + beat_interval, beat_interval)
        else:
            beats = midi.get_beats()

        if len(beats) < 2:
            return midi

        # 计算平均拍间距
        beat_spacing = float(np.median(np.diff(beats)))
        max_dist = beat_spacing * snap_threshold

        for inst in midi.instruments:
            for note in inst.notes:
                snapped = self._snap_near(note.start, beats, max_dist)
                if snapped is not None:
                    shift = snapped - note.start
                    # 只平移，不改变时值
                    note.start = snapped
                    note.end += shift

        return midi

    @staticmethod
    def _snap_near(time: float, beats: np.ndarray, max_dist: float) -> float | None:
        """只在阈值范围内对齐，超出则不动"""
        if len(beats) == 0:
            return None
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
        return None  # 离网格太远，不改动
