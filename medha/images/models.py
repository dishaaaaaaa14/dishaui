"""Contracts for extracted teaching images and VLM descriptions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from medha.ingest.models import BBox, SourceFormat

LocatorKind = Literal["page", "slide"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedImage(StrictModel):
    schema_version: str
    image_id: str
    doc_id: str
    source_filename: str
    source_format: SourceFormat
    page_no: int | None = Field(default=None, ge=1)
    locator_kind: LocatorKind
    bbox: BBox | None = None
    ordinal: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    file: str
    content_sha256: str
    description: str | None = None
    vlm_model: str | None = None
    prompt_version: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ImageManifest(StrictModel):
    schema_version: str
    images: list[ExtractedImage] = Field(default_factory=list)


class ImageExtraction(StrictModel):
    images: list[ExtractedImage]
    page_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ImageReport(StrictModel):
    doc_id: str
    source_filename: str
    extracted: int = Field(ge=0)
    described: int = Field(ge=0)
    replaced: int = Field(ge=0)
    removed: int = Field(ge=0)
    images: list[ExtractedImage]
    warnings: list[str] = Field(default_factory=list)


class ImageStats(StrictModel):
    total: int = Field(ge=0)
    described: int = Field(ge=0)
    documents: int = Field(ge=0)
    bytes: int = Field(ge=0)
