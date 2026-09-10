@echo off
rem 打包 小天tokens监控.exe
rem 需要先安装依赖:  pip install pyinstaller cryptography
cd /d "%~dp0"
python -m PyInstaller --onefile --windowed --name 小天tokens监控 --icon logo.ico --clean --noconfirm ^
  --hidden-import cryptography ^
  --hidden-import cryptography.x509 ^
  --hidden-import cryptography.hazmat.backends.openssl ^
  --collect-submodules cryptography.hazmat ^
  tokenmon.py
echo.
echo 完成: dist\小天tokens监控.exe
pause
