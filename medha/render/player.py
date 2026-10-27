"""Play a validated lesson with Kokoro speech and synchronized board action."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import config
from medha.core.schema import LessonScript
from medha.lesson.store import load_lesson
from medha.tts.speech import SpeechTrack

from .playback import LessonPlayback, prepare_playback
from .scene import Board
from .window import run

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LESSON = ROOT / "content" / "lessons" / "newton.json"
logger = logging.getLogger(__name__)


def run_lesson(
    lesson: LessonScript,
    seconds: float | None = None,
    screenshot_path: Path | None = None,
    screenshot_at_s: float | None = None,
    use_tts: bool = True,
    play_audio: bool = True,
    voice: str = config.KOKORO_VOICE,
    speed: float = config.KOKORO_SPEED,
    speech_track: SpeechTrack | None = None,
) -> int:
    try:
        prepared = prepare_playback(
            lesson,
            use_tts=use_tts,
            speech_track=speech_track,
            voice=voice,
            speed=speed,
        )
    except Exception as exc:
        logger.warning("TTS unavailable; falling back to silent timeline: %s", exc)
        prepared = prepare_playback(lesson, use_tts=False)

    playback = LessonPlayback(prepared, play_audio=play_audio)
    duration_ms = int(seconds * 1000) if seconds is not None else playback.duration_ms
    if screenshot_at_s is None:
        screenshot_delay_ms = max(500, int(duration_ms * 0.8))
    else:
        screenshot_delay_ms = int(screenshot_at_s * 1000)
    duration_ms = max(duration_ms, screenshot_delay_ms + 1200)
    screenshot_path = screenshot_path.resolve() if screenshot_path is not None else None
    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    def frame(board: Board, _elapsed_s: float) -> None:
        playback.render(board)

    return run(
        frame_factory=frame,
        duration_ms=duration_ms,
        screenshot_path=screenshot_path,
        screenshot_delay_ms=screenshot_delay_ms,
        animate=True,
        on_start=playback.start,
        on_stop=playback.stop,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-render-player")
    parser.add_argument("--lesson", type=Path, default=DEFAULT_LESSON)
    parser.add_argument("--seconds", type=float, default=None)
    parser.add_argument("--screenshot", type=Path, default=None)
    parser.add_argument("--screenshot-at", type=float, default=None)
    parser.add_argument("--voice", default=config.KOKORO_VOICE)
    parser.add_argument("--speed", type=float, default=config.KOKORO_SPEED)
    parser.add_argument("--no-tts", action="store_true", help="use estimated silent timing")
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="render silently but use TTS timing",
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    lesson = load_lesson(args.lesson)
    seconds = args.seconds
    screenshot_at = args.screenshot_at
    if args.smoke:
        seconds = seconds or 8.0
        screenshot_at = screenshot_at or 7.0
    return run_lesson(
        lesson,
        seconds,
        args.screenshot,
        screenshot_at,
        use_tts=not args.no_tts,
        play_audio=not args.no_audio,
        voice=args.voice,
        speed=args.speed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
