import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import SplitResult, urlsplit, urlunsplit


class UnsafeUrlError(ValueError):
    """A URL is not safe to send to an external extraction service."""


Resolver = Callable[..., Iterable[tuple]]


def _is_public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # Clash and similar system proxies intentionally resolve public hostnames into
    # RFC 2544's 198.18.0.0/15 fake-IP range. Literal IP inputs are still rejected
    # below; accepting this range only for a resolved hostname keeps local/TUN
    # development compatible without allowing RFC1918, loopback or link-local hosts.
    proxy_fake_ip = ipaddress.ip_network("198.18.0.0/15")
    return address.is_global or address in proxy_fake_ip


def _normalized(parts: SplitResult) -> str:
    host = (parts.hostname or "").lower()
    port = parts.port
    default_port = (parts.scheme == "https" and port == 443) or (
        parts.scheme == "http" and port == 80
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]" if port is None or default_port else f"[{host}]:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def validate_public_url(
    value: str, *, resolver: Resolver = socket.getaddrinfo
) -> str:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrlError("网址格式不正确") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise UnsafeUrlError("只支持公开的 HTTP(S) 网页")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("网址不能包含账号或密码")
    hostname = parts.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeUrlError("不允许访问本机或内网网址")
    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            addresses = resolver(
                hostname,
                port or (443 if parts.scheme.lower() == "https" else 80),
                0,
                socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise UnsafeUrlError("网址域名无法解析") from exc
        resolved = {item[4][0] for item in addresses}
        if not resolved or any(not _is_public_ip(address) for address in resolved):
            raise UnsafeUrlError("不允许访问本机或内网网址")
    else:
        if not literal_address.is_global:
            raise UnsafeUrlError("不允许访问本机或内网网址")
    return _normalized(parts)
