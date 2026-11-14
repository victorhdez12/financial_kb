"""HTTP helpers with a *total* download deadline.

`requests`' `timeout` only bounds each socket read (and the connect), so a server that
trickles bytes slowly can keep a download alive forever (wb_wdi hung 21 min in the weekly
run of 14-nov-2026). These helpers stream the body and abort once the whole transfer
exceeds `total` seconds. They are drop-in replacements for `requests.get/post` and
`Session.get`: same arguments (headers, params, data, allow_redirects...), same Response
(with `.content`/`.text`/`.json()` already loaded).
"""
from __future__ import annotations

import time

import requests


def default_total(timeout) -> float:
    """Default total deadline: 4x the per-read timeout, at least 5 minutes."""
    if isinstance(timeout, (tuple, list)):
        timeout = max(t for t in timeout if t is not None) if any(t is not None for t in timeout) else None
    if timeout is None:
        return 300.0
    return max(4 * float(timeout), 300.0)


def _iter_available(r: requests.Response, chunk_size: int):
    """Yield the (decoded) body in pieces *as they arrive*.

    `iter_content(n)` blocks until n bytes or EOF, so a body trickled slower than n bytes
    per check would dodge the deadline; urllib3's `read1` returns whatever is available.
    urllib3 errors are mapped to the same requests exceptions `iter_content` raises."""
    raw = r.raw
    if not hasattr(raw, "read1"):
        yield from r.iter_content(chunk_size=chunk_size)
        return
    from urllib3.exceptions import DecodeError, ProtocolError, ReadTimeoutError, SSLError
    while True:
        try:
            chunk = raw.read1(chunk_size, decode_content=True)
        except ProtocolError as e:
            raise requests.exceptions.ChunkedEncodingError(e) from e
        except DecodeError as e:
            raise requests.exceptions.ContentDecodingError(e) from e
        except ReadTimeoutError as e:
            raise requests.exceptions.ConnectionError(e) from e
        except SSLError as e:
            raise requests.exceptions.SSLError(e) from e
        if not chunk:
            return
        yield chunk


def request(method: str, url: str, *, session: requests.Session | None = None,
            total: float | None = None, timeout=60, chunk_size: int = 65536,
            **kw) -> requests.Response:
    """`requests.request` whose whole download must finish within `total` seconds.

    Raises `requests.Timeout` (a `RequestException`) when the deadline is exceeded."""
    total = total if total is not None else default_total(timeout)
    deadline = time.monotonic() + total
    caller = session.request if session is not None else requests.request
    kw.pop("stream", None)
    r = caller(method, url, timeout=timeout, stream=True, **kw)
    try:
        buf = bytearray()
        for chunk in _iter_available(r, chunk_size):
            buf.extend(chunk)
            if time.monotonic() > deadline:
                raise requests.Timeout(f"total download time > {total:.0f}s for {url}")
        r._content = bytes(buf)
        r._content_consumed = True
    finally:
        r.close()
    return r


def get(url: str, **kw) -> requests.Response:
    return request("GET", url, **kw)


def post(url: str, **kw) -> requests.Response:
    return request("POST", url, **kw)


def get_with_deadline(url: str, headers: dict, timeout: float, total: float) -> requests.Response:
    """GET whose whole download must finish within `total` seconds (follows redirects)."""
    return request("GET", url, headers=headers, timeout=timeout, total=total, allow_redirects=True)
