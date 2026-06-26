"""Build El Hadji's revised NTFP-only source file (Date Palm Tree, no biochar).

The main Mauritania workbook keeps all 6 methods with the original biochar NTFP
scenario. This script writes a companion file with only the three revised NTFP
rows so the dashboard shows 9 El Hadji models total (3 non-NTFP + 3 biochar
NTFP + 3 revised NTFP).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
BIOCHAR_SOURCE = ROOT.parent / "restoration_Mauritania_El_Hadji_Beye_2026-06-15.xlsx"
NTFP_ONLY_OUT = (
    ROOT.parent
    / "restoration_Mauritania_El_Hadji_Beye_2026-06-15_Date_Palm_Tree_NTFP.xlsx"
)

NEW_RESPONDENT = "Southern Mauritania Afforestation - Date Palm Tree"
NEW_SPECIES = "Date palm Tree (Phoenix dactylifera)"
NTFP_METHODS = ("anr_30_ntfp", "seed_dispersal_ntfp", "seedling_planting_ntfp")


def _apply_revised_ntfp(data: pd.DataFrame) -> pd.DataFrame:
    def setv(method_id: str, column: str, value) -> None:
        data.loc[data["Method_ID"] == method_id, column] = value

    for mid in NTFP_METHODS:
        setv(mid, "Respondent", NEW_RESPONDENT)
        setv(mid, "NTFP_Species", NEW_SPECIES)
        setv(mid, "Maint_RegInd_Seg1_From_yr", np.nan)
        setv(mid, "Maint_RegInd_Seg1_To_yr", np.nan)
        setv(mid, "Maint_RegInd_Seg1_Annual_USD", np.nan)
        setv(mid, "RevSeg1_Annual_USD", 0)
        setv(mid, "RevSeg3_Annual_USD", 23779)

    setv("anr_30_ntfp", "Impl_USD", 5678)
    setv("anr_30_ntfp", "RevSeg2_From_yr", 6)
    setv("anr_30_ntfp", "RevSeg2_Annual_USD", 11657)

    setv("seed_dispersal_ntfp", "Impl_USD", 6987)
    setv("seed_dispersal_ntfp", "RevSeg2_Annual_USD", 11985)

    setv("seedling_planting_ntfp", "Impl_USD", 8775)
    setv("seedling_planting_ntfp", "Impl_Labor_%", 40)
    setv("seedling_planting_ntfp", "Impl_Mater_%", 47)
    setv("seedling_planting_ntfp", "Impl_Mach_%", 13)
    setv("seedling_planting_ntfp", "RevSeg2_Annual_USD", 13845)

    return data


def main() -> None:
    data = pd.read_excel(BIOCHAR_SOURCE, sheet_name="Data")
    try:
        meta = pd.read_excel(BIOCHAR_SOURCE, sheet_name="Metadata", header=None)
    except Exception:
        meta = None

    revised = _apply_revised_ntfp(data.copy())
    ntfp_only = revised[revised["Method_ID"].isin(NTFP_METHODS)].copy()

    with pd.ExcelWriter(NTFP_ONLY_OUT, engine="openpyxl") as writer:
        ntfp_only.to_excel(writer, sheet_name="Data", index=False)
        if meta is not None:
            meta.to_excel(writer, sheet_name="Metadata", index=False, header=False)

    print(f"Biochar workbook (6 methods): {BIOCHAR_SOURCE.name}")
    print(f"Revised NTFP-only workbook (3 rows): {NTFP_ONLY_OUT.name}")


if __name__ == "__main__":
    main()
