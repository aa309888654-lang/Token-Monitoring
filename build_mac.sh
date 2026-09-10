#!/bin/bash
# 打包 macOS 应用：dist/小天tokens监控.app
# 需要先安装依赖:  pip install pyinstaller cryptography
cd "$(dirname "$0")"

python3 -m PyInstaller --windowed --noconfirm \
  --name "小天tokens监控" \
  --icon tokenmon.icns \
  --hidden-import cryptography \
  --hidden-import cryptography.x509 \
  --hidden-import cryptography.hazmat.backends.openssl \
  --collect-submodules cryptography.hazmat \
  tokenmon.py

echo
echo "完成: dist/小天tokens监控.app"
