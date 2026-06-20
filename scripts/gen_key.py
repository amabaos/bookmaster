"""Генерирует ENCRYPTION_KEY для .env"""
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
