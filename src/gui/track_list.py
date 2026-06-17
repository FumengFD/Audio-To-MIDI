"""音轨列表 — 选择要处理的音轨"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)


class TrackList(QGroupBox):
    """音轨选择面板"""

    def __init__(self, parent=None):
        super().__init__("音轨", parent)
        layout = QVBoxLayout(self)

        self._checks = {}
        track_names = {
            "drums":  "🥁 鼓",
            "bass":   "🎸 贝斯",
            "vocals": "🎤 人声",
            "guitar": "🎸 吉他",
            "piano":  "🎹 钢琴",
            "other":  "🎵 其他",
        }
        for key, label in track_names.items():
            cb = QCheckBox(label)
            cb.setChecked(True)
            layout.addWidget(cb)
            self._checks[key] = cb

        layout.addStretch()

    def enabled_stems(self) -> list[str]:
        """返回选中的音轨 key 列表"""
        return [k for k, cb in self._checks.items() if cb.isChecked()]

    def set_all(self, checked: bool):
        for cb in self._checks.values():
            cb.setChecked(checked)
