# WWTP Process Guide

This file is the only domain reference document injected into the LLM prompts for knowledge_agent and plan_agent.
The modeled object is simplified as a **single CSTR**. Multi-tank spatial heterogeneity, influent/effluent flows, and recycles must be represented by plan_agent in Step 6 as one of the six `boundaries`, then written by modeling_agent into the `boundaries` field of `asm_config.json`.

## 1. Main Biochemical Treatment Units in WWTPs

- **Anaerobic tank**: supports phosphorus release, hydrolysis/fermentation, and readily biodegradable substrate conversion.
- **Anoxic tank**: uses nitrate or nitrite for denitrification.
- **Aerobic tank**: supports organic-matter oxidation, ammonia nitrification, and aerobic phosphorus uptake.
- **Pre-anoxic tank**: uses influent carbon for pre-denitrification.
- **Post-anoxic tank**: further removes nitrate, often with external carbon addition if needed.
- **Anaerobic selector**: selects favorable biomass under high-substrate anaerobic conditions and can improve sludge properties.
- **Anoxic selector**: suppresses filamentous organisms and promotes denitrification under anoxic conditions.
- **Aerobic selector**: promotes rapid adsorption and organic oxidation under high-substrate aerobic conditions.
- **Facultative tank**: allows partial aerobic degradation and anoxic denitrification at low dissolved oxygen.

## 2. Single-CSTR Boundaries

The modeling basis is a single CSTR. Spatial effects such as multi-tank connections, influent/effluent flow, and recycles may only be expressed through the `boundaries` declared by plan_agent in Step 6. modeling_agent must write the six fixed boundary keys into `asm_config.json`. Boundaries not mentioned by the user must not be assigned default values; disabled boundaries must be written as `null`.

1. **Hydraulic boundary**: `hydraulic`, representing tank-to-tank or influent/effluent material exchange through `(C_in - C)` flux. Uses `k_HRT`; `C_in` may be null or a component-concentration dictionary.
2. **Internal recycle boundary**: `internal_recycle`, representing nitrified mixed-liquor recycle from aerobic to anoxic zones, carrying NO3, NO2, and other specified components. Uses `k_r` and component reference concentrations.
3. **RAS recycle boundary**: `ras_recycle`, representing return activated sludge from the secondary clarifier, bringing particulate biomass back to the front end. Uses `k_RAS` and `factor`.
4. **Aeration boundary**: `aeration`, adding oxygen transfer only to `S_sub_O_sub_2`. Uses `K_L_a` and `S_O_sat`.
5. **External carbon-dose boundary**: `carbon_dose`, adding biodegradable COD to an anoxic tank or specified location. Acts only on `S_sub_S`; uses `r_dose`.
6. **Chemical-dose boundary**: `chem_dose`, representing phosphorus-removal chemical dosing as a source/sink for `S_sub_PO_sub_4`. For phosphorus precipitation, the rate may be negative. Uses `r_chem`.

## 3. ASM Chemical Indicators: 21-Component Overview

Names follow the asmlibrary.py subscript syntax: `_sub_X` means subscript X, `_sep_X` means separator X, and `_sup_X` means superscript X.

### Soluble components (S_*)
- **S_sub_S** (mg COD/L): readily biodegradable soluble COD, such as VFAs and small organic molecules.
- **S_sub_I** (mg COD/L): inert soluble COD that does not participate in biological conversion.
- **S_sub_NH_sub_4** (mg N/L): ammonium nitrogen, nitrification substrate and assimilation nitrogen source.
- **S_sub_NO_sub_2** (mg N/L): nitrite nitrogen, AOB oxidation product and NOB substrate.
- **S_sub_NO_sub_3** (mg N/L): nitrate nitrogen, NOB product and common denitrification electron acceptor.
- **S_sub_NH_sub_2OH** (mg N/L): hydroxylamine, an AOB nitrification intermediate linked to N2O pathways.
- **S_sub_N_sub_2** (mg N/L): dissolved nitrogen gas, final denitrification product.
- **S_sub_N_sub_2O** (mg N/L): nitrous oxide, greenhouse-gas intermediate in nitrification/denitrification.
- **S_sub_NO** (mg N/L): nitric oxide, transient denitrification intermediate.
- **S_sub_ALK** (mol HCO3-/m3): alkalinity, affecting pH buffering and nitrification.
- **S_sub_O_sub_2** (mg O2/L): dissolved oxygen.
- **S_sub_PO_sub_4** (mg P/L): orthophosphate, the main EBPR release/uptake target.

### Particulate components (X_*)
- **X_sub_S** (mg COD/L): particulate substrate that must hydrolyze to S_sub_S before heterotrophic uptake.
- **X_sub_I** (mg COD/L): inert particulate COD.
- **X_sub_H** (mg COD/L): heterotrophic biomass responsible for COD removal and denitrification.
- **X_sub_AOB** (mg COD/L): ammonia-oxidizing bacteria, converting NH4 to NO2 through intermediates.
- **X_sub_NOB** (mg COD/L): nitrite-oxidizing bacteria, converting NO2 to NO3.
- **X_sub_STO** (mg COD/L): intracellular storage product such as PHB/glycogen-like material.
- **X_sub_PAO** (mg COD/L): polyphosphate-accumulating organisms.
- **X_sub_PHA** (mg COD/L): polyhydroxyalkanoate formed during PAO anaerobic phosphorus release.
- **X_sub_PP** (mg P/L): intracellular polyphosphate accumulated during aerobic/anoxic phosphorus uptake.

## 4. Coverage of the Four modelcomplex Options

| modelcomplex | Components | Reactions | Core capability | Recommended use |
|---|---:|---:|---|---|
| **SimplifiedCODN** | 13 | 9 | COD hydrolysis/degradation plus one-step nitrification | COD / NH4 / simple NO3 tasks |
| **CompleteNRN2O** | 17 | 32 | Two-step nitrification plus complete denitrification and N2O intermediates | N2O emissions or detailed nitrogen pathways |
| **EBPRCODN** | 17 | 18 | Simplified COD-N plus biological phosphorus removal | Phosphorus, PAO, PHA/PP, or EBPR tasks |
| **IntegratedNPR** | 21 | 41 | Full N + P + N2O | Tasks explicitly requiring complete N, complete P, and N2O together |

Selection rules:
- If the user only mentions COD or ammonia, choose `SimplifiedCODN`.
- If the user mentions N2O or denitrification intermediates, choose `CompleteNRN2O`.
- If the user mentions phosphorus, PAO, EBPR, or TP, choose `EBPRCODN`.
- If the user explicitly requires complete nitrogen, complete phosphorus, and N2O together, choose `IntegratedNPR`.
- If nitrogen and phosphorus both appear but the nitrogen side is simple denitrification, one-step nitrification, simplified denitrification, or unspecified complexity, choose `EBPRCODN`.
- For process optimization or unclear tasks, do not default to the full model; choose the smallest model that covers the mentioned pollutants and reaction complexity.

## 5. Three calibmode Options

| calibmode | Algorithm | sens_targets constraint | Use case |
|---|---|---|---|
| **SingleNRMSE** | Nelder-Mead single objective | exactly 1 key | User cares about one effluent indicator |
| **WeightedNRMSE** | weighted multi-target Nelder-Mead | 2-5 keys with weights | User gives multiple indicators with preference or weights |
| **ParetoMOEA** | NSGA-II Pareto multi-objective optimization | 2-5 keys | Trade-off analysis or multiple indicators without clear preference |
