"""鼓组转录 — 基于 ADTOF-pytorch (PyTorch)

论文: "Automatic Drum Transcription with Offset Features" (Zehren et al., ISMIR 2021)
模型: ADTOF-pytorch (xavriley) — 纯 PyTorch 实现，模型权重内置
准确率: ~88.5% F-measure on MDBDrums++

识别鼓件: kick, snare, 3 toms, hi-hat (closed/open), crash, ride
"""

from pathlib import Path

import pretty_midi

from .base import BaseTranscriber, NoteEvent, StemType, TrackResult

# GM MIDI 鼓音高 → 鼓件名称
DRUM_PITCH_MAP = {
    35: "Kick", 36: "Kick",
    37: "Rimshot", 38: "Snare", 40: "Snare",
    42: "Closed HH", 44: "Pedal HH", 46: "Open HH",
    43: "Low-Tom", 45: "Mid-Tom", 47: "Low-Tom", 48: "Hi-Tom", 50: "Hi-Tom",
    49: "Crash", 52: "Crash", 55: "Splash", 57: "Crash",
    51: "Ride", 53: "Ride", 59: "Ride",
}


class DrumTranscriber(BaseTranscriber):
    """使用 ADTOF-pytorch 进行鼓组转录"""

    def supports_stem(self, stem_type: StemType) -> bool:
        return stem_type == StemType.DRUMS

    def transcribe(self, audio_path: Path, **kwargs) -> TrackResult:
        from adtof_pytorch import transcribe_to_midi

        output_dir = kwargs.get("output_dir", Path("."))
        output_dir = Path(output_dir)
        midi_path = output_dir / f"{audio_path.stem}_drums.mid"

        # ADTOF 转录：WAV → MIDI
        transcribe_to_midi(str(audio_path), str(midi_path))

        # 读取生成 MIDI
        pm = pretty_midi.PrettyMIDI(str(midi_path))
        notes: list[NoteEvent] = []

        for inst in pm.instruments:
            for note in inst.notes:
                drum_name = DRUM_PITCH_MAP.get(note.pitch, f"Note{note.pitch}")
                notes.append(NoteEvent(
                    start_time=note.start,
                    end_time=note.end,
                    pitch=note.pitch,
                    velocity=note.velocity,
                    instrument=drum_name,
                ))

        return TrackResult(
            stem_type=StemType.DRUMS,
            notes=notes,
            midi_path=midi_path,
            duration=pm.get_end_time(),
            tempo=self._estimate_tempo(pm),
        )

    @staticmethod
    def _estimate_tempo(pm: pretty_midi.PrettyMIDI) -> float:
        import numpy as np
        if pm.get_tempo_changes()[1]:
            tempos = pm.get_tempo_changes()[1]
            return float(np.mean(tempos))
        return 120.0
