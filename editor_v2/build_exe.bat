@echo off
cd /d "%~dp0"
echo ==========================================
echo Starting Build Process for EK Editor v2
echo ==========================================

echo [1/2] Installing required packages (PyInstaller, Pillow)...
py -m pip install pyinstaller pillow

echo [2/2] Building executable...
rem --noconfirm: overwrites existing build without asking
rem --onefile: bundles everything into a single .exe
rem --windowed: hides the console window when running the app
py -m PyInstaller --noconfirm --onefile --windowed --name "EK_Editor_v2" main.py

echo.
echo ==========================================
echo Build completed successfully!
echo The executable (.exe) file is located in the 'dist' folder.
echo ==========================================
pause
