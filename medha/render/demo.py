"""Static B2 renderer demo."""

from __future__ import annotations

import argparse
from pathlib import Path

from .scene import Board
from .window import run


def build_scene(board: Board) -> None:
    board.add_text(
        "Medha",
        at=(0.065, 0.075),
        size=0.115,
        color="chalk",
        width_px=4.2,
    )
    board.add_text(
        "offline blackboard teacher",
        at=(0.068, 0.210),
        size=0.030,
        color="diagram",
        width_px=2.4,
    )
    board.add_polyline([(0.065, 0.192), (0.33, 0.192)], color="math", width_px=2.0)

    board.add_text("F = m a", at=(0.075, 0.305), size=0.075, color="math", width_px=3.4)
    board.add_text(
        "force equals mass times acceleration",
        at=(0.078, 0.415),
        size=0.023,
        color="chalk",
        width_px=2.0,
        max_width=0.46,
    )

    board.add_shape("axes", rect=(0.60, 0.28, 0.30, 0.34), color="diagram", width_px=2.4)
    board.add_shape(
        "arrow",
        start=(0.62, 0.55),
        end=(0.86, 0.33),
        color="yellow",
        width_px=3.0,
    )
    board.add_text("a", at=(0.53, 0.42), size=0.030, color="diagram", width_px=2.0)
    board.add_text("F", at=(0.83, 0.25), size=0.030, color="yellow", width_px=2.0)

    board.add_text("wave", at=(0.075, 0.56), size=0.026, color="diagram", width_px=2.0)
    board.add_shape("waveform", rect=(0.075, 0.59, 0.34, 0.12), cycles=2.5, color="diagram")
    board.add_text("curve", at=(0.45, 0.56), size=0.026, color="diagram", width_px=2.0)
    board.add_shape("circle", center=(0.53, 0.68), radius=0.07, color="diagram", width_px=2.4)

    board.add_text(
        "chalk + speech + vector board",
        at=(0.075, 0.84),
        size=0.028,
        color="chalk",
        width_px=2.2,
        max_width=0.8,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-render-demo")
    parser.add_argument("--smoke", action="store_true", help="render briefly and exit")
    parser.add_argument("--screenshot", type=Path, default=None)
    args = parser.parse_args(argv)
    return run(
        build_scene,
        duration_ms=1200 if args.smoke else None,
        screenshot_path=args.screenshot,
    )


if __name__ == "__main__":
    raise SystemExit(main())
