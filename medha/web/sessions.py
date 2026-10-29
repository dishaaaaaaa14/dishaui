"""In-memory lesson sessions for the web API.

Each session owns a prepared playback; frames are rendered on demand with the
existing Qt-free renderer and serialized as normalized stroke polylines.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from medha.render.color import rgba
from medha.render.playback import LessonPlayback
from medha.render.scene import Board
from medha.studio.service import StudioOptions, StudioResult, generate_lesson, open_lesson

from .models import CheckpointOut, FrameOut, StrokeOut


def _hex(color_name: str, alpha: float = 1.0) -> str:
    red, green, blue, _a = rgba(color_name, alpha)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


@dataclass
class Session:
    session_id: str
    state: str = "queued"
    progress: list[str] = field(default_factory=list)
    error: str | None = None
    result: StudioResult | None = None
    playback: LessonPlayback | None = None
    fired: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def notify(self, message: str) -> None:
        with self.lock:
            self.progress.append(message)
            if len(self.progress) > 100:
                del self.progress[:-50]

    @property
    def duration_ms(self) -> int:
        return self.playback.duration_ms if self.playback is not None else 0

    def frame(self, t_ms: int) -> FrameOut:
        if self.playback is None:
            return FrameOut(t=max(0, t_ms), strokes=[])
        board = Board()
        clamped = max(0, min(self.duration_ms, int(t_ms)))
        self.playback.render_at(board, clamped)
        strokes: list[StrokeOut] = []
        for item in board.items:
            if item.progress <= 0.0 or len(item.points) < 2:
                continue
            strokes.append(
                StrokeOut(
                    points=[[float(x), float(y)] for x, y in item.points],
                    color=_hex(item.color, item.alpha),
                    width=float(item.width_px),
                    alpha=float(item.alpha),
                    progress=float(item.progress),
                )
            )
        return FrameOut(t=clamped, strokes=strokes)

    def checkpoint(self, t_ms: int) -> CheckpointOut | None:
        if self.playback is None:
            return None
        with self.lock:
            due = [
                cp
                for cp in self.playback.timeline.checkpoints
                if cp.step_id not in self.fired and cp.at_ms <= t_ms
            ]
            if not due:
                return None
            cp = due[0]
            self.fired.add(cp.step_id)
        return CheckpointOut(
            step_id=cp.step_id,
            at_ms=cp.at_ms,
            question=cp.question,
            expected=cp.expected,
            hints=list(cp.hints),
        )

    def reset_checkpoints(self) -> None:
        with self.lock:
            self.fired.clear()

    def seek(self, t_ms: int) -> None:
        with self.lock:
            self.fired = {
                cp.step_id
                for cp in (self.playback.timeline.checkpoints if self.playback else [])
                if cp.at_ms < max(0, int(t_ms))
            }


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(session_id=uuid.uuid4().hex[:12])
        with self._lock:
            self._sessions[session.session_id] = session
            if len(self._sessions) > 32:
                oldest = next(iter(self._sessions))
                if oldest != session.session_id:
                    del self._sessions[oldest]
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)


STORE = SessionStore()


def run_generate(session: Session, options: StudioOptions) -> None:
    try:
        session.state = "running"
        result = generate_lesson(options, progress=session.notify)
        with session.lock:
            session.result = result
            session.playback = result.playback
            session.state = "ready"
            session.fired.clear()
    except Exception as exc:
        session.state = "error"
        session.error = str(exc)


def run_open(session: Session, path: Path, options: StudioOptions) -> None:
    try:
        session.state = "running"
        result = open_lesson(path, options, progress=session.notify)
        with session.lock:
            session.result = result
            session.playback = result.playback
            session.state = "ready"
            session.fired.clear()
    except Exception as exc:
        session.state = "error"
        session.error = str(exc)
