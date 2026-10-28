# Final-tool base adjustments (July 2026)

Adjustments applied to consultant source spreadsheets in `models/` before
rebuilding the master database and dashboard (`cba_checker/web/data.json`,
`docs/data.json`). Script: `cba_checker/apply_final_tool_adjustments.py`.

---

## 1. Gabriela Sarmiento (Mangrove)

**File:** `(Gabriela_Mangrove) restoration_Mangrove_Seed_Dispersal_2026-06-16-00-05-14._GABRIELA SARMIENTOxlsx.xlsx`

| Change | Detail |
|--------|--------|
| Exclude `seedling_planting_ntfp` | Oyster NTFP model produced extreme revenues (~USD 760,000 over 20 years at 5,000 kg/ha/yr × USD 8/kg). |
| How | Set `Impl_USD = 0` for that method so the parser skips it. Other Gabriela methods (`anr_30`, `seed_dispersal`, `seedling_planting`) remain. |

---

## 2. Marcel Pein (Vietnam Mangrove)

**File:** `(Marcel_Mangrove) Product 2_REVISION1_CSF_Validated Questionnaire Package_Vietnam_Mangrove_Marcel Pein.xlsx`

| Change | Detail |
|--------|--------|
| Machinery unit cost | `MachineryUnitCost_USD_hr`: **0.1 → 9.63** USD/hour on all valid method rows. (Reference labor-breakdown field; implementation totals already include machinery share.) |
| NTFP revenue density | Original revenues assume **1,667** NTFP-producing individuals/ha. Target density for the tool: **600** seedlings/ha. |
| How (revenues only) | Scale all `ProdSeg*_kg_ha_yr` on `*_ntfp` methods by **600/1667**. Costs unchanged. |
| Example | ProdSeg2 `15,000` kg/ha/yr → `≈ 5,398.92` kg/ha/yr. At USD 0.43/kg, 20-year NTFP total falls from **103,200** to **≈ 37,133** USD/ha. |

---

## 3. Nistia (Vietnam Mangrove)

**File:** `(Nistia_Mangrove) restoration_Mangrove_ANR_50%_Enrichment_2026-07-28-14-03-29.xlsx`

| Change | Detail |
|--------|--------|
| Drop fence cost | Fence was `1,676.4` USD/km × `34` ha = **USD 56,997.6** — unrealistically high for the tool base. |
| How | Set `Fence_UnitCost_USD_km = 0` and `Fence_Area_ha = 0` on all valid methods. |

*(Nistia Subtropical / other packages were not changed in this round.)*

---

## 4. Samuel Kimenyi / Sammy (Rwanda Mountaine Forest)

**File:** `(Samuel_Mountaine) restoration_Mountaine_Forest_ANR_50%_Enrichment_2026-07-01-16-22-05.xlsx`

**Method:** `seedling_planting_ntfp` only (M3 / Full Seedling + NTFP).

### Check vs technical note (Annual Revenue — Three Price Scenarios)

Sammy’s technical note **Low / pessimistic M3** schedule (USD/ha/yr):

| Period | Low M3 |
|--------|-------:|
| Year 4 | 945 |
| Years 5–6 | 1,418 |
| Years 8–10 | 1,692 |
| Years 16–20 | 2,678 |

**What was in the spreadsheet before this adjustment:** not that schedule.
Revenues were in **production mode** (`ProdSeg` kg × `NTFP_Price_USD_kg = 0.50`), e.g. 9,500 / 18,800 / 26,300 / 29,800 kg → annual cashflows of 4,750 / 9,400 / 13,150 / … totaling **USD 166,300** over 20 years — far above Low M3.

### Applied values (Low M3)

For the final-tool base we replace productivity segments with **revenue segments** equal to Low M3:

| Period | Applied Low M3 |
|--------|---------------:|
| Year 4 | **945** |
| Years 5–6 | **1,418** |
| Years 8–10 | **1,692** |
| Years 16–20 | **2,678** |

Years not listed in the note (7, 11–15) remain **zero** revenue. `NTFP_Price_USD_kg` set to 0 (unused in revenue mode). Species label kept (`Yushania alpina`).

20-year NTFP total after change: **USD 22,247** (vs 166,300 before).

---

## Rebuild

After editing the four workbooks:

```text
python apply_final_tool_adjustments.py
python build_master_database.py
python build_data.py
# copy web/data.json → docs/data.json for GitHub Pages
```

---

## 5. Edward Valencia Maningo (October 2026 intake → v2)

Uzbekistan was added to the country–continent map (`geo.py`). Active files are the **v2** corrections (2026-10-22). Original v1 workbooks are kept under `models/_archive/` (not loaded by the dashboard).

| Active file in `models/` | Ecosystem |
|--------------------------|-----------|
| `(Edward_v2)Uzbekistan Mountain Ecoystem 2026-10-22-03-44-22.xlsx` | Mountaine Forest |
| `(Edward_v2) Arid Ecosystem 2026-10-22-01-52-49.xlsx` | Arid or Semi-Arid |

### Main v1 → v2 changes
- NTFP revenues cut sharply (hectare normalization of the peak orchard rates that inflated NPV/BCR).
- Mountain `seed_dispersal_ntfp` now has revenue segments (was empty in v1).
- `HiredLaborCost_USD_day = 8` and `MachineryUnitCost_USD_hr = 240` filled (were 0). Note: 240 matches the report’s tractor **USD/ha** plow rate, not a true hourly machine rate.
- Maintenance in the raw v2 submission inflated monitoring/guard lines a lot. For the tool base we **restored v1 maintenance segments** onto the v2 workbooks (`restore_edward_v2_maint.py`), keeping v2 revenues and other fields.
- Context constraints (fire / fence / weed / pest unit costs) remain **zero**.
- Mountain GPS still incomplete in v2 (`39.1333,` without longitude). Comparison detail: `cba_checker/edward_v2_comparison.txt`.

---

## History note

Earlier Gabriela updates (weed frequency = 1; oyster NTFP setup) remain in the workbook history via `apply_consultant_updates.py`, but the oyster NTFP method is now excluded from the parsed dataset as above.
