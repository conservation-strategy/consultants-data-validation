"""
Verificador de Análise Custo-Benefício — planilhas de consultores CSF.

Uso:
  cd cba_checker
  pip install -r requirements.txt
  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Allow running as `streamlit run app.py` from cba_checker/
ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cba import DEFAULT_DISCOUNT_RATE, cba_summary_dict, compute_method_cba  # noqa: E402
from geo import get_continent  # noqa: E402
from loader import filter_comparables, group_consultant_files, load_all_from_directory, load_xlsx_file  # noqa: E402
from validation import validate_record  # noqa: E402

st.set_page_config(
    page_title="CBA Restauração Florestal",
    page_icon="🌳",
    layout="wide",
)

DATA_DIR = PARENT


@st.cache_data(show_spinner="Carregando planilhas…")
def load_data(data_dir: str) -> tuple[list[dict], list[dict]]:
    return load_all_from_directory(Path(data_dir))


def fmt_usd(n: float | None) -> str:
    if n is None:
        return "N/A"
    return f"US$ {n:,.0f}"


def fmt_pct(n: float | None) -> str:
    if n is None:
        return "N/A"
    return f"{n:.1f}%"


def render_kpi_cards(summary: dict, title: str):
    st.markdown(f"#### {title}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VPL (6%)", fmt_usd(summary["npv_usd_ha"]))
    c2.metric("TIR", fmt_pct(summary["irr_pct"]))
    c3.metric("BCR", f"{summary['bcr']:.2f}")
    payback = summary["payback_year"]
    c4.metric("Payback", f"Ano {payback}" if payback else "N/A")


def render_validation(issues: list[dict]):
    if not issues:
        st.success("Nenhum problema detectado na validação básica.")
        return
    for issue in issues:
        level = issue["level"]
        msg = issue["message"]
        if level == "error":
            st.error(msg)
        elif level == "warning":
            st.warning(msg)
        else:
            st.info(msg)


def render_cashflow_chart(result, title: str):
    years = [cf.project_year for cf in result.cash_flows]
    impl = [cf.impl_cost for cf in result.cash_flows]
    maint = [cf.maint_cost for cf in result.cash_flows]
    constr = [cf.constraint_cost for cf in result.cash_flows]
    benefit = [cf.total_benefit for cf in result.cash_flows]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Implementação", x=years, y=impl, marker_color="#c0392b"))
    fig.add_trace(go.Bar(name="Manutenção", x=years, y=maint, marker_color="#2596be"))
    fig.add_trace(go.Bar(name="Restrições", x=years, y=constr, marker_color="#f59e0b"))
    fig.add_trace(go.Scatter(name="Benefícios (NTFP)", x=years, y=benefit, mode="lines+markers", line=dict(color="#4E8465", width=2)))
    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title="Ano do projeto",
        yaxis_title="US$/ha",
        height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_npv_sensitivity(result):
    rates = [n["rate"] * 100 for n in result.npv_by_rate]
    npvs = [n["npv"] for n in result.npv_by_rate]
    colors = ["#4E8465" if v >= 0 else "#c0392b" for v in npvs]

    fig = go.Figure(go.Bar(x=[f"{r:.0f}%" for r in rates], y=npvs, marker_color=colors))
    fig.update_layout(title="Sensibilidade do VPL (taxas de desconto)", yaxis_title="VPL US$/ha", height=300)
    st.plotly_chart(fig, use_container_width=True)


def analyze_record(record: dict):
    model = record["model"]
    method_id = record["method_id"]
    method = model["methodCosts"][method_id]
    return compute_method_cba(method_id, method, model)


def render_panel(record: dict, panel_title: str):
    st.markdown(f"### {panel_title}")
    st.caption(
        f"**País:** {record.get('country', '—')} · "
        f"**Continente:** {record.get('continent', get_continent(record.get('country', '')))} · "
        f"**Ecossistema:** {record.get('ecosystem', '—')} · "
        f"**Método:** {record.get('method_label', record['method_id'])}"
    )
    if record.get("respondent"):
        st.caption(f"**Fonte:** {record['respondent'][:120]}")

    result = analyze_record(record)
    summary = cba_summary_dict(result)
    render_kpi_cards(summary, "Indicadores CBA (20 anos)")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Totais nominais (20 anos)**")
        st.write(f"- Custo total: {fmt_usd(summary['total_cost_20yr'])}")
        st.write(f"- Benefício total: {fmt_usd(summary['total_benefit_20yr'])}")
        st.write(f"- Impl. ano 1: {fmt_usd(summary['impl_cost_y1'])}")
    with col_b:
        st.markdown("**Carbono (referência)**")
        st.write(f"- Seq. estimada: {summary['carbon_seq_rate']} tCO₂/ha/ano")

    render_cashflow_chart(result, "Fluxo de caixa anual")
    render_npv_sensitivity(result)

    if record.get("source_type") == "consultant":
        with st.expander("Validação da planilha"):
            render_validation(validate_record(record))

    return result, summary


def main():
    st.title("Análise Custo-Benefício — Restauração Florestal")
    st.markdown(
        "Ferramenta para verificar planilhas exportadas do questionário CSF, "
        "calcular indicadores econômicos (VPL, TIR, BCR) e comparar com a revisão de literatura."
    )

    with st.sidebar:
        st.header("Configuração")
        data_dir = st.text_input("Pasta de dados", value=str(DATA_DIR))
        uploaded = st.file_uploader("Carregar nova planilha (.xlsx)", type=["xlsx"])

        if st.button("Recarregar dados"):
            load_data.clear()

    consultant, literature = load_data(data_dir)

    if uploaded:
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = Path(tmp.name)
        try:
            new_records = load_xlsx_file(tmp_path)
            for rec in new_records:
                rec["source_type"] = "consultant"
                rec["source_file"] = uploaded.name
            consultant = consultant + new_records
            st.sidebar.success(f"{len(new_records)} método(s) carregado(s) de {uploaded.name}")
        finally:
            tmp_path.unlink(missing_ok=True)

    if not consultant and not literature:
        st.warning("Nenhuma planilha encontrada. Coloque arquivos .xlsx na pasta do projeto.")
        st.stop()

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Consultores:** {len(consultant)} registros")
    st.sidebar.markdown(f"**Literatura:** {len(literature)} registros")

    file_groups = group_consultant_files(consultant)
    file_options = sorted(file_groups.keys())

    st.subheader("1. Selecionar modelo principal (consultor)")
    if not file_options:
        st.info("Nenhuma planilha de consultor — use apenas comparação com literatura ou faça upload.")
        primary_record = None
    else:
        selected_file = st.selectbox("Planilha do consultor", file_options, format_func=lambda f: f)
        methods_in_file = file_groups[selected_file]
        method_labels = {r["id"]: r["label"] for r in methods_in_file}
        selected_method_id = st.selectbox(
            "Método dentro da planilha",
            list(method_labels.keys()),
            format_func=lambda i: method_labels[i],
        )
        primary_record = next(r for r in methods_in_file if r["id"] == selected_method_id)

    st.subheader("2. Comparação")
    compare_mode = st.radio(
        "Modo de comparação",
        ["Literatura — mesmo continente e método", "Outra planilha de consultor", "Sem comparação"],
        horizontal=True,
    )

    compare_record: dict | None = None
    lit_comparables: list[dict] = []

    if primary_record and compare_mode == "Literatura — mesmo continente e método":
        continent = primary_record.get("continent") or get_continent(primary_record.get("country", ""))
        lit_comparables = filter_comparables(
            literature,
            method_id=primary_record["method_id"],
            continent=continent,
        )
        st.caption(
            f"Filtro: continente **{continent}**, método **{primary_record['method_label']}** "
            f"— {len(lit_comparables)} referência(s) na literatura."
        )
        if lit_comparables:
            compare_options = {r["id"]: r["label"] for r in lit_comparables}
            compare_id = st.selectbox("Referência da literatura", list(compare_options.keys()), format_func=lambda i: compare_options[i])
            compare_record = next(r for r in lit_comparables if r["id"] == compare_id)
        else:
            st.warning("Nenhuma referência na literatura com o mesmo continente e método. Tente outro método ou relaxe o filtro depois.")

    elif primary_record and compare_mode == "Outra planilha de consultor":
        other = [r for r in consultant if r["id"] != primary_record["id"]]
        if other:
            compare_options = {r["id"]: r["label"] for r in other}
            compare_id = st.selectbox("Outro modelo", list(compare_options.keys()), format_func=lambda i: compare_options[i])
            compare_record = next(r for r in other if r["id"] == compare_id)
        else:
            st.info("Só há um registro de consultor disponível.")

    st.markdown("---")

    if primary_record:
        left, right = st.columns(2)
        with left:
            primary_result, primary_summary = render_panel(primary_record, "Modelo principal")

        with right:
            if compare_record:
                compare_result, compare_summary = render_panel(compare_record, "Comparação")

                st.markdown("#### Diferença (principal − comparação)")
                d1, d2, d3 = st.columns(3)
                d1.metric("Δ VPL", fmt_usd(primary_summary["npv_usd_ha"] - compare_summary["npv_usd_ha"]))
                d2.metric("Δ BCR", f"{primary_summary['bcr'] - compare_summary['bcr']:.2f}")
                impl_diff = primary_summary["impl_cost_y1"] - compare_summary["impl_cost_y1"]
                d3.metric("Δ Impl. Y1", fmt_usd(impl_diff))
            else:
                st.markdown("### Comparação")
                st.info("Selecione uma referência para comparar lado a lado.")

        if lit_comparables and compare_mode.startswith("Literatura"):
            st.subheader("3. Panorama da literatura (mesmo filtro)")
            rows = []
            for rec in lit_comparables:
                res = analyze_record(rec)
                s = cba_summary_dict(res)
                rows.append(
                    {
                        "Referência": (rec.get("respondent") or "")[:60],
                        "País": rec.get("country"),
                        "VPL (6%)": s["npv_usd_ha"],
                        "TIR (%)": s["irr_pct"],
                        "BCR": s["bcr"],
                        "Custo 20a": s["total_cost_20yr"],
                        "Impl. Y1": s["impl_cost_y1"],
                    }
                )
            # add primary as benchmark row
            rows.insert(
                0,
                {
                    "Referência": "★ CONSULTOR (atual)",
                    "País": primary_record.get("country"),
                    "VPL (6%)": primary_summary["npv_usd_ha"],
                    "TIR (%)": primary_summary["irr_pct"],
                    "BCR": primary_summary["bcr"],
                    "Custo 20a": primary_summary["total_cost_20yr"],
                    "Impl. Y1": primary_summary["impl_cost_y1"],
                },
            )
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df["Custo 20a"],
                    y=df["VPL (6%)"],
                    mode="markers+text",
                    text=df["País"],
                    textposition="top center",
                    marker=dict(size=10, color=["#1a3530"] + ["#2596be"] * (len(df) - 1)),
                )
            )
            fig.update_layout(
                title="VPL vs Custo total — consultor vs literatura",
                xaxis_title="Custo total 20 anos (US$/ha)",
                yaxis_title="VPL @ 6% (US$/ha)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.subheader("Explorar literatura")
        if literature:
            lit_labels = {r["id"]: r["label"] for r in literature[:200]}
            lit_id = st.selectbox("Registro", list(lit_labels.keys()), format_func=lambda i: lit_labels[i])
            rec = next(r for r in literature if r["id"] == lit_id)
            render_panel(rec, "Literatura")
        else:
            st.warning("Sem dados disponíveis.")


if __name__ == "__main__":
    main()
