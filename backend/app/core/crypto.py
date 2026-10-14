"""Крипто-хелперы поверх проверенных библиотек (cryptography): Fernet для секретов в БД и HMAC для псевдонимизации."""

import hashlib
import hmac

from cryptography.fernet import Fernet

from app.core.config import get_settings


def fernet_encrypt(plaintext: str) -> str:
    """Шифрует значение ключом FERNET_KEY (TOTP-секрет, e-mail requester); в БД хранится только токен."""
    return Fernet(get_settings().fernet_key.encode()).encrypt(plaintext.encode()).decode()


def fernet_decrypt(token: str) -> str:
    """Расшифровывает значение, зашифрованное fernet_encrypt."""
    return Fernet(get_settings().fernet_key.encode()).decrypt(token.encode()).decode()


def hmac_hex(value: str) -> str:
    """HMAC-SHA256 значения ключом HMAC_KEY (e-mail для дедупа, IP): исходное значение восстановить нельзя."""
    return hmac.new(get_settings().hmac_key.encode(), value.encode(), hashlib.sha256).hexdigest()
