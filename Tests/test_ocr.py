import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call

import pymupdf
import pytest

from lib_man import ocr


def test_embedded_pdf_text_stops_at_page_limit(tmp_path, monkeypatch):
    source = tmp_path / "sample.pdf"
    pages = [f"Sample text with enough characters for page {i}." for i in range(3)]
    with pymupdf.open() as document:
        for page_text in pages:
            document.new_page().insert_text((72, 72), page_text)
        document.save(source)
    engine = Mock()
    monkeypatch.setattr(ocr, "RapidOCR", engine)

    assert ocr.ocr(0, source, 2) == "\n\n".join(pages[:2])
    engine.assert_not_called()


def test_scanned_pages_reuse_one_ocr_engine(tmp_path, monkeypatch):
    source = tmp_path / "scanned.pdf"
    with pymupdf.open() as document:
        for _ in range(2):
            document.new_page()
        document.save(source)
    engine = Mock()
    engine.return_value.side_effect = [
        SimpleNamespace(txts=["First line", "Second line"]),
        SimpleNamespace(txts=["Last page"]),
    ]
    monkeypatch.setattr(ocr, "RapidOCR", engine)

    assert ocr.ocr(1, source, 5) == "First line\nSecond line\n\nLast page"
    engine.assert_called_once_with(
        params={"Global.max_side_len": 4096, "Global.log_level": "error"}
    )
    assert engine.return_value.call_count == 2
    for args in engine.return_value.call_args_list:
        assert args.args[0].startswith(b"\x89PNG")


@pytest.mark.parametrize("contents", ["", "Short text"])
def test_ocr_reads_plain_text_without_ocr_engine(tmp_path, monkeypatch, contents):
    source = tmp_path / "notes.TXT"
    source.write_text(contents)
    engine = Mock()
    monkeypatch.setattr(ocr, "RapidOCR", engine)

    assert ocr.ocr(0, str(source), 1) == contents
    engine.assert_not_called()


@pytest.mark.parametrize(
    ("level", "pages", "message"),
    [(2, 1, "level must"), (0, -1, "pages must")],
)
def test_ocr_rejects_invalid_limits(level, pages, message):
    with pytest.raises(ValueError, match=message):
        ocr.ocr(level, "missing.pdf", pages)


def test_ocr_with_zero_pages_does_not_need_a_file():
    assert ocr.ocr(0, "missing.pdf", 0) == ""


def test_open_document_falls_back_to_calibre(tmp_path, monkeypatch):
    source = tmp_path / "book.azw"
    converted_document = MagicMock()
    converted_document.__enter__.return_value = converted_document
    open_document = Mock(
        side_effect=[pymupdf.FileDataError("format"), converted_document]
    )
    monkeypatch.setattr(ocr.pymupdf, "open", open_document)
    monkeypatch.setattr(ocr, "which", Mock(return_value="/tools/ebook-convert"))
    convert = Mock()
    monkeypatch.setattr(ocr, "_run_conversion", convert)

    with ocr._open_document(source, 3) as document:
        assert document is converted_document
        command, output = convert.call_args.args
        assert command == ["/tools/ebook-convert", str(source), str(output)]
        assert output.name == "book.epub"
        assert output.parent.is_dir()
        assert open_document.call_args_list == [
            call(source, filetype="mobi"),
            call(output),
        ]

    converted_document.__exit__.assert_called_once_with(None, None, None)
    assert not output.parent.exists()


def test_convert_office_passes_requested_pdf_page_range(tmp_path, monkeypatch):
    source = tmp_path / "My document.doc"
    monkeypatch.setattr(ocr, "which", {"libreoffice": "/tools/libreoffice"}.get)
    run = Mock()
    monkeypatch.setattr(ocr, "_run_conversion", run)

    output = ocr._convert_office(source, tmp_path, 4)

    assert output == tmp_path / "My document.pdf"
    command, destination = run.call_args.args
    assert destination == output
    assert command[:4] == [
        "/tools/libreoffice",
        f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}",
        "--headless",
        "--convert-to",
    ]
    assert json.loads(command[4].removeprefix("pdf:writer_pdf_Export:")) == {
        "PageRange": {"type": "string", "value": "1-4"}
    }
    assert command[5:] == ["--outdir", str(tmp_path), str(source)]


@pytest.mark.parametrize("program", ["ddjvu", "magick"])
def test_convert_djvu_passes_page_range_to_available_program(
    tmp_path, monkeypatch, program
):
    source = tmp_path / "book.djvu"
    executable = f"/tools/{program}"
    monkeypatch.setattr(ocr, "which", {program: executable}.get)
    run = Mock()
    monkeypatch.setattr(ocr, "_run_conversion", run)

    output = ocr._convert_djvu(source, tmp_path, 3)

    assert output == tmp_path / "pages.tiff"
    if program == "ddjvu":
        arguments = ["-format=tiff", "-page=1-3", str(source)]
    else:
        arguments = [f"djvu:{source}[0-2]", "-compress", "LZW"]
    run.assert_called_once_with([executable, *arguments, str(output)], output)


@pytest.mark.parametrize(
    ("convert", "dependency"),
    [(ocr._convert_office, "LibreOffice"), (ocr._convert_djvu, "DjVuLibre")],
)
def test_converter_reports_missing_executable(
    tmp_path, monkeypatch, convert, dependency
):
    monkeypatch.setattr(ocr, "which", Mock(return_value=None))

    with pytest.raises(RuntimeError, match=dependency):
        convert(tmp_path / "source", tmp_path, 1)


def test_run_conversion_requires_generated_file(tmp_path, monkeypatch):
    output = tmp_path / "output.pdf"
    command = ["/tools/convert", str(output)]
    run = Mock(return_value=subprocess.CompletedProcess(command, 0, "", "no output"))
    monkeypatch.setattr(ocr.subprocess, "run", run)

    with pytest.raises(RuntimeError, match="no output"):
        ocr._run_conversion(command, output)

    output.touch()
    ocr._run_conversion(command, output)
    assert run.call_args.kwargs["timeout"] == 120


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (subprocess.TimeoutExpired(["convert"], 120), "timed out"),
        (OSError("failure"), "Could not run"),
    ],
)
def test_run_conversion_reports_execution_failure(monkeypatch, error, message):
    monkeypatch.setattr(ocr.subprocess, "run", Mock(side_effect=error))

    with pytest.raises(RuntimeError, match=message):
        ocr._run_conversion(["convert"], Path("unused.pdf"))
