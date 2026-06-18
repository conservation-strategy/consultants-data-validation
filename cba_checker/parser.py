"""Parse consultant / literature-review spreadsheets into a RestorationModel dict."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

METHOD_KEYS = [
    "anr_30",
    "anr_30_ntfp",
    "seed_dispersal",
    "seed_dispersal_ntfp",
    "seedling_planting",
    "seedling_planting_ntfp",
]

METHOD_LABEL_TO_ID = {
    "anr/50% enrichment": "anr_30",
    "anr/50% enrichment (ntfp)": "anr_30",
    "anr/50% enrichment (with ntfp)": "anr_30_ntfp",
    "seed dispersal": "seed_dispersal",
    "seed dispersal (ntfp)": "seed_dispersal_ntfp",
    "seed dispersal (with ntfp)": "seed_dispersal_ntfp",
    "full seedling plantation": "seedling_planting",
    "full seedling plantation (ntfp)": "seedling_planting_ntfp",
    "full seedling plantation ntfp (agroforestry)": "seedling_planting_ntfp",
}

MAINT_ACTIVITIES = [
    ("RegInd", "Maintenance of regenerating individuals"),
    ("MaintNTFP", "Maintenance of NTFP species"),
    ("Harvest", "Harvest"),
    ("TechAssist", "Technical assistance"),
    ("Monitoring", "Monitoring General Maintenance Activities"),
]

MAINT_SLOTS = 10
PROD_REV_SLOTS = 5


def _num(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _str(val: Any) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    return str(val).strip()


def normalize_method_id(raw: Any) -> str | None:
    s = _str(raw)
    if not s:
        return None
    if s in METHOD_KEYS:
        return s
    # literature review sometimes uses display labels
    mapped = METHOD_LABEL_TO_ID.get(s.lower())
    if mapped:
        return mapped
    return s if s in METHOD_KEYS else None


def _parse_maintenance_segments(row: pd.Series) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for prefix, label in MAINT_ACTIVITIES:
        for i in range(1, MAINT_SLOTS + 1):
            y_from = _num(row.get(f"Maint_{prefix}_Seg{i}_From_yr"))
            y_to = _num(row.get(f"Maint_{prefix}_Seg{i}_To_yr"))
            cost = _num(row.get(f"Maint_{prefix}_Seg{i}_Annual_USD"))
            if y_from is None and y_to is None and cost is None:
                continue
            segments.append(
                {
                    "id": f"{prefix}_{i}",
                    "label": label,
                    "yearFrom": int(y_from) if y_from is not None else 2,
                    "yearTo": int(y_to) if y_to is not None else 20,
                    "cost": cost or 0,
                }
            )
    return segments


def _parse_prod_segments(row: pd.Series) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for i in range(1, PROD_REV_SLOTS + 1):
        y_from = _num(row.get(f"ProdSeg{i}_From_yr"))
        y_to = _num(row.get(f"ProdSeg{i}_To_yr"))
        prod = _num(row.get(f"ProdSeg{i}_kg_ha_yr"))
        if y_from is None and y_to is None and prod is None:
            continue
        segments.append(
            {
                "id": f"prod_{i}",
                "label": f"Productivity segment {i}",
                "yearFrom": int(y_from) if y_from is not None else 2,
                "yearTo": int(y_to) if y_to is not None else 20,
                "productivity": prod or 0,
            }
        )
    return segments


def _parse_rev_segments(row: pd.Series) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for i in range(1, PROD_REV_SLOTS + 1):
        y_from = _num(row.get(f"RevSeg{i}_From_yr"))
        y_to = _num(row.get(f"RevSeg{i}_To_yr"))
        rev = _num(row.get(f"RevSeg{i}_Annual_USD"))
        if y_from is None and y_to is None and rev is None:
            continue
        segments.append(
            {
                "id": f"rev_{i}",
                "label": f"Revenue segment {i}",
                "yearFrom": int(y_from) if y_from is not None else 2,
                "yearTo": int(y_to) if y_to is not None else 20,
                "revenue": rev or 0,
            }
        )
    return segments


def _method_entry_from_row(row: pd.Series, method_id: str) -> dict[str, Any]:
    is_ntfp = method_id.endswith("_ntfp")
    prod_segs = _parse_prod_segments(row) if is_ntfp else []
    rev_segs = _parse_rev_segments(row) if is_ntfp else []

    ntfp_data_mode = "production"
    if rev_segs and not prod_segs:
        ntfp_data_mode = "revenue"
    elif prod_segs:
        ntfp_data_mode = "production"

    entry: dict[str, Any] = {
        "implementationCost": _num(row.get("Impl_USD")) or 0,
        "implementationDistribution": {
            "labor": _num(row.get("Impl_Labor_%")) or 0,
            "materials": _num(row.get("Impl_Mater_%")) or 0,
            "machinery": _num(row.get("Impl_Mach_%")) or 0,
        },
        "maintenanceCost": 0,
        "maintenanceDistribution": {
            "labor": _num(row.get("Maint_Labor_%")) or 0,
            "materials": _num(row.get("Maint_Mater_%")) or 0,
            "machinery": _num(row.get("Maint_Mach_%")) or 0,
        },
        "maintenanceSegments": _parse_maintenance_segments(row),
    }

    if is_ntfp:
        entry.update(
            {
                "ntfpSpecies": _str(row.get("NTFP_Species")),
                "ntfpPrice": _num(row.get("NTFP_Price_USD_kg")) or 0,
                "ntfpDataMode": ntfp_data_mode,
                "ntfpProductivitySegments": prod_segs,
                "ntfpRevenueSegments": rev_segs,
            }
        )

    return entry


def _shared_context_from_row(row: pd.Series) -> dict[str, Any]:
    return {
        "fireRisk": {
            "cost": _num(row.get("Fire_UnitCost_USD_km")) or 0,
            "occurrences": _num(row.get("Fire_Occur")) or 0,
            "firebreakArea": _num(row.get("Fire_FirebreakArea_ha")) or 0,
            "distribution": {
                "labor": _num(row.get("Fire_Labor_%")) or 0,
                "materials": _num(row.get("Fire_Mater_%")) or 0,
                "machinery": _num(row.get("Fire_Mach_%")) or 0,
            },
        },
        "grazingPressure": {
            "cost": _num(row.get("Fence_UnitCost_USD_km")) or 0,
            "occurrences": _num(row.get("Fence_Area_ha")) or 0,
            "distribution": {
                "labor": _num(row.get("Fence_Labor_%")) or 0,
                "materials": _num(row.get("Fence_Mater_%")) or 0,
                "machinery": _num(row.get("Fence_Mach_%")) or 0,
            },
        },
        "invasiveSpeciesPressure": {
            "cost": _num(row.get("Weed_UnitCost")) or 0,
            "occurrences": _num(row.get("Weed_Occur")) or 0,
            "distribution": {
                "labor": _num(row.get("Weed_Labor_%")) or 0,
                "materials": _num(row.get("Weed_Mater_%")) or 0,
                "machinery": _num(row.get("Weed_Mach_%")) or 0,
            },
        },
        "pestControl": {
            "cost": _num(row.get("Pest_UnitCost")) or 0,
            "occurrences": _num(row.get("Pest_Occur")) or 0,
            "distribution": {
                "labor": _num(row.get("Pest_Labor_%")) or 0,
                "materials": _num(row.get("Pest_Mater_%")) or 0,
                "machinery": _num(row.get("Pest_Mach_%")) or 0,
            },
        },
    }


def _shared_labor_from_row(row: pd.Series) -> dict[str, Any]:
    return {
        "implementation": {
            "hiredLabor": _num(row.get("Impl_Hired_%")) or 0,
            "familyLabor": _num(row.get("Impl_Family_%")) or 0,
        },
        "maintenance": {
            "hiredLabor": _num(row.get("Maint_Hired_%")) or 0,
            "familyLabor": _num(row.get("Maint_Family_%")) or 0,
        },
        "hiredLaborCostPerDay": _num(row.get("HiredLaborCost_USD_day")) or 0,
        "machineryUnitCostPerHour": _num(row.get("MachineryUnitCost_USD_hr")) or 0,
        "landLeaseCostPerHaPerYear": _num(row.get("LandLease_USD_ha_yr")) or 0,
        "genderDistribution": {
            "male": _num(row.get("Gender_Male_%")) or 0,
            "female": _num(row.get("Gender_Female_%")) or 0,
            "other": _num(row.get("Gender_Other_%")) or 0,
        },
    }


def row_to_model(row: pd.Series) -> dict[str, Any]:
    """Convert one Data-sheet row into a partial RestorationModel for one method."""
    method_id = normalize_method_id(row.get("Method_ID")) or normalize_method_id(row.get("Method"))
    if not method_id:
        raise ValueError("Method_ID missing or unrecognized")

    method_costs = {mk: _method_entry_from_row(row, mk) if mk == method_id else _empty_method_entry(mk) for mk in METHOD_KEYS}
    method_costs[method_id] = _method_entry_from_row(row, method_id)

    return {
        "respondentName": _str(row.get("Respondent")),
        "userName": _str(row.get("User")),
        "dataCollectionDate": _str(row.get("Date")),
        "gpsCoordinates": _str(row.get("GPS")),
        "ecosystem": _str(row.get("Ecosystem")),
        "country": _str(row.get("Country")),
        "city": _str(row.get("City")),
        "timeHorizon": 20,
        "methodType": method_id,
        "enrichmentIntensity": 50,
        "methodCosts": method_costs,
        "contextVariables": _shared_context_from_row(row),
        "laborBreakdown": _shared_labor_from_row(row),
        "disabledMethods": [mk for mk in METHOD_KEYS if mk != method_id],
    }


def _empty_method_entry(method_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "implementationCost": 0,
        "implementationDistribution": {"labor": 0, "materials": 0, "machinery": 0},
        "maintenanceCost": 0,
        "maintenanceDistribution": {"labor": 0, "materials": 0, "machinery": 0},
        "maintenanceSegments": [],
    }
    if method_id.endswith("_ntfp"):
        entry.update(
            {
                "ntfpSpecies": "",
                "ntfpPrice": 0,
                "ntfpDataMode": "production",
                "ntfpProductivitySegments": [],
                "ntfpRevenueSegments": [],
            }
        )
    return entry


def parse_workbook(df: pd.DataFrame, source_file: str) -> list[dict[str, Any]]:
    """Parse all method rows from a Data sheet into model records."""
    records: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        method_id = normalize_method_id(row.get("Method_ID")) or normalize_method_id(row.get("Method"))
        impl = _num(row.get("Impl_USD"))
        if not method_id or impl is None or impl <= 0:
            continue
        model = row_to_model(row)
        records.append(
            {
                "id": f"{source_file}::{idx}::{method_id}",
                "source_file": source_file,
                "source_type": "literature" if "literature" in source_file.lower() else "consultant",
                "row_index": int(idx),
                "method_id": method_id,
                "method_label": _str(row.get("Method")) or method_id,
                "country": _str(row.get("Country")),
                "ecosystem": _str(row.get("Ecosystem")),
                "respondent": _str(row.get("Respondent")),
                "model": model,
            }
        )
    return records
