"""Convert Hershey futural.jhf glyphs to the compact JSON used by the renderer.

JHF layout (per the Hershey format notes):
- columns 0:5   glyph identifier
- columns 5:8   number of coordinate pairs, including the width pair
- column 8      left bearing
- column 9      right bearing
- columns 10:   vertex pairs relative to ASCII 'R'; " R" means pen up

The .jhf glyph data is permissively licensed (see assets/fonts/NOTICE.txt).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets" / "fonts" / "futural.jhf"
DEFAULT_OUT = ROOT / "assets" / "fonts" / "hershey.json"


def _decode(pair: str) -> tuple[int, int]:
    return ord(pair[0]) - ord("R"), ord(pair[1]) - ord("R")


def parse_jhf(text: str) -> dict[str, dict[str, object]]:
    glyphs: dict[str, dict[str, object]] = {}
    for index, raw_line in enumerate(text.splitlines()):
        line = raw_line.rstrip("\r")
        if len(line) < 10:
            continue
        try:
            pairs = int(line[5:8])
        except ValueError:
            continue
        # The width pair is counted by the file format but stored separately.
        count = max(0, pairs - 1)
        left = ord(line[8]) - ord("R")
        right = ord(line[9]) - ord("R")
        data = line[10 : 10 + count * 2]
        if len(data) != count * 2:
            continue

        strokes: list[list[list[int]]] = []
        stroke: list[list[int]] = []
        for pos in range(count):
            pair = data[pos * 2 : pos * 2 + 2]
            if pair == " R":
                if len(stroke) > 1:
                    strokes.append(stroke)
                stroke = []
                continue
            x, y = _decode(pair)
            stroke.append([x, y])
        if len(stroke) > 1:
            strokes.append(stroke)

        char = chr(32 + index)
        glyphs[char] = {"left": left, "right": right, "strokes": strokes}
    return glyphs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-hershey", description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    glyphs = parse_jhf(args.source.read_text(encoding="ascii"))
    if not glyphs:
        raise SystemExit(f"no glyphs found in {args.source}")
    payload = {
        "name": "Hershey Futural",
        "source": "futural.jhf",
        "license": "Hershey glyph data: permissive use and redistribution",
        "units_per_em": 32,
        "glyphs": glyphs,
    }
    args.out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out} ({len(glyphs)} glyphs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
