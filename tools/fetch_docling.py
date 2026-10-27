"""Fetch and verify the offline Docling artifact bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402

MANIFEST = ".medha_docling.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    repo: str
    revision: str
    folder: str
    allow_patterns: tuple[str, ...]
    required: tuple[str, ...]


SPECS = (
    ArtifactSpec(
        key="layout",
        repo="docling-project/docling-layout-heron",
        revision="8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
        folder="docling-project--docling-layout-heron",
        allow_patterns=(
            "config.json",
            "model.safetensors",
            "preprocessor_config.json",
            "README.md",
        ),
        required=("config.json", "model.safetensors", "preprocessor_config.json"),
    ),
    ArtifactSpec(
        key="layout_onnx",
        repo="docling-project/docling-layout-heron-onnx",
        revision="40bde044036bb181c130ddf6c51792187268748f",
        folder="docling-project--docling-layout-heron-onnx",
        allow_patterns=("config.json", "model.onnx", "preprocessor_config.json", "README.md"),
        required=("config.json", "model.onnx", "preprocessor_config.json"),
    ),
    ArtifactSpec(
        key="tableformer",
        repo="docling-project/docling-models",
        revision="fc0f2d45e2218ea24bce5045f58a389aed16dc23",
        folder="docling-project--docling-models",
        allow_patterns=("config.json", "README.md", "model_artifacts/tableformer/*"),
        required=(
            "model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
            "model_artifacts/tableformer/accurate/tm_config.json",
        ),
    ),
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError:
        return "missing"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        items.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return items


def write_manifest(root: Path) -> Path:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "verified_at": _now(),
        "docling_version": _docling_version(),
        "artifacts_dir": str(root),
        "models": [
            {
                "key": spec.key,
                "repo": spec.repo,
                "revision": spec.revision,
                "folder": spec.folder,
            }
            for spec in SPECS
        ],
        "files": _files(root),
    }
    target = root / MANIFEST
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def verify(root: Path) -> list[str]:
    problems: list[str] = []
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        return [f"manifest missing: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {exc}"]
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append("manifest schema mismatch")
    for spec in SPECS:
        destination = root / spec.folder
        for required in spec.required:
            if not (destination / required).is_file():
                problems.append(f"{spec.key}: missing {required}")
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.is_file():
            problems.append(f"missing file: {item['path']}")
            continue
        if item.get("bytes") is not None and path.stat().st_size != item["bytes"]:
            problems.append(f"size mismatch: {item['path']}")
            continue
        if item.get("sha256") and _sha256(path) != item["sha256"]:
            problems.append(f"hash mismatch: {item['path']}")
    return problems


def _download(root: Path, *, force: bool) -> None:
    from huggingface_hub import snapshot_download

    for spec in SPECS:
        destination = root / spec.folder
        if force:
            print(f"refreshing {spec.key} -> {destination}")
        else:
            print(f"fetching {spec.key} -> {destination}")
        snapshot_download(
            repo_id=spec.repo,
            revision=spec.revision,
            allow_patterns=list(spec.allow_patterns),
            local_dir=destination,
            force_download=force,
            max_workers=4,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch-docling", description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=config.DOCLING_ARTIFACTS_DIR)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.artifacts_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    if args.verify:
        problems = verify(root)
        if args.json:
            print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
        elif problems:
            for problem in problems:
                print(f"FAIL {problem}")
        else:
            print(f"ok: {root}")
        return 1 if problems else 0

    if args.offline:
        problems = verify(root)
        if problems:
            for problem in problems:
                print(f"FAIL {problem}")
            return 1
        print(f"offline artifacts ready: {root}")
        return 0

    try:
        _download(root, force=args.force)
        manifest = write_manifest(root)
    except Exception as exc:
        print(f"fetch failed: {exc}")
        return 1

    problems = verify(root)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(f"wrote {manifest}")
    print(f"ok: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
