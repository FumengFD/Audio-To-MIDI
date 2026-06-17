"""钢琴增强转录 — 基于 Transkun (ISMIR 2024, 98.33% F1 on MAESTRO)"""

from pathlib import Path

import numpy as np
import pretty_midi
import torch

from .base import BaseTranscriber, NoteEvent, StemType, TrackResult


# 全局模型缓存（只加载一次）
_TRANSKUN_MODEL = None
_TRANSKUN_FS = None


def _get_transkun_model():
    global _TRANSKUN_MODEL, _TRANSKUN_FS
    if _TRANSKUN_MODEL is not None:
        return _TRANSKUN_MODEL, _TRANSKUN_FS

    import pkg_resources
    import moduleconf

    weight_path = pkg_resources.resource_filename(
        "transkun", "pretrained/2.0.pt"
    )
    conf_path = pkg_resources.resource_filename(
        "transkun", "pretrained/2.0.conf"
    )

    conf_manager = moduleconf.parseFromFile(conf_path)
    TransKun = conf_manager["Model"].module.TransKun
    conf = conf_manager["Model"].config

    checkpoint = torch.load(weight_path, map_location="cpu", weights_only=False)
    model = TransKun(conf=conf)
    if "best_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["best_state_dict"], strict=False)
    else:
        model.load_state_dict(checkpoint["state_dict"], strict=False)
    model.eval()

    _TRANSKUN_MODEL = model
    _TRANSKUN_FS = model.fs
    return model, model.fs


class TranskunTranscriber(BaseTranscriber):
    """使用 Transkun 进行高精度钢琴转录"""

    def supports_stem(self, stem_type: StemType) -> bool:
        return stem_type in (StemType.OTHER, StemType.PIANO, StemType.FULL)

    def transcribe(self, audio_path: Path, **kwargs) -> TrackResult:
        stem_type = kwargs.get("stem_type", StemType.OTHER)
        output_dir = kwargs.get("output_dir", Path("."))
        output_dir = Path(output_dir)
        midi_path = output_dir / f"{audio_path.stem}_piano_transkun.mid"

        model, model_fs = _get_transkun_model()

        # 读取音频
        import pydub
        audio = pydub.AudioSegment.from_file(str(audio_path))
        y = np.array(audio.get_array_of_samples(), dtype=np.float32)
        max_val = float(1 << (audio.sample_width * 8 - 1))  # 按位深归一化
        y = y.reshape(-1, audio.channels) / max_val
        fs = audio.frame_rate

        # 重采样到模型采样率
        if fs != model_fs:
            import soxr
            y = soxr.resample(y, fs, model_fs)

        # 转录
        with torch.no_grad():
            x = torch.from_numpy(y).float()
            notes_est = model.transcribe(x, discardSecondHalf=False)

        # 写 MIDI
        from transkun.Data import writeMidi
        out_midi = writeMidi(notes_est)
        out_midi.write(str(midi_path))

        # 读取回 pretty_midi
        pm = pretty_midi.PrettyMIDI(str(midi_path))
        notes: list[NoteEvent] = []
        for inst in pm.instruments:
            for note in inst.notes:
                notes.append(NoteEvent(
                    start_time=note.start,
                    end_time=note.end,
                    pitch=note.pitch,
                    velocity=note.velocity,
                    instrument="piano",
                ))

        return TrackResult(
            stem_type=stem_type,
            notes=notes,
            midi_path=midi_path,
            duration=pm.get_end_time(),
        )
