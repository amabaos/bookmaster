"""Центральный конфиг — читает переменные окружения."""
import os

# Папка для загружаемых файлов.
# Локально: ./uploads
# Railway: /data/uploads  (Volume примонтирован в /data)
UPLOAD_DIR = os.path.abspath(os.getenv("UPLOAD_DIR", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
