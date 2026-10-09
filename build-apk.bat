@echo off
REM ============================================================
REM  Field Moisture App - one-click local APK build (via WSL)
REM  Double-click this file. No signing/certificate needed:
REM  the output is a debug APK, auto-signed, ready to install.
REM ============================================================
setlocal

where wsl >nul 2>nul
if errorlevel 1 (
  echo [ERROR] WSL not found. Enable it first: run "wsl --install" in an
  echo         Administrator PowerShell, reboot, then run this file again.
  pause
  exit /b 1
)

wsl -l -q 2>nul | findstr /i "Ubuntu" >nul
if errorlevel 1 (
  echo [SETUP] Installing Ubuntu for WSL ^(one time only^)...
  wsl --install -d Ubuntu --no-launch
  if errorlevel 1 (
    echo [ERROR] Ubuntu install failed. If Windows asked for a reboot,
    echo         reboot and run this file again.
    pause
    exit /b 1
  )
  echo [SETUP] Ubuntu installed.
)

echo [BUILD] Starting build inside WSL Ubuntu...
echo         First run downloads Android SDK/NDK (~3GB), 30-60 minutes.
echo         Do NOT close this window.
wsl -d Ubuntu -u root -e bash /mnt/c/Users/hlwsh/WorkBuddy/2026-10-08-06-12-32/moisture-app/tools/build_wsl.sh

echo.
if exist "bin\*.apk" (
  echo [DONE] APK is ready in the "bin" folder next to this file:
  dir /b bin\*.apk
  echo Copy it to your phone and install ^(allow unknown sources^).
) else (
  echo [FAIL] No APK produced. Scroll up to see the error.
)
pause
