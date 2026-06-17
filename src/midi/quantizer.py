"""MIDI 量化与去噪"""

import numpy as np
import pretty_midi


class MidiQuantizer:
    """对 MIDI 音符做节拍量化和去噪处理"""

    def quantize(
        self,
        midi: pretty_midi.PrettyMIDI,
        resolution: float = 0.125,  # 三十二分音符精度 (1/32 = 0.125 拍)
        min_duration: float = 0.02,  # 最短音符时长 (秒)
        min_velocity: int = 10,      # 最弱力度
        bpm: float | None = None,    # 手动指定 BPM，None=自动检测
    ) -> pretty_midi.PrettyMIDI:
        """量化所有音符到最近的拍点"""

        # 获取拍点
        if bpm:
            # 手动 BPM：生成均匀拍点网格
            end_time = midi.get_end_time()
            beat_interval = 60.0 / bpm
            beats = np.arange(0, end_time + beat_interval, beat_interval)
        else:
            beats = midi.get_beats()

        if len(beats) < 2:
            return midi

        # 构建全拍网格（包括细分）
        grid = self._build_grid(beats, resolution)

        for inst in midi.instruments:
            keep_notes = []
            for note in inst.notes:
                # 力度过滤
                if note.velocity < min_velocity:
                    continue
                # 时值过滤
                duration = note.end - note.start
                if duration < min_duration:
                    continue
                # 量化起始和结束时间到最近网格点
                note.start = self._snap(note.start, grid)
                note.end = self._snap(note.end, grid)
                if note.end <= note.start:
                    note.end = note.start + min_duration
                keep_notes.append(note)

            # 合并重叠音符（同音高）
            inst.notes = self._merge_overlapping(keep_notes)

        return midi

    def _build_grid(self, beats: np.ndarray, resolution: float) -> np.ndarray:
        """从拍点构建细分网格"""
        grid_points = []
        for i in range(len(beats) - 1):
            beat_start = beats[i]
            beat_end = beats[i + 1]
            n_subdivisions = max(1, int(round(1.0 / resolution)))
            for j in range(n_subdivisions):
                t = beat_start + j * (beat_end - beat_start) / n_subdivisions
                grid_points.append(t)
        # 加上最后一个拍点
        grid_points.append(beats[-1])
        return np.array(sorted(set(grid_points)))

    @staticmethod
    def _snap(time: float, grid: np.ndarray) -> float:
        """把时间对齐到最近的网格点"""
        idx = np.searchsorted(grid, time)
        if idx == 0:
            return float(grid[0])
        if idx >= len(grid):
            return float(grid[-1])
        left = grid[idx - 1]
        right = grid[idx]
        return float(left if (time - left) < (right - time) else right)

    @staticmethod
    def _merge_overlapping(notes: list[pretty_midi.Note]) -> list[pretty_midi.Note]:
        """合并同音高重叠的相邻音符"""
        if not notes:
            return notes
        # 按起始时间 + 音高排序
        notes.sort(key=lambda n: (n.start, n.pitch))
        merged = []
        current = notes[0]
        for next_note in notes[1:]:
            if next_note.pitch == current.pitch and next_note.start <= current.end + 0.01:
                # 重叠：扩展结束时间
                current.end = max(current.end, next_note.end)
            else:
                merged.append(current)
                current = next_note
        merged.append(current)
        return merged
