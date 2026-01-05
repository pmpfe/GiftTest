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

# python-for-android pins
ANDROID_PYTHON_VERSION="${ANDROID_PYTHON_VERSION:-3.11.6}"
P4A_BRANCH="${P4A_BRANCH:-master}"

# Keep generated deployment/build files for debugging and for local patching.
# Set KEEP_DEPLOYMENT_FILES=0 to revert to the default purge behavior.
KEEP_DEPLOYMENT_FILES="${KEEP_DEPLOYMENT_FILES:-1}"

# Performance defaults:
# - Incremental builds (reuse venv/deployment/.buildozer) unless CLEAN=1
# - Avoid re-generating buildozer.spec unless FORCE_DEPLOY=1
CLEAN="${CLEAN:-0}"
FORCE_DEPLOY="${FORCE_DEPLOY:-0}"
FORCE_VENV_SETUP="${FORCE_VENV_SETUP:-0}"

# Size reduction:
# This app is Widgets-only; pruning Qt QML/QtQuick reduces APK size significantly.
PRUNE_QT_QML="${PRUNE_QT_QML:-1}"
ANDROID_BLACKLIST_FILE="${ANDROID_BLACKLIST_FILE:-$PROJECT_DIR/packaging/android-blacklist.txt}"

# Build mode: debug (apk) or release (aab)
BUILD_MODE="${BUILD_MODE:-debug}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON_BIN not found. Install Python 3.11 and retry." >&2
  exit 1
fi

PYTHON_MAJOR_MINOR="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

if [[ -d "$VENV_DIR" ]]; then
  VENV_PY="$VENV_DIR/bin/python"
  if [[ -x "$VENV_PY" ]]; then
    VENV_MAJOR_MINOR="$($VENV_PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' || true)"
    if [[ -n "$VENV_MAJOR_MINOR" && "$VENV_MAJOR_MINOR" != "$PYTHON_MAJOR_MINOR" ]]; then
      echo "Recreating venv: $VENV_DIR (was Python $VENV_MAJOR_MINOR, need $PYTHON_MAJOR_MINOR)"
      rm -rf "$VENV_DIR"
    fi
  fi
fi

if [[ -z "${ANDROID_SDK_ROOT:-}" ]]; then
  echo "ERROR: ANDROID_SDK_ROOT is not set (Android SDK location)." >&2
  exit 1
fi

# p4a/gradle in this pipeline requires Java 17.
# If you have multiple JDKs installed, export JAVA_HOME to your JDK17.
if [[ -n "${JAVA_HOME:-}" ]]; then
  export PATH="$JAVA_HOME/bin:$PATH"
fi

if ! command -v java >/dev/null 2>&1; then
  echo "ERROR: java not found. Install Java 17 and retry." >&2
  exit 1
fi

JAVA_MAJOR="$(java -version 2>&1 | head -n 1 | sed -n 's/.*"\([0-9][0-9]*\)\..*/\1/p')"
if [[ -z "$JAVA_MAJOR" ]]; then
  # Handles formats like: openjdk version "17" 2021-09-14
  JAVA_MAJOR="$(java -version 2>&1 | head -n 1 | sed -n 's/.*"\([0-9][0-9]*\)".*/\1/p')"
fi

if [[ "$JAVA_MAJOR" != "17" ]]; then
  echo "ERROR: Java 17 is required for this Android build (found Java ${JAVA_MAJOR:-unknown})." >&2
  echo "Set JAVA_HOME to a JDK 17 installation (e.g. /usr/lib/jvm/java-17-openjdk) and retry." >&2
  exit 1
fi

NDK_VERSION="${NDK_VERSION:-26.1.10909125}"
NDK_PATH="${NDK_PATH:-$ANDROID_SDK_ROOT/ndk/$NDK_VERSION}"

if [[ ! -d "$NDK_PATH" ]]; then
  echo "ERROR: Android NDK not found at $NDK_PATH" >&2
  echo "Install it via sdkmanager, or set NDK_PATH." >&2
  exit 1
fi

if [[ "$CLEAN" == "1" ]]; then
  echo "CLEAN=1: Removing local Android build artifacts (.buildozer/, deployment/, dist_android/, buildozer.spec)" >&2
  rm -rf "$PROJECT_DIR/.buildozer" "$PROJECT_DIR/deployment" "$PROJECT_DIR/dist_android" "$PROJECT_DIR/buildozer.spec"
fi

mkdir -p "$PROJECT_DIR/dist_android"

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PIP_PROGRESS_BAR=off

setup_venv() {
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/pip" install -r requirements.txt
  "$VENV_DIR/bin/pip" install qtpip

  ANDROID_REQ_FILE="$($VENV_DIR/bin/python - <<'PY'
import pathlib

try:
    import PySide6
except Exception:
    print("")
    raise SystemExit(0)

base = pathlib.Path(PySide6.__file__).resolve().parent
req = base / "scripts" / "requirements-android.txt"
print(str(req) if req.exists() else "")
PY
)"

  if [[ -n "$ANDROID_REQ_FILE" ]]; then
    "$VENV_DIR/bin/pip" install -r "$ANDROID_REQ_FILE"
  else
    # Fallback for older layouts.
    "$VENV_DIR/bin/pip" install jinja2 pkginfo tqdm "packaging==24.1"
  fi

  # Store a marker so subsequent runs can skip pip network checks.
  "$VENV_DIR/bin/python" - <<'PY'
from __future__ import annotations

import hashlib
from pathlib import Path

project_dir = Path.cwd()
venv_dir = project_dir / ".venv-android"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

req_txt = project_dir / "requirements.txt"
data = {
    "requirements.txt": sha256_file(req_txt) if req_txt.exists() else "",
}

marker = venv_dir / ".setup-hash"
marker.write_text("\n".join(f"{k}={v}" for k, v in sorted(data.items())) + "\n", encoding="utf-8")
PY
}

need_venv_setup=0
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  need_venv_setup=1
elif [[ "$FORCE_VENV_SETUP" == "1" ]]; then
  need_venv_setup=1
elif [[ ! -f "$VENV_DIR/.setup-hash" ]]; then
  need_venv_setup=1
else
  # If requirements.txt changed since the last setup, re-run installs.
  if ! "$PYTHON_BIN" - <<'PY' "$VENV_DIR/.setup-hash" "$PROJECT_DIR/requirements.txt"
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

marker_path = Path(sys.argv[1])
req_path = Path(sys.argv[2])

expected = {}
for line in marker_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    k, v = line.split("=", 1)
    expected[k] = v

h = hashlib.sha256()
h.update(req_path.read_bytes())
current = h.hexdigest()

sys.exit(0 if expected.get("requirements.txt") == current else 1)
PY
  then
    need_venv_setup=1
  fi
fi

if [[ "$need_venv_setup" == "1" ]]; then
  echo "Setting up Python venv for Android build: $VENV_DIR" >&2
  setup_venv
else
  echo "Reusing existing venv (skip pip installs): $VENV_DIR" >&2
fi

# pyside6-android-deploy currently hardcodes python-for-android settings.
# We patch the installed helper to avoid building whatever the newest CPython is,
# and instead build a cp311-compatible runtime (to match the Android wheels).
PYSIDE_BUILD_SCRIPT="$VENV_DIR/lib/python$PYTHON_MAJOR_MINOR/site-packages/PySide6/scripts/deploy_lib/android/buildozer.py"
if [[ -f "$PYSIDE_BUILD_SCRIPT" ]]; then
  "$VENV_DIR/bin/python" - <<PY
from pathlib import Path

path = Path(r"$PYSIDE_BUILD_SCRIPT")
text = path.read_text(encoding="utf-8")

python_version = r"$ANDROID_PYTHON_VERSION"
p4a_branch = r"$P4A_BRANCH"

updated = text
updated = updated.replace(
    'self.set_value("app", "requirements", "python3,shiboken6,PySide6")',
    f'self.set_value("app", "requirements", "python3=={python_version},shiboken6,PySide6")',
)
updated = updated.replace(
    'self.set_value("app", "p4a.branch", "develop")',
    f'self.set_value("app", "p4a.branch", "{p4a_branch}")',
)

if updated != text:
    path.write_text(updated, encoding="utf-8")
PY
fi

mkdir -p "$WHEELS_DIR"

# You can bypass qtpip download by providing wheel paths directly.
PYSIDE_WHEEL="${PYSIDE_WHEEL:-}"
SHIBOKEN_WHEEL="${SHIBOKEN_WHEEL:-}"

if [[ -z "$PYSIDE_WHEEL" || -z "$SHIBOKEN_WHEEL" ]]; then
  echo "Downloading Qt for Python Android wheels into: $WHEELS_DIR"
  if ! (
    cd "$WHEELS_DIR"
    "$VENV_DIR/bin/qtpip" download PySide6 --android --arch aarch64 --no-input
  ); then
    echo "ERROR: qtpip failed to download Android wheels." >&2
    echo "This usually means Qt for Python Android wheels require Qt commercial credentials." >&2
    echo "If you have a commercial Qt account, run the Qt MaintenanceTool to generate local credentials," >&2
    echo "then retry. Otherwise, set PYSIDE_WHEEL and SHIBOKEN_WHEEL to pre-downloaded wheel file paths." >&2
    exit 1
  fi

  PYSIDE_WHEEL=$(ls "$WHEELS_DIR"/PySide6*-android* 2>/dev/null | head -n 1 || true)
  SHIBOKEN_WHEEL=$(ls "$WHEELS_DIR"/shiboken6*-android* 2>/dev/null | head -n 1 || true)
fi

if [[ -z "$PYSIDE_WHEEL" || -z "$SHIBOKEN_WHEEL" ]]; then
  echo "ERROR: Could not find Android wheels in $WHEELS_DIR" >&2
  echo "If qtpip printed 'No Commercial License found', you need Qt commercial credentials on this machine" >&2
  echo "(generated by the Qt MaintenanceTool) or you must provide wheel paths via PYSIDE_WHEEL and SHIBOKEN_WHEEL." >&2
  echo "Found:" >&2
  ls -la "$WHEELS_DIR" >&2 || true
  exit 1
fi

# Ensure tools that check for active virtualenv (e.g. buildozer) behave correctly.
export VIRTUAL_ENV="$VENV_DIR"
export PATH="$VENV_DIR/bin:$PATH"

deploy_state_ready() {
  [[ -f "$PROJECT_DIR/buildozer.spec" ]] && [[ -d "$PROJECT_DIR/deployment" ]] && [[ -d "$PROJECT_DIR/.buildozer" ]]
}

ensure_blacklist() {
  if [[ "$PRUNE_QT_QML" != "1" ]]; then
    return 0
  fi
  if [[ ! -f "$ANDROID_BLACKLIST_FILE" ]]; then
    echo "WARN: PRUNE_QT_QML=1 but blacklist file not found: $ANDROID_BLACKLIST_FILE" >&2
    return 0
  fi
  if [[ ! -f "$PROJECT_DIR/buildozer.spec" ]]; then
    return 0
  fi

  if grep -qE '^android\.blacklist_src\s*=|^android\.p4a_blacklist_src\s*=' "$PROJECT_DIR/buildozer.spec"; then
    return 0
  fi

  echo "Enabling p4a blacklist (prune Qt QML/QtQuick): $ANDROID_BLACKLIST_FILE" >&2
  printf '\nandroid.blacklist_src = %s\n' "$ANDROID_BLACKLIST_FILE" >> "$PROJECT_DIR/buildozer.spec"
}

DEPLOY_LOG_FILE="$(mktemp -t pyside6-android-deploy.XXXXXX.log)"
set +e
if [[ "$FORCE_DEPLOY" != "1" ]] && deploy_state_ready; then
  ensure_blacklist
  "$VENV_DIR/bin/python" -m buildozer android "$BUILD_MODE" 2>&1 | tee "$DEPLOY_LOG_FILE"
  DEPLOY_RC=${PIPESTATUS[0]}
else
  "$VENV_DIR/bin/pyside6-android-deploy" \
    --config-file "$PROJECT_DIR/pysidedeploy.spec" \
    $([[ "$KEEP_DEPLOYMENT_FILES" == "1" ]] && echo "--keep-deployment-files") \
    $([[ "$FORCE_DEPLOY" == "1" ]] && echo "--force") \
    --name "GiftTest" \
    --wheel-pyside "$PYSIDE_WHEEL" \
    --wheel-shiboken "$SHIBOKEN_WHEEL" \
    --sdk-path "$ANDROID_SDK_ROOT" \
    --ndk-path "$NDK_PATH" \
    --extra-ignore-dirs ".venv,.venv-android,dist,build,packaging,perguntas_anatomia" \
    --verbose 2>&1 | tee "$DEPLOY_LOG_FILE"
  DEPLOY_RC=${PIPESTATUS[0]}
fi
set -e

have_apk() {
  ls "$PROJECT_DIR"/dist_android/*.apk >/dev/null 2>&1
}

# Treat any failure as a failure signal and attempt known remediations.
if [[ "$DEPLOY_RC" -ne 0 ]] || ! have_apk; then
  # Known issue: python-for-android's generated Qt bootstrap Java code calls
  # QtNative.setEnvironmentVariable(), which doesn't exist in Qt 6. Replace with
  # android.system.Os.setenv() (API 21+) and retry buildozer.
  # Note: some environments wrap long lines, so match both the full symbol and
  # partial/wrapped fragments.
  if grep -qE "QtNative\\.setEnvir|setEnvironmentVariable\\(" "$DEPLOY_LOG_FILE"; then
    echo "Detected Qt6 Android Java API mismatch (QtNative.setEnvironmentVariable). Patching generated sources and retrying buildozer..." >&2

  "$VENV_DIR/bin/python" - <<'PY'
from __future__ import annotations

from pathlib import Path

project_dir = Path.cwd()
buildozer_dir = project_dir / ".buildozer"

if not buildozer_dir.exists():
  raise SystemExit("Expected .buildozer directory to exist (enable --keep-deployment-files).")

targets = [
  # dist Java sources
  *buildozer_dir.glob("android/platform/**/dists/**/src/main/java/org/kivy/android/PythonActivity.java"),
  # bootstrap build sources
  *buildozer_dir.glob("android/platform/**/bootstrap_builds/qt/src/main/java/org/kivy/android/PythonActivity.java"),
  # p4a bootstrap templates
  *buildozer_dir.glob("android/platform/python-for-android/pythonforandroid/bootstraps/qt/build/src/main/java/org/kivy/android/PythonActivity.java"),
]

def patch_file(path: Path) -> bool:
  text = path.read_text(encoding="utf-8")
  if "QtNative.setEnvironmentVariable" not in text:
    return False

  updated = text
  # Ensure Os import exists
  if "import android.system.Os;" not in updated:
    updated = updated.replace(
      "import android.content.pm.PackageManager;",
      "import android.content.pm.PackageManager;\nimport android.system.Os;",
    )

  # Drop QtNative import if present
  updated = updated.replace("import org.qtproject.qt.android.QtNative;\n", "")

  replacements = {
    'QtNative.setEnvironmentVariable("ANDROID_ENTRYPOINT", entry_point);':
      'try { Os.setenv("ANDROID_ENTRYPOINT", entry_point, true); } catch (Exception e) { Log.w(TAG, "Failed to set ANDROID_ENTRYPOINT", e); }',
    'QtNative.setEnvironmentVariable("ANDROID_ARGUMENT", app_root_dir);':
      'try { Os.setenv("ANDROID_ARGUMENT", app_root_dir, true); } catch (Exception e) { Log.w(TAG, "Failed to set ANDROID_ARGUMENT", e); }',
    'QtNative.setEnvironmentVariable("ANDROID_APP_PATH", app_root_dir);':
      'try { Os.setenv("ANDROID_APP_PATH", app_root_dir, true); } catch (Exception e) { Log.w(TAG, "Failed to set ANDROID_APP_PATH", e); }',
    'QtNative.setEnvironmentVariable("ANDROID_PRIVATE", mFilesDirectory);':
      'try { Os.setenv("ANDROID_PRIVATE", mFilesDirectory, true); } catch (Exception e) { Log.w(TAG, "Failed to set ANDROID_PRIVATE", e); }',
    'QtNative.setEnvironmentVariable("ANDROID_UNPACK", app_root_dir);':
      'try { Os.setenv("ANDROID_UNPACK", app_root_dir, true); } catch (Exception e) { Log.w(TAG, "Failed to set ANDROID_UNPACK", e); }',
    'QtNative.setEnvironmentVariable("PYTHONHOME", app_root_dir);':
      'try { Os.setenv("PYTHONHOME", app_root_dir, true); } catch (Exception e) { Log.w(TAG, "Failed to set PYTHONHOME", e); }',
    'QtNative.setEnvironmentVariable("PYTHONPATH", app_root_dir + ":" + app_root_dir + "/lib");':
      'try { Os.setenv("PYTHONPATH", app_root_dir + ":" + app_root_dir + "/lib", true); } catch (Exception e) { Log.w(TAG, "Failed to set PYTHONPATH", e); }',
    'QtNative.setEnvironmentVariable("PYTHONOPTIMIZE", "2");':
      'try { Os.setenv("PYTHONOPTIMIZE", "2", true); } catch (Exception e) { Log.w(TAG, "Failed to set PYTHONOPTIMIZE", e); }',
  }

  for old, new in replacements.items():
    updated = updated.replace(old, new)

  if updated == text:
    return False

  path.write_text(updated, encoding="utf-8")
  return True


patched_any = False
for path in targets:
  try:
    patched_any |= patch_file(path)
  except Exception as exc:
    raise SystemExit(f"Failed to patch {path}: {exc}")

if not patched_any:
  raise SystemExit("Did not find any QtNative.setEnvironmentVariable call sites to patch.")

print("Patched Qt bootstrap Java sources:")
for path in targets:
  if path.exists():
    print(f"- {path}")
PY

    # Retry using the kept buildozer.spec/.buildozer state.
    "$VENV_DIR/bin/python" -m buildozer android debug

    # Ensure we end up with a stable output location.
    if ! have_apk; then
      FOUND_APK="$(ls -t "$PROJECT_DIR"/*.apk 2>/dev/null | head -n 1 || true)"
      if [[ -z "$FOUND_APK" ]]; then
        FOUND_APK="$(ls -t "$PROJECT_DIR"/bin/*.apk 2>/dev/null | head -n 1 || true)"
      fi
      if [[ -z "$FOUND_APK" ]]; then
        FOUND_APK="$(ls -t "$PROJECT_DIR"/.buildozer/android/platform/python-for-android/*.apk 2>/dev/null | head -n 1 || true)"
      fi
      if [[ -n "$FOUND_APK" ]]; then
        cp -f "$FOUND_APK" "$PROJECT_DIR/dist_android/$(basename "$FOUND_APK")"
      fi
    fi
  elif [[ "$DEPLOY_RC" -ne 0 ]]; then
    echo "Android build failed (see $DEPLOY_LOG_FILE)." >&2
    exit "$DEPLOY_RC"
  fi
fi

if ! have_apk; then
  echo "ERROR: Android build completed but no APK was produced in dist_android/." >&2
  echo "See log: $DEPLOY_LOG_FILE" >&2
  exit 1
fi

echo "Done. Search for output APK/AAB under: $PROJECT_DIR"

# Convenience: keep a copy of the latest built APK in /tmp so it survives any
# subsequent clean/rebuild iterations.
APK_SRC="$(ls -t "$PROJECT_DIR"/dist_android/*.apk 2>/dev/null | head -n 1 || true)"
if [[ -n "$APK_SRC" ]]; then
  APK_BASENAME="$(basename "$APK_SRC")"
  APK_TS="$(date +%Y%m%d-%H%M%S)"
  APK_DST="/tmp/${APK_BASENAME%.apk}-$APK_TS.apk"
  cp -f "$APK_SRC" "$APK_DST"
  echo "Copied APK to: $APK_DST"
fi