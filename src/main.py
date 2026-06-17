"""Music Transcriber 入口"""

import os
import sys
import warnings
from pathlib import Path

# 静默 TensorFlow / basic-pitch 的启动警告
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import logging
logging.getLogger().setLevel(logging.WARNING)
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*use_reentrant.*")
warnings.filterwarnings("ignore", message=".*requires_grad.*")

# Windows: 注册 PyTorch DLL 路径
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
if sys.platform == "win32":
    import torch
    _torch_lib = Path(torch.__file__).parent / "lib"
    if _torch_lib.exists():
        os.add_dll_directory(str(_torch_lib))

# 禁用 torch dynamo 编译（避免每首歌重复编译导致卡顿）
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main():
    # Windows 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Audio-To-MIDI")
    app.setOrganizationName("MusicTranscriber")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
