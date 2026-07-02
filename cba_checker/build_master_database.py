"""Build a single master-database .xlsx consolidating every model.

Scans the data folder for all source spreadsheets (consultant questionnaires
and the literature review), keeps the valid model rows (recognized method with
a positive implementation cost), and concatenates them into one workbook that
follows the same fixed 231-column "Data" layout the questionnaire exports. A
"Metadata" sheet is copied from a canonical source file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from loader import _detect_sheet_name, _is_excluded_file
from parser import _num, normalize_method_id

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent
CANONICAL_FILE = DATA_DIR / (
    "(Hadji_Arid) restoration_Arid_or_Semi-Arid_Zones_Full_Seedling_Plantation_"
    "NTFP_(agroforestry)_2026-06-29-16-56-10.xlsx"
)
OUT_PATH = DATA_DIR / "Consultants Data Validation - Master Database.xlsx"


def _valid_rows(df: pd.DataFrame) -> list[pd.Series]:
    rows: list[pd.Series] = []
    for _, row in df.iterrows():
        method_id = normalize_method_id(row.get("Method_ID")) or normalize_method_id(
            row.get("Method")
        )
        impl = _num(row.get("Impl_USD"))
        if method_id and impl is not None and impl > 0:
            rows.append(row)
    return rows


def build_master() -> int:
    canon_xl = pd.ExcelFile(CANONICAL_FILE)
    canon_data = pd.read_excel(CANONICAL_FILE, sheet_name=_detect_sheet_name(canon_xl))
    columns = list(canon_data.columns)

    try:
        meta = pd.read_excel(CANONICAL_FILE, sheet_name="Metadata", header=None)
    except Exception:
        meta = None

    collected: list[pd.Series] = []
    for path in sorted(DATA_DIR.glob("*.xlsx")):
        if _is_excluded_file(path.name) or path.resolve() == OUT_PATH.resolve():
            continue
        try:
            xl = pd.ExcelFile(path)
            df = pd.read_excel(path, sheet_name=_detect_sheet_name(xl))
        except Exception as exc:
            print(f"  skip {path.name}: {exc}")
            continue
        for row in _valid_rows(df):
            collected.append(row.reindex(columns))

    master = pd.DataFrame(collected, columns=columns)

    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        master.to_excel(writer, sheet_name="Data", index=False)
        if meta is not None:
            meta.to_excel(writer, sheet_name="Metadata", index=False, header=False)

    print(f"Master database: {len(master)} rows, {len(columns)} columns -> {OUT_PATH.name}")
    return len(master)


if __name__ == "__main__":
    build_master()
