"""Image extraction and description orchestration."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import config
from medha.ingest.docling_parser import inspect_source

from .errors import ImageError
from .extractor import DoclingImageExtractor
from .models import ExtractedImage, ImageReport, ImageStats
from .store import ImageStore
from .vlm import ImageDescriber, SmolVlmDescriber


class ImageService:
    def __init__(
        self,
        *,
        extractor: DoclingImageExtractor | None = None,
        describer: ImageDescriber | None = None,
        store: ImageStore | None = None,
    ) -> None:
        self.extractor = extractor or DoclingImageExtractor()
        self.describer = describer
        self.store = store or ImageStore()

    def _describer(self) -> ImageDescriber:
        if self.describer is None:
            self.describer = SmolVlmDescriber()
        return self.describer

    def _merge_cached(
        self,
        images: list[ExtractedImage],
        previous: list[ExtractedImage],
        describer: ImageDescriber | None,
    ) -> list[ExtractedImage]:
        old = {image.image_id: image for image in previous}
        merged: list[ExtractedImage] = []
        for image in images:
            cached = old.get(image.image_id)
            if (
                cached is not None
                and cached.description
                and cached.content_sha256 == image.content_sha256
                and (
                    describer is None
                    or (
                        cached.vlm_model == describer.name
                        and cached.prompt_version == describer.prompt_version
                    )
                )
            ):
                image = image.model_copy(
                    update={
                        "description": cached.description,
                        "vlm_model": cached.vlm_model,
                        "prompt_version": cached.prompt_version,
                    }
                )
            merged.append(image)
        return merged

    def _describe(
        self,
        images: list[ExtractedImage],
        warnings: list[str],
        *,
        refresh: bool,
    ) -> list[ExtractedImage]:
        describer = self._describer()
        describer.check()
        updated: list[ExtractedImage] = []
        for image in images:
            if (
                not refresh
                and image.description
                and image.vlm_model == describer.name
                and image.prompt_version == describer.prompt_version
            ):
                updated.append(image)
                continue
            path = self.store.path_for(image)
            if not path.is_file():
                warnings.append(f"{image.image_id}: image file is missing")
                updated.append(image)
                continue
            try:
                with Image.open(path) as picture:
                    description = describer.describe(picture)
            except Exception as exc:
                warnings.append(f"{image.image_id}: VLM failed: {exc}")
                updated.append(image)
                continue
            updated.append(
                image.model_copy(
                    update={
                        "description": description,
                        "vlm_model": describer.name,
                        "prompt_version": describer.prompt_version,
                    }
                )
            )
        return updated

    def extract_file(
        self,
        path: Path,
        *,
        describe: bool = True,
        use_cache: bool = True,
    ) -> ImageReport:
        source = inspect_source(path)
        describer = self._describer() if describe and config.VLM_ENABLED else None
        if describer is not None:
            describer.check()
        extraction = self.extractor.extract(path, source)
        images = extraction.images
        previous = self.store.for_document(source.sha256)
        if use_cache:
            images = self._merge_cached(images, previous, describer)
        replaced, removed = self.store.replace_document(source.sha256, images)
        warnings = list(extraction.warnings)
        if describer is not None:
            images = self._describe(images, warnings, refresh=False)
            self.store.replace_document(source.sha256, images)
        elif describe:
            warnings.append("VLM is disabled; images were not described")
        return ImageReport(
            doc_id=source.sha256,
            source_filename=source.filename,
            extracted=len(images),
            described=sum(1 for image in images if image.description),
            replaced=replaced,
            removed=removed,
            images=images,
            warnings=warnings,
        )

    def describe_document(self, doc_id: str, *, refresh: bool = False) -> ImageReport:
        images = self.store.for_document(doc_id)
        if not images:
            raise ImageError(f"no extracted images for document {doc_id}")
        warnings: list[str] = []
        images = self._describe(images, warnings, refresh=refresh)
        self.store.replace_document(doc_id, images)
        return ImageReport(
            doc_id=doc_id,
            source_filename=images[0].source_filename,
            extracted=len(images),
            described=sum(1 for image in images if image.description),
            replaced=len(images),
            removed=0,
            images=images,
            warnings=warnings,
        )

    def describe_all(self, *, refresh: bool = False) -> list[ImageReport]:
        reports: list[ImageReport] = []
        for doc_id in sorted({image.doc_id for image in self.store.all()}):
            reports.append(self.describe_document(doc_id, refresh=refresh))
        return reports

    def stats(self) -> ImageStats:
        return self.store.stats()

    def reset(self) -> int:
        return self.store.reset()
