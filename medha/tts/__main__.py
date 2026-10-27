"""Synthesize a lesson or a single sentence to a WAV file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import config
from medha.core.schema import LessonScript, validate_lesson

from .kokoro import KokoroEngine
from .speech import SpeechCache, synthesize_lesson

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LESSON = ROOT / "content" / "lessons" / "newton.json"


def _load_lesson(path: Path) -> LessonScript:
    return validate_lesson(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-tts")
    parser.add_argument("--lesson", type=Path, default=DEFAULT_LESSON)
    parser.add_argument("--text", default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--voice", default=config.KOKORO_VOICE)
    parser.add_argument("--speed", type=float, default=config.KOKORO_SPEED)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)

    config.ensure_dirs()
    engine = KokoroEngine(voice=args.voice, speed=args.speed)
    cache = None if args.no_cache else SpeechCache()

    if args.smoke or args.text:
        text = args.text or "Force equals mass times acceleration."
        samples = (
            cache.load(text, args.voice, args.speed, config.TTS_SAMPLE_RATE)
            if cache
            else None
        )
        if samples is None:
            samples = engine.synthesize(text)
            if cache is not None:
                cache.store(text, args.voice, args.speed, config.TTS_SAMPLE_RATE, samples)
        out = args.out or (config.TTS_CACHE_DIR / "smoke.wav")
        out.parent.mkdir(parents=True, exist_ok=True)
        from soundfile import write

        write(str(out), np.asarray(samples, dtype=np.float32), config.TTS_SAMPLE_RATE)
        summary = {
            "text": text,
            "out": str(out),
            "duration_ms": round(len(samples) / config.TTS_SAMPLE_RATE * 1000),
            "sample_rate": config.TTS_SAMPLE_RATE,
        }
        print(json.dumps(summary, indent=2))
        return 0

    lesson = _load_lesson(args.lesson)
    track = synthesize_lesson(
        lesson,
        engine=engine,
        cache=cache,
        use_cache=not args.no_cache,
        voice=args.voice,
        speed=args.speed,
    )
    out = args.out or (config.TTS_CACHE_DIR / f"{lesson.lesson_id}.wav")
    track.write_wav(out)
    print(
        json.dumps(
            {
                "lesson_id": lesson.lesson_id,
                "out": str(out),
                "duration_ms": track.duration_ms,
                "sentence_ms": track.sentence_ms,
                "voice": track.voice,
                "speed": track.speed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
