"""总管线编排 — Demucs 分轨 → 专用模型转录 → 合并"""

from pathlib import Path
import pretty_midi

from .midi.merger import MidiMerger
from .midi.quantizer import MidiQuantizer
from .separation.demucs_runner import DemucsSeparator
from .transcription.base import StemType, TrackResult
from .transcription.drum import DrumTranscriber
from .transcription.melodic import BasicPitchTranscriber
from .transcription.transkun import TranskunTranscriber


class TranscriptionPipeline:

    def __init__(self):
        self.separator = DemucsSeparator()
        self.drum_transcriber = DrumTranscriber()
        self.melodic_transcriber = BasicPitchTranscriber()
        self.piano_transcriber = TranskunTranscriber()
        self.merger = MidiMerger()
        self.quantizer = MidiQuantizer()

    def run(
        self,
        audio_path: Path,
        output_dir: Path,
        enabled_stems: list[str] | None = None,
        bpm: float | None = None,
    ) -> dict:
        enabled_stems = enabled_stems or ["drums", "bass", "vocals", "guitar", "piano", "other"]
        output_dir.mkdir(parents=True, exist_ok=True)

        # 清理 Demucs 上次残留，避免 WinError 183
        import shutil
        for model_name in ["htdemucs", "htdemucs_6s"]:
            old = output_dir / model_name / audio_path.stem
            if old.exists():
                shutil.rmtree(old, ignore_errors=True)

        # 6 声部需要 guitar/piano → 用 6-stem 模型
        need_6 = any(s in enabled_stems for s in ("guitar", "piano"))
        separation = self.separator.separate(audio_path, output_dir, six_stem=need_6)

        stem_map = {
            "drums": StemType.DRUMS, "bass": StemType.BASS,
            "vocals": StemType.VOCALS, "other": StemType.OTHER,
            "guitar": StemType.GUITAR, "piano": StemType.PIANO,
        }

        track_results = []
        for key in enabled_stems:
            st = stem_map.get(key)
            if st is None or st not in separation.stems:
                continue
            sp = separation.stems[st]
            if st == StemType.DRUMS:
                r = self.drum_transcriber.transcribe(sp, output_dir=output_dir)
            elif st == StemType.PIANO:
                r = self.piano_transcriber.transcribe(sp, output_dir=output_dir)
            else:
                r = self.melodic_transcriber.transcribe(sp, output_dir=output_dir, stem_type=st)
            track_results.append(r)

        merged = output_dir / f"{audio_path.stem}_merged.mid"
        merged_pm = self.merger.merge(track_results, merged)

        pm = self.quantizer.quantize(merged_pm, bpm=bpm)
        quantized = output_dir / f"{audio_path.stem}_quantized.mid"
        if bpm:
            final = pretty_midi.PrettyMIDI(initial_tempo=bpm)
            for inst in pm.instruments:
                final.instruments.append(inst)
            final.write(str(quantized))
        else:
            pm.write(str(quantized))

        # 给所有分轨 MIDI 也覆写 BPM
        if bpm:
            for midi_file in output_dir.glob("*.mid"):
                try:
                    orig = pretty_midi.PrettyMIDI(str(midi_file))
                    fixed = pretty_midi.PrettyMIDI(initial_tempo=bpm)
                    for inst in orig.instruments:
                        fixed.instruments.append(inst)
                    fixed.write(str(midi_file))
                except Exception:
                    pass

        return {
            "midi_path": quantized,
            "track_results": track_results,
            "bpm": bpm,
        }
