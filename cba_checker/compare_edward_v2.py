# -*- coding: utf-8 -*-
"""Compare Edward v1 vs Edward v2 workbooks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from cba import METHOD_LABELS, compute_method_cba
from loader import MODELS_DIR, _detect_sheet_name
from parser import parse_workbook

PAIRS = [
    (
        "Arid",
        "(Edward_Arid) restoration_Arid_or_Semi-Arid_Zones_Full_Seedling_Plantation_NTFP_(agroforestry)_2026-10-07-02-17-52.xlsx",
        "(Edward_v2) Arid Ecosystem 2026-10-22-01-52-49.xlsx",
    ),
    (
        "Mountaine",
        "(Edward_Mountaine) restoration_Mountaine_Forest_Full_Seedling_Plantation_NTFP_(agroforestry)_2026-10-07-03-04-47.xlsx",
        "(Edward_v2)Uzbekistan Mountain Ecoystem 2026-10-22-03-44-22.xlsx",
    ),
]

COMPARE_COLS = [
    "Country",
    "City",
    "GPS",
    "Ecosystem",
    "Impl_USD",
    "NTFP_Species",
    "NTFP_Price_USD_kg",
    "Fire_UnitCost_USD_km",
    "Fire_Occur",
    "Fence_UnitCost_USD_km",
    "Fence_Area_ha",
    "Weed_UnitCost",
    "Weed_Occur",
    "Pest_UnitCost",
    "Pest_Occur",
    "HiredLaborCost_USD_day",
    "MachineryUnitCost_USD_hr",
    "LandLease_USD_ha_yr",
]


def load_df(name: str) -> pd.DataFrame:
    path = MODELS_DIR / name
    xl = pd.ExcelFile(path)
    sheet = _detect_sheet_name(xl)
    return pd.read_excel(path, sheet_name=sheet)


def row_by_method(df: pd.DataFrame) -> dict:
    out = {}
    for _, row in df.iterrows():
        mid = row.get("Method_ID")
        if pd.isna(mid):
            continue
        if pd.isna(row.get("Impl_USD")) or float(row["Impl_USD"]) <= 0:
            continue
        out[str(mid)] = row
    return out


def seg_text(row: pd.Series, prefix: str, value_col: str) -> str:
    parts = []
    for i in range(1, 6):
        s = row.get(f"{prefix}{i}_From_yr")
        e = row.get(f"{prefix}{i}_To_yr")
        v = row.get(f"{prefix}{i}_{value_col}")
        if pd.isna(s) and pd.isna(v):
            continue
        parts.append(f"Y{s:g}-{e:g}={v}")
    return " | ".join(parts) if parts else "(empty)"


def maint_text(row: pd.Series) -> str:
    parts = []
    for family in (
        "Maint_RegInd",
        "Maint_TechAssist",
        "Maint_MaintNTFP",
        "Maint_Harvest",
        "Maint_Monitoring",
    ):
        for i in range(1, 11):
            s = row.get(f"{family}_Seg{i}_From_yr")
            e = row.get(f"{family}_Seg{i}_To_yr")
            v = row.get(f"{family}_Seg{i}_Annual_USD")
            if pd.isna(s) and pd.isna(v):
                continue
            if pd.isna(v) or float(v) == 0:
                continue
            parts.append(f"{family}{i}:Y{s:g}-{e:g}={v}")
    return " | ".join(parts) if parts else "(empty)"


def kpis_for(path_name: str) -> dict:
    path = MODELS_DIR / path_name
    records = parse_workbook(pd.read_excel(path, sheet_name=_detect_sheet_name(pd.ExcelFile(path))), path_name)
    out = {}
    for rec in records:
        model = rec["model"]
        mid = rec["method_id"]
        method = model["methodCosts"][mid]
        result = compute_method_cba(mid, method, model)
        fence = (model.get("contextVariables") or {}).get("grazingPressure") or {}
        weed = (model.get("contextVariables") or {}).get("invasiveSpeciesPressure") or {}
        fire = (model.get("contextVariables") or {}).get("fireRisk") or {}
        pest = (model.get("contextVariables") or {}).get("pestControl") or {}
        fence_tot = (fence.get("cost") or 0) * (fence.get("occurrences") or 0)
        weed_tot = (weed.get("cost") or 0) * (weed.get("occurrences") or 0)
        fire_tot = (fire.get("cost") or 0) * (fire.get("occurrences") or 0)
        pest_tot = (pest.get("cost") or 0) * (pest.get("occurrences") or 0)
        out[mid] = {
            "impl": result.cash_flows[0].impl_cost if result.cash_flows else 0,
            "maint": sum(cf.maint_cost for cf in result.cash_flows),
            "constraints": sum(cf.constraint_cost for cf in result.cash_flows),
            "cost20": result.total_costs_20yr,
            "ntfp": sum(cf.ntfp_revenue for cf in result.cash_flows),
            "npv": next((n["npv"] for n in result.npv_by_rate if abs(n["rate"] - 0.06) < 1e-9), None),
            "irr": result.irr,
            "bcr": result.bcr,
            "fence": fence_tot,
            "weed": weed_tot,
            "fire": fire_tot,
            "pest": pest_tot,
        }
    return out


def compare_pair(label: str, old_name: str, new_name: str) -> None:
    print("=" * 78)
    print(f"{label}: {old_name}")
    print(f"  vs  {new_name}")
    old = row_by_method(load_df(old_name))
    new = row_by_method(load_df(new_name))
    methods = sorted(set(old) | set(new), key=lambda m: list(METHOD_LABELS).index(m) if m in METHOD_LABELS else 99)

    # Meta from first rows
    o0 = next(iter(old.values()))
    n0 = next(iter(new.values()))
    for c in ("Country", "City", "GPS", "Ecosystem", "User", "Respondent"):
        ov = o0.get(c)
        nv = n0.get(c)
        if str(ov) != str(nv):
            print(f"  META {c}: '{ov}' -> '{nv}'")

    old_k = kpis_for(old_name)
    new_k = kpis_for(new_name)

    for mid in methods:
        print(f"\n--- {mid} ({METHOD_LABELS.get(mid, mid)}) ---")
        if mid not in old:
            print("  NEW method (absent in v1)")
            continue
        if mid not in new:
            print("  REMOVED in v2")
            continue
        o, n = old[mid], new[mid]
        for c in COMPARE_COLS:
            if c not in o.index and c not in n.index:
                continue
            ov, nv = o.get(c), n.get(c)
            if pd.isna(ov) and pd.isna(nv):
                continue
            if (pd.isna(ov) and not pd.isna(nv)) or (not pd.isna(ov) and pd.isna(nv)) or str(ov) != str(nv):
                print(f"  {c}: {ov} -> {nv}")

        o_rev = seg_text(o, "RevSeg", "Annual_USD")
        n_rev = seg_text(n, "RevSeg", "Annual_USD")
        if o_rev != n_rev:
            print(f"  RevSeg: {o_rev}")
            print(f"       -> {n_rev}")
        o_prod = seg_text(o, "ProdSeg", "kg_ha_yr")
        n_prod = seg_text(n, "ProdSeg", "kg_ha_yr")
        if o_prod != n_prod:
            print(f"  ProdSeg: {o_prod}")
            print(f"        -> {n_prod}")
        o_m = maint_text(o)
        n_m = maint_text(n)
        if o_m != n_m:
            print(f"  Maint: {o_m}")
            print(f"      -> {n_m}")

        ok, nk = old_k[mid], new_k[mid]
        print(
            f"  KPI cost20 {ok['cost20']:.0f}->{nk['cost20']:.0f} | "
            f"ntfp {ok['ntfp']:.0f}->{nk['ntfp']:.0f} | "
            f"npv {ok['npv']:.0f}->{nk['npv']:.0f} | "
            f"bcr {ok['bcr']:.2f}->{nk['bcr']:.2f} | "
            f"constraints {ok['constraints']:.0f}->{nk['constraints']:.0f}"
        )


if __name__ == "__main__":
    for label, old_name, new_name in PAIRS:
        compare_pair(label, old_name, new_name)
