"""Basic validation checks on parsed spreadsheet records."""

from __future__ import annotations

from typing import Any


def _sum_shares(shares: dict[str, float]) -> float:
    return (shares.get("labor") or 0) + (shares.get("materials") or 0) + (shares.get("machinery") or 0)


def validate_record(record: dict[str, Any]) -> list[dict[str, str]]:
    """Return list of {level, message} validation findings."""
    issues: list[dict[str, str]] = []
    model = record["model"]
    method_id = record["method_id"]
    method = model["methodCosts"][method_id]

    impl = method.get("implementationCost") or 0
    if impl <= 0:
        issues.append({"level": "error", "message": "Custo de implementação (Impl_USD) ausente ou zero."})

    impl_sum = _sum_shares(method.get("implementationDistribution") or {})
    if impl_sum > 0 and abs(impl_sum - 100) > 1:
        issues.append(
            {
                "level": "warning",
                "message": f"Distribuição de implementação soma {impl_sum:.0f}% (esperado 100%).",
            }
        )

    maint_sum = _sum_shares(method.get("maintenanceDistribution") or {})
    if maint_sum > 0 and abs(maint_sum - 100) > 1:
        issues.append(
            {
                "level": "warning",
                "message": f"Distribuição de manutenção soma {maint_sum:.0f}% (esperado 100%).",
            }
        )

    segments = method.get("maintenanceSegments") or []
    if not segments:
        issues.append(
            {
                "level": "info",
                "message": "Nenhum segmento de manutenção preenchido — custos de manutenção podem estar subestimados.",
            }
        )
    else:
        for seg in segments:
            y_from = seg.get("yearFrom", 0)
            y_to = seg.get("yearTo", 0)
            if y_to < y_from:
                issues.append(
                    {
                        "level": "error",
                        "message": f"Segmento '{seg.get('label')}': ano final ({y_to}) < ano inicial ({y_from}).",
                    }
                )

    if method_id.endswith("_ntfp"):
        has_prod = bool(method.get("ntfpProductivitySegments"))
        has_rev = bool(method.get("ntfpRevenueSegments"))
        if not has_prod and not has_rev:
            issues.append(
                {
                    "level": "warning",
                    "message": "Método NTFP sem dados de produtividade nem receita.",
                }
            )

    if not record.get("country"):
        issues.append({"level": "warning", "message": "País não informado."})
    if not record.get("ecosystem"):
        issues.append({"level": "warning", "message": "Ecossistema não informado."})

    ctx = model.get("contextVariables") or {}
    for key, label in [
        ("fireRisk", "Quebra-fogo"),
        ("grazingPressure", "Cercamento"),
        ("invasiveSpeciesPressure", "Controle de invasoras"),
        ("pestControl", "Controle de pragas"),
    ]:
        entry = ctx.get(key) or {}
        dist_sum = _sum_shares(entry.get("distribution") or {})
        if dist_sum > 0 and abs(dist_sum - 100) > 1:
            issues.append(
                {
                    "level": "warning",
                    "message": f"{label}: distribuição de fatores soma {dist_sum:.0f}%.",
                }
            )

    labor = model.get("laborBreakdown") or {}
    for phase, label in [("implementation", "Implementação"), ("maintenance", "Manutenção")]:
        phase_data = labor.get(phase) or {}
        hired = phase_data.get("hiredLabor") or 0
        family = phase_data.get("familyLabor") or 0
        if (hired + family) > 0 and abs(hired + family - 100) > 1:
            issues.append(
                {
                    "level": "warning",
                    "message": f"Mão de obra ({label}): hired+family = {hired + family:.0f}%.",
                }
            )

    return issues
