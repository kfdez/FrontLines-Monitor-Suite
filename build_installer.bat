@echo off
echo ================================
echo  FrontLines Monitor Suite Build
echo ================================
echo.

echo [1/3] Cleaning old build files...
if exist "dist\FrontLinesMonitorSuite" rmdir /s /q "dist\FrontLinesMonitorSuite"
if exist "build\FrontLinesMonitorSuite" rmdir /s /q "build\FrontLinesMonitorSuite"
echo Done.
echo.

echo [2/3] Building executable with PyInstaller...
python -m PyInstaller FrontLinesMonitorSuite.spec
if %errorlevel% neq 0 (
    echo.
    echo ERROR: PyInstaller failed. Aborting.
    pause
    exit /b 1
)
echo.

echo [3/3] Building installer with Inno Setup...
"C:\Users\Kyle\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Inno Setup failed.
    pause
    exit /b 1
)

echo.
echo ================================
echo  Build complete!
echo  Output: installer\FrontLinesMonitorSuite_Setup_v7.exe
echo ================================
pause
