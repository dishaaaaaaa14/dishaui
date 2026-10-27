"""Fetch, verify and document Medha models.

Examples:
    python tools/fetch_models.py --profile demo_gpu
    python tools/fetch_models.py --profile indic --verify
    python tools/fetch_models.py --list
    python tools/fetch_models.py --write-docs
    python tools/fetch_models.py --bundle E:\\Medha
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402

MARKER = ".medha_model.json"


class FetchError(RuntimeError):
    pass


def load_lock() -> dict[str, Any]:
    if not config.MODEL_LOCK_PATH.exists():
        raise FetchError(f"{config.MODEL_LOCK_PATH} is missing")
    return json.loads(config.MODEL_LOCK_PATH.read_text(encoding="utf-8"))


def all_entries(lock: dict[str, Any]) -> list[dict[str, Any]]:
    entries = lock.get("entries") or []
    if not isinstance(entries, list):
        raise FetchError("models.lock.json: entries must be a list")
    return entries


def selected(entry: dict[str, Any], profile: str) -> bool:
    if profile == "all":
        return True
    profiles = entry.get("profiles") or []
    return "core" in profiles or profile in profiles


def profile_names(lock: dict[str, Any]) -> list[str]:
    names = set(lock.get("profiles") or {})
    names.update({"core", "all"})
    for entry in all_entries(lock):
        names.update(entry.get("profiles") or [])
    return sorted(names)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _human(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _ollama_tags() -> dict[str, dict[str, Any]]:
    import httpx

    try:
        with httpx.Client(timeout=5.0) as client:
            payload = client.get(f"{config.OLLAMA_BASE_URL}/api/tags").json()
    except Exception as exc:
        raise FetchError(
            f"Ollama is not reachable at {config.OLLAMA_BASE_URL}. Run: ollama serve"
        ) from exc
    result: dict[str, dict[str, Any]] = {}
    for model in payload.get("models", []):
        name = model.get("name", "")
        result[name] = model
        if ":" not in name:
            result[f"{name}:latest"] = model
    return result


def _pull_ollama(model: str, offline: bool, dry_run: bool) -> None:
    tags = _ollama_tags()
    if model in tags:
        print(f"  ollama: {model} already present")
        return
    if offline:
        raise FetchError(f"offline: ollama model {model} is not present")
    if dry_run:
        print(f"  would run: ollama pull {model}")
        return
    exe = shutil.which("ollama")
    if not exe:
        raise FetchError("ollama executable not found on PATH")
    print(f"  pulling {model} (this can take several minutes)")
    proc = subprocess.run([exe, "pull", model], check=False)
    if proc.returncode != 0:
        raise FetchError(f"ollama pull {model} failed with exit code {proc.returncode}")


def _entry_dest(entry: dict[str, Any]) -> Path:
    return config.MODEL_DIR / entry.get("dest", entry["id"])


def _write_license(entry: dict[str, Any], local_dir: Path) -> Path:
    config.MODEL_LICENSES_DIR.mkdir(parents=True, exist_ok=True)
    target = config.MODEL_LICENSES_DIR / f"{entry['id']}.txt"
    text: str | None = None
    for candidate in (local_dir / "LICENSE", local_dir / "LICENSE.txt"):
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8", errors="replace")
            break
    if text is None:
        license_file = entry.get("license_file")
        if license_file:
            source = config.LICENSES_DIR / license_file
            if source.exists():
                text = source.read_text(encoding="utf-8", errors="replace")
    if text is None:
        text = f"{entry.get('license')} (license text not bundled; see {entry.get('license_url')})"

    header = (
        f"Model: {entry['id']}\n"
        f"Job: {entry.get('job')}\n"
        f"License: {entry.get('license')}\n"
        f"Source: {entry.get('license_url')}\n"
        f"Revision: {(entry.get('source') or {}).get('revision', 'n/a')}\n"
        f"Fetched: {_now()}\n"
        f"{'-' * 72}\n"
    )
    target.write_text(header + text + "\n", encoding="utf-8")
    return target


def _hf_download(entry: dict[str, Any], offline: bool, dry_run: bool) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise FetchError(
            "huggingface_hub is not installed. Install requirements/rag.txt first."
        ) from exc

    source = entry["source"]
    repo: str = source["repo"]
    revision: str = source["revision"]
    patterns: list[str] | None = source.get("allow_patterns")
    dest = _entry_dest(entry)
    marker = dest / MARKER

    if marker.exists():
        try:
            meta = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
        if meta.get("revision") == revision:
            print(f"  hf: {entry['id']} already present ({_human(_dir_size(dest))})")
            _write_license(entry, dest)
            return dest

    if offline:
        raise FetchError(f"offline: {entry['id']} is not downloaded")
    if dry_run:
        print(f"  would download {repo}@{revision[:8]} -> {dest}")
        return dest

    token = os.getenv("HF_TOKEN") or None
    print(f"  downloading {repo}@{revision[:8]} -> {dest}")
    try:
        snapshot_download(
            repo_id=repo,
            revision=revision,
            allow_patterns=patterns,
            local_dir=dest,
            token=token,
            max_workers=4,
        )
    except Exception as exc:
        message = str(exc)
        if entry.get("gated") or "gated" in message.lower() or "401" in message or "403" in message:
            raise FetchError(
                f"{entry['id']} is gated. Accept the terms at {entry.get('license_url')} "
                "and set HF_TOKEN before retrying."
            ) from exc
        raise FetchError(f"{entry['id']} download failed: {message}") from exc

    files = []
    for path in sorted(dest.rglob("*")):
        if path.is_file() and path.name != MARKER:
            files.append({"path": str(path.relative_to(dest)), "bytes": path.stat().st_size})
    marker.write_text(
        json.dumps(
            {
                "id": entry["id"],
                "repo": repo,
                "revision": revision,
                "license": entry.get("license"),
                "fetched_at": _now(),
                "files": files,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_license(entry, dest)
    print(f"  done: {entry['id']} ({_human(_dir_size(dest))})")
    return dest


def verify_entry(entry: dict[str, Any]) -> tuple[bool, str]:
    source = entry.get("source") or {}
    if source.get("type") == "ollama":
        try:
            tags = _ollama_tags()
        except FetchError as exc:
            return False, str(exc)
        model = source.get("model")
        if model in tags:
            return True, "ollama model present"
        return False, f"missing ollama model {model}"

    dest = _entry_dest(entry)
    marker = dest / MARKER
    if not marker.exists():
        return False, "not downloaded"
    try:
        meta = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "marker is corrupt"
    if meta.get("revision") != source.get("revision"):
        return False, "revision mismatch"
    missing = [
        item["path"] for item in meta.get("files", []) if not (dest / item["path"]).exists()
    ]
    if missing:
        return False, f"missing {len(missing)} file(s), first: {missing[0]}"
    return True, f"ok ({_human(_dir_size(dest))})"


def write_docs(lock: dict[str, Any]) -> None:
    entries = all_entries(lock)
    lines = [
        "# Medha models",
        "",
        "Weights are **fetched, never committed**. `models.lock.json` is the source of truth; "
        "`tools/fetch_models.py` pins revisions, downloads, verifies and writes the license "
        "sidecars in `MODEL_LICENSES/`.",
        "",
        "| ID | Job | Profiles | Runtime | Device | Disk | License | Gated |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        profiles = ", ".join(f"`{p}`" for p in e.get("profiles", []))
        gated = "**yes**" if e.get("gated") else "no"
        lines.append(
            f"| `{e['id']}` | {e.get('job', '')} | {profiles} | {e.get('runtime', '')} | "
            f"{e.get('device', '')} | {e.get('size_gb', '?')} GB | "
            f"{e.get('license', '')} | {gated} |"
        )

    lines += [
        "",
        "## Profiles",
        "",
        "```powershell",
        "python tools/fetch_models.py --profile demo_gpu",
        "python tools/fetch_models.py --profile safe_gpu",
        "python tools/fetch_models.py --profile cpu",
        "python tools/fetch_models.py --profile indic",
        "python tools/fetch_models.py --profile optional",
        "python tools/fetch_models.py --verify",
        "```",
        "",
        "`core` entries are included in every profile. `indic` downloads are gated: accept the "
        "model terms on Hugging Face and set `HF_TOKEN` first.",
        "",
        "## Deliberately not shipped",
        "",
        "| ID | Reason |",
        "|---|---|",
    ]
    for item in lock.get("not_shipped", []):
        lines.append(f"| `{item['id']}` | {item['reason']} |")

    lines += [
        "",
        "## Hardware notes",
        "",
        "- Qwen3-4B-Instruct Q4_K_M + q8 KV at 3072 ctx is roughly 3.0 GB VRAM. "
        "Do not open a browser.",
        "- All non-LLM models run CPU-only. Install `requirements/cpu.txt`, "
        "never the CUDA torch wheel.",
        "- Prefetch Docling artifacts with `python tools/fetch_docling.py` and verify "
        "offline bundles with `python tools/fetch_docling.py --offline`.",
        "- BGE-M3 ONNX embeddings and the BGE reranker are CPU-only and use about "
        "4.5 GB RAM when both are warm.",
        "- SmolVLM-500M is CPU-only and adds about 1 GB of weights. Image descriptions "
        "are cached; the first cold description can take 15-20 seconds.",
        "",
        f"Generated from `models.lock.json` on {_now()}.",
        "",
    ]
    config.MODELS_DOC_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {config.MODELS_DOC_PATH}")


def bundle(dest: Path, lock: dict[str, Any]) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    models_dest = dest / "models"
    licenses_dest = dest / "MODEL_LICENSES"
    print(f"bundling models -> {models_dest}")
    if config.MODEL_DIR.exists():
        shutil.copytree(config.MODEL_DIR, models_dest, dirs_exist_ok=True)
    if config.MODEL_LICENSES_DIR.exists():
        shutil.copytree(config.MODEL_LICENSES_DIR, licenses_dest, dirs_exist_ok=True)
    (dest / "bundle.json").write_text(
        json.dumps(
            {
                "created_at": _now(),
                "models_dir": "models",
                "licenses_dir": "MODEL_LICENSES",
                "ollama_models": [
                    e["source"]["model"]
                    for e in all_entries(lock)
                    if (e.get("source") or {}).get("type") == "ollama"
                ],
                "env": {
                    "OLLAMA_MODELS": str(models_dest / "ollama"),
                    "HF_HOME": str(models_dest / "hf"),
                    "DOCLING_ARTIFACTS_DIR": str(models_dest / "docling"),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("bundle ready")


def main(argv: list[str] | None = None) -> int:
    lock = load_lock()
    parser = argparse.ArgumentParser(prog="fetch-models", description=__doc__)
    parser.add_argument("--profile", choices=profile_names(lock))
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--write-docs", action="store_true")
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args(argv)

    config.ensure_dirs()
    profile = args.profile or config.DEFAULT_PROFILE
    entries = [e for e in all_entries(lock) if selected(e, profile)]

    if args.list:
        for e in entries:
            print(f"{e['id']:<34} {','.join(e.get('profiles', [])):<22} {e.get('license')}")
        return 0

    if args.write_docs:
        write_docs(lock)

    if args.bundle:
        bundle(args.bundle, lock)

    if not entries:
        print(f"no entries for profile {profile}")
        return 1

    failures: list[str] = []
    print(f"profile: {profile} ({len(entries)} entries)")

    if args.verify:
        for entry in entries:
            ok, detail = verify_entry(entry)
            print(f"  {'ok  ' if ok else 'FAIL'} {entry['id']}: {detail}")
            if not ok:
                failures.append(entry["id"])
        return 1 if failures else 0

    for entry in entries:
        try:
            source = entry.get("source") or {}
            if source.get("type") == "ollama":
                _pull_ollama(source["model"], args.offline, args.dry_run)
            elif source.get("type") == "hf":
                _hf_download(entry, args.offline, args.dry_run)
            else:
                raise FetchError(f"{entry['id']}: unknown source type {source.get('type')}")
        except FetchError as exc:
            print(f"  FAIL {entry['id']}: {exc}")
            failures.append(entry["id"])

    if failures:
        print(f"\n{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("\nall selected models ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
