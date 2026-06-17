"""Music Transcriber 入口"""

import logging
import os
import sys
import warnings
from pathlib import Path

# 静默 TensorFlow / basic-pitch 的启动警告
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
logging.getLogger().setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*use_reentrant.*")
warnings.filterwarnings("ignore", message=".*requires_grad.*")

# Windows: 注册 PyTorch DLL 路径
if sys.platform == "win32":
    import torch
    _torch_lib = Path(torch.__file__).parent / "lib"
    if _torch_lib.exists():
        os.add_dll_directory(str(_torch_lib))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Audio-To-MIDI")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
