"""MIDI 合并与后处理"""

from pathlib import Path

import pretty_midi

from ..transcription.base import StemType, TrackResult

# 各音轨对应的 MIDI program 和通道
STEM_CHANNEL_MAP = {
    StemType.DRUMS:   9,
    StemType.BASS:    0,
    StemType.VOCALS:  1,
    StemType.GUITAR:  2,
    StemType.PIANO:   3,
    StemType.OTHER:   4,
}

STEM_PROGRAM_MAP = {
    StemType.DRUMS:   0,    # Drum Kit
    StemType.BASS:    34,   # Electric Bass (pick)
    StemType.VOCALS:  54,   # Synth Voice
    StemType.GUITAR:  25,   # Acoustic Guitar (nylon)
    StemType.PIANO:    0,   # Acoustic Grand Piano
    StemType.OTHER:   49,   # String Ensemble 2 ← 默认弦乐
}


class MidiMerger:
    """合并多轨转录结果为一个统一的多通道 MIDI 文件"""

    def merge(
        self,
        track_results: list[TrackResult],
        output_path: Path,
        tempo: float | None = None,
    ) -> pretty_midi.PrettyMIDI:
        pm = pretty_midi.PrettyMIDI(initial_tempo=tempo or 120)

        for tr in track_results:
            if not tr.notes:
                continue

            channel = STEM_CHANNEL_MAP.get(tr.stem_type, 2)
            program = STEM_PROGRAM_MAP.get(tr.stem_type, 0)

            if tr.stem_type == StemType.DRUMS:
                inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
            else:
                inst = pretty_midi.Instrument(program=program, name=tr.stem_type.value.capitalize())

            for ne in tr.notes:
                note = pretty_midi.Note(
                    velocity=ne.velocity,
                    pitch=ne.pitch,
                    start=ne.start_time,
                    end=ne.end_time,
                )
                inst.notes.append(note)

            pm.instruments.append(inst)

        pm.write(str(output_path))
        return pm
