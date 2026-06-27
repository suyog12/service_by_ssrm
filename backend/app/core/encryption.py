import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()


def _get_key() -> bytes:
    secret = os.getenv("ENCRYPTION_SECRET", "")
    if not secret:
        raise ValueError("ENCRYPTION_SECRET not set in environment")
    raw = bytes.fromhex(secret)
    return raw[:32]


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    try:
        key = _get_key()
        aesgcm = AESGCM(key)
        raw = base64.b64decode(ciphertext)
        nonce, ct = raw[:12], raw[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception:
        return "[encrypted]"