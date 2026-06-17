"""钢琴卷帘视图 — MIDI 音符可视化"""

import pretty_midi
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget


class PianoRollView(QWidget):
    """钢琴卷帘 — 展示 MIDI 音符的位置与时长"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Time", "s")
        self._plot.setLabel("left", "MIDI Pitch")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setYRange(0, 127)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def set_midi(self, midi: pretty_midi.PrettyMIDI):
        """从 PrettyMIDI 对象加载并绘制音符"""
        self._plot.clear()

        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
        color_idx = 0

        for inst in midi.instruments:
            color = colors[color_idx % len(colors)]
            color_idx += 1
            for note in inst.notes:
                rect = pg.QtWidgets.QGraphicsRectItem(
                    note.start, note.pitch,
                    note.end - note.start, 1,
                )
                rect.setPen(pg.mkPen(None))
                rect.setBrush(pg.mkBrush(color))
                self._plot.addItem(rect)

        self._plot.autoRange()

    def clear(self):
        self._plot.clear()
