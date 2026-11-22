import json

from lib_man.file_track import FileTrack


def test_finds_documents(tmp_path):

    # Arrange
    pdf = tmp_path / "paper.pdf"
    txt = tmp_path / "notes.txt"
    image = tmp_path / "cover.png"

    pdf.write_text("placeholder")
    txt.write_text("placeholder")
    image.write_text("placeholder")

    # Act
    tracker = FileTrack(tmp_path)

    # Assert
    assert set(tracker.get_files()) == {pdf, txt}


def test_does_not_rediscover_existing_files(tmp_path):

    # Arrange
    pdf = tmp_path / "paper.pdf"
    pdf.write_text("placeholder")

    # First scan
    FileTrack(tmp_path)

    # Act: Scan again without changing anything
    tracker = FileTrack(tmp_path)

    # Assert
    assert tracker.get_files() == []


def test_detects_new_files(tmp_path):

    # Arrange
    old_pdf = tmp_path / "old.pdf"
    old_pdf.write_text("placeholder")

    # Record the first PDF
    FileTrack(tmp_path)

    # Add another PDF
    new_pdf = tmp_path / "new.pdf"
    new_pdf.write_text("placeholder")

    # Act
    tracker = FileTrack(tmp_path)

    # Assert
    assert set(tracker.get_files()) == {new_pdf}


def test_detects_reintroduced_files(tmp_path):

    # Arrange
    pdf = tmp_path / "paper.pdf"
    pdf.write_text("placeholder")

    # First discovery
    FileTrack(tmp_path)

    # Delete the file and scan again
    pdf.unlink()
    FileTrack(tmp_path)

    # Reintroduce the file
    pdf.write_text("placeholder")

    # Act
    tracker = FileTrack(tmp_path)

    # Assert
    assert set(tracker.get_files()) == {pdf}


def test_recursively_finds_supported_extensions_in_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    paths = [
        nested / f"item{suffix}"
        for suffix in (".PDF", ".txt", ".doc", ".azw", ".epub", ".djvu")
    ]
    for path in [*paths, nested / "ignored.docx", nested / "no_extension"]:
        path.touch()
    (nested / "folder.pdf").mkdir()

    tracker = FileTrack()

    assert tracker.get_files() == sorted(paths)
    tracker.create_file()
    assert json.loads(tracker.file_path.read_text()) == [
        path.relative_to(tmp_path).as_posix() for path in sorted(paths)
    ]
