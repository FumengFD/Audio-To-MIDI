"""转录引擎抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class StemType(Enum):
    """音轨类型"""
    DRUMS = "drums"
    BASS = "bass"
    VOCALS = "vocals"
    OTHER = "other"
    GUITAR = "guitar"
    PIANO = "piano"
    FULL = "full"  # 原始音频（未分离）


@dataclass
class NoteEvent:
    """单个音符事件"""
    start_time: float  # 起始时间 (秒)
    end_time: float    # 结束时间 (秒)
    pitch: int         # MIDI 音高 (0-127)
    velocity: int      # 力度 (0-127)
    instrument: str = ""  # 乐器名称（鼓件等）


@dataclass
class TrackResult:
    """单音轨转录结果"""
    stem_type: StemType
    notes: list[NoteEvent] = field(default_factory=list)
    midi_path: Path | None = None
    duration: float = 0.0
    tempo: float = 120.0


@dataclass
class SeparationResult:
    """音源分离结果"""
    stems: dict[StemType, Path]  # stem_type → 分离后的音频文件路径
    sample_rate: int = 44100
    duration: float = 0.0


class BaseSeparator(ABC):
    """音源分离器基类"""

    @abstractmethod
    def separate(self, audio_path: Path, output_dir: Path) -> SeparationResult:
        """将音频分离为独立音轨"""
        ...


class BaseTranscriber(ABC):
    """音符转录器基类"""

    @abstractmethod
    def transcribe(self, audio_path: Path, **kwargs) -> TrackResult:
        """从音频转录为音符事件"""
        ...

    @abstractmethod
    def supports_stem(self, stem_type: StemType) -> bool:
        """检查是否支持此音轨类型"""
        ...
