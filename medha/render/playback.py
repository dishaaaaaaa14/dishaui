"""Reusable lesson playback: board visuals, audio clock, pause and seek."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import config
from medha.core.schema import LessonScript
from medha.tts.audio import AudioPlayer
from medha.tts.speech import SpeechTrack, synthesize_lesson

from .actions import ActionVisual, build_visuals, render_frame
from .scene import Board
from .timeline import CheckpointTiming, Timeline, build_timeline


@dataclass(frozen=True)
class PreparedPlayback:
    lesson: LessonScript
    visuals: dict[str, ActionVisual]
    timeline: Timeline
    track: SpeechTrack | None = None
    tail_ms: int = 1200

    @property
    def duration_ms(self) -> int:
        audio_ms = self.track.duration_ms if self.track is not None else 0
        return max(self.timeline.total_ms, audio_ms) + max(0, self.tail_ms)


def prepare_playback(
    lesson: LessonScript,
    *,
    use_tts: bool = False,
    speech_track: SpeechTrack | None = None,
    voice: str = config.KOKORO_VOICE,
    speed: float = config.KOKORO_SPEED,
    tail_ms: int = 1200,
) -> PreparedPlayback:
    visuals = build_visuals(lesson)
    track = speech_track
    if track is None and use_tts:
        track = synthesize_lesson(lesson, voice=voice, speed=speed)
    if track is not None:
        timeline = build_timeline(
            lesson,
            sentence_ms=[list(step) for step in track.sentence_ms],
            step_gap_ms=track.step_gap_ms,
            sentence_gap_ms=track.sentence_gap_ms,
            lead_ms=track.lead_ms,
        )
    else:
        timeline = build_timeline(lesson)
    return PreparedPlayback(
        lesson=lesson,
        visuals=visuals,
        timeline=timeline,
        track=track,
        tail_ms=max(0, tail_ms),
    )


class LessonPlayback:
    """Render a prepared lesson and keep the board locked to its audio clock."""

    def __init__(self, prepared: PreparedPlayback, *, play_audio: bool = True) -> None:
        self.prepared = prepared
        self._player = (
            AudioPlayer(
                prepared.track.audio,
                prepared.track.sample_rate,
                enabled=play_audio,
            )
            if prepared.track is not None
            else None
        )
        self._position_ms = 0
        self._started_at: float | None = None
        self._playing = False
        self._fired_checkpoints: set[str] = set()

    @property
    def duration_ms(self) -> int:
        return self.prepared.duration_ms

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def visuals(self) -> dict[str, ActionVisual]:
        return self.prepared.visuals

    @property
    def timeline(self) -> Timeline:
        return self.prepared.timeline

    def position_ms(self) -> int:
        if not self._playing or self._started_at is None:
            return self._position_ms
        elapsed = int((time.perf_counter() - self._started_at) * 1000)
        return min(self.duration_ms, self._position_ms + max(0, elapsed))

    def is_finished(self) -> bool:
        return self.position_ms() >= self.duration_ms

    def start(self) -> None:
        if self._playing:
            return
        if self._position_ms >= self.duration_ms:
            self._position_ms = 0
            self._fired_checkpoints.clear()
        self._started_at = time.perf_counter()
        self._playing = True
        if self._player is not None:
            self._player.start(self._position_ms)

    def pause(self) -> None:
        if not self._playing:
            return
        self._position_ms = self.position_ms()
        self._playing = False
        self._started_at = None
        if self._player is not None:
            self._player.stop()

    def stop(self) -> None:
        self._playing = False
        self._started_at = None
        self._position_ms = 0
        self._fired_checkpoints.clear()
        if self._player is not None:
            self._player.stop()

    def seek(self, position_ms: int) -> None:
        target = max(0, min(self.duration_ms, int(position_ms)))
        was_playing = self._playing
        if self._player is not None:
            self._player.stop()
        self._position_ms = target
        for checkpoint in self.timeline.checkpoints:
            if checkpoint.at_ms < target:
                self._fired_checkpoints.add(checkpoint.step_id)
            else:
                self._fired_checkpoints.discard(checkpoint.step_id)
        if was_playing:
            self._playing = False
            self.start()

    def take_checkpoint(self, position_ms: int | None = None) -> CheckpointTiming | None:
        """Return the next due checkpoint once, so the UI can pause and ask."""
        position = self.position_ms() if position_ms is None else int(position_ms)
        for checkpoint in self.timeline.checkpoints:
            if checkpoint.step_id in self._fired_checkpoints:
                continue
            if checkpoint.at_ms <= position:
                self._fired_checkpoints.add(checkpoint.step_id)
                return checkpoint
        return None

    def reset_checkpoints(self) -> None:
        self._fired_checkpoints.clear()

    def render(self, board: Board) -> None:
        render_frame(board, self.prepared.visuals, self.prepared.timeline, self.position_ms())

    def render_at(self, board: Board, position_ms: int) -> None:
        render_frame(
            board,
            self.prepared.visuals,
            self.prepared.timeline,
            max(0, min(self.duration_ms, int(position_ms))),
        )

    def write_audio(self, path: Path) -> Path | None:
        if self.prepared.track is None:
            return None
        return self.prepared.track.write_wav(path)
