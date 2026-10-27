from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from medha.core.schema import LessonScript, split_sentences, validate_lesson
from medha.render.geometry import Transform
from medha.render.playback import LessonPlayback, prepare_playback
from medha.render.scene import Board
from medha.tts.speech import SpeechTrack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def load_lesson() -> LessonScript:
    return validate_lesson(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def fake_track(lesson: LessonScript) -> SpeechTrack:
    sentence_ms = tuple(
        tuple(500 for _ in split_sentences(step.narration)) for step in lesson.steps
    )
    return SpeechTrack(
        audio=np.zeros(24000, dtype=np.float32),
        sample_rate=24000,
        sentence_ms=sentence_ms,
        lead_ms=250,
        sentence_gap_ms=0,
        step_gap_ms=0,
        voice="af_heart",
        speed=1.0,
    )


def test_prepare_uses_speech_track_timing() -> None:
    lesson = load_lesson()
    prepared = prepare_playback(lesson, speech_track=fake_track(lesson))
    assert prepared.timeline.actions["a1"].start_ms == 250
    assert prepared.duration_ms > prepared.timeline.total_ms
    assert prepared.track is not None


def test_playback_pause_resume_seek_and_stop() -> None:
    prepared = prepare_playback(load_lesson(), use_tts=False)
    playback = LessonPlayback(prepared, play_audio=False)
    assert playback.position_ms() == 0
    assert not playback.playing

    playback.start()
    time.sleep(0.03)
    position = playback.position_ms()
    assert 10 <= position < 1000
    playback.pause()
    assert not playback.playing
    assert playback.position_ms() == position

    time.sleep(0.01)
    assert playback.position_ms() == position

    playback.seek(1000)
    assert playback.position_ms() == 1000
    playback.start()
    time.sleep(0.02)
    assert playback.position_ms() >= 1000
    playback.stop()
    assert playback.position_ms() == 0
    assert not playback.playing


def test_seek_is_clamped_and_frame_renders() -> None:
    prepared = prepare_playback(load_lesson(), use_tts=False)
    playback = LessonPlayback(prepared, play_audio=False)
    playback.seek(playback.duration_ms + 5000)
    assert playback.position_ms() == playback.duration_ms
    assert playback.is_finished()

    board = Board()
    playback.render(board)
    mesh = board.build(Transform(1600, 900))
    assert mesh.vertex_count > 0


def test_finished_playback_restarts_from_zero() -> None:
    prepared = prepare_playback(load_lesson(), use_tts=False)
    playback = LessonPlayback(prepared, play_audio=False)
    playback.seek(playback.duration_ms)
    playback.start()
    assert playback.position_ms() < 100
    playback.stop()
