@echo off
echo ===========================================
echo   Video Compressor Pro - Build Script
echo ===========================================

:: 1. Setup Environment
if not exist "venv" (
    echo [ERROR] Virtual environment 'venv' not found!
    echo Please run 'setup_env.bat' first.
    pause
    exit /b
)

call venv\Scripts\activate
echo [INFO] Virtual environment activated.

:: 2. Install PyInstaller
echo [INFO] Ensuring PyInstaller is installed...
pip install pyinstaller

:: 3. Find CustomTkinter Path
:: We need to tell PyInstaller where to find CustomTkinter's data files (json, themes)
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i

echo [INFO] CustomTkinter found at: %CTK_PATH%

:: 4. Run PyInstaller
echo [INFO] Building Executable...
:: --noconfirm: overwrite existing build folders
:: --onedir: create a folder (easier for debugging permissions) or --onefile (single exe)
:: We use --onefile for distribution convenience
:: --windowed: no console window popup
:: --add-data: include customtkinter layout files
:: --name: output filename

pyinstaller --noconfirm --onefile --windowed --name "VideoCompressorPro" ^
    --add-data "%CTK_PATH%;customtkinter" ^
    --hidden-import "PIL._tkinter_finder" ^
    app.py

echo.
echo ===========================================
echo   BUILD COMPLETE
echo ===========================================
echo.
if exist "dist\VideoCompressorPro.exe" (
    echo [SUCCESS] Your app is ready: dist\VideoCompressorPro.exe
    echo You can upload this file to GitHub Releases.
) else (
    echo [ERROR] Build failed. Check the errors above.
)
pause
