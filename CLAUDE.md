# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoneyPrinterV2 (MPV2) is a Python 3.12 CLI tool that automates four online workflows:
1. **YouTube Shorts** — generate video (LLM script → TTS → images → MoviePy composite) and upload via Selenium
2. **Twitter/X Bot** — generate and post tweets via Selenium
3. **Affiliate Marketing** — scrape Amazon product info, generate pitch, share on Twitter
4. **Local Lead Collection** — scrape Google Maps (Go binary) for local businesses, normalize phone numbers, persist as a reusable JSON lead store for other pipelines to consume via `get_leads()`

There is no web UI, no REST API, no CI, and no linting config. A `pytest` suite lives under `tests/`; run it with `venv/bin/python -m pytest` from the project root.

## Running the Application

```bash
# First-time setup
cp config.example.json config.json   # then fill in values
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# macOS quick setup (auto-configures Ollama, ImageMagick, Firefox profile)
bash scripts/setup_local.sh

# Preflight check (validates services are reachable)
python scripts/preflight_local.py

# Run
python src/main.py
```

The app **must** be run from the project root. `python src/main.py` adds `src/` to `sys.path`, so all imports use bare module names (e.g., `from config import *`, not `from src.config import *`).

## Architecture

### Entry Points
- `src/main.py` — interactive menu loop (primary)
- `src/cron.py` — headless runner invoked by the scheduler as a subprocess: `python src/cron.py <platform> <account_uuid>`

### Provider Pattern
Two service categories use a string-based dispatch pattern configured in `config.json`:

| Category | Config key | Options |
|---|---|---|
| LLM | `ollama_model` | Ollama (via `ollama` Python SDK). If empty, user picks from available models at startup. |
| Image gen | — | `nanobanana2` (Gemini image API) |
| STT | `stt_provider` | `local_whisper`, `third_party_assemblyai` |

LLM always uses the local Ollama server. Image generation always uses Nano Banana 2.

### Key Modules
- **`src/llm_provider.py`** — unified `generate_text(prompt)` function using the Ollama Python SDK
- **`src/config.py`** — 30+ getter functions reading from `config.json`, cached once per process via `load_config()` (`_CONFIG_CACHE`; pass `force_reload=True` to re-read from disk). `ROOT_DIR` = project root, computed as `os.path.dirname(sys.path[0])`
- **`src/cache.py`** — JSON file persistence in `.mp/` directory (accounts, videos, posts, products)
- **`src/constants.py`** — menu strings, Selenium selectors (YouTube Studio, X.com, Amazon)
- **`src/classes/YouTube.py`** — most complex class; full pipeline: topic → script → metadata → image prompts → images → TTS → subtitles → MoviePy combine → Selenium upload
- **`src/classes/Twitter.py`** — Selenium automation against x.com
- **`src/classes/AFM.py`** — Amazon scraping + LLM pitch generation
- **`src/classes/LeadScraper.py`** — Google Maps scraper (requires Go) + phone normalization; exposes `get_leads(niche=...)` pull API for other pipelines
- **`src/classes/Tts.py`** — `TTS` provider dispatch (`tts_provider`: `kittentts` or `gemini`); `unsupported_language_reason()` blocks kittentts (English-only) from narrating a non-English account/template
- **`src/templates.py`** — reference-based YouTube Shorts format templates: analyzes reference URLs via Gemini, synthesizes/stores a reusable template (niche, hook pattern, tone, visual style, sentence count) in `.mp/templates.json`, and loads a YouTube account's linked template for the generation pipeline

### Data Storage
All persistent state lives in `.mp/` at the project root as JSON files (`youtube.json`, `twitter.json`, `afm.json`). This directory also serves as scratch space for temporary WAV, PNG, SRT, and MP4 files — non-JSON files are cleaned on each run by `rem_temp_files()`.


### Browser Automation
Selenium uses pre-authenticated Firefox profiles (never handles login). The profile path is stored per-account in the cache JSON and also in `config.json` as a default.

### CRON Scheduling
Uses Python's `schedule` library (in-process, not OS cron). The scheduled job spawns `subprocess.run(["python", "src/cron.py", platform, account_id])`.

## Configuration

All config lives in `config.json` at the project root. See `config.example.json` for the full template and `docs/Configuration.md` for reference. Key external dependencies to configure:
- **ImageMagick** — required for MoviePy subtitle rendering (`imagemagick_path`)
- **Firefox profile** — must be pre-logged-in to target platforms (`firefox_profile`)
- **Ollama** — for LLM text generation (via `ollama` Python SDK)
- **Nano Banana 2** — for image generation (Gemini image API)
- **Go** — only needed for LeadScraper (Google Maps scraper)

## Contributing

PRs go against `main`. One feature/fix per PR. Open an issue first. Use `WIP` label for in-progress PRs.
