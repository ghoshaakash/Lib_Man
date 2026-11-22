import sys

from lib_man.config import get_file_configs, set_file_cofigs
from lib_man.file_track import FileTrack
from lib_man.metadata import PromptAttemptsExhausted, metadataLookup
from lib_man.ocr import ocr
from lib_man.shelver import shelver


def main() -> None:
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

    for file in FileTrack().get_files():
        txt = ocr(0, file, 5)
        try:
            metadata = mdl.get_metadata(file.stem, txt)
            shelf_key = shelf_keys.get(metadata["type"])
            if shelf_key is None:
                continue

            shelf_path = config.get(shelf_key)
            if shelf_path:
                shelver(shelf_path, metadata, source=file, ask=mdl._ask)
        except PromptAttemptsExhausted as error:
            print(f"{error} Skipping {file}.", file=sys.stderr)


if __name__ == "__main__":
    main()
