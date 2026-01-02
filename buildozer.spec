[app]
# Application title
title = GiftTest

# Package name (must be alphanumeric lowercase)
package.name = gifttest

# Package domain (for app identification)
package.domain = org.gifttest

# Source code entry point
source.dir = .
source.include_exts = py,png,jpg,gif,txt,json

# Application version (sync with setup.py)
version = 1.0.0

# Application requirements
# IMPORTANT: PySide6 Android support is experimental and limited.
# PySide6 is primarily designed for desktop platforms.
# For production Android apps, consider Kivy or BeeWare frameworks.
# This spec provides the base structure for Android builds.
requirements = python3,pyside6,pillow

# Permissions needed (minimal for mobile readiness)
android.permissions = INTERNET

# Orientation (both portrait and landscape for mobile readiness)
orientation = all

# Android API target versions
android.api = 31
android.minapi = 21
android.ndk = 25b
android.sdk = 31

# Build architecture (supporting both 32 and 64 bit)
android.archs = arm64-v8a,armeabi-v7a

# Application icon (using default if not provided)
# icon.filename = %(source.dir)s/assets/icon.png

# Presplash
# presplash.filename = %(source.dir)s/assets/presplash.png

[buildozer]
# Build log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# Do not warn about various issues
warn_on_root = 1

# Build directory
build_dir = ./.buildozer

# Binary directory
bin_dir = ./bin

