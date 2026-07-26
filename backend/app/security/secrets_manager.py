"""SecretsManager — encrypt/decrypt sensitive config fields using Fernet.

Uses PBKDF2 from an ENCRYPTION_KEY environment variable to derive a Fernet key.
DISABLE_ENCRYPTION=1 puts the manager into read-only migration mode:
  - encrypt_dict() raises RuntimeError (no new writes allowed)
  - decrypt_dict() passes through plaintext fields (for reading old configs)
"""

import base64
import hashlib
import logging
import os
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

SENSITIVE_FIELDS = frozenset({
    "api_key",
    "discord_token",
    "ocr_api_key",
    "embedding_api_key",
    "rerank_api_key",
    "api_secret_key",
})

_FERNET_PREFIX = "gAAAAA"


def _derive_key(encryption_key: str) -> bytes:
    """Derive a url-safe-base64 Fernet key from *encryption_key* via PBKDF2-HMAC-SHA256."""
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        encryption_key.encode("utf-8"),
        b"discord-llm-chatbot-salt",
        100000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(derived)


def _is_encrypted(value: str) -> bool:
    """Return True if *value* looks like a Fernet ciphertext (starts with gAAAAA)."""
    return value.startswith(_FERNET_PREFIX)


class SecretsManager:
    """Manages Fernet-based encryption/decryption of sensitive config fields.

    Parameters
    ----------
    encryption_key : str, optional
        Master key from which the Fernet key is derived.  Falls back to the
        ``ENCRYPTION_KEY`` environment variable when not provided.
    """

    def __init__(self, encryption_key: str = ""):
        self._disabled = os.environ.get("DISABLE_ENCRYPTION", "0") == "1"

        if not encryption_key:
            encryption_key = os.environ.get("ENCRYPTION_KEY", "")

        # Always derive the key if provided — even in DISABLE_ENCRYPTION mode
        # so that already-encrypted fields can still be decrypted during migration.
        self._fernet = Fernet(_derive_key(encryption_key)) if encryption_key else None

        if self._disabled:
            logger.warning(
                "DISABLE_ENCRYPTION=1 — running in read-only migration mode. "
                "Config writes are blocked."
            )
            return

        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable is required. "
                "Set DISABLE_ENCRYPTION=1 to read plaintext configs for migration."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a new dict with sensitive string fields encrypted.

        Raises ``RuntimeError`` in ``DISABLE_ENCRYPTION=1`` mode.
        """
        if self._disabled:
            raise RuntimeError(
                "Cannot write config when DISABLE_ENCRYPTION=1. "
                "Unset DISABLE_ENCRYPTION to enable writes."
            )
        result = dict(data)
        for field in SENSITIVE_FIELDS:
            value = result.get(field)
            if isinstance(value, str) and value:
                result[field] = self._encrypt(value)
        return result

    def decrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a new dict with encrypted string fields decrypted.

        In ``DISABLE_ENCRYPTION=1`` mode, plaintext values (non-encrypted) are
        passed through as-is so that old plaintext configs can be read.
        """
        result = dict(data)
        for field in SENSITIVE_FIELDS:
            value = result.get(field)
            if not isinstance(value, str) or not value:
                continue

            if self._disabled:
                # Migration mode: decrypt if it looks encrypted, else pass
                if _is_encrypted(value) and self._fernet is not None:
                    try:
                        result[field] = self._decrypt(value)
                    except InvalidToken:
                        logger.warning(
                            "Field '%s' looks encrypted but token is invalid — leaving as-is", field
                        )
                # Plaintext values stay as-is
                continue

            # Normal mode: always decrypt (raises on non-encrypted values)
            if _is_encrypted(value):
                try:
                    result[field] = self._decrypt(value)
                except InvalidToken:
                    raise ValueError(
                        f"Field '{field}' contains an invalid Fernet token. "
                        "The encryption key may have changed or the data is corrupted."
                    ) from None
            else:
                raise ValueError(
                    f"Field '{field}' is stored in plaintext but encryption is enabled. "
                    "Set DISABLE_ENCRYPTION=1 to read plaintext configs for migration."
                )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
