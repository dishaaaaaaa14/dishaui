"""Wall-clock audio playback used as the master clock for board animation."""

from __future__ import annotations

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)


class AudioPlayer:
    def __init__(self, samples: np.ndarray, sample_rate: int, enabled: bool = True) -> None:
        self.samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        self.sample_rate = sample_rate
        self.enabled = enabled
        self._started_at: float | None = None
        self._offset_ms = 0
        self._duration_ms = round(self.samples.size / sample_rate * 1000)

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    def start(self, at_ms: int = 0) -> None:
        if self._started_at is not None:
            return
        self._offset_ms = max(0, min(self._duration_ms, int(at_ms)))
        if self.enabled:
            try:
                import sounddevice as sd

                start = round(self.samples.size * self._offset_ms / max(1, self._duration_ms))
                if start < self.samples.size:
                    sd.play(self.samples[start:], self.sample_rate)
            except Exception as exc:
                logger.warning("Audio output unavailable (%s); continuing silently", exc)
                self.enabled = False
        self._started_at = time.perf_counter()

    def clock_ms(self) -> int:
        if self._started_at is None:
            return self._offset_ms
        elapsed = int((time.perf_counter() - self._started_at) * 1000)
        return self._offset_ms + max(0, elapsed)

    def position_ms(self) -> int:
        return min(self._duration_ms, self.clock_ms())

    def stop(self) -> None:
        if self.enabled:
            try:
                import sounddevice as sd

                sd.stop()
            except Exception:
                pass
        self._started_at = None
        self._offset_ms = 0
