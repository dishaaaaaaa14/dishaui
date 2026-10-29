"""Run the Medha web API with uvicorn."""

from __future__ import annotations

import argparse

import config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-web", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    config.ensure_dirs()
    import uvicorn

    uvicorn.run(
        "medha.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
