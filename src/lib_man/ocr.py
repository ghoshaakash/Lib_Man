import json
import os
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory

import pymupdf
from pymupdf.mupdf import FzErrorBase
from rapidocr import RapidOCR

MIN_EXTRACTED_CHARACTERS = 30
OFFICE_FORMATS = {".doc", ".docx", ".odt", ".rtf"}
KINDLE_FORMATS = {".azw", ".azw3", ".azw4", ".mobi"}
CONVERSION_TIMEOUT = 120


def ocr(level: int, path: Path | str, pages: int) -> str:
    """Return text from up to the first `pages` pages, in document order.

    PDF, EPUB, TXT, and common images open directly. Word and other Writer
    formats use LibreOffice. Kindle formats use Calibre when needed. DjVu
    uses DjVuLibre or ImageMagick. Reflowable formats use PyMuPDF's pagination.

    Except for TXT, pages with fewer than 30 non-whitespace characters of
    embedded text fall back to OCR. Level 0 renders at 150 DPI and level 1
    renders at 300 DPI. A page count of zero returns an empty string.
    """
    if level not in (0, 1):
        raise ValueError("level must be 0 (standard) or 1 (high)")
    if pages < 0:
        raise ValueError("pages must be non-negative")
    if pages == 0:
        return ""

    path = Path(path)
    plain_text = path.suffix.lower() == ".txt"
    if plain_text and path.stat().st_size == 0:
        return ""

    dpi = 150 if level == 0 else 300
    # Allow full-resolution scans of typical pages in high-detail mode.
    max_side_len = 2000 if level == 0 else 4096
    engine: RapidOCR | None = None
    page_texts: list[str] = []

    with _open_document(path, pages) as document:
        for page_number in range(min(pages, len(document))):
            page = document[page_number]
            try:
                text = page.get_text().strip()
            except FzErrorBase, RuntimeError:
                text = ""
            if (
                not plain_text
                and sum(not char.isspace() for char in text) < MIN_EXTRACTED_CHARACTERS
            ):
                if engine is None:
                    engine = RapidOCR(params={"Global.max_side_len": max_side_len})
                image = page.get_pixmap(dpi=dpi)
                result = engine(image.tobytes("png"))
                lines = getattr(result, "txts", None)
                text = "\n".join(lines or ()).strip() or text
            page_texts.append(text)

    return "\n\n".join(page_texts).strip()


@contextmanager
def _open_document(path: Path, pages: int) -> Generator[pymupdf.Document]:
    suffix = path.suffix.lower()
    if suffix in KINDLE_FORMATS:
        try:
            document = pymupdf.open(path, filetype="mobi")
        except pymupdf.FileDataError, FzErrorBase:
            # Calibre can open some Kindle containers that MuPDF cannot read.
            pass
        else:
            with document:
                yield document
            return
    elif suffix not in OFFICE_FORMATS and suffix != ".djvu":
        with pymupdf.open(
            path, filetype="txt" if suffix == ".txt" else None
        ) as document:
            yield document
        return

    with TemporaryDirectory(prefix="lib-man-ocr-") as temporary:
        output_dir = Path(temporary).resolve()
        source = path.absolute()
        if suffix in OFFICE_FORMATS:
            converted = _convert_office(source, output_dir, pages)
        elif suffix == ".djvu":
            converted = _convert_djvu(source, output_dir, pages)
        else:
            executable = which("ebook-convert")
            if executable is None:
                raise RuntimeError("This Kindle file requires Calibre's ebook-convert.")
            converted = output_dir / "book.epub"
            _run_conversion([executable, str(source), str(converted)], converted)

        with pymupdf.open(converted) as document:
            yield document


def _convert_office(source: Path, output_dir: Path, pages: int) -> Path:
    executable = which("soffice") or which("libreoffice")
    if executable is None:
        raise RuntimeError("Word document OCR requires LibreOffice.")

    output = output_dir / f"{source.stem}.pdf"
    options = json.dumps({"PageRange": {"type": "string", "value": f"1-{pages}"}})
    profile = (output_dir / "profile").as_uri()
    _run_conversion(
        [
            executable,
            f"-env:UserInstallation={profile}",
            "--headless",
            "--convert-to",
            f"pdf:writer_pdf_Export:{options}",
            "--outdir",
            str(output_dir),
            str(source),
        ],
        output,
    )
    return output


def _convert_djvu(source: Path, output_dir: Path, pages: int) -> Path:
    output = output_dir / "pages.tiff"
    executable = which("ddjvu")
    if executable is not None:
        command = [
            executable,
            "-format=tiff",
            f"-page=1-{pages}",
            str(source),
            str(output),
        ]
    else:
        executable = which("magick")
        if executable is None and os.name != "nt":
            executable = which("convert")
        if executable is None:
            raise RuntimeError(
                "DjVu OCR requires DjVuLibre's ddjvu or ImageMagick with DjVu support."
            )
        command = [
            executable,
            f"djvu:{source}[0-{pages - 1}]",
            "-compress",
            "LZW",
            str(output),
        ]
    _run_conversion(command, output)
    return output


def _run_conversion(command: list[str], output: Path) -> None:
    name = Path(command[0]).name
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=CONVERSION_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{name} timed out converting the document.") from error
    except OSError as error:
        raise RuntimeError(f"Could not run {name} to convert the document.") from error

    if result.returncode != 0 or not output.is_file():
        details = result.stderr.strip() or result.stdout.strip()
        message = f"{name} could not convert the document."
        raise RuntimeError(f"{message}\n{details}" if details else message)
