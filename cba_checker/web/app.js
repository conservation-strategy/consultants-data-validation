/** Consultants Data Validation — client-side dashboard */

const CONTINENT_COLORS = {
  Africa: "#e67e22",
  Americas: "#2980b9",
  Asia: "#8e44ad",
  Europe: "#27ae60",
  Oceania: "#16a085",
  Unknown: "#95a5a6",
};

const PLOTLY_LAYOUT_BASE = {
  margin: { t: 24, r: 16, b: 48, l: 56 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { family: "Segoe UI, system-ui, sans-serif", size: 11, color: "#1a2e28" },
  legend: { orientation: "h", y: 1.14, x: 0 },
};

const ZERO_LINE_SHAPE = [{
  type: "line",
  x0: 0,
  x1: 0,
  y0: 0,
  y1: 1,
  xref: "x",
  yref: "paper",
  line: { color: "#666", width: 1.5, dash: "dash" },
}];

const METHOD_ABBR = {
  anr_30: "ANR",
  anr_30_ntfp: "ANR+NTFP",
  seed_dispersal: "Seed Disp.",
  seed_dispersal_ntfp: "Seed Disp.+NTFP",
  seedling_planting: "Seedling",
  seedling_planting_ntfp: "Seedling+NTFP",
};

const AVERAGE_BASIS_LABELS = {
  literature: "Lit. avg",
  consultant: "Cons. avg",
  combined: "Combined avg",
};

let DATA = null;
let methodFilter = null;
let ecosystemFilter = "all";
let discountRate = 0.06;
let primaryId = null;

const $ = (id) => document.getElementById(id);

function fmtUSD(n) {
  if (n == null || Number.isNaN(n)) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return "N/A";
  return `${n.toFixed(1)}%`;
}

function fmtRate(r) {
  return `${Math.round(r * 100)}%`;
}

function avg(nums) {
  const v = nums.filter((n) => n != null && !Number.isNaN(n));
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0;
}

function stdDev(nums) {
  const v = nums.filter((n) => n != null && !Number.isNaN(n));
  if (v.length < 2) return 0;
  const m = avg(v);
  const variance = v.reduce((s, x) => s + (x - m) ** 2, 0) / v.length;
  return Math.sqrt(variance);
}

function meanStd(pool, getter) {
  const vals = pool.map(getter).filter((v) => v != null && !Number.isNaN(v));
  if (!vals.length) return { mean: null, std: null, n: 0 };
  return { mean: avg(vals), std: stdDev(vals), n: vals.length };
}

function normEco(s) {
  return (s || "").trim().toLowerCase();
}

function sameEcosystem(a, b) {
  const na = normEco(a);
  const nb = normEco(b);
  if (!na || !nb) return false;
  return na === nb || na.includes(nb) || nb.includes(na);
}

function byMethod(records, methodId) {
  return records.filter((r) => r.methodId === methodId);
}

function byEcosystem(records, ecosystem) {
  if (!ecosystem || ecosystem === "all") return records;
  return records.filter((r) => sameEcosystem(r.ecosystem, ecosystem));
}

function consultants(records) {
  return records.filter((r) => r.sourceType === "consultant");
}

function literature(records) {
  return records.filter((r) => r.sourceType === "literature");
}

function getNpv(rec, rate = discountRate) {
  const entry = rec.npvByRate?.find((n) => Math.abs(n.rate - rate) < 0.0001);
  return entry ? entry.npv : rec.kpis.npv;
}

function methodAbbr(methodId) {
  return METHOD_ABBR[methodId] || methodId;
}

function consultantDisplayName(r) {
  if (!r) return "Consultant";
  if (r.consultantName) return r.consultantName;
  if (r.userName) return r.userName;
  return r.respondent || r.country || "Consultant";
}

function shortCitation(r) {
  const text = (r.respondent || "").trim();
  if (!text) return "";
  return text.length > 72 ? `${text.slice(0, 72)}…` : text;
}

function modelOptionLabel(r) {
  if (r.isAverage) {
    const basis = r.averageBasis || "combined";
    return `${AVERAGE_BASIS_LABELS[basis] || "Average"} — ${methodAbbr(r.methodId)}`;
  }
  const country = r.country || "—";
  const abbr = methodAbbr(r.methodId);
  if (r.sourceType === "literature") {
    const cite = shortCitation(r);
    return cite ? `${country} — ${abbr} · ${cite}` : `${country} — ${abbr}`;
  }
  return `${country} — ${abbr}`;
}

function renderModelCaption(el, rec) {
  if (!el) return;
  if (!rec) {
    el.innerHTML = "";
    return;
  }
  if (rec.isAverage) {
    el.innerHTML = `<strong>${modelOptionLabel(rec)}</strong>`;
    return;
  }
  const country = rec.country || "—";
  const abbr = methodAbbr(rec.methodId);
  let html = `<strong>${country} — ${abbr}</strong>`;
  if (rec.sourceType === "literature" && rec.respondent) {
    html += ` · <span class="cite-line">${rec.respondent}</span>`;
  } else if (rec.sourceType === "consultant") {
    const name = consultantDisplayName(rec);
    if (name && name !== country) html += ` · ${name}`;
  }
  el.innerHTML = html;
}

function getFilteredRecords() {
  return byEcosystem(byMethod(DATA.records, methodFilter), ecosystemFilter);
}

function uniqueEcosystems() {
  const seen = new Map();
  for (const r of DATA.records) {
    const eco = (r.ecosystem || "").trim();
    if (!eco) continue;
    const key = normEco(eco);
    if (!seen.has(key)) seen.set(key, eco);
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b));
}

function syncEcosystemSelects() {
  $("ecosystemFilter").value = ecosystemFilter;
}

function populateEcosystemFilters() {
  const ecosystems = uniqueEcosystems();
  const sel = $("ecosystemFilter");
  sel.innerHTML = '<option value="all">All ecosystems</option>';
  for (const eco of ecosystems) {
    const opt = document.createElement("option");
    opt.value = eco;
    opt.textContent = eco;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", () => {
    ecosystemFilter = sel.value;
    syncEcosystemSelects();
    refreshAll();
  });
  ecosystemFilter = "all";
  syncEcosystemSelects();
}

function populateDiscountSelect() {
  const rates = DATA.meta.discountRates || [0.03, 0.06, 0.08, 0.10, 0.12];
  discountRate = DATA.meta.discountRate || 0.06;

  const sel = $("discountRateCompare");
  sel.innerHTML = "";
  for (const r of rates) {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = fmtRate(r);
    sel.appendChild(opt);
  }
  sel.value = String(discountRate);
  sel.addEventListener("change", () => {
    discountRate = parseFloat(sel.value);
    refreshAll();
  });
}

function populateMethodFilter() {
  const sel = $("methodFilter");
  sel.innerHTML = "";
  for (const mid of DATA.methods) {
    const opt = document.createElement("option");
    opt.value = mid;
    opt.textContent = DATA.methodLabels[mid] || mid;
    sel.appendChild(opt);
  }
  methodFilter = DATA.methods[0];
  sel.value = methodFilter;
  sel.addEventListener("change", () => {
    methodFilter = sel.value;
    refreshAll();
  });
}

function fillSelect(sel, records, selectedId) {
  sel.innerHTML = "";
  for (const r of records) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = modelOptionLabel(r);
    sel.appendChild(opt);
  }
  if (records.length && !records.find((r) => r.id === selectedId)) {
    sel.value = records[0].id;
  } else if (selectedId) {
    sel.value = selectedId;
  }
}

function uniqueContextRecords() {
  const seen = new Map();
  for (const r of DATA.records) {
    const key = r.sourceType === "consultant" ? r.sourceFile : r.id;
    if (!seen.has(key)) seen.set(key, r);
  }
  return [...seen.values()];
}

function uniqueConsultants(records) {
  const cons = consultants(records);
  const seen = new Map();
  for (const r of cons) {
    const key = r.sourceFile || `${r.country}|${r.respondent}`;
    if (!seen.has(key)) seen.set(key, r);
  }
  return [...seen.values()];
}

function renderConsultantBanner(records) {
  const el = $("consultantList");
  const list = uniqueConsultants(records);
  const methodLabel = DATA.methodLabels[methodFilter] || methodFilter;
  const ecoNote = ecosystemFilter === "all" ? "" : ` · ecosystem: <strong>${ecosystemFilter}</strong>`;

  if (list.length === 0) {
    el.innerHTML = `<p class="consultant-empty">No consultant questionnaires for <strong>${methodLabel}</strong>${ecoNote}.</p>`;
    return;
  }

  const chips = list
    .map(
      (r) =>
        `<span class="consultant-chip" title="${r.sourceFile || ""}">` +
        `<strong>${r.country || "?"}</strong> · ${r.ecosystem || "?"} · ${consultantDisplayName(r).slice(0, 50)}` +
        `</span>`
    )
    .join("");

  el.innerHTML =
    `<p class="consultant-banner-title">Consultants — <strong>${methodLabel}</strong>${ecoNote} (${list.length}):</p>` +
    `<div class="consultant-chips">${chips}</div>`;
}

function resolveAveragePool(basis, methodRecords, consultantRecords, primary) {
  let pool = methodRecords;
  if (basis === "literature") pool = literature(methodRecords);
  else if (basis === "consultant") pool = consultantRecords;

  const ecoScope = $("averageEcoScope")?.value || "all";
  if (ecoScope === "same" && primary?.ecosystem) {
    pool = byEcosystem(pool, primary.ecosystem);
  }

  return pool;
}

function buildAverageRecord(pool, basis) {
  if (!pool.length) return null;

  const methodLabel = DATA.methodLabels[methodFilter] || methodFilter;
  const ecoScope = $("averageEcoScope")?.value || "all";
  const ecoSuffix =
    ecoScope === "same" && pool[0]?.ecosystem ? ` · ${pool[0].ecosystem}` : " · all ecosystems";
  const basisNames = {
    literature: "Literature",
    consultant: "Consultants",
    combined: "Combined",
  };
  const title = `${basisNames[basis] || "Average"} average — ${methodLabel}${ecoSuffix}`;

  const horizon = DATA.meta.timeHorizon || 20;
  const cashFlows = [];
  for (let y = 1; y <= horizon; y++) {
    const rows = pool.map((r) => r.cashFlows.find((cf) => cf.year === y)).filter(Boolean);
    cashFlows.push({
      year: y,
      implCost: avg(rows.map((r) => r.implCost)),
      maintCost: avg(rows.map((r) => r.maintCost)),
      constraintCost: avg(rows.map((r) => r.constraintCost)),
      totalCost: avg(rows.map((r) => r.totalCost)),
      ntfpRevenue: avg(rows.map((r) => r.ntfpRevenue)),
      totalBenefit: avg(rows.map((r) => r.totalBenefit)),
      netFlow: avg(rows.map((r) => r.netFlow)),
    });
  }

  const npvByRate = (DATA.meta.discountRates || [0.03, 0.06, 0.08, 0.10, 0.12]).map((rate) => ({
    rate,
    npv: avg(pool.map((r) => getNpv(r, rate))),
  }));

  const irrVals = pool.map((r) => r.kpis.irr).filter((v) => v != null);

  const detail = {
    implementationY1: avg(pool.map((r) => r.detail.implementationY1)),
    maintenanceTotal: avg(pool.map((r) => r.detail.maintenanceTotal)),
    constraints: {
      firebreak: avg(pool.map((r) => r.detail.constraints.firebreak)),
      fencing: avg(pool.map((r) => r.detail.constraints.fencing)),
      weedControl: avg(pool.map((r) => r.detail.constraints.weedControl)),
      pestControl: avg(pool.map((r) => r.detail.constraints.pestControl)),
      total: avg(pool.map((r) => r.detail.constraints.total)),
    },
    maintenanceSegments: [],
    benefits: {
      ntfpRevenueTotal: avg(pool.map((r) => r.detail.benefits.ntfpRevenueTotal)),
      total: avg(pool.map((r) => r.detail.benefits.total)),
    },
    costTotal20yr: avg(pool.map((r) => r.detail.costTotal20yr)),
    benefitTotal20yr: avg(pool.map((r) => r.detail.benefitTotal20yr)),
  };

  return {
    id: `average_${basis}_${methodFilter}`,
    isAverage: true,
    averageBasis: basis,
    sourceType: "average",
    country: `n=${pool.length}`,
    continent: "—",
    ecosystem: pool[0]?.ecosystem || "—",
    respondent: title,
    methodId: methodFilter,
    methodLabel: title,
    kpis: {
      npv: getNpv({ npvByRate }, discountRate),
      irr: irrVals.length ? avg(irrVals) : null,
      bcr: avg(pool.map((r) => r.kpis.bcr)),
      paybackYear: null,
      totalCost20yr: avg(pool.map((r) => r.kpis.totalCost20yr)),
      totalBenefit20yr: avg(pool.map((r) => r.kpis.totalBenefit20yr)),
      implCostY1: avg(pool.map((r) => r.kpis.implCostY1)),
      maintenanceTotal: avg(pool.map((r) => r.kpis.maintenanceTotal)),
      ntfpRevenueTotal: avg(pool.map((r) => r.kpis.ntfpRevenueTotal)),
    },
    npvByRate,
    cashFlows,
    detail,
  };
}

function plotHistogram(elementId, values, xTitle, color) {
  Plotly.react(
    elementId,
    [{
      type: "histogram",
      x: values,
      marker: { color, opacity: 0.75 },
      nbinsx: 20,
    }],
    {
      ...PLOTLY_LAYOUT_BASE,
      height: 260,
      shapes: ZERO_LINE_SHAPE,
      xaxis: { title: xTitle, zeroline: true, zerolinecolor: "#ccc" },
      yaxis: { title: "Count" },
      showlegend: false,
    }
  );
}

function refreshMethodCharts(records) {
  const continents = [...new Set(records.map((r) => r.continent || "Unknown"))].sort();
  const scatterTraces = [];

  for (const cont of continents) {
    const litSubset = records.filter(
      (r) => r.sourceType === "literature" && (r.continent || "Unknown") === cont
    );
    if (litSubset.length) {
      scatterTraces.push({
        type: "scatter",
        mode: "markers",
        name: `${cont} (literature)`,
        x: litSubset.map((r) => r.kpis.totalCost20yr),
        y: litSubset.map((r) => getNpv(r)),
        text: litSubset.map((r) => `${r.country}<br>${r.ecosystem}<br>${(r.respondent || "").slice(0, 40)}`),
        hovertemplate: "%{text}<br>Cost: %{x:,.0f}<br>NPV: %{y:,.0f}<extra></extra>",
        marker: {
          size: 9,
          color: CONTINENT_COLORS[cont] || CONTINENT_COLORS.Unknown,
          symbol: "circle",
          opacity: 0.85,
          line: { width: 1, color: "#fff" },
        },
      });
    }

    const consSubset = records.filter(
      (r) => r.sourceType === "consultant" && (r.continent || "Unknown") === cont
    );
    if (consSubset.length) {
      scatterTraces.push({
        type: "scatter",
        mode: "markers",
        name: `${cont} (consultant)`,
        x: consSubset.map((r) => r.kpis.totalCost20yr),
        y: consSubset.map((r) => getNpv(r)),
        text: consSubset.map(
          (r) => `★ ${r.country}<br>${r.ecosystem}<br>${consultantDisplayName(r).slice(0, 40)}`
        ),
        hovertemplate: "%{text}<br>Cost: %{x:,.0f}<br>NPV: %{y:,.0f}<extra></extra>",
        marker: {
          size: consSubset.map((r) => (r.id === primaryId ? 14 : 11)),
          color: CONTINENT_COLORS[cont] || CONTINENT_COLORS.Unknown,
          symbol: "star",
          opacity: 0.95,
          line: {
            width: consSubset.map((r) => (r.id === primaryId ? 2.5 : 1.5)),
            color: "#fff",
          },
        },
      });
    }
  }

  const rateLabel = fmtRate(discountRate);
  $("scatterTitle").textContent = `NPV vs Total Cost (NPV @ ${rateLabel})`;
  $("histNpvTitle").textContent = `NPV distribution (@ ${rateLabel})`;

  Plotly.react("chartScatter", scatterTraces, {
    ...PLOTLY_LAYOUT_BASE,
    height: 360,
    xaxis: { title: "Total cost (20 yr, US$/ha)" },
    yaxis: { title: `NPV @ ${rateLabel} (US$/ha)` },
    showlegend: true,
  });

  plotHistogram("chartHistNpv", records.map((r) => getNpv(r)), `NPV @ ${rateLabel} (US$/ha)`, "#2a5c4e");
  plotHistogram("chartHistCost", records.map((r) => r.kpis.totalCost20yr), "Total cost (US$/ha)", "#2563eb");
  plotHistogram("chartHistImpl", records.map((r) => r.kpis.implCostY1), "Implementation cost Y1 (US$/ha)", "#c0392b");
  plotHistogram(
    "chartHistMaint",
    records.map((r) => r.kpis.maintenanceTotal ?? r.detail.maintenanceTotal),
    "Maintenance cost 20 yr (US$/ha)",
    "#2596be"
  );
  plotHistogram(
    "chartHistNtfp",
    records.map((r) => r.kpis.ntfpRevenueTotal ?? r.detail.benefits.ntfpRevenueTotal),
    "NTFP revenue 20 yr (US$/ha)",
    "#4E8465"
  );
}

function refreshContextChart() {
  const records = uniqueContextRecords();
  const ctxKey = $("contextVar").value;
  plotHistogram(
    "chartHistContext",
    records.map((r) => r.detail.constraints[ctxKey] ?? 0),
    `${$("contextVar").selectedOptions[0].text} (US$/ha)`,
    "#f59e0b"
  );
}

function renderKpis(rec) {
  const k = rec.kpis;
  const npv = getNpv(rec);
  const rateLabel = fmtRate(discountRate);
  return `
    <div class="kpi-grid">
      <div class="kpi"><div class="label">NPV @ ${rateLabel}</div><div class="value">${fmtUSD(npv)}</div></div>
      <div class="kpi"><div class="label">IRR</div><div class="value">${fmtPct(k.irr)}</div></div>
      <div class="kpi"><div class="label">BCR</div><div class="value">${k.bcr != null ? k.bcr.toFixed(2) : "N/A"}</div></div>
      <div class="kpi"><div class="label">Payback</div><div class="value">${k.paybackYear ? `Year ${k.paybackYear}` : "N/A"}</div></div>
      <div class="kpi"><div class="label">Total cost (20 yr)</div><div class="value">${fmtUSD(k.totalCost20yr)}</div></div>
      <div class="kpi"><div class="label">Total benefit (20 yr)</div><div class="value">${fmtUSD(k.totalBenefit20yr)}</div></div>
    </div>
  `;
}

function renderMeta(rec) {
  if (rec.isAverage) {
    return `
      <div class="meta-line average-meta">
        <strong>${rec.methodLabel}</strong><br>
        ${rec.respondent} · based on ${rec.country} observations
      </div>
    `;
  }
  const name = consultantDisplayName(rec);
  const project =
    rec.respondent && rec.respondent !== name ? rec.respondent : "";
  return `
    <div class="meta-line">
      <strong>${name}</strong> · ${rec.country} (${rec.continent}) · ${rec.ecosystem}
      ${project ? `<br><span class="project-line">${project.slice(0, 120)}</span>` : ""}
    </div>
  `;
}

function renderCashflowChart(containerId, rec) {
  const cf = rec.cashFlows;
  const years = cf.map((r) => r.year);

  Plotly.react(containerId, [
    { name: "Implementation", x: years, y: cf.map((r) => r.implCost), type: "bar", marker: { color: "#c0392b" } },
    { name: "Maintenance", x: years, y: cf.map((r) => r.maintCost), type: "bar", marker: { color: "#2596be" } },
    { name: "Constraints", x: years, y: cf.map((r) => r.constraintCost), type: "bar", marker: { color: "#f59e0b" } },
    {
      name: "Benefits (NTFP)",
      x: years,
      y: cf.map((r) => r.totalBenefit),
      type: "scatter",
      mode: "lines+markers",
      line: { color: "#4E8465", width: 2 },
      marker: { size: 5 },
    },
  ], {
    ...PLOTLY_LAYOUT_BASE,
    barmode: "stack",
    height: 300,
    margin: { t: 48, r: 16, b: 48, l: 56 },
    xaxis: { title: "Project year", dtick: 2 },
    yaxis: { title: "" },
    showlegend: true,
    annotations: [{
      xref: "paper",
      yref: "paper",
      x: 0.5,
      y: 1.14,
      xanchor: "center",
      yanchor: "bottom",
      text: "US$/ha",
      showarrow: false,
      font: { size: 12, color: "#1a2e28" },
    }],
  });
}

function renderDetail(rec) {
  const d = rec.detail;
  const c = d.constraints;
  const segHtml =
    d.maintenanceSegments.length > 0
      ? `<ul class="segment-list">${d.maintenanceSegments
          .map((s) => `<li>${s.label}: yrs ${s.yearFrom}–${s.yearTo}, ${fmtUSD(s.annualCost)}/yr</li>`)
          .join("")}</ul>`
      : rec.isAverage
        ? "<p class=\"segment-list\">Average model — segment detail not shown.</p>"
        : "<p class=\"segment-list\">No maintenance segments filled in spreadsheet.</p>";

  return `
    <div class="detail-block">
      <h4>Costs used in analysis</h4>
      <table class="detail-table">
        <tr><th>Component</th><th class="num">US$/ha</th></tr>
        <tr><td>Implementation (Year 1)</td><td class="num">${fmtUSD(d.implementationY1)}</td></tr>
        <tr><td>Maintenance (20 yr total)</td><td class="num">${fmtUSD(d.maintenanceTotal)}</td></tr>
        <tr><td>Firebreak / fire risk</td><td class="num">${fmtUSD(c.firebreak)}</td></tr>
        <tr><td>Fencing / grazing pressure</td><td class="num">${fmtUSD(c.fencing)}</td></tr>
        <tr><td>Weed / invasive species</td><td class="num">${fmtUSD(c.weedControl)}</td></tr>
        <tr><td>Pest control</td><td class="num">${fmtUSD(c.pestControl)}</td></tr>
        <tr><td><strong>Total cost (20 yr)</strong></td><td class="num"><strong>${fmtUSD(d.costTotal20yr)}</strong></td></tr>
      </table>
      <h4>Maintenance segments</h4>
      ${segHtml}
      <h4>Benefits</h4>
      <table class="detail-table">
        <tr><th>Component</th><th class="num">US$/ha</th></tr>
        <tr><td>NTFP revenue (20 yr total)</td><td class="num">${fmtUSD(d.benefits.ntfpRevenueTotal)}</td></tr>
        <tr><td><strong>Total benefit (20 yr)</strong></td><td class="num"><strong>${fmtUSD(d.benefitTotal20yr)}</strong></td></tr>
      </table>
    </div>
  `;
}

function renderPanel(bodyEl, chartId, rec) {
  if (!rec) {
    bodyEl.innerHTML = "<p class=\"meta-line\">No model available for this filter.</p>";
    return;
  }
  bodyEl.innerHTML = `
    ${renderMeta(rec)}
    ${renderKpis(rec)}
    <div class="cashflow-chart" id="${chartId}"></div>
    ${renderDetail(rec)}
  `;
  renderCashflowChart(chartId, rec);
}

function updateComparePoolUI() {
  const pool = $("comparePool").value;
  const isAverage = pool === "average";
  $("labelCompareModel").classList.toggle("field-hidden", isAverage);
  $("labelAverageType").classList.toggle("field-hidden", !isAverage);
  $("labelAverageEcoScope").classList.toggle("field-hidden", !isAverage);
}

function pctChange(val, ref) {
  if (val == null || ref == null || Number.isNaN(val) || Number.isNaN(ref)) return null;
  if (Math.abs(ref) < 1e-9) return null;
  return ((val - ref) / Math.abs(ref)) * 100;
}

function withinStd(val, mean, std) {
  if (val == null || mean == null || std == null) return null;
  if (std < 1e-9) return Math.abs(val - mean) < 1e-9;
  return Math.abs(val - mean) <= std;
}

function fmtMeanStd(mean, std, likeFmt) {
  if (mean == null || Number.isNaN(mean)) return "—";
  const s = std ?? 0;
  if (likeFmt === fmtUSD) {
    return `${fmtUSD(mean)} ± ${fmtUSD(s)}`;
  }
  if (likeFmt === fmtPct) {
    return `${fmtPct(mean)} ± ${s.toFixed(1)} pp`;
  }
  return `${mean.toFixed(2)} ± ${s.toFixed(2)}`;
}

function renderAvgCell(val, stats, fmt) {
  if (stats.n === 0 || stats.mean == null) {
    return `<td class="num muted">—</td>`;
  }
  const pct = pctChange(val, stats.mean);
  const inside = withinStd(val, stats.mean, stats.std);
  const cls = inside === null ? "muted" : inside ? "ok" : "outlier";
  const pctText = pct == null ? "—" : `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;

  return `<td class="num ${cls}">
    <div class="delta-cell-avg">
      <div>${fmtMeanStd(stats.mean, stats.std, fmt)}</div>
      <div class="pct">${pctText}</div>
    </div>
  </td>`;
}

function renderDeltaPanel(primary) {
  const el = $("deltaPanel");

  if (!primary) {
    el.innerHTML = "<p class=\"meta-line\">Select a consultant model to see deviation analysis.</p>";
    return;
  }

  const rateLabel = fmtRate(discountRate);
  const methodPool = byMethod(DATA.records, methodFilter);
  const ecoPool = byEcosystem(methodPool, primary.ecosystem);

  const consultantName = consultantDisplayName(primary).slice(0, 80);
  const ecoLabel = primary.ecosystem || "—";
  const methodLabel = DATA.methodLabels[methodFilter] || methodFilter;

  const rows = [
    {
      section: "Economic indicators",
      items: [
        { label: `NPV @ ${rateLabel}`, get: (r) => getNpv(r), fmt: fmtUSD },
        { label: "IRR", get: (r) => r.kpis.irr, fmt: fmtPct },
        { label: "BCR", get: (r) => r.kpis.bcr, fmt: (v) => (v != null ? v.toFixed(2) : "N/A") },
        { label: "Total cost (20 yr)", get: (r) => r.kpis.totalCost20yr, fmt: fmtUSD },
        { label: "Total benefit (20 yr)", get: (r) => r.kpis.totalBenefit20yr, fmt: fmtUSD },
      ],
    },
    {
      section: "Cost components",
      items: [
        { label: "Implementation (Y1)", get: (r) => r.detail.implementationY1, fmt: fmtUSD },
        { label: "Maintenance (20 yr)", get: (r) => r.detail.maintenanceTotal, fmt: fmtUSD },
        { label: "NTFP revenue (20 yr)", get: (r) => r.detail.benefits.ntfpRevenueTotal, fmt: fmtUSD },
      ],
    },
    {
      section: "Context constraints",
      items: [
        { label: "Firebreak / fire risk", get: (r) => r.detail.constraints.firebreak, fmt: fmtUSD },
        { label: "Fencing / grazing", get: (r) => r.detail.constraints.fencing, fmt: fmtUSD },
        { label: "Weed / invasive species", get: (r) => r.detail.constraints.weedControl, fmt: fmtUSD },
        { label: "Pest control", get: (r) => r.detail.constraints.pestControl, fmt: fmtUSD },
      ],
    },
  ];

  let html = `<table class="delta-table"><thead><tr>
    <th>Metric</th>
    <th>Consultant Data<span class="sub">${consultantName}</span></th>
    <th>Average Data on same method<span class="sub-muted">${methodLabel} · n = ${methodPool.length}</span></th>
    <th>Average Data on same ecosystem<span class="sub-muted">${ecoLabel} · n = ${ecoPool.length}</span></th>
  </tr></thead><tbody>`;

  for (const group of rows) {
    html += `<tr class="section-row"><td colspan="4">${group.section}</td></tr>`;
    for (const item of group.items) {
      const val = item.get(primary);
      const methodStats = meanStd(methodPool, item.get);
      const ecoStats = meanStd(ecoPool, item.get);

      html += `<tr>
        <td>${item.label}</td>
        <td class="num consultant-val">${item.fmt(val)}</td>
        ${renderAvgCell(val, methodStats, item.fmt)}
        ${renderAvgCell(val, ecoStats, item.fmt)}
      </tr>`;
    }
  }

  html += `</tbody></table>`;
  el.innerHTML = html;
}

function refreshComparePanels() {
  const methodRecords = getFilteredRecords();
  const consultantRecords = consultants(methodRecords);

  const primarySel = $("selectPrimary");
  const compareSel = $("selectCompare");
  const pool = $("comparePool").value;

  updateComparePoolUI();

  fillSelect(primarySel, consultantRecords, primarySel.value);
  const primary = consultantRecords.find((r) => r.id === primarySel.value) || consultantRecords[0];
  primaryId = primary?.id || null;

  let compare = null;

  if (pool === "average") {
    const basis = $("averageType").value;
    const avgPool = resolveAveragePool(basis, methodRecords, consultantRecords, primary);
    compare = buildAverageRecord(avgPool, basis);
  } else {
    let comparePool = methodRecords;
    if (pool === "literature") comparePool = literature(methodRecords);
    else if (pool === "consultant") {
      comparePool = consultantRecords.filter((r) => r.id !== primary?.id);
    }

    if (comparePool.length === 0) {
      compareSel.innerHTML = "<option value=\"\">—</option>";
    } else {
      fillSelect(compareSel, comparePool, compareSel.value);
    }
    compare = comparePool.find((r) => r.id === compareSel.value) || comparePool[0];
  }

  renderPanel($("bodyPrimary"), "cashflowPrimary", primary);
  renderPanel($("bodyCompare"), "cashflowCompare", compare);
  renderModelCaption($("captionPrimary"), primary);
  renderModelCaption($("captionCompare"), compare);

  renderDeltaPanel(primary);
  renderConsultantBanner(methodRecords);
  refreshMethodCharts(methodRecords);
}

function refreshAll() {
  refreshComparePanels();
}

async function init() {
  try {
    const res = await fetch("data.json");
    if (!res.ok) throw new Error("data.json not found — run: python build_data.py");
    DATA = await res.json();
    $("status").hidden = true;
    $("app").hidden = false;

    populateMethodFilter();
    populateEcosystemFilters();
    populateDiscountSelect();

    $("selectPrimary").addEventListener("change", refreshComparePanels);
    $("selectCompare").addEventListener("change", refreshComparePanels);
    $("comparePool").addEventListener("change", refreshComparePanels);
    $("averageType").addEventListener("change", refreshComparePanels);
    $("averageEcoScope").addEventListener("change", refreshComparePanels);
    $("contextVar").addEventListener("change", refreshContextChart);

    refreshContextChart();
    refreshAll();
  } catch (err) {
    $("status").className = "error";
    $("status").textContent = `Failed to load: ${err.message}`;
  }
}

init();
