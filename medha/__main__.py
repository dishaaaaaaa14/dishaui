"""Launch Medha Studio, or run a named command-line tool."""

from __future__ import annotations

import argparse

import config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="medha",
        description="Offline AI blackboard teacher. Runs Medha Studio by default.",
    )
    parser.add_argument("--health", action="store_true", help="run environment checks")
    parser.add_argument(
        "--version", action="version", version=f"{config.APP_NAME} {config.APP_VERSION}"
    )
    args, rest = parser.parse_known_args(argv)

    if args.health:
        from medha.health import main as health_main

        return health_main(rest)

    from medha.studio.__main__ import main as studio_main

    return studio_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
