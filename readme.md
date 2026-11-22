# Auto File Naming and Management

Issue: you have downloaded a bunch of files. More often than not the file names contain stuff you would rather not have it there, or is something incomprehensible. The goal is to monitor files, fix names and metadata and shelf them appropriately.

## First run

Set `GROQ_KEY` or `GEMINI_KEY` for your provider as shown in [.env.example](.env.example). You can put the key in a `.env` file in the checkout. Replace the checkout path below with yours and run these commands to scan Downloads.

```sh
lib_man_repo=/absolute/path/to/Lib_Man
cd "$lib_man_repo"
uv sync --locked
cd ~/Downloads
PYTHONPATH="$lib_man_repo/src" "$lib_man_repo/.venv/bin/python" -m lib_man.main
```

If `file_config.json` is missing, the app asks for your provider and the document, paper, and book shelves. Leave a shelf blank to skip moving that type. Keep every shelf outside the folder you scan and keep the scan folder outside every shelf. For example, scan `~/Downloads` and set the document shelf to `~/Documents`.

The command scans once and exits. Run it again from the same folder when you need it. Later runs reuse the saved configuration and scan history.

If a model request fails, the app waits 10 seconds before each of two retries. If both retries fail, it leaves that file in place and moves on to the next one. The skipped file stays in the scan history.

The scan picks up `.pdf`, `.txt`, `.doc`, `.azw`, `.epub`, and `.djvu` files. Put LibreOffice on your PATH to read Word files. Install Calibre's `ebook-convert` for Kindle files that need conversion. For DjVu, use DjVuLibre's `ddjvu` or ImageMagick with DjVu support.

Flow:

Pre loops:
1. Get your LLM interface ready (done)
2. Get the OCR interface ready (done)
3. Set the provider and shelf paths on first run (done)

On loops:

1. Scan for new files(done)
2. OCR first few pages(done)
3. Send file name+ OCRed data to llm and recieve feedback(done)
4. Fix the file name and move it to the appropiate place(done)

TODO

- Write metadata into the files themselves.

## Tests

Run these from the checkout.

```sh
PYTHONPATH=src .venv/bin/python -m pytest
```

The Groq and Gemini tests use mocks by default. To try the live tests, set the provider keys and run this command. Replace `-k live_llm` with `-k 'live_llm and groq'` or `-k 'live_llm and google'` to try one provider. Each live test skips if its key is missing.

```sh
LIB_MAN_LIVE_LLM_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest Tests/test_llm_bridge.py -k live_llm
```
