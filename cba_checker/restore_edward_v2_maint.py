# -*- coding: utf-8 -*-
"""Restore Edward v1 maintenance segments onto Edward v2 workbooks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from loader import MODELS_DIR, _detect_sheet_name

ROOT = MODELS_DIR
ARCHIVE = ROOT / "_archive"

PAIRS = [
    (
        ARCHIVE
        / (
            "(Edward_Arid) restoration_Arid_or_Semi-Arid_Zones_Full_Seedling_"
            "Plantation_NTFP_(agroforestry)_2026-10-07-02-17-52.xlsx"
        ),
        ROOT / "(Edward_v2) Arid Ecosystem 2026-10-22-01-52-49.xlsx",
    ),
    (
        ARCHIVE
        / (
            "(Edward_Mountaine) restoration_Mountaine_Forest_Full_Seedling_"
            "Plantation_NTFP_(agroforestry)_2026-10-07-03-04-47.xlsx"
        ),
        ROOT / "(Edward_v2)Uzbekistan Mountain Ecoystem 2026-10-22-03-44-22.xlsx",
    ),
]


def restore(old_path: Path, new_path: Path) -> None:
    xl = pd.ExcelFile(new_path)
    sheets = {name: pd.read_excel(new_path, sheet_name=name) for name in xl.sheet_names}
    data_name = _detect_sheet_name(xl)
    new = sheets[data_name]
    old = pd.read_excel(old_path, sheet_name=_detect_sheet_name(pd.ExcelFile(old_path)))

    maint_cols = [c for c in old.columns if c.startswith("Maint_") and c in new.columns]
    old_by = {str(r["Method_ID"]): r for _, r in old.iterrows() if pd.notna(r.get("Method_ID"))}

    for idx, row in new.iterrows():
        mid = str(row.get("Method_ID"))
        if mid not in old_by:
            print(f"  skip missing old method {mid}")
            continue
        src = old_by[mid]
        for c in maint_cols:
            new.at[idx, c] = src.get(c)
        print(f"  restored maint for {mid}")

    sheets[data_name] = new
    with pd.ExcelWriter(new_path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    print(f"wrote {new_path.name}")


if __name__ == "__main__":
    for old_path, new_path in PAIRS:
        print(new_path.name)
        restore(old_path, new_path)
