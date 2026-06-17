"""旋律转录 — 基于 Spotify Basic Pitch"""

from pathlib import Path

import pretty_midi

from .base import BaseTranscriber, NoteEvent, StemType, TrackResult


# StemType → MIDI program (General MIDI)
STEM_PROGRAM_MAP = {
    StemType.BASS:    33,  # Electric Bass (finger)
    StemType.VOCALS:  54,  # Synth Voice / Choir
    StemType.OTHER:    0,  # Acoustic Grand Piano
    StemType.FULL:      0,
}


class BasicPitchTranscriber(BaseTranscriber):
    """使用 Spotify Basic Pitch 进行单旋律/多乐器转录"""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from basic_pitch.inference import predict
            self._predict_fn = predict
        return self._predict_fn

    def supports_stem(self, stem_type: StemType) -> bool:
        return stem_type in (StemType.BASS, StemType.VOCALS, StemType.OTHER,
                             StemType.GUITAR, StemType.FULL)

    def transcribe(self, audio_path: Path, **kwargs) -> TrackResult:
        stem_type = kwargs.get("stem_type", StemType.OTHER)
        output_dir = kwargs.get("output_dir", Path("."))
        output_dir = Path(output_dir)
        midi_path = output_dir / f"{audio_path.stem}_{stem_type.value}.mid"

        from basic_pitch.inference import predict_and_save
        from basic_pitch import ICASSP_2022_MODEL_PATH

        predict_and_save(
            [str(audio_path)], str(output_dir),
            save_midi=True, sonify_midi=False,
            save_model_outputs=False, save_notes=False,
            model_or_model_path=ICASSP_2022_MODEL_PATH,
        )

        # Basic Pitch 默认输出路径: <output_dir>/<filename>_basic_pitch.mid
        default_midi = output_dir / f"{audio_path.stem}_basic_pitch.mid"
        if default_midi.exists():
            default_midi.rename(midi_path)

        return self._load_midi(midi_path, stem_type)

    def _load_midi(self, midi_path: Path, stem_type: StemType) -> TrackResult:
        notes: list[NoteEvent] = []
        duration = 0.0
        tempo = 120.0

        if midi_path.exists():
            pm = pretty_midi.PrettyMIDI(str(midi_path))
            duration = pm.get_end_time()
            if pm.get_tempo_changes()[1]:
                import numpy as np
                tempos = pm.get_tempo_changes()[1]
                tempo = float(np.mean(tempos))
            for inst in pm.instruments:
                for note in inst.notes:
                    notes.append(NoteEvent(
                        start_time=note.start,
                        end_time=note.end,
                        pitch=note.pitch,
                        velocity=note.velocity,
                    ))

        return TrackResult(
            stem_type=stem_type,
            notes=notes,
            midi_path=midi_path if midi_path.exists() else None,
            duration=duration,
            tempo=tempo,
        )
