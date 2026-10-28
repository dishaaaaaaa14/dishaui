"""Sentence-level speech generation, cache, and lesson audio assembly."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

import config
from medha.core.schema import LessonScript, split_sentences

logger = logging.getLogger(__name__)


class Synthesizer(Protocol):
    voice: str
    speed: float

    def synthesize(self, text: str) -> np.ndarray: ...


@dataclass(frozen=True)
class SpeechTrack:
    audio: np.ndarray
    sample_rate: int
    sentence_ms: tuple[tuple[int, ...], ...]
    lead_ms: int
    sentence_gap_ms: int
    step_gap_ms: int
    voice: str
    speed: float

    @property
    def duration_ms(self) -> int:
        return round(len(self.audio) / self.sample_rate * 1000)

    def write_wav(self, path: Path) -> Path:
        import soundfile as sf

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), self.audio, self.sample_rate, subtype="PCM_16")
        return path


def _cache_key(
    text: str,
    voice: str,
    speed: float,
    sample_rate: int,
    engine: str = "kokoro",
) -> str:
    payload = "|".join(
        (
            config.TTS_CACHE_VERSION,
            engine,
            config.KOKORO_REVISION,
            voice,
            f"{speed:.6f}",
            str(sample_rate),
            text,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SpeechCache:
    """Per-sentence WAV cache; a miss never requires the lesson model to load."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else config.TTS_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: str) -> tuple[Path, Path]:
        return self.cache_dir / f"{key}.wav", self.cache_dir / f"{key}.json"

    def load(
        self,
        text: str,
        voice: str,
        speed: float,
        sample_rate: int,
        engine: str = "kokoro",
    ) -> np.ndarray | None:
        import soundfile as sf

        key = _cache_key(text, voice, speed, sample_rate, engine)
        wav_path, meta_path = self._paths(key)
        if not wav_path.is_file() or not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sample_rate") != sample_rate:
                return None
            data, actual_rate = sf.read(str(wav_path), dtype="float32", always_2d=False)
        except (OSError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring unreadable TTS cache entry %s", wav_path)
            return None
        if actual_rate != sample_rate:
            return None
        return np.asarray(data, dtype=np.float32).reshape(-1)

    def store(
        self,
        text: str,
        voice: str,
        speed: float,
        sample_rate: int,
        samples: np.ndarray,
        engine: str = "kokoro",
    ) -> None:
        import soundfile as sf

        key = _cache_key(text, voice, speed, sample_rate, engine)
        wav_path, meta_path = self._paths(key)
        sample_data = np.asarray(samples, dtype=np.float32).reshape(-1)
        tmp_wav = wav_path.with_suffix(".tmp.wav")
        tmp_meta = meta_path.with_suffix(".tmp.json")
        sf.write(str(tmp_wav), sample_data, sample_rate, subtype="PCM_16")
        meta = {
            "version": config.TTS_CACHE_VERSION,
            "text": text,
            "voice": voice,
            "speed": speed,
            "engine": engine,
            "sample_rate": sample_rate,
            "duration_ms": round(len(sample_data) / sample_rate * 1000),
        }
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp_wav.replace(wav_path)
        tmp_meta.replace(meta_path)


def _silence(sample_rate: int, duration_ms: int) -> np.ndarray:
    count = max(0, round(sample_rate * duration_ms / 1000))
    return np.zeros(count, dtype=np.float32)


def synthesize_lesson(
    lesson: LessonScript,
    engine: Synthesizer | None = None,
    cache: SpeechCache | None = None,
    use_cache: bool = True,
    voice: str = config.KOKORO_VOICE,
    speed: float = config.KOKORO_SPEED,
    sample_rate: int = config.TTS_SAMPLE_RATE,
    lead_ms: int = config.TTS_LEAD_MS,
    sentence_gap_ms: int = config.TTS_SENTENCE_GAP_MS,
    step_gap_ms: int = config.TTS_STEP_GAP_MS,
) -> SpeechTrack:
    """Generate or load every sentence and assemble a playable lesson track."""
    automatic_engine = engine is None
    if engine is None:
        if lesson.language == "en":
            from .kokoro import KokoroEngine

            engine = KokoroEngine(voice=voice, speed=speed)
        else:
            from .indic import IndicParlerEngine

            engine = IndicParlerEngine(language=lesson.language, speed=speed)
    if not automatic_engine:
        if getattr(engine, "voice", voice) != voice:
            raise ValueError(f"engine voice is {engine.voice!r}, expected {voice!r}")
        if getattr(engine, "speed", speed) != speed:
            raise ValueError(f"engine speed is {engine.speed!r}, expected {speed!r}")
    voice = str(getattr(engine, "voice", voice))
    engine_id = str(getattr(engine, "engine_id", "kokoro"))
    if not use_cache:
        cache = None
    elif cache is None:
        cache = SpeechCache()

    parts: list[np.ndarray] = [np.zeros(0, dtype=np.float32)]
    if lead_ms > 0:
        parts.append(_silence(sample_rate, lead_ms))
    sentence_ms: list[tuple[int, ...]] = []
    for step_index, step in enumerate(lesson.steps):
        sentences = split_sentences(step.narration)
        if not sentences:
            sentence_ms.append(())
            continue
        step_durations: list[int] = []
        for sentence_index, sentence in enumerate(sentences):
            samples = (
                cache.load(sentence, voice, speed, sample_rate, engine_id)
                if cache is not None
                else None
            )
            if samples is None:
                samples = engine.synthesize(sentence)
                if samples.size == 0:
                    raise RuntimeError(f"empty speech for sentence: {sentence!r}")
                if cache is not None:
                    cache.store(sentence, voice, speed, sample_rate, samples, engine_id)
            samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            step_durations.append(round(samples.size / sample_rate * 1000))
            parts.append(samples)
            if sentence_index < len(sentences) - 1:
                parts.append(_silence(sample_rate, sentence_gap_ms))
        sentence_ms.append(tuple(step_durations))
        if step_index < len(lesson.steps) - 1:
            parts.append(_silence(sample_rate, step_gap_ms))

    audio = np.concatenate(parts).astype(np.float32)
    return SpeechTrack(
        audio=audio,
        sample_rate=sample_rate,
        sentence_ms=tuple(sentence_ms),
        lead_ms=max(0, lead_ms),
        sentence_gap_ms=max(0, sentence_gap_ms),
        step_gap_ms=max(0, step_gap_ms),
        voice=voice,
        speed=speed,
    )
