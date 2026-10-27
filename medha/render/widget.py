"""Embeddable QOpenGLWidget board used by Studio."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from .geometry import Transform
from .gl import GLRenderer
from .scene import Board

SceneFactory = Callable[[Board], None]
FrameFactory = Callable[[Board, float], None]


class BoardWidget(QOpenGLWidget):
    def __init__(
        self,
        scene_factory: SceneFactory | None = None,
        frame_factory: FrameFactory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene_factory = scene_factory
        self._frame_factory = frame_factory
        self._renderer = GLRenderer()
        self._board = Board()
        self._started_at = time.perf_counter()
        self.setMinimumSize(480, 360)

    def initializeGL(self) -> None:
        self._renderer.initialize()
        self._board = Board()
        self._started_at = time.perf_counter()
        if self._scene_factory is not None:
            self._scene_factory(self._board)

    def resizeGL(self, width: int, height: int) -> None:
        self._renderer.resize(width, height)

    def paintGL(self) -> None:
        elapsed = time.perf_counter() - self._started_at
        if self._frame_factory is not None:
            self._frame_factory(self._board, elapsed)
        self._renderer.draw_background(elapsed)
        transform = Transform(max(1, self.width()), max(1, self.height()))
        self._renderer.draw_mesh(self._board.build(transform))
