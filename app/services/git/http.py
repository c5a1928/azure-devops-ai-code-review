from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class GitAPIError(RuntimeError):
    def __init__(self, status_code: int, url: str, message: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"Git API error {status_code} for {url}: {message}")


def request_json(
    *,
    method: str,
    url: str,
    token: str,
    auth_header: str = "Bearer",
    auth_prefix: str = "",
    body: dict | None = None,
    timeout: int = 60,
) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        if auth_header == "PRIVATE-TOKEN":
            req.add_header("PRIVATE-TOKEN", token)
        elif auth_header == "Basic":
            req.add_header("Authorization", f"Basic {token}")
        else:
            prefix = auth_prefix or "Bearer"
            req.add_header("Authorization", f"{prefix} {token}".strip())
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        message = exc.read().decode(errors="replace")
        raise GitAPIError(exc.code, url, message) from exc
    except urllib.error.URLError as exc:
        raise GitAPIError(0, url, str(exc.reason)) from exc


def request_text(
    *,
    method: str,
    url: str,
    token: str,
    auth_header: str = "Bearer",
    auth_prefix: str = "",
    body: dict | None = None,
    timeout: int = 60,
) -> str:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        if auth_header == "PRIVATE-TOKEN":
            req.add_header("PRIVATE-TOKEN", token)
        elif auth_header == "Basic":
            req.add_header("Authorization", f"Basic {token}")
        else:
            prefix = auth_prefix or "Bearer"
            req.add_header("Authorization", f"{prefix} {token}".strip())
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        message = exc.read().decode(errors="replace")
        raise GitAPIError(exc.code, url, message) from exc
    except urllib.error.URLError as exc:
        raise GitAPIError(0, url, str(exc.reason)) from exc
