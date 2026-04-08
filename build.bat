@echo off
echo Building FrontLines Monitor Suite...
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Check if Pillow is installed
pip show Pillow >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Pillow...
    pip install Pillow
)

REM Check if pystray is installed
pip show pystray >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing pystray...
    pip install pystray
)

echo.
echo ========================================
echo STEP 1: Building application...
echo ========================================
echo.

python -m PyInstaller --onedir --windowed --icon=app.ico --name=FrontLinesMonitorSuite --add-data "app.ico;." --add-data "Bag_Safari_Ball_SV_Sprite.png;." --add-data "credentials.json;." --hidden-import=discord --hidden-import=googleapiclient --hidden-import=google_auth_oauthlib --hidden-import=requests --hidden-import=PIL --hidden-import=pystray main.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo STEP 2: Building installer...
echo ========================================
echo.

"C:\Users\Kyle\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Installer build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo BUILD COMPLETE!
echo ========================================
echo.
echo Installer: installer\FrontLinesMonitorSuite_Setup_3.0.exe
echo.

pause
