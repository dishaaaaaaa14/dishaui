from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from medha.ingest import WhitespaceTokenCounter, ingest_file
from medha.ingest.models import Block, IngestDocument, ParserInfo, SourceInfo

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "ingest" / "sample.pdf"


class FakeParser:
    ocr = False
    parser_info = ParserInfo(version="fake", schema_version="1.0.0")
    calls = 0

    def parse(self, path: Path, source: SourceInfo | None = None) -> IngestDocument:
        assert source is not None
        self.calls += 1
        return IngestDocument(
            schema_version="1.0.0",
            doc_id=source.sha256,
            source=source,
            parser=self.parser_info,
            title="Fake",
            page_count=1,
            locator_kind="page",
            blocks=[
                Block(
                    block_id=f"{source.sha256[:12]}-b0000",
                    ordinal=0,
                    kind="paragraph",
                    text="Cached ingestion text.",
                    page_no=1,
                    locator_kind="page",
                )
            ],
        )


def test_cache_avoids_second_parser_call(tmp_path: Path) -> None:
    parser = FakeParser()
    first = ingest_file(
        SAMPLE,
        parser=cast(Any, parser),
        counter=WhitespaceTokenCounter(),
        cache_dir=tmp_path,
    )
    second_parser = FakeParser()
    second = ingest_file(
        SAMPLE,
        parser=cast(Any, second_parser),
        counter=WhitespaceTokenCounter(),
        cache_dir=tmp_path,
    )
    assert parser.calls == 1
    assert second_parser.calls == 0
    assert first.model_dump() == second.model_dump()
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_no_cache_forces_parser_call(tmp_path: Path) -> None:
    first_parser = FakeParser()
    ingest_file(
        SAMPLE,
        parser=cast(Any, first_parser),
        counter=WhitespaceTokenCounter(),
        cache_dir=tmp_path,
    )
    second_parser = FakeParser()
    ingest_file(
        SAMPLE,
        parser=cast(Any, second_parser),
        counter=WhitespaceTokenCounter(),
        cache_dir=tmp_path,
        use_cache=False,
    )
    assert first_parser.calls == 1
    assert second_parser.calls == 1
