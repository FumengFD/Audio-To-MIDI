"""后台工作线程 — 避免阻塞 UI"""

from PySide6.QtCore import QThread, Signal


class WorkerThread(QThread):
    """在后台执行耗时操作的线程"""
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._is_running = True

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        self._is_running = False
        self.terminate()
        self.wait(2000)
