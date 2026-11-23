# Auto File Naming and Management

Issue: you have downloaded a bunch of files. More often than not the file names contain stuff you would rather not have it there, or is something incomprehensible. The goal is to monitor files, fix names and metadata and shelf them appropriately.

## Setup

Clone the repository and run the setup script from the checkout.

```sh
./LibManInit.sh
```

The script runs `uv sync --locked` and adds the `libman` alias to your Zsh startup file. Open a new Zsh session or run `source ~/.zshrc` to load the alias in your current terminal.

Set `GROQ_KEY` or `GEMINI_KEY` for your provider as shown in [.env.example](.env.example). You can put the key in a `.env` file in the checkout.

## Usage

Run `libman` from any directory. The `-base` flag selects the folder to scan. Use `-base=.` for the current directory.

```sh
libman -base="$HOME/Downloads"
```

LibMan scans immediately, then waits five seconds between scans. Press Ctrl+C to stop.

If `file_config.json` is missing, the app asks for your provider and the document, paper, and book shelves. Leave a shelf blank to skip moving that type. Keep every shelf outside the folder you scan and keep the scan folder outside every shelf. For example, scan `~/Downloads` and set the document shelf to `~/Documents`.

Use `-provider=groq` or `-provider=google`, `-docpath=PATH`, `-paperpath=PATH`, or `-bookpath=PATH` to save settings and exit. Existing settings carry over unless you supply a new value. Use an empty shelf path to disable that shelf. A configuration created with flags defaults to Groq and leaves unspecified shelves disabled.

```sh
libman -base="$HOME/Downloads" -docpath="$HOME/Documents" -bookpath="$HOME/Books"
```

Later runs reuse the saved configuration and scan history. Each successful move appends the original filename, full destination path, and metadata to `lib_man.log` in the scan folder.

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

## Classify with an AI subscription

Use your configured scan folder and shelves.

```sh
libman -base="$HOME/lib_man_test" -I_have_an_ai_subsciption -init
```

The scan folder gets an `ai_subscription` directory with `reference.csv`,
`to_fill.csv`, and `rules.md`. Give your AI `to_fill.csv` and `rules.md` and
replace `to_fill.csv` with the result. Keep `reference.csv` as generated. The
CSV includes extracted document text and full local paths, so review it before
uploading it to an external service.

```sh
libman -base="$HOME/lib_man_test" -I_have_an_ai_subsciption -finalize
```

Finalize checks the complete CSV against the reference and checks destinations
for collisions before moving files. An unknown classification or a disabled
shelf leaves a file in place. Move the `ai_subscription` directory aside when
you are ready to export another batch.

## Tests

Run these from the checkout.

```sh
PYTHONPATH=src .venv/bin/python -m pytest
```

The Groq and Gemini tests use mocks by default. To try the live tests, set the provider keys and run this command. Replace `-k live_llm` with `-k 'live_llm and groq'` or `-k 'live_llm and google'` to try one provider. Each live test skips if its key is missing.

```sh
LIB_MAN_LIVE_LLM_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest Tests/test_llm_bridge.py -k live_llm
```
