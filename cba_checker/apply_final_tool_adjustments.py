"""Apply final-tool adjustments to consultant source spreadsheets.

See FINAL_TOOL_ADJUSTMENTS.md for the rationale and before/after notes.
"""

from __future__ import annotations

import pandas as pd

from loader import MODELS_DIR, _detect_sheet_name

ROOT = MODELS_DIR

GABRIELA = (
    "(Gabriela_Mangrove) restoration_Mangrove_Seed_Dispersal_"
    "2026-06-16-00-05-14._GABRIELA SARMIENTOxlsx.xlsx"
)
MARCEL = (
    "(Marcel_Mangrove) Product 2_REVISION1_CSF_Validated Questionnaire "
    "Package_Vietnam_Mangrove_Marcel Pein.xlsx"
)
NISTIA = (
    "(Nistia_Mangrove) restoration_Mangrove_ANR_50%_Enrichment_"
    "2026-07-28-14-03-29.xlsx"
)
SAMMY = (
    "(Samuel_Mountaine) restoration_Mountaine_Forest_ANR_50%_Enrichment_"
    "2026-07-01-16-22-05.xlsx"
)

# Marcel NTFP density: revenues were built for 1667 NTFP individuals/ha;
# target density is 600 seedlings/ha. Costs unchanged.
MARCEL_DENSITY_FACTOR = 600 / 1667

# Sammy M3 Low (pessimistic) annual revenues USD/ha/yr from technical note.
SAMMY_M3_LOW = [
    (4, 4, 945),
    (5, 6, 1418),
    (8, 10, 1692),
    (16, 20, 2678),
]


def _load_sheets(path):
    xl = pd.ExcelFile(path)
    sheets = {name: pd.read_excel(path, sheet_name=name) for name in xl.sheet_names}
    data_name = _detect_sheet_name(xl)
    return sheets, data_name


def _save_sheets(path, sheets):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)


def adjust_gabriela() -> None:
    """Exclude seedling_planting_ntfp (oyster model) by zeroing Impl_USD."""
    path = ROOT / GABRIELA
    sheets, data_name = _load_sheets(path)
    df = sheets[data_name]
    mask = df["Method_ID"] == "seedling_planting_ntfp"
    before = float(df.loc[mask, "Impl_USD"].iloc[0])
    df.loc[mask, "Impl_USD"] = 0
    sheets[data_name] = df
    _save_sheets(path, sheets)
    print(f"Gabriela: seedling_planting_ntfp Impl {before} -> 0 (excluded)")


def adjust_marcel() -> None:
    """Set machinery to USD 9.63/hr; set NTFP productivity for 600/1667."""
    path = ROOT / MARCEL
    sheets, data_name = _load_sheets(path)
    df = sheets[data_name]
    valid = df["Impl_USD"].fillna(0) > 0

    old_mach = df.loc[valid, "MachineryUnitCost_USD_hr"].iloc[0]
    df.loc[valid, "MachineryUnitCost_USD_hr"] = 9.63

    ntfp = valid & df["Method_ID"].astype(str).str.endswith("_ntfp")
    scaled_cols = []
    for i in range(1, 6):
        col = f"ProdSeg{i}_kg_ha_yr"
        if col not in df.columns:
            continue
        before = df.loc[ntfp, col].tolist()
        # The original non-zero productivity was 15,000 kg/ha/yr.
        # Assign the scaled value directly so this script is idempotent.
        if i == 2:
            df.loc[ntfp, col] = 15000 * MARCEL_DENSITY_FACTOR
        after = df.loc[ntfp, col].tolist()
        if any(pd.notna(x) and float(x) != 0 for x in before):
            scaled_cols.append((col, before, after))

    sheets[data_name] = df
    _save_sheets(path, sheets)
    print(f"Marcel: MachineryUnitCost_USD_hr {old_mach} -> 9.63")
    for col, before, after in scaled_cols:
        print(f"Marcel: {col} {before} -> {after} (x{MARCEL_DENSITY_FACTOR:.6f})")


def adjust_nistia() -> None:
    """Drop Vietnam mangrove fence cost (~USD 56,998)."""
    path = ROOT / NISTIA
    sheets, data_name = _load_sheets(path)
    df = sheets[data_name]
    valid = df["Impl_USD"].fillna(0) > 0
    before_km = df.loc[valid, "Fence_UnitCost_USD_km"].iloc[0]
    before_ha = df.loc[valid, "Fence_Area_ha"].iloc[0]
    df.loc[valid, "Fence_UnitCost_USD_km"] = 0
    df.loc[valid, "Fence_Area_ha"] = 0
    sheets[data_name] = df
    _save_sheets(path, sheets)
    print(
        f"Nistia Vietnam: fence {before_km} USD/km x {before_ha} ha "
        f"(~{float(before_km) * float(before_ha):.1f}) -> 0"
    )


def adjust_sammy() -> None:
    """Replace seedling+NTFP revenues with the M3 Low (pessimistic) schedule."""
    path = ROOT / SAMMY
    sheets, data_name = _load_sheets(path)
    df = sheets[data_name]
    mask = df["Method_ID"] == "seedling_planting_ntfp"

    # Clear production mode inputs
    for i in range(1, 6):
        for col in (
            f"ProdSeg{i}_From_yr",
            f"ProdSeg{i}_To_yr",
            f"ProdSeg{i}_kg_ha_yr",
            f"RevSeg{i}_From_yr",
            f"RevSeg{i}_To_yr",
            f"RevSeg{i}_Annual_USD",
        ):
            if col in df.columns:
                df.loc[mask, col] = pd.NA

    # Price unused in revenue mode; keep species for labelling
    if "NTFP_Price_USD_kg" in df.columns:
        df.loc[mask, "NTFP_Price_USD_kg"] = 0

    for i, (y0, y1, annual) in enumerate(SAMMY_M3_LOW, start=1):
        df.loc[mask, f"RevSeg{i}_From_yr"] = y0
        df.loc[mask, f"RevSeg{i}_To_yr"] = y1
        df.loc[mask, f"RevSeg{i}_Annual_USD"] = annual

    sheets[data_name] = df
    _save_sheets(path, sheets)
    segs = ", ".join(
        f"Y{a}-{b}={c:g}" for a, b, c in SAMMY_M3_LOW
    )
    print(f"Sammy seedling_planting_ntfp: revenue mode Low-M3 -> {segs}")


if __name__ == "__main__":
    adjust_gabriela()
    adjust_marcel()
    adjust_nistia()
    adjust_sammy()
    print("Done.")
