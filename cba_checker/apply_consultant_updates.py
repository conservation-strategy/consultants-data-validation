"""One-off updates: Gabriela weed/NTFP, Pedro RSC1 NaN fix."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def update_gabriela() -> None:
    path = ROOT / (
        "(Gabriela_Mangrove) restoration_Mangrove_Seed_Dispersal_"
        "2026-06-16-00-05-14._GABRIELA SARMIENTOxlsx.xlsx"
    )
    xl = pd.ExcelFile(path)
    sheets = {name: pd.read_excel(path, sheet_name=name) for name in xl.sheet_names}
    df = sheets["Data"]

    # Weed/invasive species: 300 USD total, frequency 1 (was 15 × 300 = 4,500)
    df["Weed_Occur"] = 1

    ntfp_mask = df["Method_ID"] == "seedling_planting_ntfp"
    row = df.loc[ntfp_mask].iloc[0]
    daily_rate = float(row.get("HiredLaborCost_USD_day") or 50)
    harvest_annual = daily_rate * 20

    df.loc[ntfp_mask, "NTFP_Species"] = "Mangrove oyster (Crassostrea rhizophorae)"
    df.loc[ntfp_mask, "NTFP_Price_USD_kg"] = 8
    df.loc[ntfp_mask, "Impl_USD"] = float(row["Impl_USD"]) + 1390

    df.loc[ntfp_mask, "ProdSeg1_From_yr"] = 2
    df.loc[ntfp_mask, "ProdSeg1_To_yr"] = 20
    df.loc[ntfp_mask, "ProdSeg1_kg_ha_yr"] = 5000

    for i in range(2, 6):
        for col in (f"ProdSeg{i}_From_yr", f"ProdSeg{i}_To_yr", f"ProdSeg{i}_kg_ha_yr"):
            df.loc[ntfp_mask, col] = pd.NA
        for col in (f"RevSeg{i}_From_yr", f"RevSeg{i}_To_yr", f"RevSeg{i}_Annual_USD"):
            df.loc[ntfp_mask, col] = pd.NA

    df.loc[ntfp_mask, "Maint_Harvest_Seg1_From_yr"] = 2
    df.loc[ntfp_mask, "Maint_Harvest_Seg1_To_yr"] = 20
    df.loc[ntfp_mask, "Maint_Harvest_Seg1_Annual_USD"] = harvest_annual

    for i in range(2, 11):
        for col in (
            f"Maint_Harvest_Seg{i}_From_yr",
            f"Maint_Harvest_Seg{i}_To_yr",
            f"Maint_Harvest_Seg{i}_Annual_USD",
        ):
            if col in df.columns:
                df.loc[ntfp_mask, col] = pd.NA

    sheets["Data"] = df
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    print(f"Updated Gabriela: weed occur=1, oyster NTFP, harvest={harvest_annual}/yr")


def fix_pedro_rsc1_nan() -> None:
    path = ROOT / (
        "(Pedro_Cerrado) RSC1_restoration_Savanna_or_Dry_Forest_"
        "Full_Seedling_Plantation_NTFP_(agroforestry)_2026-07-02-01-04-34.xlsx"
    )
    fixed = path.read_bytes()
    with zipfile.ZipFile(path, "r") as zin:
        out_buf = __import__("io").BytesIO()
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                    text = data.decode("utf-8")
                    text = re.sub(r"<v>NaN</v>", "", text)
                    data = text.encode("utf-8")
                zout.writestr(item, data)
        fixed = out_buf.getvalue()
    path.write_bytes(fixed)
    # verify
    df = pd.read_excel(path, sheet_name="Data")
    valid = df[df["Impl_USD"].fillna(0) > 0]
    print(f"Fixed Pedro RSC1: {len(valid)} valid model rows")


if __name__ == "__main__":
    update_gabriela()
    fix_pedro_rsc1_nan()
