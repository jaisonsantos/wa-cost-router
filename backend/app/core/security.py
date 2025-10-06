from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import hashlib
import json
from typing import Any, Dict
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_fernet_key():
    """Derive a Fernet key from APP_SECRET_KEY"""
    key = hashlib.sha256(settings.APP_SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)

fernet = Fernet(get_fernet_key())

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        return payload
    except JWTError:
        return None

def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()


def encrypt_credentials(data: Dict[str, Any]) -> str:
    """Encrypt arbitrary credential payloads using Fernet."""
    plaintext = json.dumps(data, sort_keys=True).encode()
    return fernet.encrypt(plaintext).decode()


def decrypt_credentials(ciphertext: str) -> Dict[str, Any]:
    """Decrypt previously encrypted credential payloads."""
    plaintext = fernet.decrypt(ciphertext.encode()).decode()
    return json.loads(plaintext)
