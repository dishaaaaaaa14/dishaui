"""Persistent image files and manifest."""

from __future__ import annotations

import json
from pathlib import Path

import config

from .errors import ImageError
from .models import ExtractedImage, ImageManifest, ImageStats


class ImageStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory or config.IMAGE_DIR)
        self.manifest_path = self.directory / "manifest.json"

    def load(self) -> ImageManifest:
        if not self.manifest_path.exists():
            return ImageManifest(schema_version=config.IMAGE_SCHEMA_VERSION)
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ImageError(f"image manifest is unreadable: {exc}") from exc
        return ImageManifest.model_validate(payload)

    def save(self, manifest: ImageManifest) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.manifest_path)

    def path_for(self, image: ExtractedImage) -> Path:
        name = Path(image.file)
        if name.name != image.file or name.suffix.lower() != ".png":
            raise ImageError(f"unsafe image path: {image.file}")
        return self.directory / name

    def replace_document(
        self,
        doc_id: str,
        images: list[ExtractedImage],
    ) -> tuple[int, int]:
        manifest = self.load()
        previous = [item for item in manifest.images if item.doc_id == doc_id]
        keep = {item.image_id for item in images}
        for item in previous:
            if item.image_id not in keep:
                path = self.path_for(item)
                if path.exists():
                    path.unlink()
        merged = [item for item in manifest.images if item.doc_id != doc_id] + list(images)
        merged.sort(key=lambda item: (item.doc_id, item.page_no or 0, item.ordinal))
        self.save(ImageManifest(schema_version=config.IMAGE_SCHEMA_VERSION, images=merged))
        return len(previous), max(0, len(previous) - len(images))

    def for_document(self, doc_id: str) -> list[ExtractedImage]:
        return [item for item in self.load().images if item.doc_id == doc_id]

    def all(self) -> list[ExtractedImage]:
        return self.load().images

    def stats(self) -> ImageStats:
        images = self.load().images
        size = 0
        for image in images:
            path = self.path_for(image)
            if path.exists():
                size += path.stat().st_size
        return ImageStats(
            total=len(images),
            described=sum(1 for image in images if image.description),
            documents=len({image.doc_id for image in images}),
            bytes=size,
        )

    def reset(self) -> int:
        removed = 0
        if self.directory.exists():
            for path in self.directory.glob("*.png"):
                path.unlink()
                removed += 1
        if self.manifest_path.exists():
            self.manifest_path.unlink()
        return removed
