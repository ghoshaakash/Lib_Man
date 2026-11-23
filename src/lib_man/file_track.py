import json
import pathlib
from collections.abc import Iterator

DOCUMENT_EXTENSIONS = {".pdf", ".txt", ".doc", ".azw", ".epub", ".djvu"}


class FileTrack:
    def __init__(self, base_path: str | None = None):
        self.base_path = (
            pathlib.Path(base_path) if base_path is not None else pathlib.Path.cwd()
        )

        all_entries: Iterator[pathlib.Path] = self.base_path.rglob(pattern="*")
        all_files: list[pathlib.Path] = [p for p in all_entries if p.is_file()]
        doc_files: set[str] = {
            p.relative_to(self.base_path).as_posix()
            for p in all_files
            if self.is_doc(file_path=p)
        }

        self.create_file()
        with open(self.file_path, mode="r") as f:
            old_doc_files: set[str] = set(json.load(fp=f))

        new_doc_files: set[str] = doc_files - old_doc_files

        with open(self.file_path, mode="w") as f:
            json.dump(obj=sorted(doc_files), fp=f)

        self.files: set[pathlib.Path] = {self.base_path / p for p in new_doc_files}

    def create_file(self) -> None:
        self.file_path: pathlib.Path = self.base_path / "lib_man.json"
        if self.file_path.exists():
            return
        else:
            with open(self.file_path, mode="w") as f:
                json.dump([], fp=f)

    def is_doc(self, file_path: pathlib.Path) -> bool:
        return file_path.suffix.lower() in DOCUMENT_EXTENSIONS

    def get_files(self) -> list[pathlib.Path]:
        return sorted(self.files)
