"""Lazy English-to-Indic translation with IndicTrans2."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Protocol

import config
from medha.core.schema import LanguageCode

logger = logging.getLogger(__name__)


class TranslationError(RuntimeError):
    pass


class Translator(Protocol):
    model_id: str

    def translate_batch(self, texts: list[str], target: LanguageCode) -> list[str]: ...


class IndicTransTranslator:
    """IndicTrans2 dist-200M on CPU, loaded only when translation is requested."""

    model_id = config.INDICTRANS2_MODEL_ID

    def __init__(
        self,
        model_dir: Path | None = None,
        *,
        revision: str = config.INDICTRANS2_REVISION,
        device: str = "cpu",
        token: str | None = None,
    ) -> None:
        self.model_dir = (
            Path(model_dir) if model_dir is not None else config.INDICTRANS2_MODEL_DIR
        )
        self.revision = revision
        self.device = device
        self.token = token or os.environ.get("HF_TOKEN") or None
        self._tokenizer: Any = None
        self._model: Any = None
        self._processor: Any = None

    def _source(self) -> str:
        if (self.model_dir / "config.json").is_file():
            return str(self.model_dir)
        return self.model_id

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from IndicTransToolkit.processor import IndicProcessor
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise TranslationError(
                "Indic translation needs requirements/indic.txt "
                "(IndicTransToolkit and torch)"
            ) from exc

        source = self._source()
        local = Path(source).is_dir()
        kwargs: dict[str, object] = {
            "trust_remote_code": True,
            "token": self.token,
        }
        if not local:
            kwargs["revision"] = self.revision
        logger.info("Loading IndicTrans2 from %s", source)
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
            self._model = (
                AutoModelForSeq2SeqLM.from_pretrained(
                    source,
                    torch_dtype=torch.float32,
                    **kwargs,
                )
                .to(self.device)
                .eval()
            )
            self._processor = IndicProcessor(inference=True)
        except Exception as exc:
            raise TranslationError(f"cannot load IndicTrans2: {exc}") from exc

    def translate_batch(
        self,
        texts: list[str],
        target: LanguageCode,
        *,
        batch_size: int = 8,
        max_length: int = 512,
    ) -> list[str]:
        if not texts:
            return []
        if target not in config.INDIC_LANG_CODES:
            raise TranslationError(f"unsupported translation target: {target}")
        self._load()
        import torch

        target_code = config.INDIC_LANG_CODES[target]
        outputs: list[str] = []
        for start in range(0, len(texts), max(1, batch_size)):
            chunk = texts[start : start + max(1, batch_size)]
            try:
                processed = self._processor.preprocess_batch(
                    chunk,
                    src_lang="eng_Latn",
                    tgt_lang=target_code,
                    visualize=False,
                )
                inputs = self._tokenizer(
                    processed,
                    truncation=True,
                    padding="longest",
                    max_length=max_length,
                    return_tensors="pt",
                    return_attention_mask=True,
                ).to(self.device)
                with torch.inference_mode():
                    generated = self._model.generate(
                        **inputs,
                        use_cache=True,
                        min_length=0,
                        max_length=max_length,
                        num_beams=4,
                        num_return_sequences=1,
                    )
                decoded = self._tokenizer.batch_decode(
                    generated,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )
                translated = self._processor.postprocess_batch(
                    decoded, lang=target_code
                )
            except Exception as exc:
                raise TranslationError(f"IndicTrans2 inference failed: {exc}") from exc
            if len(translated) != len(chunk):
                raise TranslationError("IndicTrans2 returned the wrong batch size")
            outputs.extend(str(item).strip() for item in translated)
        if len(outputs) != len(texts):
            raise TranslationError("IndicTrans2 lost part of the batch")
        return outputs


def default_translator() -> Translator:
    return IndicTransTranslator()
