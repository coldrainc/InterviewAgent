from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    status: int
    data: Any
    raw: Any
    content_type: str


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
    ) -> ApiResponse:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        body = None
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return self._response(response.status, response.headers, response.read())
        except urllib.error.HTTPError as exc:
            return self._response(exc.code, exc.headers, exc.read())

    @staticmethod
    def _response(status: int, headers: Any, body: bytes) -> ApiResponse:
        content_type = headers.get("Content-Type", "")
        text = body.decode("utf-8", errors="replace")
        if "json" in content_type:
            raw = json.loads(text or "null")
            data = raw.get("data") if isinstance(raw, dict) and raw.get("code") == 0 else raw
        else:
            raw = text
            data = text
        return ApiResponse(status=status, data=data, raw=raw, content_type=content_type)


def expect(response: ApiResponse, status: int, label: str) -> Any:
    if response.status != status:
        detail = response.raw
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("detail") or detail.get("error")
        raise AssertionError(f"{label}: expected HTTP {status}, got {response.status}: {detail}")
    print(f"PASS  {label}")
    return response.data
