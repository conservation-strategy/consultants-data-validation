"""Load consultant spreadsheets and literature review data from disk."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from geo import get_continent
from parser import parse_workbook

LITERATURE_KEYWORDS = ("literature", "literatura", "review")


def _detect_sheet_name(xl: pd.ExcelFile) -> str:
    for name in xl.sheet_names:
        if name.lower() == "data":
            return name
    return xl.sheet_names[0]


def _is_literature_file(filename: str) -> bool:
    lower = filename.lower()
    return any(kw in lower for kw in LITERATURE_KEYWORDS)


def load_xlsx_file(path: Path) -> list[dict]:
    xl = pd.ExcelFile(path)
    sheet = _detect_sheet_name(xl)
    df = pd.read_excel(path, sheet_name=sheet)
    source_type = "literature" if _is_literature_file(path.name) else "consultant"
    records = parse_workbook(df, path.name)
    for rec in records:
        rec["source_type"] = source_type
        rec["source_path"] = str(path)
        rec["continent"] = get_continent(rec.get("country", ""))
        rec["label"] = _format_label(rec)
    return records


def _format_label(rec: dict) -> str:
    parts = [
        rec.get("country") or "?",
        rec.get("ecosystem") or "?",
        rec.get("method_label") or rec.get("method_id"),
    ]
    if rec.get("source_type") == "consultant":
        user = (rec.get("model") or {}).get("userName") or ""
        name = user.strip() or rec.get("respondent") or rec.get("source_file", "")[:30]
        parts.insert(0, name)
    else:
        parts.insert(0, (rec.get("respondent") or "Lit.")[:40])
    return " · ".join(parts)


def load_all_from_directory(data_dir: Path) -> tuple[list[dict], list[dict]]:
    """Return (consultant_records, literature_records)."""
    consultant: list[dict] = []
    literature: list[dict] = []

    if not data_dir.exists():
        return consultant, literature

    for path in sorted(data_dir.glob("*.xlsx")):
        try:
            records = load_xlsx_file(path)
        except Exception as exc:
            print(f"Warning: failed to load {path.name}: {exc}")
            continue
        if _is_literature_file(path.name):
            literature.extend(records)
        else:
            consultant.extend(records)

    return consultant, literature


def filter_comparables(
    literature: list[dict],
    *,
    method_id: str,
    continent: str,
    exclude_id: str | None = None,
) -> list[dict]:
    """Literature entries with same method and continent."""
    out = []
    for rec in literature:
        if rec["method_id"] != method_id:
            continue
        if continent != "Unknown" and rec.get("continent") != continent:
            continue
        if exclude_id and rec["id"] == exclude_id:
            continue
        out.append(rec)
    return out


def group_consultant_files(consultant: list[dict]) -> dict[str, list[dict]]:
    """Group records by source file."""
    groups: dict[str, list[dict]] = {}
    for rec in consultant:
        key = rec["source_file"]
        groups.setdefault(key, []).append(rec)
    return groups
