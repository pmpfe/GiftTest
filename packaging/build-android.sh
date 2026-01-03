#!/usr/bin/env bash
set -euo pipefail

# Build Android APK using Qt for Python's pyside6-android-deploy.
# Requires:
# - Python 3.11+
# - ANDROID_SDK_ROOT set and Android SDK/NDK installed (see CI workflow)
# - Java 17

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv-android}"
WHEELS_DIR="${WHEELS_DIR:-$PROJECT_DIR/.android-wheels}"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON_BIN not found. Install Python 3.11 and retry." >&2
  exit 1
fi

if [[ -z "${ANDROID_SDK_ROOT:-}" ]]; then
  echo "ERROR: ANDROID_SDK_ROOT is not set (Android SDK location)." >&2
  exit 1
fi

NDK_VERSION="${NDK_VERSION:-26.1.10909125}"
NDK_PATH="${NDK_PATH:-$ANDROID_SDK_ROOT/ndk/$NDK_VERSION}"

if [[ ! -d "$NDK_PATH" ]]; then
  echo "ERROR: Android NDK not found at $NDK_PATH" >&2
  echo "Install it via sdkmanager, or set NDK_PATH." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt
"$VENV_DIR/bin/pip" install qtpip

mkdir -p "$WHEELS_DIR"
"$VENV_DIR/bin/qtpip" download PySide6 --android --arch aarch64 --output-dir "$WHEELS_DIR"

PYSIDE_WHEEL=$(ls "$WHEELS_DIR"/PySide6*-android* 2>/dev/null | head -n 1 || true)
SHIBOKEN_WHEEL=$(ls "$WHEELS_DIR"/shiboken6*-android* 2>/dev/null | head -n 1 || true)

if [[ -z "$PYSIDE_WHEEL" || -z "$SHIBOKEN_WHEEL" ]]; then
  echo "ERROR: Could not find downloaded Android wheels in $WHEELS_DIR" >&2
  echo "Found:" >&2
  ls -la "$WHEELS_DIR" >&2 || true
  exit 1
fi

"$VENV_DIR/bin/pyside6-android-deploy" \
  --config-file "$PROJECT_DIR/pysidedeploy.spec" \
  --force \
  --name "GiftTest" \
  --wheel-pyside "$PYSIDE_WHEEL" \
  --wheel-shiboken "$SHIBOKEN_WHEEL" \
  --sdk-path "$ANDROID_SDK_ROOT" \
  --ndk-path "$NDK_PATH" \
  --extra-ignore-dirs ".venv,.venv-android,dist,build,packaging,perguntas_anatomia" \
  --verbose

echo "Done. Search for output APK/AAB under: $PROJECT_DIR"