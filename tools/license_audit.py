"""License gate for models, assets and Python packages.

Examples:
    python tools/license_audit.py
    python tools/license_audit.py --packages
    python tools/license_audit.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402

ALLOWED = {
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "CC0-1.0",
    "CC-BY-4.0",
    "CDLA-Permissive-2.0",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "PSF-2.0",
    "HPND",
    "Zlib",
    "MPL-2.0",
}
REVIEW = {
    "Llama-3.2-Community",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
}
FORBIDDEN_MARKERS = ("non-commercial", "noncommercial", "research", "nc-", "-nc", "agpl")


@dataclass
class Finding:
    item: str
    license: str
    status: str
    detail: str


def _split_license(value: str) -> list[str]:
    parts = [p.strip() for p in value.replace("/", " ").split(" OR ") if p.strip()]
    return parts or [value.strip()]


def audit_models(lock: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    not_shipped = {item["id"] for item in lock.get("not_shipped", [])}
    for entry in lock.get("entries", []):
        eid = entry.get("id", "<unknown>")
        lic = entry.get("license", "")
        alternatives = _split_license(lic)
        lowered = lic.lower()
        if eid in not_shipped:
            findings.append(Finding(eid, lic, "fail", "listed as not_shipped but present"))
            continue
        if any(marker in lowered for marker in FORBIDDEN_MARKERS):
            findings.append(Finding(eid, lic, "fail", "forbidden license marker"))
            continue
        if all(alt in ALLOWED for alt in alternatives):
            status, detail = "ok", "permissive / allowed"
        elif any(alt in REVIEW for alt in alternatives):
            status, detail = "warn", "review before commercial release"
        else:
            status, detail = "warn", "unknown license; verify model card"
        license_file = entry.get("license_file")
        if license_file and not (config.LICENSES_DIR / license_file).exists():
            status, detail = "fail", f"license file missing: {license_file}"
        findings.append(Finding(eid, lic, status, detail))
    return findings


def audit_assets() -> list[Finding]:
    manifest = config.IMAGE_LIB_DIR / "MANIFEST.json"
    if not manifest.exists():
        return [Finding("assets/images", "-", "skip", "no manifest yet")]
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Finding("assets/images", "-", "fail", f"manifest corrupt: {exc}")]
    findings: list[Finding] = []
    for item in data.get("items", []):
        name = item.get("file", "<unknown>")
        lic = item.get("license", "")
        lowered = lic.lower()
        if any(marker in lowered for marker in FORBIDDEN_MARKERS):
            findings.append(Finding(name, lic, "fail", "non-commercial/ND image"))
        elif "sa" in lowered.replace("apache", ""):
            findings.append(Finding(name, lic, "warn", "share-alike; prefer CC0/CC BY"))
        elif item.get("attribution"):
            findings.append(Finding(name, lic, "ok", "attributed"))
        else:
            findings.append(Finding(name, lic, "warn", "missing attribution"))
    return findings


def audit_packages() -> list[Finding]:
    from importlib.metadata import distributions

    findings: list[Finding] = []
    for dist in distributions():
        name = dist.metadata.get("Name") or "<unknown>"
        raw = dist.metadata.get("License") or ""
        classifiers = " ".join(dist.metadata.get_all("Classifier") or [])
        lic = raw or "UNKNOWN"
        haystack = f"{lic} {classifiers}".lower()
        if "agpl" in haystack:
            findings.append(Finding(name, lic, "fail", "AGPL dependency"))
        elif "gpl" in haystack and "lgpl" not in haystack and "apache" not in haystack:
            findings.append(Finding(name, lic, "warn", "GPL dependency; isolate or review"))
        elif not raw and "License ::" not in classifiers:
            findings.append(Finding(name, lic, "skip", "license metadata missing"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="license-audit", description=__doc__)
    parser.add_argument("--packages", action="store_true", help="also audit installed packages")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    lock = json.loads(config.MODEL_LOCK_PATH.read_text(encoding="utf-8"))
    findings = audit_models(lock) + audit_assets()
    if args.packages:
        findings += audit_packages()

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for f in findings:
            print(f"{f.status:<4} {f.item:<42} {f.license:<34} {f.detail}")

    failures = [f for f in findings if f.status == "fail"]
    warns = [f for f in findings if f.status == "warn"]
    print(f"\n{len(findings)} items: {len(failures)} fail, {len(warns)} warn")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
