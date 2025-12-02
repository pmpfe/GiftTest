# Packaging & Release Guide

Complete documentation for cross-platform packaging and automated releases.

## Quick Start: Creating a Release

### Step 1: Prepare Code
```bash
git add .
git commit -m "Version 1.0.0 release"
```

### Step 2: Create Version Tag
```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### Step 3: Monitor Build
- GitHub Actions automatically triggers
- Monitor at: https://github.com/pmpfe/GiftTest/actions
- Builds for Windows, macOS, Linux simultaneously

### Step 4: Download Packages
Visit: https://github.com/pmpfe/GiftTest/releases/tag/v1.0.0

You'll find:
- **Windows:** Standalone `.exe` and NSIS installer
- **macOS:** Standalone `.app` and DMG installer
- **Linux:** Standalone executable and `.deb` package

### Step 5: Distribute
Choose your distribution channels:
- Direct downloads from GitHub Releases
- Package stores (Chocolatey, Homebrew, Snap, etc.)
- Your website

---

## Local Builds (Development/Testing)

For testing before release, build locally on your platform:

```bash
chmod +x packaging/build-local.sh
./packaging/build-local.sh linux    # Linux
./packaging/build-local.sh macos    # macOS (requires macOS)
./packaging/build-local.sh windows  # Windows (requires Windows)
```

Output: `dist/` directory with platform-specific builds.

---

## Troubleshooting

**"Workflow failed on Windows build"**
- Check NSIS installer syntax
- Fallback: Standalone `.exe` will still be created

**"Workflow failed on macOS build"**
- Check DMG creation steps
- Fallback: Standalone `.app` will still be created

**"Workflow failed on Linux build"**
- Check FPM syntax in workflow
- System uses `.deb` (works on Ubuntu, Debian, etc.)

---

## Technical Configuration

### Setup Requirements

#### Global
```bash
pip install -r requirements.txt
pip install pyinstaller
```

#### Platform-Specific

| Platform | Requirements |
|----------|--------------|
| **Linux** | `fpm` (package manager) |
| **macOS** | Xcode Command Line Tools |
| **Windows** | NSIS (optional, exe still builds without it) |

### File Structure

```
packaging/
├── PACKAGING.md                # This file
├── build-local.sh              # Local build script
├── pyinstaller/
│   └── gift-test-practice.spec # PyInstaller configuration
├── windows/
│   └── installer.nsi            # NSIS Windows installer script
└── linux/
    └── gift-test-practice.desktop # Linux desktop entry
```

### Configuration Files

#### PyInstaller (`pyinstaller/gift-test-practice.spec`)
- Creates standalone executables
- Includes PyQt6 modules and dependencies
- Bundles application data directory
- Platform-specific icons (PNG, ICO, ICNS)

#### Windows Installer (`windows/installer.nsi`)
- Creates NSIS `.exe` installer
- Installs to Program Files
- Creates Start Menu and Desktop shortcuts
- Registers in Windows Registry

#### Linux Desktop (`linux/gift-test-practice.desktop`)
- Desktop entry for application launchers
- Works with GNOME, KDE, XFCE, etc.
- Includes icon reference
- Categorized as Education application

### Icons

Pre-generated icons in `assets/`:
- `icon.png` - Linux (256x256)
- `icon.ico` - Windows (256x256)
- `icon.icns` - macOS (512x512)

### Build Script (`build-local.sh`)

Local build script for development/testing:

```bash
chmod +x packaging/build-local.sh
./packaging/build-local.sh linux    # Linux executable + .deb
./packaging/build-local.sh macos    # macOS app + DMG
./packaging/build-local.sh windows  # Windows .exe + installer
./packaging/build-local.sh all      # All platforms (cross-platform)
```

Output goes to `dist/` directory with platform-specific subdirectories.

### GitHub Actions Workflow

The workflow (`.github/workflows/build-releases.yml`) is triggered when you push a version tag.

**Triggers on:** `git push origin v*.*.* ` tags

**Builds:**
1. Windows: Standalone `.exe` + NSIS installer
2. macOS: Standalone `.app` + DMG disk image
3. Linux: Standalone executable + `.deb` package

**Output:** Creates GitHub Release with all artifacts

## Local vs Automated Builds

### Local Builds (Development)
- Run `packaging/build-local.sh` on your machine
- Test on your platform before pushing
- Output in `dist/` directory

### Automated Builds (Release)
- Push version tag to GitHub
- GitHub Actions builds all platforms simultaneously
- Results in GitHub Release page
- Each platform built on its native runner (best compatibility)
