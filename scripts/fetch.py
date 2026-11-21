"""HTTP fetching with retries, size limits and an optional build cache."""

from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = (
    "fast4g-geo-files/1.0 "
    "(+https://github.com/BranchSeeker/fast4g.ru-geo-files)"
)
MAX_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class FetchResult:
    url: str
    data: bytes
    sha256: str
    fetched_at: str

    @property
    def text(self) -> str:
        return self.data.decode("utf-8-sig", "replace")


def _download(url: str, timeout: int) -> FetchResult:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError(f"response is larger than {MAX_BYTES} bytes")
            chunks.append(chunk)
        raw = b"".join(chunks)
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
    return FetchResult(
        url=url,
        data=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def fetch(
    url: str,
    *,
    timeout: int = 60,
    retries: int = 3,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> FetchResult:
    """Fetch ``url`` with retries.

    If ``cache_dir`` is set and ``refresh`` is false, a previously cached body
    is used.  This keeps local rebuilds fast; CI always downloads fresh data.
    """
    cache_path: Path | None = None
    if cache_dir is not None:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        cache_path = cache_dir / f"{key}.bin"

    if cache_path is not None and cache_path.exists() and not refresh:
        raw = cache_path.read_bytes()
        return FetchResult(
            url=url,
            data=raw,
            sha256=hashlib.sha256(raw).hexdigest(),
            fetched_at=datetime.fromtimestamp(
                cache_path.stat().st_mtime, timezone.utc
            ).isoformat(timespec="seconds"),
        )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            result = _download(url, timeout)
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(result.data)
            return result
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8))

    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def fetch_json(url: str, **kwargs) -> object:
    result = fetch(url, **kwargs)
    return json.loads(result.text)
