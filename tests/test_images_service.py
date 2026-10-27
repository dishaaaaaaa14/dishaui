from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from PIL import Image

import config
from medha.images import (
    ExtractedImage,
    ImageError,
    ImageExtraction,
    ImageService,
    ImageStore,
)
from medha.ingest import inspect_source

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "ingest" / "sample.pptx"


class FakeExtractor:
    def __init__(self, store: ImageStore) -> None:
        self.store = store
        self.calls = 0

    def extract(self, path: Path, source: Any = None) -> ImageExtraction:
        self.calls += 1
        assert source is not None
        self.store.directory.mkdir(parents=True, exist_ok=True)
        path_out = self.store.directory / f"{source.sha256[:12]}-i000.png"
        Image.new("RGB", (80, 60), "white").save(path_out, format="PNG")
        content = hashlib.sha256(path_out.read_bytes()).hexdigest()
        image = ExtractedImage(
            schema_version=config.IMAGE_SCHEMA_VERSION,
            image_id=f"{source.sha256[:12]}-i000",
            doc_id=source.sha256,
            source_filename=source.filename,
            source_format=source.format,
            page_no=1,
            locator_kind="slide",
            ordinal=0,
            width=80,
            height=60,
            file=path_out.name,
            content_sha256=content,
        )
        return ImageExtraction(images=[image], page_count=1)


class FakeDescriber:
    name = "fake-vlm"
    prompt_version = "test"
    calls = 0

    def check(self) -> None:
        return None

    def describe(self, image: Image.Image) -> str:
        self.calls += 1
        return "A labelled force diagram."


def test_extract_describes_and_caches(tmp_path: Path) -> None:
    store = ImageStore(tmp_path)
    extractor = FakeExtractor(store)
    describer = FakeDescriber()
    service = ImageService(
        extractor=cast(Any, extractor),
        describer=describer,
        store=store,
    )
    first = service.extract_file(SAMPLE)
    assert first.extracted == 1
    assert first.described == 1
    assert first.images[0].description == "A labelled force diagram."

    second = service.extract_file(SAMPLE)
    assert extractor.calls == 2
    assert describer.calls == 1
    assert second.images[0].description == first.images[0].description

    third = service.extract_file(SAMPLE, describe=False)
    assert third.images[0].description == first.images[0].description

    service.extract_file(SAMPLE, use_cache=False)
    assert describer.calls == 2


def test_describe_document_and_stats(tmp_path: Path) -> None:
    store = ImageStore(tmp_path)
    extractor = FakeExtractor(store)
    service = ImageService(
        extractor=cast(Any, extractor),
        describer=FakeDescriber(),
        store=store,
    )
    report = service.extract_file(SAMPLE, describe=False)
    assert report.described == 0
    assert service.stats().described == 0

    described = service.describe_document(report.doc_id)
    assert described.described == 1
    assert service.stats().described == 1


def test_describe_missing_document_raises(tmp_path: Path) -> None:
    service = ImageService(store=ImageStore(tmp_path))
    try:
        service.describe_document("missing")
    except ImageError as exc:
        assert "no extracted images" in str(exc)
    else:
        raise AssertionError("expected ImageError")


def test_source_is_reinspected() -> None:
    source = inspect_source(SAMPLE)
    assert source.format == "pptx"
