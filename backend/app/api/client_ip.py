"""HMAC от peer-IP: единственная форма, в которой IP попадает в Redis, аудит и логи (SR-25, SR-28)."""

from fastapi import Request

from app.core.crypto import hmac_hex


def client_ip_hash(request: Request) -> str:
    """Доверяет peer-IP из соединения, а не присланному клиентом X-Forwarded-For."""
    peer = request.client.host if request.client else "unknown"
    return hmac_hex(peer)
