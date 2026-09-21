@echo off
setlocal
py -m pip install --upgrade pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name LicenseManager license_manager.py
echo.
echo Da tao: dist\LicenseManager.exe
pause
