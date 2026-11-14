"""Tolerant .xlsx reader.

Some publishers (Philadelphia Fed since ~oct-2026) write malformed dates in
docProps/core.xml, e.g. "2026-10-30T 9:58:23" (unpadded hour), which openpyxl rejects
before reading any cell. `read_excel_tolerant` fixes that metadata in memory only (the
raw file on disk stays byte-identical) and otherwise behaves exactly like
`pd.read_excel`. Non-zip inputs (.xls, anything else) go straight to `pd.read_excel`.
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

_CORE = "docProps/core.xml"
_BAD_HOUR = re.compile(r"T ?(\d):")


def _is_zip(src) -> bool:
    try:
        ok = zipfile.is_zipfile(src)
    except Exception:  # noqa: BLE001
        return False
    if hasattr(src, "seek"):
        src.seek(0)
    return ok


def xlsx_source(src):
    """Return `src` unchanged, or an in-memory copy with docProps/core.xml dates fixed
    when they are malformed. Accepts a path, bytes or a binary file-like object; non-zip
    inputs (.xls...) are returned as is. Usable with pd.read_excel, pd.ExcelFile or
    openpyxl.load_workbook."""
    if isinstance(src, (bytes, bytearray)):
        src = io.BytesIO(src)
    if not _is_zip(src):
        return src
    with zipfile.ZipFile(src) as zin:
        if _CORE not in zin.namelist():
            fixed = txt = None
        else:
            txt = zin.read(_CORE).decode("utf-8")
            fixed = _BAD_HOUR.sub(r"T0\1:", txt)
        if fixed == txt:
            if hasattr(src, "seek"):
                src.seek(0)
            return src
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = fixed.encode("utf-8") if item.filename == _CORE else zin.read(item.filename)
                zout.writestr(item, data)
    buf.seek(0)
    return buf


def read_excel_tolerant(src, **kw) -> pd.DataFrame | dict:
    """`pd.read_excel(src, **kw)` that survives malformed docProps dates in .xlsx files."""
    return pd.read_excel(xlsx_source(src), **kw)


def excel_file_tolerant(src, **kw) -> pd.ExcelFile:
    """`pd.ExcelFile(src, **kw)` that survives malformed docProps dates in .xlsx files."""
    return pd.ExcelFile(xlsx_source(src), **kw)
