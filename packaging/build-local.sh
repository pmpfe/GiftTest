#!/bin/bash
# Local build script for cross-platform packaging
# Usage: ./packaging/build-local.sh [windows|macos|linux|all]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BUILD_TARGET=${1:-all}
DIST_DIR="dist"
VERSION=$(grep "version=" setup.py | head -1 | grep -oP '"\K[^"]+')

echo -e "${YELLOW}Building Gift Test Practice v${VERSION}${NC}"

# Ensure dependencies are installed
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt
pip install -q pyinstaller

# Function to build for Linux
build_linux() {
    echo -e "${YELLOW}Building for Linux...${NC}"
    
    # Install system dependencies if not present
    if command -v apt-get &> /dev/null; then
        echo "Installing Linux build dependencies..."
        sudo apt-get update
        sudo apt-get install -y libpython3-dev fpm 2>/dev/null || true
    fi
    
    LINUX_DIST="$DIST_DIR/linux"
    mkdir -p "$LINUX_DIST"
    
    pyinstaller \
        --onefile \
        --name "gift-test-practice" \
        --add-data "data:data" \
        --distpath "$LINUX_DIST" \
        main.py
    
    echo -e "${GREEN}✓ Linux build complete: $LINUX_DIST/gift-test-practice${NC}"
}

# Function to build for macOS
build_macos() {
    echo -e "${YELLOW}Building for macOS...${NC}"
    
    if [[ "$OSTYPE" != "darwin"* ]]; then
        echo -e "${RED}Error: macOS build can only run on macOS${NC}"
        return 1
    fi
    
    MACOS_DIST="$DIST_DIR/macos"
    mkdir -p "$MACOS_DIST"
    
    pyinstaller \
        --onefile \
        --windowed \
        --name "GiftTestPractice" \
        --icon="assets/icon.icns" \
        --add-data "data:data" \
        --distpath "$MACOS_DIST" \
        main.py
    
    # Create DMG
    echo "Creating DMG installer..."
    mkdir -p "$MACOS_DIST/dmg-tmp"
    cp -r "$MACOS_DIST/GiftTestPractice.app" "$MACOS_DIST/dmg-tmp/"
    ln -s /Applications "$MACOS_DIST/dmg-tmp/Applications" || true
    
    hdiutil create -volname "GiftTestPractice" \
        -srcfolder "$MACOS_DIST/dmg-tmp" \
        -ov -format UDZO \
        "$DIST_DIR/GiftTestPractice.dmg"
    
    rm -rf "$MACOS_DIST/dmg-tmp"
    
    echo -e "${GREEN}✓ macOS build complete: $DIST_DIR/GiftTestPractice.dmg${NC}"
}

# Function to build for Windows
build_windows() {
    echo -e "${YELLOW}Building for Windows...${NC}"
    
    WINDOWS_DIST="$DIST_DIR/windows"
    mkdir -p "$WINDOWS_DIST"
    
    pyinstaller \
        --onefile \
        --windowed \
        --name "GiftTestPractice" \
        --icon="assets/icon.ico" \
        --add-data "data:data" \
        --distpath "$WINDOWS_DIST" \
        main.py
    
    echo -e "${GREEN}✓ Windows build complete: $WINDOWS_DIST/GiftTestPractice.exe${NC}"
    
    # Check for NSIS
    if command -v makensis &> /dev/null; then
        echo "Creating NSIS installer..."
        makensis packaging/windows/installer.nsi || echo "NSIS installation failed - exe is still available"
    else
        echo -e "${YELLOW}Note: NSIS not found - installer not created. Executable available at $WINDOWS_DIST/GiftTestPractice.exe${NC}"
    fi
}

# Main build logic
case $BUILD_TARGET in
    windows)
        build_windows
        ;;
    macos)
        build_macos
        ;;
    linux)
        build_linux
        ;;
    all)
        build_linux
        if [[ "$OSTYPE" == "darwin"* ]]; then
            build_macos
        fi
        # Windows build requires Windows or cross-compilation setup
        echo -e "${YELLOW}Note: Windows build requires Windows OS. Use GitHub Actions for cross-platform builds.${NC}"
        ;;
    *)
        echo "Usage: $0 [windows|macos|linux|all]"
        exit 1
        ;;
esac

echo -e "${GREEN}Build process complete!${NC}"
echo -e "${YELLOW}Artifacts located in: $DIST_DIR/${NC}"
