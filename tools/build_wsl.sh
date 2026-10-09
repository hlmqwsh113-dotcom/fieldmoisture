#!/bin/bash
# Local APK build inside WSL Ubuntu (runs as root, fully non-interactive).
# First run downloads Android SDK/NDK (~3GB) and takes 30-60 minutes.
set -e

export DEBIAN_FRONTEND=noninteractive

echo "=== [1/4] Installing build dependencies ==="
apt-get update -qq
apt-get install -y -qq git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo5 cmake libffi-dev libssl-dev ccache

echo "=== [2/4] Installing buildozer ==="
pip3 install --break-system-packages -q buildozer cython 2>/dev/null \
  || pip3 install -q buildozer cython

echo "=== [3/4] Copying project to Linux filesystem (faster & avoids /mnt/c issues) ==="
SRC=/mnt/c/Users/hlwsh/WorkBuddy/2026-10-08-06-12-32/moisture-app
WORK=$HOME/moisture-app
rm -rf "$WORK"
mkdir -p "$WORK"
cp -r "$SRC"/. "$WORK"/
rm -rf "$WORK/.buildozer" "$WORK/bin"
cd "$WORK"

echo "=== [4/4] Building APK (first run downloads SDK/NDK, please wait) ==="
buildozer android debug

echo "=== Copying APK back to Windows project bin/ ==="
mkdir -p "$SRC/bin"
cp -v bin/*.apk "$SRC/bin/"

echo ""
echo "BUILD OK - APK copied to: moisture-app/bin/"
ls -la "$SRC/bin/"
