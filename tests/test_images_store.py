from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

import config
from medha.images import ExtractedImage, ImageError, ImageStore


def make_image(directory: Path, image_id: str, color: str = "white") -> ExtractedImage:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{image_id}.png"
    Image.new("RGB", (80, 60), color).save(path, format="PNG")
    data = path.read_bytes()
    return ExtractedImage(
        schema_version=config.IMAGE_SCHEMA_VERSION,
        image_id=image_id,
        doc_id="doc-a",
        source_filename="lesson.pdf",
        source_format="pdf",
        page_no=1,
        locator_kind="page",
        ordinal=0,
        width=80,
        height=60,
        file=path.name,
        content_sha256=hashlib.sha256(data).hexdigest(),
    )


def test_replace_document_removes_stale_files(tmp_path: Path) -> None:
    store = ImageStore(tmp_path)
    first = make_image(tmp_path, "doc-a-i000")
    second = make_image(tmp_path, "doc-a-i001", "blue")
    assert store.replace_document("doc-a", [first, second]) == (0, 0)
    assert (tmp_path / second.file).exists()

    assert store.replace_document("doc-a", [first]) == (2, 1)
    assert not (tmp_path / second.file).exists()
    assert store.stats().total == 1
    assert store.stats().documents == 1


def test_manifest_round_trip(tmp_path: Path) -> None:
    store = ImageStore(tmp_path)
    image = make_image(tmp_path, "doc-a-i000")
    store.replace_document("doc-a", [image])
    loaded = ImageStore(tmp_path).all()
    assert len(loaded) == 1
    assert loaded[0].image_id == image.image_id


def test_path_for_rejects_traversal(tmp_path: Path) -> None:
    store = ImageStore(tmp_path)
    image = make_image(tmp_path, "doc-a-i000")
    unsafe = image.model_copy(update={"file": "../secret.png"})
    with pytest.raises(ImageError):
        store.path_for(unsafe)


def test_reset_removes_images_and_manifest(tmp_path: Path) -> None:
    store = ImageStore(tmp_path)
    image = make_image(tmp_path, "doc-a-i000")
    store.replace_document("doc-a", [image])
    Image.new("RGB", (80, 60), "red").save(tmp_path / "orphan.png")
    assert store.reset() == 2
    assert not store.manifest_path.exists()
    assert not (tmp_path / image.file).exists()
    assert not (tmp_path / "orphan.png").exists()
