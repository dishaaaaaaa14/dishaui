"""Qt worker wrappers for generated and opened lessons."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .service import StudioOptions, generate_lesson, open_lesson


class _Worker(QObject):
    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _run(self) -> None:
        raise NotImplementedError


class GenerateWorker(_Worker):
    def __init__(self, options: StudioOptions) -> None:
        super().__init__()
        self.options = options

    def _run(self) -> None:
        self.finished.emit(generate_lesson(self.options, self.status.emit))


class OpenWorker(_Worker):
    def __init__(self, path: Path, options: StudioOptions) -> None:
        super().__init__()
        self.path = path
        self.options = options

    def _run(self) -> None:
        self.finished.emit(open_lesson(self.path, self.options, self.status.emit))
