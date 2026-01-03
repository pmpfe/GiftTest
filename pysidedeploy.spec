[app]
# Display name
title = GiftTest
# Project directory (parent of main entry point)
project_dir = .
# Main entry point (must be named main.py for pyside6-android-deploy)
input_file = main.py
# Optional Qt Creator .pyproject file (not used)
project_file =
# Output directory for deployment artefacts
exec_directory = dist_android

[python]
# Recommended: run inside a venv. Leave empty to use the current interpreter.
python_path =
# Packages that pyside6-android-deploy may install for Android deployment.
android_packages = buildozer,Cython

[qt]
# Let the tool auto-detect modules/plugins. You can append modules here if needed.
modules =

[android]
# Wheels are provided at build time via CLI (--wheel-pyside/--wheel-shiboken).
wheel_pyside =
wheel_shiboken =
# Let the tool auto-detect. Append plugin folder names if needed.
plugins =

[buildozer]
# debug -> APK, release -> AAB
mode = debug
# Target architecture for CI/local default
arch = aarch64
