from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.errors import AppError


def validate_target_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise AppError(1002, "url parse failed") from exc

    if parsed.scheme not in {"http", "https"}:
        raise AppError(1002, "only http/https urls are allowed")
    if not parsed.netloc:
        raise AppError(1002, "url host is required")

    hostname = parsed.hostname
    if not hostname:
        raise AppError(1002, "url host is required")
    if hostname.lower() == "localhost":
        raise AppError(1002, "localhost is not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
        _assert_public_ip(ip)
    except ValueError:
        _assert_hostname(hostname)

    return url


def assert_public_network_target(url: str) -> str:
    parsed = urlparse(validate_target_url(url))
    hostname = parsed.hostname
    if not hostname:
        raise AppError(1002, "url host is required")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise AppError(1002, "url host could not be resolved") from exc

    if not infos:
        raise AppError(1002, "url host could not be resolved")

    for info in infos:
        raw_ip = info[4][0]
        _assert_public_ip(ipaddress.ip_address(raw_ip))

    return url


def _assert_hostname(hostname: str) -> None:
    # Avoid environment-dependent DNS resolution here. Validation blocks unsafe
    # literal IPs and obviously local hostnames; real fetches can fail later.
    if "." not in hostname:
        raise AppError(1002, "url host is invalid")
    labels = hostname.split(".")
    if any(not label or len(label) > 63 for label in labels):
        raise AppError(1002, "url host is invalid")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    for label in labels:
        lowered = label.lower()
        if lowered.startswith("-") or lowered.endswith("-"):
            raise AppError(1002, "url host is invalid")
        if any(char not in allowed for char in lowered):
            raise AppError(1002, "url host is invalid")


def _assert_public_ip(ip: ipaddress._BaseAddress) -> None:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        raise AppError(1002, "private or unsafe network targets are forbidden")
