[app]

# display name
title = GiftTest

# project directory (parent of main entry point)
project_dir = .

# main entry point (must be named main.py for pyside6-android-deploy)
input_file = main.py

# optional qt creator .pyproject file (not used)
project_file = 

# output directory for deployment artefacts
exec_directory = dist_android
icon = /home/paulo/code/GiftTest/.venv-android/lib/python3.11/site-packages/PySide6/scripts/deploy_lib/pyside_icon.jpg

[python]

# recommended = run inside a venv. Leave empty to use the current interpreter.
python_path = /home/paulo/code/GiftTest/.venv-android/bin/python

# packages that pyside6-android-deploy may install for android deployment.
android_packages = buildozer,Cython

[qt]

# let the tool auto-detect modules/plugins. you can append modules here if needed.
modules = Gui,Core,Widgets
qml_files = 

[android]

# wheels are provided at build time via cli (--wheel-pyside/--wheel-shiboken).
wheel_pyside = /home/paulo/code/GiftTest/.android-wheels/PySide6-6.10.1-6.10.1-cp311-cp311-android_aarch64.whl
wheel_shiboken = /home/paulo/code/GiftTest/.android-wheels/shiboken6-6.10.1-6.10.1-cp311-cp311-android_aarch64.whl

# let the tool auto-detect. append plugin folder names if needed.
plugins = platforms_qtforandroid

[buildozer]

# debug -> apk, release -> aab
mode = debug

# target architecture for ci/local default
arch = aarch64
ndk_path = /home/paulo/Android/Sdk/ndk/26.1.10909125
sdk_path = /home/paulo/Android/Sdk
local_libs = plugins_platforms_qtforandroid
jars_dir = /home/paulo/code/GiftTest/deployment/jar/PySide6/jar
recipe_dir = /home/paulo/code/GiftTest/deployment/recipes

