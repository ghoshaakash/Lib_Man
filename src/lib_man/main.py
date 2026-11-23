import json
import sys
from pathlib import Path
from textwrap import indent

from lib_man.config import get_file_configs, set_file_cofigs
from lib_man.file_track import FileTrack
from lib_man.metadata import PromptAttemptsExhausted, metadataLookup
from lib_man.ocr import ocr
from lib_man.shelver import DestinationExists, shelver


def main(*, show_empty: bool = True) -> None:
    try:
        config = get_file_configs()
    except FileNotFoundError:
        try:
            set_file_cofigs()
        except EOFError:
            raise SystemExit(
                "Run the app interactively to create file_config.json."
            ) from None
        config = get_file_configs()

    mdl = metadataLookup(provider=config["provider"])
    shelf_keys = {"book": "book_path", "paper": "paper_path", "document": "doc_path"}
    scan_dir = Path.cwd()
    files = FileTrack().get_files()
    if not files:
        if show_empty:
            print(f"Scanning {scan_dir}\nNo new files.", flush=True)
        return

    total = len(files)
    moved = 0
    print(f"Scanning {scan_dir}\nNew files: {total}", flush=True)
    for index, file in enumerate(files, start=1):
        source = file.relative_to(scan_dir)
        print(f"\n[{index}/{total}] {source}\n  Reading the first pages...", flush=True)
        txt = ocr(0, file, 5)
        try:
            print("  Identifying metadata...", flush=True)
            metadata = mdl.get_metadata(file.stem, txt)
            shelf_key = shelf_keys.get(metadata["type"])
            if shelf_key is None:
                print("  Skipped. File type could not be identified.", flush=True)
                continue

            shelf_path = config.get(shelf_key)
            if not shelf_path:
                print(
                    f"  Skipped. No {metadata['type']} shelf is configured.", flush=True
                )
                continue

            print("  Choosing the destination...", flush=True)
            original = file.resolve()
            shelf = shelver(shelf_path, metadata, source=file, ask=mdl._ask)
            destination = shelf.destination
            if destination is None or destination == original:
                print("  Skipped. File is already at the destination.", flush=True)
                continue

            details = indent(
                json.dumps(shelf.metadata, ensure_ascii=False, indent=2), "    "
            )
            entry = (
                f"Moved\n  From  {source}\n  To    {destination}\n  Metadata\n{details}"
            )
            print(entry, flush=True)
            with Path("lib_man.log").open(
                "a", encoding="utf-8", errors="backslashreplace"
            ) as log:
                log.write(f"{entry}\n\n")
            moved += 1
        except DestinationExists as error:
            print(
                f"  Warning: {error.filename} already exists. Left {source} in place.",
                file=sys.stderr,
                flush=True,
            )
        except PromptAttemptsExhausted as error:
            print(f"  {error} Skipping {source}.", file=sys.stderr, flush=True)

    print(f"\nScan complete. {moved} moved, {total - moved} skipped.", flush=True)


if __name__ == "__main__":
    main()
