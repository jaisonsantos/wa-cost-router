from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from passlib.handlers import bcrypt as passlib_bcrypt
from cryptography.fernet import Fernet
import base64
import hashlib
import json
from typing import Any, Dict
from app.core.config import settings
from importlib import metadata
from types import SimpleNamespace

# passlib 1.7.x expects pyca/bcrypt to expose a ``__about__`` module attribute
# and silently truncates long passwords when probing for the historic wraparound
# bug.  bcrypt 4.1 removed ``__about__`` and now raises ``ValueError`` for
# passwords longer than 72 bytes, which breaks passlib's backend detection.
# We patch the imported module here so passlib can continue to operate with
# newer bcrypt releases without forcing a hard pin at the package level.

_bcrypt_backend = getattr(passlib_bcrypt, "_bcrypt", None)

if _bcrypt_backend is not None and not hasattr(_bcrypt_backend, "__about__"):
    version = getattr(_bcrypt_backend, "__version__", None)
    if version is None:
        try:
            version = metadata.version("bcrypt")
        except metadata.PackageNotFoundError:  # pragma: no cover - defensive
            version = None
    _bcrypt_backend.__about__ = SimpleNamespace(__version__=version)

_bcrypt_backend_cls = getattr(passlib_bcrypt, "_BcryptBackend", None)

if _bcrypt_backend_cls is not None:
    load_backend = _bcrypt_backend_cls.__dict__.get("_load_backend_mixin")
    if isinstance(load_backend, classmethod):
        _original_load_backend = load_backend.__func__

        def _safe_load_backend(mixin_cls, name, dryrun):
            try:
                return _original_load_backend(mixin_cls, name, dryrun)
            except ValueError as exc:
                if "password cannot be longer than 72 bytes" in str(exc):
                    return mixin_cls._finalize_backend_mixin(name, dryrun)
                raise

        _bcrypt_backend_cls._load_backend_mixin = classmethod(_safe_load_backend)

    calc_checksum = _bcrypt_backend_cls.__dict__.get("_calc_checksum")
    if calc_checksum is not None:
        def _safe_calc_checksum(self, secret):
            try:
                return calc_checksum(self, secret)
            except ValueError as exc:
                if "password cannot be longer than 72 bytes" in str(exc):
                    secret = secret[:72]
                    return calc_checksum(self, secret)
                raise

        _bcrypt_backend_cls._calc_checksum = _safe_calc_checksum

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
