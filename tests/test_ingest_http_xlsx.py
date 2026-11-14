"""Mechanical hardening of ingest: total HTTP deadline (_http) and tolerant .xlsx reader (_xlsx)."""
from __future__ import annotations

import http.server
import io
import threading
import time
import zipfile

import pandas as pd
import pytest
import requests

from src.ingest import _http
from src.ingest._xlsx import excel_file_tolerant, read_excel_tolerant, xlsx_source


# ---------------------------------------------------------------- HTTP deadline
class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path == "/slow":
            # 100 bytes, one every 0.2 s: each read is fast (per-read timeout never fires)
            # but the whole body would take 20 s.
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            try:
                for _ in range(100):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.2)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            body = b"hello " * 1000
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = b"echo:" + self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.daemon_threads = True
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_deadline_cuts_slow_trickle(server):
    t0 = time.monotonic()
    with pytest.raises(requests.Timeout, match="total download time"):
        _http.get(server + "/slow", timeout=5, total=1.0)
    assert time.monotonic() - t0 < 4


def test_get_with_deadline_cuts_slow_trickle(server):
    from src.ingest._extlong_common import _get_with_deadline as g1
    from src.ingest.texts_common import _get_with_deadline as g2
    assert g1 is g2 is _http.get_with_deadline
    with pytest.raises(requests.Timeout):
        _http.get_with_deadline(server + "/slow", {"User-Agent": "t"}, 5, 1.0)


def test_fast_response_is_complete(server):
    r = _http.get(server + "/fast", timeout=5)
    assert r.status_code == 200 and r.content == b"hello " * 1000 and r.text.startswith("hello")
    with requests.Session() as s:
        r2 = _http.get(server + "/fast", session=s, timeout=5)
    assert r2.content == r.content
    p = _http.post(server + "/", data={"a": "1"}, timeout=5)
    assert p.content == b"echo:a=1"


def test_default_total():
    assert _http.default_total(60) == 300
    assert _http.default_total(600) == 2400
    assert _http.default_total((10, 120)) == 480
    assert _http.default_total(None) == 300


# ---------------------------------------------------------------- tolerant xlsx
def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="DATA", index=False)
        df.iloc[:2].to_excel(w, sheet_name="Other", index=False)
    return buf.getvalue()


def _break_core(xb: bytes) -> bytes:
    """Rewrite docProps/core.xml dates as 'YYYY-MM-DDT 9:58:23' (unpadded hour)."""
    import re
    zin = zipfile.ZipFile(io.BytesIO(xb))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == "docProps/core.xml":
                txt = data.decode("utf-8")
                txt2 = re.sub(r">(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}Z?<", r">\1T 9:58:23<", txt)
                assert txt2 != txt
                data = txt2.encode("utf-8")
            zout.writestr(it, data)
    return out.getvalue()


@pytest.fixture()
def frames():
    return pd.DataFrame({"Date": pd.date_range("2000-01-01", periods=5, freq="MS"),
                         "x": [1.0, 2.5, None, 4.0, 5.0], "s": list("abcde")})


def test_broken_core_fails_plain_but_tolerant_matches(tmp_path, frames):
    good = tmp_path / "good.xlsx"
    bad = tmp_path / "bad.xlsx"
    good.write_bytes(_xlsx_bytes(frames))
    bad.write_bytes(_break_core(good.read_bytes()))
    raw_before = bad.read_bytes()

    with pytest.raises(Exception):
        pd.read_excel(bad, sheet_name="DATA")

    ref = pd.read_excel(good, sheet_name="DATA")
    pd.testing.assert_frame_equal(read_excel_tolerant(bad, sheet_name="DATA"), ref)
    pd.testing.assert_frame_equal(read_excel_tolerant(bad.read_bytes(), sheet_name="DATA"), ref)
    pd.testing.assert_frame_equal(read_excel_tolerant(io.BytesIO(bad.read_bytes()), sheet_name="DATA"), ref)
    allb = read_excel_tolerant(bad, sheet_name=None, header=None)
    allg = pd.read_excel(good, sheet_name=None, header=None)
    assert allb.keys() == allg.keys()
    for k in allg:
        pd.testing.assert_frame_equal(allb[k], allg[k])
    assert excel_file_tolerant(bad).sheet_names == ["DATA", "Other"]
    assert bad.read_bytes() == raw_before  # raw on disk untouched


def test_tolerant_is_transparent_on_good_files(tmp_path, frames):
    good = tmp_path / "good.xlsx"
    good.write_bytes(_xlsx_bytes(frames))
    assert xlsx_source(good) is good  # no rewrite when nothing to fix
    pd.testing.assert_frame_equal(read_excel_tolerant(good, sheet_name="DATA", header=None),
                                  pd.read_excel(good, sheet_name="DATA", header=None))
    csv = tmp_path / "a.csv"
    csv.write_text("a,b\n1,2\n")
    assert xlsx_source(csv) is csv  # non-zip inputs pass through untouched
