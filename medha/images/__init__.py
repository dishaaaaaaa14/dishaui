"""Offline teaching image extraction and CPU VLM descriptions."""

from .errors import ImageError
from .extractor import DoclingImageExtractor
from .models import (
    ExtractedImage,
    ImageExtraction,
    ImageManifest,
    ImageReport,
    ImageStats,
    LocatorKind,
)
from .service import ImageService
from .store import ImageStore
from .vlm import ImageDescriber, SmolVlmDescriber

__all__ = [
    "DoclingImageExtractor",
    "ExtractedImage",
    "ImageDescriber",
    "ImageError",
    "ImageExtraction",
    "ImageManifest",
    "ImageReport",
    "ImageService",
    "ImageStats",
    "ImageStore",
    "LocatorKind",
    "SmolVlmDescriber",
]
