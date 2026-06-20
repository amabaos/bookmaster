import os
import base64
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

def _get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY не задан в .env")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


def generate_key() -> str:
    """Генерирует новый ключ — запустить один раз при настройке"""
    return Fernet.generate_key().decode()
