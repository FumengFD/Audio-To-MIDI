"""主窗口 — PySide6 图形界面"""

from pathlib import Path

import librosa
import pretty_midi
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..pipeline import TranscriptionPipeline
from .piano_roll import PianoRollView
from .track_list import TrackList
from .waveform_view import WaveformView
from .worker import WorkerThread


class MainWindow(QMainWindow):
    """音乐扒谱主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio-To-MIDI")
        self.setMinimumSize(1200, 750)
        self.setAcceptDrops(True)

        self._pipeline = TranscriptionPipeline()
        self._audio_path: Path | None = None
        self._output_dir: Path | None = None
        self._result_midi: pretty_midi.PrettyMIDI | None = None
        self._result_midi_path: Path | None = None


        self._build_ui()
        self._setup_status_bar()

    # ── UI 构建 ─────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 工具栏
        toolbar = QHBoxLayout()
        self._btn_import = QPushButton("📁 导入音频")
        self._btn_import.clicked.connect(self._on_import)
        self._btn_transcribe = QPushButton("🎹 开始扒谱")
        self._btn_transcribe.clicked.connect(self._on_transcribe)
        self._btn_transcribe.setEnabled(False)
        self._btn_export_midi = QPushButton("💾 导出 MIDI")
        self._btn_export_midi.clicked.connect(self._on_export_midi)
        self._btn_export_midi.setEnabled(False)
        self._btn_batch = QPushButton("📂 批量扒谱")
        self._btn_batch.clicked.connect(self._on_batch)

        toolbar.addWidget(self._btn_import)
        toolbar.addWidget(self._btn_transcribe)
        toolbar.addWidget(self._btn_export_midi)
        toolbar.addWidget(self._btn_batch)
        from PySide6.QtWidgets import QSpinBox

        toolbar.addWidget(QLabel(" BPM:"))
        self._bpm_input = QSpinBox()
        self._bpm_input.setRange(0, 300)
        self._bpm_input.setValue(0)
        self._bpm_input.setSuffix(" (自动)")
        self._bpm_input.setSpecialValueText("自动")
        self._bpm_input.valueChanged.connect(lambda v: self._bpm_input.setSuffix("" if v==0 else " (手动)"))
        toolbar.addWidget(self._bpm_input)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # 主分割区
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左面板：波形 + 钢琴卷帘
        left_panel = QVBoxLayout()

        self._wave_view = WaveformView()
        left_panel.addWidget(self._wave_view, 3)

        self._piano_roll = PianoRollView()
        left_panel.addWidget(self._piano_roll, 3)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        splitter.addWidget(left_widget)

        # 右面板：音轨列表
        right_panel = QVBoxLayout()

        self._track_list = TrackList()
        right_panel.addWidget(self._track_list)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        splitter.addWidget(right_widget)

        splitter.setSizes([700, 350])
        root.addWidget(splitter, 1)

    def _setup_status_bar(self):
        self._status = QStatusBar()
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(300)
        self._progress.setVisible(False)
        self._progress.setStyleSheet("QProgressBar { border: 1px solid #aaa; border-radius: 3px; background: #eee; } QProgressBar::chunk { background: #4CAF50; }")
        self._status.addPermanentWidget(self._progress)
        self._status_label = QLabel("就绪")
        self._status.addWidget(self._status_label)
        self.setStatusBar(self._status)

    # ── 事件处理 ────────────────────────────────

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入音频文件", "",
            "音频文件 (*.flac *.wav *.mp3 *.ogg *.m4a *.aiff);;All (*.*)",
        )
        if path:
            self._load_audio(Path(path))

    def _load_audio(self, path: Path):
        self._audio_path = path
        self._status_label.setText(f"已加载: {self._audio_path.name}")
        self._bpm_input.setValue(0)  # 重置 BPM 为自动
        self._piano_roll.clear()
        self._result_midi = None
        self._result_midi_path = None
        self._btn_export_midi.setEnabled(False)
        try:
            y, sr = librosa.load(str(self._audio_path), sr=None, mono=False)
            self._wave_view.set_audio(y, sr)
            self._btn_transcribe.setEnabled(True)

            # 自动检测 BPM
            y_mono = y if y.ndim == 1 else y.mean(0)
            tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
            if tempo > 0:
                bpm = int(round(float(tempo)))
                self._bpm_input.setValue(bpm)
                self._status_label.setText(
                    f"已加载: {self._audio_path.name}  检测到 {bpm} BPM"
                )
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    # ── 拖拽导入 ──────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".flac", ".wav", ".mp3", ".ogg", ".m4a", ".aiff"):
                paths.append(p)

        if not paths:
            return

        if len(paths) == 1:
            self._load_audio(paths[0])
        else:
            # 多个文件 → 批量扒谱
            self._start_batch(paths)

    def _on_transcribe(self):
        if not self._audio_path:
            return

        # 输出目录：原音频旁边创建 "歌名_扒谱" 文件夹
        self._output_dir = self._audio_path.parent / f"{self._audio_path.stem}_result"
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._set_busy(True)
        self._status_label.setText("正在扒谱…")
        enabled = self._track_list.enabled_stems()
        self._bpm_input.interpretText()  # 强制提交输入的文字
        bpm = self._bpm_input.value() or None  # 0 = 自动
        self._worker = WorkerThread(self._pipeline.run, self._audio_path, self._output_dir, enabled, bpm)
        self._worker.finished.connect(self._on_transcribe_done)
        self._worker.error.connect(self._on_transcribe_error)
        self._worker.start()

    def _on_transcribe_done(self, result: dict):
        self._set_busy(False)

        # 更新钢琴卷帘
        midi_path = result.get("midi_path")
        if midi_path:
            self._result_midi_path = Path(midi_path)
            pm = pretty_midi.PrettyMIDI(str(midi_path))
            self._piano_roll.set_midi(pm)
            self._result_midi = pm
            self._btn_export_midi.setEnabled(True)


        self._status_label.setText(f"扒谱完成 — {self._output_dir}")
        if result.get("bpm"):
            self._status_label.setText(
                f"扒谱完成 (BPM={result['bpm']}) — {self._output_dir}"
            )

        out_files = "\n".join(
            f"  • {f.name}" for f in sorted(self._output_dir.iterdir())
            if f.is_file()
        )
        QMessageBox.information(
            self, "扒谱完成",
            f"输出目录：\n{self._output_dir}\n\n生成文件：\n{out_files}",
        )

    def _on_transcribe_error(self, msg: str):
        self._set_busy(False)
        self._status_label.setText("扒谱失败 ❌")
        QMessageBox.critical(self, "扒谱失败", msg)

    def _on_export_midi(self):
        if self._result_midi is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出 MIDI", f"{self._audio_path.stem}.mid", "MIDI (*.mid)",
        )
        if path:
            import shutil
            shutil.copy(self._result_midi_path, path)
            self._status_label.setText(f"MIDI 已导出: {Path(path).name}")



    # ── 批量扒谱 ──────────────────────────────

    def _on_batch(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "批量选择音频文件", "",
            "音频文件 (*.flac *.wav *.mp3 *.ogg *.m4a *.aiff);;All (*.*)",
        )
        if paths:
            self._start_batch([Path(p) for p in paths])

    def _start_batch(self, files: list[Path]):
        self._set_busy(True)
        self._status_label.setText(f"批量扒谱 0/{len(files)}…")
        self._progress.setRange(0, len(files))
        self._progress.show()

        self._batch_worker = WorkerThread(self._process_batch, files,
                                           self._bpm_input.value() or None,
                                           self._track_list.enabled_stems())
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_done)
        self._batch_worker.error.connect(self._on_batch_error)
        self._batch_worker.start()

    def _process_batch(self, files: list[Path], bpm, enabled) -> list[tuple[Path, str]]:
        results = []
        for i, f in enumerate(files):
            results.append((f, "处理中…"))
            self._batch_worker.progress.emit(f"批量扒谱 {i+1}/{len(files)}: {f.name}")

            output_dir = f.parent / f"{f.stem}_result"

            try:
                self._pipeline.run(f, output_dir, enabled, bpm)
                results[-1] = (f, "✅ 完成")
            except Exception as e:
                results[-1] = (f, f"❌ {e}")
        return results

    def _on_batch_progress(self, msg: str):
        self._status_label.setText(msg)
        # 从消息里提取当前进度
        import re
        m = re.search(r"(\d+)/(\d+)", msg)
        if m:
            self._progress.setValue(int(m.group(1)))

    def _on_batch_done(self, results: list):
        self._set_busy(False)
        self._progress.setVisible(False)
        self._status_label.setText(f"批量扒谱完成 — {len(results)} 个文件")

        text = "\n".join(f"{r[0].name}: {r[1]}" for r in results)
        QMessageBox.information(self, "批量扒谱完成", text)

    def _on_batch_error(self, msg: str):
        self._set_busy(False)
        QMessageBox.critical(self, "批量扒谱错误", msg)


    # ── 辅助方法 ────────────────────────────────

    def _set_busy(self, busy: bool):
        self._btn_import.setEnabled(not busy)
        self._btn_transcribe.setEnabled(not busy)
        self._progress.setVisible(busy)
        if busy:
            self._progress.setRange(0, 0)  # 不确定进度条
        else:
            self._progress.setRange(0, 100)

    def closeEvent(self, event):
        for attr in ["_worker", "_batch_worker"]:
            w = getattr(self, attr, None)
            if w and w.isRunning():
                w.stop()
        event.accept()
