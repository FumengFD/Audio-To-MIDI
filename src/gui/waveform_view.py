"""波形视图 — 音频波形显示 + 选段"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget


class WaveformView(QWidget):
    """可交互的音频波形视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "时间 (秒)")
        self._plot.setLabel("left", "振幅")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._curve = self._plot.plot(pen="c")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def set_audio(self, audio_data: np.ndarray, sample_rate: int):
        """加载音频数据并显示波形"""
        self._curve.clear()
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=0)  # 立体声→单声道：沿声道轴求均值

        # 降采样以避免绘图卡顿
        max_points = 200_000
        if len(audio_data) > max_points:
            step = len(audio_data) // max_points
            audio_data = audio_data[::step]

        time_axis = np.arange(len(audio_data)) / sample_rate
        self._curve.clear()
        self._curve.setData(time_axis, audio_data, fillLevel=0, brush=(0, 200, 255, 80))
        self._plot.autoRange()

    def clear(self):
        self._curve.clear()
