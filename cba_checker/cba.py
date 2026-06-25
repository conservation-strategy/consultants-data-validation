"""Cost-Benefit Analysis — ported from questionnaire-restoration-master/src/utils/cba.ts"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

DISCOUNT_RATES = [0.03, 0.06, 0.08, 0.10, 0.12]
DEFAULT_DISCOUNT_RATE = 0.06
CARBON_PRICE = 10
NTFP_LAG_YEARS = 4

METHOD_LABELS = {
    "anr_30": "ANR/50% Enrichment",
    "anr_30_ntfp": "ANR/50% Enrichment (NTFP)",
    "seed_dispersal": "Seed Dispersal",
    "seed_dispersal_ntfp": "Seed Dispersal (NTFP)",
    "seedling_planting": "Full Seedling Plantation",
    "seedling_planting_ntfp": "Full Seedling Plantation (NTFP)",
}

CARBON_SEQ = {
    "Tropical Forest": 12.0,
    "Subtropical Forest": 9.0,
    "Savanna or Dry Forest": 5.0,
    "Mangrove": 8.0,
    "Mountaine Forest": 7.0,
    "Arid or Semi-Arid Zones": 2.5,
}

METHOD_CARBON_MULT = {
    "anr_30": 0.65,
    "anr_30_ntfp": 0.65,
    "seed_dispersal": 0.80,
    "seed_dispersal_ntfp": 0.80,
    "seedling_planting": 1.0,
    "seedling_planting_ntfp": 1.0,
}


@dataclass
class YearCashFlow:
    year: int
    project_year: int
    impl_cost: float
    maint_cost: float
    constraint_cost: float
    total_cost: float
    ntfp_productivity: float
    ntfp_revenue: float
    carbon_benefit: float
    total_benefit: float
    net_flow: float
    cumulative_net: float
    discounted_net: float
    cumulative_discounted_net: float


@dataclass
class MethodCBA:
    method_id: str
    method_label: str
    is_ntfp: bool
    cash_flows: list[YearCashFlow] = field(default_factory=list)
    npv_by_rate: list[dict[str, float]] = field(default_factory=list)
    irr: float | None = None
    bcr: float = 0.0
    payback_year: int | None = None
    total_costs_20yr: float = 0.0
    total_benefits_20yr: float = 0.0
    carbon_seq_rate: float = 0.0
    cost_per_tco2: float | None = None


def get_carbon(ecosystem: str) -> float:
    if ecosystem in CARBON_SEQ:
        return CARBON_SEQ[ecosystem]
    eco_lower = ecosystem.lower()
    for key, val in CARBON_SEQ.items():
        if eco_lower in key.lower() or key.lower() in eco_lower:
            return val
    return 6.0


def _create_year_map(horizon: int) -> dict[int, float]:
    return {year: 0.0 for year in range(1, horizon + 1)}


def _add_segment_series(
    year_map: dict[int, float],
    segments: list[dict[str, Any]],
    get_value,
    start_year: int = 2,
) -> dict[int, float]:
    horizon = len(year_map)
    for segment in segments:
        y_from = max(start_year, int(segment.get("yearFrom", 2)))
        y_to = min(horizon, int(segment.get("yearTo", horizon)))
        for year in range(y_from, y_to + 1):
            year_map[year] += get_value(segment, year)
    return year_map


def _build_maintenance_cost_map(method: dict[str, Any], horizon: int) -> dict[int, float]:
    maintenance_by_year = _create_year_map(horizon)
    segments = method.get("maintenanceSegments") or []

    if segments:
        return _add_segment_series(
            maintenance_by_year,
            segments,
            lambda seg, _y: seg.get("cost", 0) or 0,
        )

    maint_total = method.get("maintenanceCost") or 0
    maint_years = max(0, horizon - 1)
    per_year = maint_total / maint_years if maint_years > 0 else 0
    for year in range(2, horizon + 1):
        maintenance_by_year[year] = per_year
    return maintenance_by_year


def _build_productivity_map(method: dict[str, Any], horizon: int) -> dict[int, float]:
    productivity_by_year = _create_year_map(horizon)
    segments = method.get("ntfpProductivitySegments") or []

    if segments:
        return _add_segment_series(
            productivity_by_year,
            segments,
            lambda seg, _y: seg.get("productivity", 0) or 0,
        )

    prod = method.get("ntfpProductivity") or 0
    for year in range(2, horizon + 1):
        productivity_by_year[year] = prod
    return productivity_by_year


def _build_revenue_map(method: dict[str, Any], horizon: int) -> dict[int, float]:
    revenue_by_year = _create_year_map(horizon)
    revenue_segments = method.get("ntfpRevenueSegments") or []

    if revenue_segments:
        return _add_segment_series(
            revenue_by_year,
            revenue_segments,
            lambda seg, _y: seg.get("revenue", 0) or 0,
        )

    prod_segments = method.get("ntfpProductivitySegments") or []
    price = method.get("ntfpPrice") or 0
    if prod_segments and price > 0:
        productivity_by_year = _build_productivity_map(method, horizon)
        for year in range(2, horizon + 1):
            revenue_by_year[year] = productivity_by_year[year] * price
        return revenue_by_year

    ntfp_revenue_total = method.get("ntfpRevenue") or 0
    ntfp_revenue_years = max(1, horizon - NTFP_LAG_YEARS)
    ntfp_per_year = ntfp_revenue_total / ntfp_revenue_years
    for year in range(NTFP_LAG_YEARS + 1, horizon + 1):
        revenue_by_year[year] = ntfp_per_year
    return revenue_by_year


def _build_cash_flows(
    method: dict[str, Any],
    method_id: str,
    data: dict[str, Any],
    discount_rate: float,
) -> list[YearCashFlow]:
    horizon = data.get("timeHorizon") or 20
    maint_years = horizon - 1
    flows: list[YearCashFlow] = []

    impl_cost_total = method.get("implementationCost") or 0
    maintenance_by_year = _build_maintenance_cost_map(method, horizon)

    ctx = data.get("contextVariables") or {}
    fire = ctx.get("fireRisk") or {}
    fence = ctx.get("grazingPressure") or {}
    weed = ctx.get("invasiveSpeciesPressure") or {}
    pest = ctx.get("pestControl") or {}

    fire_total = (fire.get("cost") or 0) * (fire.get("occurrences") or 0)
    fence_total = (fence.get("cost") or 0) * (fence.get("occurrences") or 0)
    weed_total = (weed.get("cost") or 0) * (weed.get("occurrences") or 0)
    pest_total = (pest.get("cost") or 0) * (pest.get("occurrences") or 0)

    fire_per_year = fire_total / horizon
    fence_year0 = fence_total * 0.7
    fence_per_year_maint = (fence_total * 0.3) / max(1, maint_years)
    weed_per_year = weed_total / horizon
    pest_per_year = pest_total / horizon

    is_ntfp = method_id.endswith("_ntfp")
    productivity_by_year = _build_productivity_map(method, horizon) if is_ntfp else _create_year_map(horizon)
    revenue_by_year = _build_revenue_map(method, horizon) if is_ntfp else _create_year_map(horizon)

    cum_net = 0.0
    cum_disc_net = 0.0

    for t in range(horizon):
        is_impl = t == 0
        impl_cost = impl_cost_total if is_impl else 0.0
        year_number = t + 1
        maint_cost = maintenance_by_year[year_number] if t > 0 else 0.0

        constraint_cost = (
            (fence_year0 if is_impl else fence_per_year_maint)
            + fire_per_year
            + weed_per_year
            + pest_per_year
        )
        total_cost = impl_cost + maint_cost + constraint_cost

        ntfp_productivity = productivity_by_year[year_number] if is_ntfp else 0.0
        ntfp_rev = revenue_by_year[year_number] if is_ntfp else 0.0
        total_benefit = ntfp_rev
        net_flow = total_benefit - total_cost
        cum_net += net_flow

        disc_net = net_flow / ((1 + discount_rate) ** t)
        cum_disc_net += disc_net

        flows.append(
            YearCashFlow(
                year=t,
                project_year=year_number,
                impl_cost=impl_cost,
                maint_cost=maint_cost,
                constraint_cost=constraint_cost,
                total_cost=total_cost,
                ntfp_productivity=ntfp_productivity,
                ntfp_revenue=ntfp_rev,
                carbon_benefit=0.0,
                total_benefit=total_benefit,
                net_flow=net_flow,
                cumulative_net=cum_net,
                discounted_net=disc_net,
                cumulative_discounted_net=cum_disc_net,
            )
        )

    return flows


def _compute_npv(cash_flows: list[YearCashFlow], rate: float) -> float:
    return sum(cf.net_flow / ((1 + rate) ** cf.year) for cf in cash_flows)


def _compute_irr(cash_flows: list[YearCashFlow]) -> float | None:
    lo, hi = -0.5, 5.0

    def npv_at(r: float) -> float:
        return sum(cf.net_flow / ((1 + r) ** cf.year) for cf in cash_flows)

    if npv_at(lo) * npv_at(hi) > 0:
        return None

    for _ in range(200):
        mid = (lo + hi) / 2
        if npv_at(mid) > 0:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 1e-8:
            break
    result = (lo + hi) / 2
    return result if math.isfinite(result) else None


def compute_method_cba(method_id: str, method: dict[str, Any], data: dict[str, Any]) -> MethodCBA:
    cash_flows = _build_cash_flows(method, method_id, data, DEFAULT_DISCOUNT_RATE)
    is_ntfp = method_id.endswith("_ntfp")

    npv_by_rate = [{"rate": rate, "npv": _compute_npv(cash_flows, rate)} for rate in DISCOUNT_RATES]
    irr = _compute_irr(cash_flows)

    total_costs = sum(
        cf.total_cost / ((1 + DEFAULT_DISCOUNT_RATE) ** cf.year) for cf in cash_flows
    )
    total_benefits = sum(
        cf.total_benefit / ((1 + DEFAULT_DISCOUNT_RATE) ** cf.year) for cf in cash_flows
    )
    bcr = total_benefits / total_costs if total_costs > 0 else 0.0

    payback_year = next(
        (cf.project_year for cf in cash_flows if cf.cumulative_discounted_net >= 0),
        None,
    )

    ecosystem = data.get("ecosystem") or ""
    carbon_seq_rate = get_carbon(ecosystem) * METHOD_CARBON_MULT.get(method_id, 0.75)

    return MethodCBA(
        method_id=method_id,
        method_label=METHOD_LABELS.get(method_id, method_id),
        is_ntfp=is_ntfp,
        cash_flows=cash_flows,
        npv_by_rate=npv_by_rate,
        irr=irr,
        bcr=bcr,
        payback_year=payback_year,
        total_costs_20yr=sum(cf.impl_cost + cf.maint_cost for cf in cash_flows),
        total_benefits_20yr=sum(cf.total_benefit for cf in cash_flows),
        carbon_seq_rate=carbon_seq_rate,
        cost_per_tco2=None,
    )


def cba_summary_dict(result: MethodCBA, discount_rate: float = DEFAULT_DISCOUNT_RATE) -> dict[str, Any]:
    npv = next((n["npv"] for n in result.npv_by_rate if n["rate"] == discount_rate), 0.0)
    return {
        "method": result.method_label,
        "npv_usd_ha": round(npv, 2),
        "irr_pct": round(result.irr * 100, 1) if result.irr is not None else None,
        "bcr": round(result.bcr, 2),
        "payback_year": result.payback_year,
        "total_cost_20yr": round(result.total_costs_20yr, 2),
        "total_benefit_20yr": round(result.total_benefits_20yr, 2),
        "impl_cost_y1": round(result.cash_flows[0].impl_cost, 2) if result.cash_flows else 0,
        "carbon_seq_rate": round(result.carbon_seq_rate, 1),
    }
