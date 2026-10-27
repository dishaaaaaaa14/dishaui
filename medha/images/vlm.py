"""Lazy CPU SmolVLM describer for extracted teaching images."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from PIL import Image

import config

from .errors import ImageError


class ImageDescriber(Protocol):
    name: str
    prompt_version: str

    def check(self) -> None: ...

    def describe(self, image: Image.Image) -> str: ...


def clean_description(value: str) -> str:
    text = " ".join(value.split()).strip()
    if text and text[-1] not in ".!?":
        cut = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if cut >= 0:
            text = text[: cut + 1]
    return text


class SmolVlmDescriber:
    name = "smolvlm-500m-instruct"
    prompt_version = config.VLM_PROMPT_VERSION

    def __init__(
        self,
        *,
        model_dir: Path | None = None,
        num_threads: int | None = None,
        max_new_tokens: int | None = None,
        image_splitting: bool | None = None,
        prompt: str | None = None,
    ) -> None:
        self.model_dir = Path(model_dir or config.VLM_MODEL_DIR)
        self.num_threads = num_threads or config.VLM_NUM_THREADS
        self.max_new_tokens = max_new_tokens or config.VLM_MAX_NEW_TOKENS
        self.image_splitting = (
            config.VLM_IMAGE_SPLITTING if image_splitting is None else image_splitting
        )
        self.prompt = prompt or config.VLM_PROMPT
        self._processor: Any = None
        self._model: Any = None

    def _required_files(self) -> tuple[Path, ...]:
        return (
            self.model_dir / "config.json",
            self.model_dir / "model.safetensors",
            self.model_dir / "processor_config.json",
            self.model_dir / "preprocessor_config.json",
            self.model_dir / "tokenizer.json",
            self.model_dir / "tokenizer_config.json",
        )

    def check(self) -> None:
        missing = [str(path) for path in self._required_files() if not path.is_file()]
        if missing:
            raise ImageError(
                "SmolVLM artifacts are incomplete ("
                + ", ".join(missing[:3])
                + "). Run: python tools/fetch_models.py --profile core"
            )

    def _load(self) -> None:
        if self._model is not None:
            return
        self.check()
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise ImageError(
                "SmolVLM dependencies are missing; install requirements/rag.txt "
                "and requirements/cpu.txt"
            ) from exc

        torch.set_num_threads(self.num_threads)
        self._processor = AutoProcessor.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
        )
        self._model = AutoModelForImageTextToText.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
            dtype=torch.float32,
        )
        self._model.to("cpu")
        self._model.eval()

    def describe(self, image: Image.Image) -> str:
        self._load()
        import torch

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": self.prompt},
                ],
            }
        ]
        text_prompt = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
        )
        inputs = self._processor(
            text=text_prompt,
            images=[image.convert("RGB")],
            return_tensors="pt",
            do_image_splitting=self.image_splitting,
        )
        with torch.inference_mode():
            generated = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        prompt_length = inputs["input_ids"].shape[1]
        decoded = self._processor.batch_decode(
            generated[:, prompt_length:],
            skip_special_tokens=True,
        )[0]
        description = clean_description(decoded)
        if not description:
            raise ImageError("SmolVLM returned an empty description")
        return description

    def describe_path(self, path: Path) -> str:
        with Image.open(path) as image:
            return self.describe(image)

    def close(self) -> None:
        self._model = None
        self._processor = None
