"""音源分离 — 基于 Meta Demucs (htdemucs / htdemucs_6s)"""

import warnings
from pathlib import Path

import torchaudio

from ..transcription.base import BaseSeparator, SeparationResult, StemType


class DemucsSeparator(BaseSeparator):
    """使用 Demucs 将混合音频分离为独立音轨"""

    FOUR_STEM = "htdemucs"
    SIX_STEM = "htdemucs_6s"

    def separate(self, audio_path: Path, output_dir: Path,
                 six_stem: bool = False) -> SeparationResult:
        model = self.SIX_STEM if six_stem else self.FOUR_STEM

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            from demucs import separate
            separate.main([
                "-n", model,
                "-o", str(output_dir),
                str(audio_path),
            ])

        stem_name = audio_path.stem
        stem_dir = output_dir / model / stem_name

        # 映射所有声部
        all_suffix_map = {
            "drums": StemType.DRUMS, "bass": StemType.BASS,
            "vocals": StemType.VOCALS, "other": StemType.OTHER,
            "guitar": StemType.GUITAR, "piano": StemType.PIANO,
        }

        stems = {}
        duration = 0.0
        sample_rate = 44100
        for suffix, stem_type in all_suffix_map.items():
            candidate = stem_dir / f"{suffix}.wav"
            if candidate.exists():
                stems[stem_type] = candidate
                if duration == 0.0:
                    info = torchaudio.info(str(candidate))
                    duration = info.num_frames / info.sample_rate
                    sample_rate = info.sample_rate

        return SeparationResult(stems=stems, sample_rate=sample_rate, duration=duration)
