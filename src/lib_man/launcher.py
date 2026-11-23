import os
from argparse import ArgumentParser
from fcntl import LOCK_EX, LOCK_UN, flock
from math import inf
from pathlib import Path
from time import sleep

from lib_man.config import get_file_configs, write_file_configs


def update_config(updates: dict[str, str]) -> None:
    try:
        config = get_file_configs()
    except FileNotFoundError:
        config = {"provider": "groq", "doc_path": "", "paper_path": "", "book_path": ""}
    except (OSError, ValueError) as error:
        raise SystemExit(f"Could not read file_config.json: {error}") from None
    else:
        if not isinstance(config, dict):
            raise SystemExit("file_config.json must contain a JSON object.")
        if not updates:
            return

    try:
        write_file_configs(config | updates)
    except OSError as error:
        raise SystemExit(f"Could not write file_config.json: {error}") from None


def scan(directory: int, interval: float | None) -> None:
    from lib_man.main import main

    if interval is not None:
        print(
            f"Monitoring {Path.cwd()} every {interval:g} seconds. Press Ctrl+C to stop."
        )
    main()
    while interval is not None:
        flock(directory, LOCK_UN)
        sleep(interval)
        flock(directory, LOCK_EX)
        main(show_empty=False)


def run(
    base: str,
    updates: dict[str, str],
    *,
    scan_once: bool,
    interval: float | None,
) -> None:
    try:
        os.chdir(Path(base).expanduser())
        directory = os.open(".", os.O_RDONLY)
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"Could not open the scan folder: {error}") from None

    # Serialize scans and configuration writes in the same folder.
    try:
        flock(directory, LOCK_EX)
        update_config(updates)
        if scan_once or interval is not None:
            scan(directory, interval)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    finally:
        os.close(directory)


def main() -> None:
    parser = ArgumentParser(
        prog="libman",
        description="Save configuration for a folder and optionally scan it.",
    )
    parser.add_argument(
        "-basedir", "-base", required=True, metavar="PATH", help="folder to scan"
    )
    parser.add_argument(
        "-provider",
        type=lambda value: value.strip().lower(),
        choices=("groq", "google"),
    )
    parser.add_argument(
        "-bookpath", dest="book_path", metavar="PATH", help="book shelf"
    )
    parser.add_argument(
        "-docpath", dest="doc_path", metavar="PATH", help="document shelf"
    )
    parser.add_argument(
        "-paperpath", dest="paper_path", metavar="PATH", help="paper shelf"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-run", action="store_true", help="scan once")
    mode.add_argument("-monitor", action="store_true", help="scan repeatedly")
    parser.add_argument(
        "-t",
        type=float,
        metavar="SECONDS",
        help="wait between scans with -monitor (default: 5)",
    )
    args = parser.parse_args()
    if not args.basedir:
        parser.error("-basedir requires a nonempty path")
    if args.t is not None:
        if not args.monitor:
            parser.error("-t requires -monitor")
        if not 0 < args.t < inf:
            parser.error("-t must be a positive, finite number of seconds")

    updates = {
        key: value
        for key in ("provider", "book_path", "doc_path", "paper_path")
        if (value := getattr(args, key)) is not None
    }
    interval = None
    if args.monitor:
        interval = args.t or 5.0
    run(args.basedir, updates, scan_once=args.run, interval=interval)


if __name__ == "__main__":
    main()
