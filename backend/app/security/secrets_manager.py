"""SecretsManager — encrypt/decrypt sensitive config fields using Fernet.

Uses PBKDF2 from an ENCRYPTION_KEY environment variable to derive a Fernet key.
DISABLE_ENCRYPTION=1 puts the manager into read-only migration mode:
  - encrypt_dict() raises RuntimeError (no new writes allowed)
  - decrypt_dict() passes through plaintext fields (for reading old configs)

v2 (MEDIUM-5): 嵌套敏感字段（quota_alert.webhook_url）支持。
- encrypt_dict 幂等：顶层 + 嵌套均已加密的值跳过（避免二次加密）
- decrypt_dict 顶层语义严格（与 v1 一致）；嵌套字段采用宽容策略：
  正常模式明文 → warning + 透传 + 记录 last_migrated_paths（下次保存自动写回加密）；
  迁移模式明文 → info + 记录 last_migrated_paths；密文解密失败（InvalidToken）→ warning + 原样保留。
- 输入 dict 永不被修改（deepcopy 纯函数语义）。
"""

import base64
import copy
import hashlib
import logging
import os
from typing import Any, Dict, List

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

# 嵌套敏感字段：顶层容器键 → 内层敏感字段集合 (v2 MEDIUM-5)
NESTED_SENSITIVE_FIELDS = {"quota_alert": frozenset({"webhook_url"})}

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
        self._last_migrated: List[str] = []

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

    @property
    def write_enabled(self) -> bool:
        """是否允许写盘（非 DISABLE_ENCRYPTION 迁移模式）.

        Returns:
            迁移模式下为 False，其余为 True
        """
        return not self._disabled

    @property
    def last_migrated_paths(self) -> List[str]:
        """最近一次 decrypt_dict() 发现的明文嵌套字段路径（点分路径）.

        Returns:
            路径列表副本，如 ["quota_alert.webhook_url"]
        """
        return list(self._last_migrated)

    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a new dict with sensitive string fields encrypted (幂等).

        顶层 SENSITIVE_FIELDS 与嵌套 NESTED_SENSITIVE_FIELDS 中的字符串字段
        均被加密；已是密文的值跳过（幂等）。输入 dict 不会被修改（deepcopy）。

        Raises:
            RuntimeError: 在 ``DISABLE_ENCRYPTION=1`` 模式下（只读迁移）
        """
        if self._disabled:
            raise RuntimeError(
                "Cannot write config when DISABLE_ENCRYPTION=1. "
                "Unset DISABLE_ENCRYPTION to enable writes."
            )
        result = copy.deepcopy(data)
        for field in SENSITIVE_FIELDS:
            value = result.get(field)
            if isinstance(value, str) and value and not _is_encrypted(value):
                result[field] = self._encrypt(value)
        for container_key, nested_fields in NESTED_SENSITIVE_FIELDS.items():
            container = result.get(container_key)
            if not isinstance(container, dict):
                continue
            for field in nested_fields:
                value = container.get(field)
                if isinstance(value, str) and value and not _is_encrypted(value):
                    container[field] = self._encrypt(value)
        return result

    def decrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a new dict with encrypted string fields decrypted.

        顶层字段语义严格（与 v1 一致）: 正常模式遇明文抛 ValueError；
        ``DISABLE_ENCRYPTION=1`` 迁移模式透传明文。

        嵌套敏感字段（NESTED_SENSITIVE_FIELDS）采用 v2 宽容策略:
        - 正常模式明文 → warning + 透传 + 记录 last_migrated_paths（下次保存写回加密）
        - 迁移模式明文 → info + 记录 last_migrated_paths
        - 密文解密失败（InvalidToken）→ warning + 原样保留

        输入 dict 不会被修改（deepcopy）。
        """
        self._last_migrated = []
        result = copy.deepcopy(data)

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

        for container_key, nested_fields in NESTED_SENSITIVE_FIELDS.items():
            container = result.get(container_key)
            if not isinstance(container, dict):
                continue
            for field in nested_fields:
                value = container.get(field)
                if not isinstance(value, str) or not value:
                    continue
                path = f"{container_key}.{field}"
                if _is_encrypted(value):
                    if self._fernet is None:
                        logger.warning(
                            "Field '%s' looks encrypted but no key available — leaving as-is",
                            path,
                        )
                        continue
                    try:
                        container[field] = self._decrypt(value)
                    except InvalidToken:
                        logger.warning(
                            "Field '%s' looks encrypted but token is invalid — leaving as-is",
                            path,
                        )
                    continue
                # 明文（未加密）→ 宽容透传
                if self._disabled:
                    logger.info(
                        "Field '%s' is plaintext (migration mode) — passed through", path
                    )
                else:
                    logger.warning(
                        "Field '%s' is stored in plaintext but encryption is enabled — "
                        "passing through (will be encrypted on next save)", path
                    )
                self._last_migrated.append(path)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
