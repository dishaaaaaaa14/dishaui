"""Docling-backed extraction of figure images from PDF and PPTX sources."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import config
from medha.ingest.docling_parser import IngestError, inspect_source, missing_artifacts
from medha.ingest.models import BBox, SourceInfo

from .errors import ImageError
from .models import ExtractedImage, ImageExtraction, LocatorKind


def _page_no(item: Any) -> int | None:
    provenance = getattr(item, "prov", None) or []
    if not provenance:
        return None
    value = getattr(provenance[0], "page_no", None)
    if value is None:
        return None
    try:
        page = int(str(value))
    except (TypeError, ValueError):
        return None
    return page if page >= 1 else None


def _bbox(item: Any) -> BBox | None:
    provenance = getattr(item, "prov", None) or []
    if not provenance:
        return None
    box = getattr(provenance[0], "bbox", None)
    if box is None:
        return None
    try:
        return BBox(
            left=float(box.l),
            top=float(box.t),
            right=float(box.r),
            bottom=float(box.b),
        )
    except (AttributeError, TypeError, ValueError):
        return None


class DoclingImageExtractor:
    def __init__(
        self,
        *,
        output_dir: Path | None = None,
        ocr: bool | None = None,
        artifacts_dir: Path | None = None,
        num_threads: int | None = None,
        timeout_s: float | None = None,
        scale: float | None = None,
        min_side: int | None = None,
        max_images: int | None = None,
    ) -> None:
        self.output_dir = Path(output_dir or config.IMAGE_DIR)
        self.ocr = config.OCR_ENABLED if ocr is None else ocr
        self.artifacts_dir = Path(artifacts_dir or config.DOCLING_ARTIFACTS_DIR)
        self.num_threads = num_threads or config.DOCLING_NUM_THREADS
        self.timeout_s = timeout_s or config.DOCLING_TIMEOUT_S
        self.scale = scale or config.IMAGE_RENDER_SCALE
        self.min_side = min_side or config.IMAGE_MIN_SIDE
        self.max_images = max_images or config.IMAGE_MAX_PER_DOC
        self._converter: Any = None

    def _check_runtime(self) -> None:
        try:
            import docling  # noqa: F401
        except ImportError as exc:
            raise ImageError(
                "Docling is not installed; install requirements/ingest.txt and requirements/cpu.txt"
            ) from exc
        problems = missing_artifacts(self.artifacts_dir)
        if problems:
            raise ImageError(
                "Docling artifacts are incomplete ("
                + ", ".join(problems)
                + "). Run: python tools/fetch_docling.py"
            )

    def _build_converter(self) -> Any:
        if self._converter is not None:
            return self._converter
        self._check_runtime()
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            AcceleratorDevice,
            AcceleratorOptions,
            PdfPipelineOptions,
            TesseractOcrOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            PdfFormatOption,
            PowerpointFormatOption,
        )

        options = PdfPipelineOptions(artifacts_path=str(self.artifacts_dir))
        options.document_timeout = self.timeout_s
        options.enable_remote_services = False
        options.allow_external_plugins = False
        options.do_ocr = self.ocr
        options.do_table_structure = False
        options.do_code_enrichment = False
        options.do_formula_enrichment = False
        options.do_picture_classification = False
        options.do_picture_description = False
        options.generate_page_images = False
        options.generate_picture_images = True
        options.generate_table_images = False
        options.images_scale = self.scale
        options.accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.CPU,
            num_threads=self.num_threads,
        )
        if self.ocr:
            options.ocr_options = TesseractOcrOptions(lang=["eng"])

        self._converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.PPTX],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
                InputFormat.PPTX: PowerpointFormatOption(),
            },
        )
        return self._converter

    def extract(self, path: Path, source: SourceInfo | None = None) -> ImageExtraction:
        source = source or inspect_source(path)
        max_pages = (
            config.MAX_PPTX_SLIDES if source.format == "pptx" else config.MAX_PDF_PAGES
        )
        try:
            result = self._build_converter().convert(
                Path(source.path),
                raises_on_error=False,
                max_num_pages=max_pages,
                max_file_size=config.MAX_INGEST_BYTES,
            )
        except ImageError:
            raise
        except IngestError:
            raise
        except Exception as exc:
            raise ImageError(f"Docling could not inspect {source.filename}: {exc}") from exc

        status = str(getattr(result.status, "value", result.status)).lower()
        errors = [str(error) for error in (getattr(result, "errors", None) or [])]
        if "failure" in status:
            detail = "; ".join(errors[:3]) or "no error detail"
            raise ImageError(f"Docling failed on {source.filename}: {detail}")
        document = getattr(result, "document", None)
        if document is None:
            raise ImageError(f"Docling returned no document for {source.filename}")

        locator_kind: LocatorKind = "slide" if source.format == "pptx" else "page"
        warnings: list[str] = []
        if "partial" in status:
            warnings.append("Docling returned a partial conversion")
        if self.ocr:
            warnings.append("OCR was enabled for this image extraction")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        images: list[ExtractedImage] = []
        pictures = list(getattr(document, "pictures", None) or [])
        for ordinal, item in enumerate(pictures):
            if len(images) >= self.max_images:
                warnings.append(
                    f"image limit reached ({self.max_images}); remaining pictures were skipped"
                )
                break
            page_no = _page_no(item)
            try:
                picture = item.get_image(document)
            except Exception as exc:
                warnings.append(f"picture {ordinal} could not be decoded: {exc}")
                continue
            if picture is None:
                warnings.append(f"picture {ordinal} has no rendered image")
                continue
            if picture.width < self.min_side or picture.height < self.min_side:
                warnings.append(
                    f"picture {ordinal} is too small ({picture.width}x{picture.height})"
                )
                continue

            canvas = picture.convert("RGB")
            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG", optimize=True)
            payload = buffer.getvalue()
            content_hash = hashlib.sha256(payload).hexdigest()
            image_id = f"{source.sha256[:12]}-i{ordinal:03d}"
            filename = f"{image_id}.png"
            (self.output_dir / filename).write_bytes(payload)
            images.append(
                ExtractedImage(
                    schema_version=config.IMAGE_SCHEMA_VERSION,
                    image_id=image_id,
                    doc_id=source.sha256,
                    source_filename=source.filename,
                    source_format=source.format,
                    page_no=page_no,
                    locator_kind=locator_kind,
                    bbox=_bbox(item),
                    ordinal=ordinal,
                    width=canvas.width,
                    height=canvas.height,
                    file=filename,
                    content_sha256=content_hash,
                )
            )

        page_count = max(
            (image.page_no or 0 for image in images),
            default=0,
        )
        page_count = max(page_count, len(getattr(result, "pages", None) or []))
        if not pictures:
            warnings.append("no picture regions were found")
        return ImageExtraction(images=images, page_count=page_count, warnings=warnings)
