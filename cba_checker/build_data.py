"""Build JSON dataset for the HTML dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cba import DEFAULT_DISCOUNT_RATE, METHOD_LABELS, cba_summary_dict, compute_method_cba
from loader import load_all_from_directory

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent
OUT_PATH = ROOT / "web" / "data.json"


CONSULTANT_NAME_ALIASES: dict[str, str] = {
    "javier gutierrez bardales": "Javier Gutierrez",
}


def normalize_consultant_name(name: str) -> str:
    """Normalize person names for consistent grouping and display."""
    name = " ".join((name or "").split())
    if not name:
        return name

    alias = CONSULTANT_NAME_ALIASES.get(name.lower())
    if alias:
        return alias

    # e.g. SAMUEL KIMENYI -> Samuel Kimenyi
    if name.isupper():
        return name.title()

    return name


def _consultant_display_name(record: dict[str, Any], model: dict[str, Any]) -> str:
    """Prefer the person who filled the form (User) over project title (Respondent)."""
    user = normalize_consultant_name((model.get("userName") or "").strip())
    respondent = (record.get("respondent") or "").strip()
    if record.get("source_type") == "consultant" and user:
        return user
    return normalize_consultant_name(respondent) or user


def _cash_flow_row(cf) -> dict[str, float | int]:
    return {
        "year": cf.project_year,
        "implCost": round(cf.impl_cost, 2),
        "maintCost": round(cf.maint_cost, 2),
        "constraintCost": round(cf.constraint_cost, 2),
        "totalCost": round(cf.total_cost, 2),
        "ntfpRevenue": round(cf.ntfp_revenue, 2),
        "totalBenefit": round(cf.total_benefit, 2),
        "netFlow": round(cf.net_flow, 2),
    }


def _cost_benefit_detail(model: dict[str, Any], method_id: str, result) -> dict[str, Any]:
    method = model["methodCosts"][method_id]
    ctx = model.get("contextVariables") or {}

    fire = ctx.get("fireRisk") or {}
    fence = ctx.get("grazingPressure") or {}
    weed = ctx.get("invasiveSpeciesPressure") or {}
    pest = ctx.get("pestControl") or {}

    fire_total = (fire.get("cost") or 0) * (fire.get("occurrences") or 0)
    fence_total = (fence.get("cost") or 0) * (fence.get("occurrences") or 0)
    weed_total = (weed.get("cost") or 0) * (weed.get("occurrences") or 0)
    pest_total = (pest.get("cost") or 0) * (pest.get("occurrences") or 0)

    impl_y1 = result.cash_flows[0].impl_cost if result.cash_flows else 0
    maint_total = sum(cf.maint_cost for cf in result.cash_flows)
    constraint_total = sum(cf.constraint_cost for cf in result.cash_flows)
    ntfp_total = sum(cf.ntfp_revenue for cf in result.cash_flows)

    maint_segments = method.get("maintenanceSegments") or []
    segment_summary = [
        {
            "label": s.get("label", ""),
            "yearFrom": s.get("yearFrom"),
            "yearTo": s.get("yearTo"),
            "annualCost": s.get("cost", 0),
        }
        for s in maint_segments
    ]

    return {
        "implementationY1": round(impl_y1, 2),
        "maintenanceTotal": round(maint_total, 2),
        "constraints": {
            "firebreak": round(fire_total, 2),
            "fencing": round(fence_total, 2),
            "weedControl": round(weed_total, 2),
            "pestControl": round(pest_total, 2),
            "total": round(constraint_total, 2),
        },
        "maintenanceSegments": segment_summary,
        "benefits": {
            "ntfpRevenueTotal": round(ntfp_total, 2),
            "total": round(ntfp_total, 2),
        },
        "costTotal20yr": round(result.total_costs_20yr, 2),
        "benefitTotal20yr": round(result.total_benefits_20yr, 2),
    }


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    model = record["model"]
    method_id = record["method_id"]
    method = model["methodCosts"][method_id]
    result = compute_method_cba(method_id, method, model)
    summary = cba_summary_dict(result)

    raw_user = (model.get("userName") or "").strip()
    user_name = (
        normalize_consultant_name(raw_user)
        if record.get("source_type") == "consultant"
        else raw_user
    )
    consultant_name = _consultant_display_name(record, model)

    return {
        "id": record["id"],
        "label": record.get("label", ""),
        "sourceType": record.get("source_type", ""),
        "sourceFile": record.get("source_file", ""),
        "country": record.get("country", ""),
        "continent": record.get("continent", ""),
        "ecosystem": record.get("ecosystem", ""),
        "respondent": record.get("respondent", ""),
        "userName": user_name,
        "consultantName": consultant_name,
        "methodId": method_id,
        "methodLabel": record.get("method_label") or METHOD_LABELS.get(method_id, method_id),
        "kpis": {
            "npv": summary["npv_usd_ha"],
            "irr": summary["irr_pct"],
            "bcr": summary["bcr"],
            "paybackYear": summary["payback_year"],
            "totalCost20yr": summary["total_cost_20yr"],
            "totalBenefit20yr": summary["total_benefit_20yr"],
            "implCostY1": summary["impl_cost_y1"],
            "maintenanceTotal": round(
                sum(cf.maint_cost for cf in result.cash_flows), 2
            ),
            "ntfpRevenueTotal": round(
                sum(cf.ntfp_revenue for cf in result.cash_flows), 2
            ),
        },
        "npvByRate": [
            {"rate": n["rate"], "npv": round(n["npv"], 2)} for n in result.npv_by_rate
        ],
        "cashFlows": [_cash_flow_row(cf) for cf in result.cash_flows],
        "detail": _cost_benefit_detail(model, method_id, result),
    }


def build(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or DATA_DIR
    consultant, literature = load_all_from_directory(data_dir)

    all_records = consultant + literature
    enriched = [enrich_record(r) for r in all_records]

    methods = sorted({r["methodId"] for r in enriched}, key=lambda m: METHOD_LABELS.get(m, m))

    return {
        "meta": {
            "discountRate": DEFAULT_DISCOUNT_RATE,
            "discountRates": [0.03, 0.06, 0.08, 0.10, 0.12],
            "timeHorizon": 20,
            "generatedFrom": str(data_dir),
            "consultantCount": len(consultant),
            "literatureCount": len(literature),
        },
        "methodLabels": METHOD_LABELS,
        "methods": methods,
        "records": enriched,
    }


def main() -> None:
    payload = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['records'])} records -> {OUT_PATH}")


if __name__ == "__main__":
    main()
