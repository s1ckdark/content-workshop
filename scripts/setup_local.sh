#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

echo "[setup] Root: $ROOT_DIR"

if [[ ! -f "config.json" ]]; then
  cp config.example.json config.json
  echo "[setup] Created config.json from config.example.json"
fi

if [[ -x "$HOME/.asdf/installs/python/3.12.12/bin/python3.12" ]]; then
  SYSTEM_PYTHON="$HOME/.asdf/installs/python/3.12.12/bin/python3.12"
elif command -v python3.12 >/dev/null 2>&1; then
  SYSTEM_PYTHON="$(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1; then
  SYSTEM_PYTHON="$(command -v python3)"
else
  echo "[setup] Python 3.12 is required but no usable python interpreter was found."
  exit 1
fi

SYSTEM_PYTHON_VERSION="$("$SYSTEM_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$SYSTEM_PYTHON_VERSION" != "3.12" ]]; then
  echo "[setup] Python 3.12 is required. Found: $SYSTEM_PYTHON_VERSION ($SYSTEM_PYTHON)"
  exit 1
fi

PYTHON_BIN="${ROOT_DIR}/venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  "$SYSTEM_PYTHON" -m venv venv
  echo "[setup] Created virtual environment at venv/"
else
  VENV_PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$VENV_PYTHON_VERSION" != "3.12" ]]; then
    echo "[setup] Existing venv uses Python $VENV_PYTHON_VERSION. Recreate venv with Python 3.12."
    exit 1
  fi
fi

"$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r requirements.txt

MAGICK_PATH="$(command -v magick || true)"
if [[ -z "$MAGICK_PATH" ]]; then
  MAGICK_PATH="$(command -v convert || true)"
fi

BROWSER_PROFILE=""
if [[ -d "$HOME/Library/Application Support/Google/Chrome" ]]; then
  BROWSER_PROFILE="$HOME/Library/Application Support/Google/Chrome"
elif [[ -d "$HOME/Library/Application Support/Chromium" ]]; then
  BROWSER_PROFILE="$HOME/Library/Application Support/Chromium"
fi

OLLAMA_MODELS_JSON="$(curl -sS http://127.0.0.1:11434/api/tags || true)"

MAGICK_PATH="$MAGICK_PATH" BROWSER_PROFILE="$BROWSER_PROFILE" "$PYTHON_BIN" - <<'PY'
import json
import os
import subprocess

ROOT_DIR = os.getcwd()
cfg_path = os.path.join(ROOT_DIR, "config.json")

with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

cfg.setdefault("stt_provider", "local_whisper")
cfg.setdefault("ollama_base_url", "http://127.0.0.1:11434")
cfg.setdefault("ollama_model", "")
cfg.setdefault(
    "nanobanana2_api_base_url",
    "https://generativelanguage.googleapis.com/v1beta",
)
cfg.setdefault("nanobanana2_api_key", "")
cfg.setdefault("nanobanana2_model", "gemini-3.1-flash-image-preview")
cfg.setdefault("nanobanana2_aspect_ratio", "9:16")
cfg.setdefault("whisper_model", "base")
cfg.setdefault("whisper_device", "auto")
cfg.setdefault("whisper_compute_type", "int8")

magick_path = os.environ.get("MAGICK_PATH", "")
if magick_path:
    cfg["imagemagick_path"] = magick_path

browser_profile = os.environ.get("BROWSER_PROFILE", "")
if browser_profile and not cfg.get("browser_profile"):
    cfg["browser_profile"] = browser_profile

# Pick a reasonable installed Ollama model.
ollama_model = cfg.get("ollama_model", "llama3.2:3b")
installed = []
try:
    out = subprocess.check_output(
        ["curl", "-sS", "http://127.0.0.1:11434/api/tags"],
        text=True,
    )
    payload = json.loads(out)
    installed = [m.get("name") for m in payload.get("models", []) if m.get("name")]
except Exception:
    installed = []

if installed:
    preferred = [
        "glm-4.7-flash:latest",
        "qwen3:14b",
        "phi4:latest",
        "phi4:14b",
        "gpt-oss:20b",
        "deepseek-r1:32b",
    ]
    selected = None
    for candidate in preferred:
        if candidate in installed:
            selected = candidate
            break

    if selected is None:
        selected = installed[0]

    if ollama_model not in installed or ollama_model != selected:
        cfg["ollama_model"] = selected

with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")

print(f"[setup] Updated {cfg_path}")
print(f"[setup] ollama_model={cfg.get('ollama_model')}")
print(f"[setup] nanobanana2_model={cfg.get('nanobanana2_model')}")
print(f"[setup] stt_provider={cfg.get('stt_provider')}")
PY

"$PYTHON_BIN" -m playwright install chromium

echo "[setup] Running local preflight..."
"$PYTHON_BIN" scripts/preflight_local.py || true

echo ""
echo "[setup] Done."
echo "[setup] Start app with: source venv/bin/activate && python3 src/main.py"
