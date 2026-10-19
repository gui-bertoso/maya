@echo off
setlocal

cd /d "%~dp0\.."

if not exist ".venv" (
    py -3.11 -m venv .venv
    if errorlevel 1 goto :error
)

set "PYTHON_EXE=%cd%\.venv\Scripts\python.exe"

"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :error

"%PYTHON_EXE%" -m pip install pyinstaller
if errorlevel 1 goto :error

"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean setup.spec
if errorlevel 1 goto :error

echo.
echo Build finalizado.
echo Executavel: dist\setup.exe
exit /b 0

:error
echo.
echo Falha ao gerar o setup.exe.
exit /b 1
