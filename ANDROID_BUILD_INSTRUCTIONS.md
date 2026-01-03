# How to Generate and Test the Android APK

## Option 1: Using GitHub Actions (Recommended)

This is the easiest method and will generate the APK automatically.

### Steps:

1. **Merge this PR** to main branch (or push to a branch that will be tagged)

2. **Create and push a version tag**:
   ```bash
   git checkout main
   git pull
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Wait for GitHub Actions to complete** (30-60 minutes for first build)
   - Go to: https://github.com/pmpfe/GiftTest/actions
   - Watch the "Build and Release" workflow
   - The `build-android` job will create the APK

4. **Download the APK**:
   - Go to: https://github.com/pmpfe/GiftTest/releases/latest
   - Download the `.apk` file
   - APK name will be something like: `gifttest-1.0.0-arm64-v8a-debug.apk`

## Option 2: Building Locally (Advanced)

If you want to build the APK on your local machine:

### Prerequisites:
- Linux or macOS (recommended)
- Python 3.11+
- Java 17
- Git
- At least 20GB free disk space

### Steps:

1. **Install buildozer**:
   ```bash
   pip install buildozer cython
   ```

2. **Install system dependencies**:
   
   **Ubuntu/Debian**:
   ```bash
   sudo apt-get install -y git zip unzip openjdk-17-jdk wget \
     automake autoconf libtool pkg-config zlib1g-dev libncurses-dev \
     cmake libffi-dev libssl-dev
   ```
   
   **macOS**:
   ```bash
   brew install autoconf automake libtool pkg-config
   brew install --cask adoptopenjdk
   ```

3. **Navigate to the project directory**:
   ```bash
   cd /path/to/GiftTest
   ```

4. **Build the APK** (first build takes 30-60 minutes):
   ```bash
   buildozer android debug
   ```

5. **Find the APK**:
   ```bash
   ls -lh bin/*.apk
   ```
   The APK will be in the `bin/` directory with a name like:
   - `gifttest-1.0.0-arm64-v8a-debug.apk` (64-bit ARM)
   - `gifttest-1.0.0-armeabi-v7a-debug.apk` (32-bit ARM)

## Testing the APK on Android Device

### Enable Developer Options:
1. Go to **Settings** > **About Phone**
2. Tap **Build Number** 7 times
3. Go back to **Settings** > **Developer Options**
4. Enable **USB Debugging**

### Install the APK:

**Method 1: Via USB (ADB)**
```bash
adb install bin/gifttest-1.0.0-arm64-v8a-debug.apk
```

**Method 2: Direct Transfer**
1. Copy the APK to your Android device (via USB, email, cloud storage, etc.)
2. On your device, use a file manager to locate the APK
3. Tap the APK file to install
4. You may need to allow "Install from Unknown Sources" in Settings

### What to Test:

1. **App Launch**:
   - Does the app open without crashing?
   - Does the main menu appear?

2. **UI/UX**:
   - Are buttons visible and properly sized?
   - Can you tap/touch all interactive elements?
   - Does the layout fit the screen (portrait/landscape)?
   - Are fonts readable?

3. **Core Functionality**:
   - Can you load a GIFT file?
   - Can you select categories?
   - Can you start a test?
   - Can you answer questions?
   - Can you view results?

4. **LLM Features** (requires internet):
   - Can you configure API keys?
   - Can you request explanations?
   - Do explanations display properly?

5. **Performance**:
   - Is the app responsive?
   - Any lag or stuttering?
   - Memory usage (check in Android Settings > Apps)?

### Known Limitations (Expected Issues):

⚠️ **This is an EXPERIMENTAL build** using PySide6 which has limited Android support.

**Expect:**
- UI elements may not display correctly
- Touch interactions may be problematic
- Some Qt widgets may not work on Android
- Performance may be poor
- App may crash on certain operations
- Screen layouts may not adapt well to mobile

**Document any issues you encounter!**

## Getting the APK URL for Testing

After GitHub Actions completes the build:

1. Go to the latest release: https://github.com/pmpfe/GiftTest/releases/latest
2. Look for the APK file in the "Assets" section
3. Right-click on the APK filename and select "Copy Link Address"
4. Share this URL for testing

**Example URL format**:
```
https://github.com/pmpfe/GiftTest/releases/download/v1.0.0/gifttest-1.0.0-arm64-v8a-debug.apk
```

## Troubleshooting

### Build fails in GitHub Actions:
- Check the logs in the Actions tab
- Verify buildozer.spec syntax
- Ensure all dependencies are listed in requirements.txt

### APK won't install on device:
- Check Android version (minimum API 21 / Android 5.0)
- Try different installation method
- Check device architecture (arm64-v8a or armeabi-v7a)

### App crashes on launch:
- Check logcat logs: `adb logcat | grep python`
- PySide6 may have compatibility issues on your device
- Consider this a known limitation of experimental support

### Blank screen or UI issues:
- PySide6 Qt widgets may not render properly on Android
- This is a fundamental limitation of using desktop UI framework on mobile
- Consider this expected behavior for this experimental build

## Next Steps After Testing

Based on test results, decide whether to:

1. **Continue with PySide6 Android** (if basic functionality works)
   - Document all issues
   - Create workarounds for mobile UI
   - Add mobile-specific configurations

2. **Switch to mobile-friendly framework** (if major issues found)
   - Kivy (Python, mobile-first)
   - BeeWare (Python, native UI)
   - React Native (JavaScript)
   - Flutter (Dart)
   - Native Android (Kotlin/Java)

3. **Create web version** (simplest cross-platform approach)
   - Build a web app with Flask/FastAPI backend
   - Works on all devices with a browser
   - Progressive Web App (PWA) for app-like experience
