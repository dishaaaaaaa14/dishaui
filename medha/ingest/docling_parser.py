"""Docling-backed PDF and PPTX parsing into normalized blocks."""

from __future__ import annotations

import hashlib
import importlib.util
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import config

from .models import (
    BBox,
    Block,
    BlockKind,
    IngestDocument,
    LocatorKind,
    ParserInfo,
    SourceFormat,
    SourceInfo,
)

_SUPPORTED: dict[str, SourceFormat] = {".pdf": "pdf", ".pptx": "pptx"}
_WHITESPACE_RE = re.compile(r"[ \t]+")
_SKIPPED_LABELS = {"page_header", "page_footer"}


class IngestError(RuntimeError):
    """Raised when a source cannot be ingested safely."""


def docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError:
        return "missing"


def missing_artifacts(path: Path | None = None) -> list[str]:
    root = Path(path) if path is not None else config.DOCLING_ARTIFACTS_DIR
    if not root.exists():
        return [f"artifact directory missing: {root}"]
    problems: list[str] = []
    layout = [p for p in root.rglob("model.safetensors") if "layout" in p.parent.name.lower()]
    layout += [p for p in root.rglob("model.onnx") if "layout" in p.parent.name.lower()]
    if not layout:
        problems.append("layout model missing")
    tableformer = list(root.rglob("tableformer_*.safetensors"))
    if not tableformer:
        problems.append("tableformer weights missing")
    if not list(root.rglob("tm_config.json")):
        problems.append("tableformer config missing")
    return problems


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def inspect_source(path: Path) -> SourceInfo:
    path = Path(path).expanduser()
    if not path.is_file():
        raise IngestError(f"input is not a file: {path}")
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED:
        raise IngestError(f"unsupported format {suffix or '<none>'}; expected PDF or PPTX")
    size = path.stat().st_size
    if size <= 0:
        raise IngestError(f"input is empty: {path.name}")
    if size > config.MAX_INGEST_BYTES:
        limit = config.MAX_INGEST_BYTES / (1024 * 1024)
        raise IngestError(f"input is {size / (1024 * 1024):.1f} MB; limit is {limit:.0f} MB")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    fmt: SourceFormat = _SUPPORTED[suffix]
    return SourceInfo(
        path=str(path.resolve()),
        filename=path.name,
        sha256=digest.hexdigest(),
        format=fmt,
        bytes=size,
    )


def _clean(text: str, *, keep_lines: bool = False) -> str:
    if keep_lines:
        lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()
    return _WHITESPACE_RE.sub(" ", text.replace("\r\n", "\n")).strip()


def _item_label(item: Any) -> str:
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label)).strip().lower()


def _kind(item: Any, label: str) -> BlockKind:
    name = type(item).__name__.lower()
    if name == "tableitem" or label == "table":
        return "table"
    if name == "titleitem" or label == "title":
        return "title"
    if name == "sectionheaderitem" or label == "section_header":
        return "heading"
    if name == "listitem" or label == "list_item":
        return "list"
    if name == "formulaitem" or label == "formula":
        return "formula"
    if name == "captionitem" or label == "caption":
        return "caption"
    if name == "footnoteitem" or label == "footnote":
        return "footnote"
    if name == "codeitem" or label == "code":
        return "code"
    if name == "pictureitem" or label == "picture":
        return "picture"
    return "paragraph"


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


def _page_no(item: Any) -> int | None:
    provenance = getattr(item, "prov", None) or []
    if not provenance:
        return None
    value = getattr(provenance[0], "page_no", None)
    if value is None:
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page >= 1 else None


def _item_text(item: Any, kind: BlockKind, document: Any) -> tuple[str, str | None]:
    if kind == "table":
        try:
            markdown = item.export_to_markdown(doc=document)
        except TypeError:
            markdown = item.export_to_markdown()
        except Exception:
            markdown = ""
        markdown = _clean(str(markdown), keep_lines=True)
        return markdown, markdown or None
    raw = getattr(item, "text", "") or getattr(item, "orig", "") or ""
    return _clean(str(raw)), None


class DoclingParser:
    """Lazy Docling converter that never downloads models at runtime."""

    def __init__(
        self,
        *,
        ocr: bool | None = None,
        artifacts_dir: Path | None = None,
        num_threads: int | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.ocr = config.OCR_ENABLED if ocr is None else ocr
        self.artifacts_dir = Path(artifacts_dir or config.DOCLING_ARTIFACTS_DIR)
        self.num_threads = num_threads or config.DOCLING_NUM_THREADS
        self.timeout_s = timeout_s or config.DOCLING_TIMEOUT_S
        self._converter: Any = None

    @property
    def parser_info(self) -> ParserInfo:
        return ParserInfo(
            name="docling",
            version=docling_version(),
            schema_version=config.INGEST_SCHEMA_VERSION,
        )

    def _check_runtime(self) -> None:
        if not _module_present("docling"):
            raise IngestError(
                "Docling is not installed; install requirements/ingest.txt and requirements/cpu.txt"
            )
        problems = missing_artifacts(self.artifacts_dir)
        if problems:
            raise IngestError(
                "Docling artifacts are incomplete ("
                + ", ".join(problems)
                + "). Run: python tools/fetch_docling.py"
            )
        if self.ocr:
            if not _module_present("pytesseract"):
                raise IngestError("OCR requested but pytesseract is not installed")
            try:
                import pytesseract  # type: ignore[import-untyped]

                pytesseract.get_tesseract_version()
            except Exception as exc:
                raise IngestError("OCR requested but the Tesseract binary is unavailable") from exc

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
        options.do_table_structure = True
        options.do_code_enrichment = False
        options.do_formula_enrichment = False
        options.do_picture_classification = False
        options.do_picture_description = False
        options.generate_page_images = False
        options.generate_picture_images = False
        options.generate_table_images = False
        options.heading_hierarchy_options.enabled = True
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

    def parse(self, path: Path, source: SourceInfo | None = None) -> IngestDocument:
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
        except IngestError:
            raise
        except Exception as exc:
            raise IngestError(f"Docling could not parse {source.filename}: {exc}") from exc

        status = str(getattr(result.status, "value", result.status)).lower()
        errors = [str(error) for error in (getattr(result, "errors", None) or [])]
        if "failure" in status:
            detail = "; ".join(errors[:3]) or "no error detail"
            raise IngestError(f"Docling failed on {source.filename}: {detail}")
        document = getattr(result, "document", None)
        if document is None:
            raise IngestError(f"Docling returned no document for {source.filename}")

        warnings: list[str] = []
        if "partial" in status:
            warnings.append("Docling returned a partial conversion")
        if self.ocr:
            warnings.append("OCR was enabled for this ingestion")

        blocks = self._blocks(document, source, warnings)
        page_count = max(
            (block.page_no or 0 for block in blocks),
            default=0,
        )
        page_count = max(page_count, len(getattr(result, "pages", None) or []))
        if page_count >= max_pages:
            warnings.append(f"page/slide limit reached ({max_pages}); input may be truncated")
        title = next(
            (block.text for block in blocks if block.kind in {"title", "heading"}),
            Path(source.filename).stem,
        )
        if not blocks:
            warnings.append("no text blocks were extracted; the source may be scanned or empty")
        if any(block.kind == "picture" for block in blocks):
            warnings.append("picture blocks are metadata-only in B5; images are handled in B7")

        return IngestDocument(
            schema_version=config.INGEST_SCHEMA_VERSION,
            doc_id=source.sha256,
            source=source,
            parser=self.parser_info,
            title=title,
            page_count=page_count,
            locator_kind="slide" if source.format == "pptx" else "page",
            blocks=blocks,
            warnings=warnings,
        )

    def _blocks(
        self,
        document: Any,
        source: SourceInfo,
        warnings: list[str],
    ) -> list[Block]:
        locator_kind: LocatorKind = "slide" if source.format == "pptx" else "page"
        blocks: list[Block] = []
        heading_stack: list[tuple[int, str]] = []
        current_page: int | None = None
        skipped_pictures = 0

        for item, _depth in document.iterate_items():
            label = _item_label(item)
            kind = _kind(item, label)
            page_no = _page_no(item)
            if source.format == "pptx" and page_no is not None and page_no != current_page:
                heading_stack = []
            if page_no is not None:
                current_page = page_no
            if label in _SKIPPED_LABELS:
                continue
            if kind == "picture":
                skipped_pictures += 1
                continue

            text, markdown = _item_text(item, kind, document)
            if not text:
                continue
            level: int | None = None
            if kind in {"title", "heading"}:
                raw_level = getattr(item, "level", None)
                if raw_level is None:
                    level = 1
                elif isinstance(raw_level, int):
                    level = raw_level
                else:
                    try:
                        level = int(str(raw_level))
                    except (TypeError, ValueError):
                        level = 1
                level = max(1, level)
                if kind == "title":
                    level = 1
                    heading_stack = []
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, text))
            heading_path = [entry[1] for entry in heading_stack]

            ordinal = len(blocks)
            blocks.append(
                Block(
                    block_id=f"{source.sha256[:12]}-b{ordinal:04d}",
                    ordinal=ordinal,
                    kind=kind,
                    text=text,
                    markdown=markdown,
                    page_no=page_no,
                    locator_kind=locator_kind,
                    heading_path=heading_path,
                    level=level,
                    bbox=_bbox(item),
                )
            )

        if skipped_pictures:
            warnings.append(f"skipped {skipped_pictures} picture block(s); B7 handles images")
        return blocks
