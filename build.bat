@echo off
REM Build tcplat.exe on Windows.
REM Requires Python 3 installed and on PATH (https://python.org).

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m PyInstaller --onefile --console --name tcplat tcplat.py

echo.
echo Listo. El ejecutable esta en dist\tcplat.exe
pause
