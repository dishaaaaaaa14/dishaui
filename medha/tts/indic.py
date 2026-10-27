"""Optional Indic Parler-TTS engine, resampled to Medha's track format."""

from __future__ import annotations

import logging
import os
from math import gcd
from pathlib import Path
from typing import Any

import numpy as np

import config
from medha.core.schema import LanguageCode

logger = logging.getLogger(__name__)


def _resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    if source_rate == target_rate or audio.size == 0:
        return audio
    from scipy.signal import resample_poly

    common = gcd(source_rate, target_rate)
    up = target_rate // common
    down = source_rate // common
    return np.asarray(resample_poly(audio, up, down), dtype=np.float32).reshape(-1)


class IndicParlerEngine:
    engine_id = "indic-parler"

    def __init__(
        self,
        language: LanguageCode,
        *,
        model_dir: Path | None = None,
        description: str = config.INDIC_PARLER_DESCRIPTION,
        speed: float = 1.0,
        device: str = "cpu",
        token: str | None = None,
    ) -> None:
        if language not in config.INDIC_LANG_CODES:
            raise ValueError(f"Indic TTS does not support {language!r}")
        self.language = language
        self.model_dir = (
            Path(model_dir) if model_dir is not None else config.INDIC_PARLER_MODEL_DIR
        )
        self.description = description
        self.speed = speed
        self.device = device
        self.token = token or os.environ.get("HF_TOKEN") or None
        self.voice = f"indic-{language}"
        self._model: Any = None
        self._tokenizer: Any = None
        self._description_tokenizer: Any = None
        self._description_inputs: Any = None
        self._sample_rate = config.TTS_SAMPLE_RATE

    def _source(self) -> tuple[str, bool]:
        if (self.model_dir / "config.json").is_file():
            return str(self.model_dir), True
        return config.INDIC_PARLER_MODEL_ID, False

    def _description_source(self) -> str:
        if (config.INDIC_PARLER_DESCRIPTION_TOKENIZER_DIR / "tokenizer.json").is_file():
            return str(config.INDIC_PARLER_DESCRIPTION_TOKENIZER_DIR)
        return config.INDIC_PARLER_DESCRIPTION_TOKENIZER

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Indic speech needs requirements/indic.txt (parler-tts and torch)"
            ) from exc

        source, local = self._source()
        kwargs: dict[str, object] = {"token": self.token}
        if not local:
            kwargs["revision"] = config.INDIC_PARLER_REVISION
        logger.info("Loading Indic Parler-TTS from %s", source)
        try:
            self._model = (
                ParlerTTSForConditionalGeneration.from_pretrained(
                    source,
                    torch_dtype=torch.float32,
                    **kwargs,
                )
                .to(self.device)
                .eval()
            )
            self._tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
            description_source = self._description_source()
            description_kwargs: dict[str, object] = {"token": self.token}
            if not Path(description_source).is_dir():
                description_kwargs["revision"] = (
                    "0613663d0d48ea86ba8cb3d7a44f0f65dc596a2a"
                )
            self._description_tokenizer = AutoTokenizer.from_pretrained(
                description_source, **description_kwargs
            )
            self._description_inputs = self._description_tokenizer(
                self.description, return_tensors="pt"
            ).to(self.device)
            self._sample_rate = int(
                getattr(self._model.config, "sampling_rate", 44100)
            )
        except Exception as exc:
            raise RuntimeError(f"cannot load Indic Parler-TTS: {exc}") from exc

    def synthesize(self, text: str) -> np.ndarray:
        text = text.strip()
        if not text:
            raise ValueError("cannot synthesize empty text")
        self._load()
        import torch

        try:
            prompt = self._tokenizer(text, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                generation = self._model.generate(
                    input_ids=self._description_inputs.input_ids,
                    attention_mask=self._description_inputs.attention_mask,
                    prompt_input_ids=prompt.input_ids,
                    prompt_attention_mask=prompt.attention_mask,
                    do_sample=False,
                )
        except Exception as exc:
            raise RuntimeError(f"Indic Parler-TTS inference failed: {exc}") from exc
        audio = generation.detach().cpu().numpy()
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            raise RuntimeError(f"Indic Parler-TTS produced no audio for: {text!r}")
        return _resample(samples, self._sample_rate, config.TTS_SAMPLE_RATE)
