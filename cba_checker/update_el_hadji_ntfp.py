"""One-time data fix for El Hadji Beye (Mauritania).

The consultant re-submitted a revised questionnaire that dropped the biochar
component. The three non-NTFP methods are unchanged, so only the three NTFP
methods are updated here (matching the revised "Date Palm Tree" export). This
applies those revisions in place to the existing source file.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "restoration_Mauritania_El_Hadji_Beye_2026-06-15.xlsx"

NEW_RESPONDENT = "Southern Mauritania Afforestation - Date Palm Tree"
NEW_SPECIES = "Date palm Tree (Phoenix dactylifera)"
NTFP_METHODS = ("anr_30_ntfp", "seed_dispersal_ntfp", "seedling_planting_ntfp")


def main() -> None:
    data = pd.read_excel(SOURCE, sheet_name="Data")
    try:
        meta = pd.read_excel(SOURCE, sheet_name="Metadata", header=None)
    except Exception:
        meta = None

    def setv(method_id: str, column: str, value) -> None:
        data.loc[data["Method_ID"] == method_id, column] = value

    # Revised project name (biochar dropped) on every row.
    data["Respondent"] = NEW_RESPONDENT

    # Shared NTFP revisions.
    for mid in NTFP_METHODS:
        setv(mid, "NTFP_Species", NEW_SPECIES)
        setv(mid, "Maint_RegInd_Seg1_From_yr", np.nan)
        setv(mid, "Maint_RegInd_Seg1_To_yr", np.nan)
        setv(mid, "Maint_RegInd_Seg1_Annual_USD", np.nan)
        setv(mid, "RevSeg1_Annual_USD", 0)
        setv(mid, "RevSeg3_Annual_USD", 23779)

    # ANR/50% Enrichment (NTFP)
    setv("anr_30_ntfp", "Impl_USD", 5678)
    setv("anr_30_ntfp", "RevSeg2_From_yr", 6)
    setv("anr_30_ntfp", "RevSeg2_Annual_USD", 11657)

    # Seed Dispersal (NTFP)
    setv("seed_dispersal_ntfp", "Impl_USD", 6987)
    setv("seed_dispersal_ntfp", "RevSeg2_Annual_USD", 11985)

    # Full Seedling Plantation (NTFP)
    setv("seedling_planting_ntfp", "Impl_USD", 8775)
    setv("seedling_planting_ntfp", "Impl_Labor_%", 40)
    setv("seedling_planting_ntfp", "Impl_Mater_%", 47)
    setv("seedling_planting_ntfp", "Impl_Mach_%", 13)
    setv("seedling_planting_ntfp", "RevSeg2_Annual_USD", 13845)

    with pd.ExcelWriter(SOURCE, engine="openpyxl") as writer:
        data.to_excel(writer, sheet_name="Data", index=False)
        if meta is not None:
            meta.to_excel(writer, sheet_name="Metadata", index=False, header=False)

    print(f"Updated El Hadji NTFP rows -> {SOURCE.name}")


if __name__ == "__main__":
    main()
