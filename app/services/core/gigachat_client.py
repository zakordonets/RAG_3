"""
GigaChat client wrapper around the official SDK.

- берет client_id/client_secret из CONFIG, кодирует в base64 как credentials;
- переиспользует один синхронный клиент с потокобезопасной инициализацией;
- предоставляет метод chat_completion в терминах Chat Completions.
"""
from __future__ import annotations

import base64
import threading
from typing import Dict, List, Optional

from loguru import logger

from app.config import CONFIG

try:
    from gigachat import GigaChatSyncClient
    from gigachat.exceptions import GigaChatException, AuthenticationError, ResponseError
    from gigachat.models import Chat, Messages, MessagesRole
except Exception as exc:  # pragma: no cover - импортируем только при установленном SDK
    raise ImportError("gigachat SDK is required. Install with `pip install gigachat`.") from exc


class GigachatClient:
    """Потокобезопасный фасад над официальным SDK."""

    def __init__(self) -> None:
        self._client: Optional[GigaChatSyncClient] = None
        self._lock = threading.Lock()

    def _build_credentials(self) -> str:
        client_id = CONFIG.gigachat_client_id.strip()
        client_secret = CONFIG.gigachat_client_secret.strip()
        if not client_id or not client_secret:
            raise RuntimeError("GigaChat credentials are not configured")
        raw = f"{client_id}:{client_secret}"
        return base64.b64encode(raw.encode("utf-8")).decode("utf-8")

    def _get_client(self) -> GigaChatSyncClient:
        if self._client:
            return self._client
        with self._lock:
            if self._client:
                return self._client

            credentials = self._build_credentials()
            self._client = GigaChatSyncClient(
                credentials=credentials,
                scope=CONFIG.gigachat_scope,
                model=CONFIG.gigachat_model,
                timeout=float(CONFIG.gigachat_timeout),
                base_url=CONFIG.gigachat_api_url,
                auth_url=CONFIG.gigachat_auth_url,
                verify_ssl_certs=CONFIG.gigachat_verify_ssl,
                ca_bundle_file=CONFIG.gigachat_ca_bundle or None,
            )
            logger.info(
                "GigaChat client initialized (model={}, scope={}, base_url={})",
                CONFIG.gigachat_model,
                CONFIG.gigachat_scope,
                CONFIG.gigachat_api_url,
            )
            return self._client

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Messages]:
        converted: List[Messages] = []
        for msg in messages:
            role = str(msg.get("role") or "user").lower()
            try:
                role_enum = MessagesRole(role)
            except ValueError:
                role_enum = MessagesRole.USER
            converted.append(Messages(role=role_enum, content=str(msg.get("content") or "")))
        return converted

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        client = self._get_client()
        chat = Chat(
            messages=self._convert_messages(messages),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            model=CONFIG.gigachat_model or None,
        )
        try:
            response = client.chat(chat)
        except (AuthenticationError, ResponseError) as exc:
            logger.warning("GigaChat auth/response error: %s", exc)
            # сбрасываем токен и пробуем один повтор
            try:
                client._reset_token()  # type: ignore[attr-defined]
            except Exception:
                pass
            response = client.chat(chat)
        except GigaChatException as exc:
            logger.error("GigaChat failed: %s", exc)
            raise

        if not response.choices:
            raise RuntimeError("GigaChat returned empty choices")

        message = response.choices[0].message
        return message.content


_gigachat_client: Optional[GigachatClient] = None


def get_gigachat_client() -> GigachatClient:
    global _gigachat_client
    if _gigachat_client is None:
        _gigachat_client = GigachatClient()
    return _gigachat_client
