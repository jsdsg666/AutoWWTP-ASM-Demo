# ASM Mechanistic Modeling Report (9-Step Workflow + Effect Analysis)

This report is generated from `midoutput/asm_config.json`, `midoutput/sensitivity.json`, and `midoutput/calibration.json`. All executable model definitions come from `script/asmlibrary.py`.

## 1. Define Model Boundaries

The selected modelcomplex is **IntegratedNPR**. Full nitrogen, phosphorus, and N2O model with 21 components and 41 reactions.

The reactor basis is a single completely stirred tank reactor (CSTR). Biological reaction terms define the internal conversion rates, while optional boundary source/sink terms are injected through the `boundaries` argument of `run_pipeline`.

### 1.1 Enabled Boundary Source/Sink Terms

| Boundary | Configuration | Interpretation |
|---|---|---|
| `aeration` | `K_L_a`=2, `S_O_sat`=8 | Oxygen transfer source/sink acting only on S_sub_O_sub_2. |

## 2. Define State Components

The ODE state vector contains **21** active components for `IntegratedNPR`. Soluble components use the `S_sub_*` prefix and particulate components use the `X_sub_*` prefix.

| # | Component | Formula label | Meaning | Unit | Role |
|---:|---|---|---|---|---|
| 1 | `S_sub_S` | S_S | readily biodegradable soluble COD | mg COD/L | Direct heterotrophic substrate and PAO anaerobic carbon source. |
| 2 | `S_sub_I` | S_I | inert soluble COD | mg COD/L | Soluble organic matter that is not biologically converted. |
| 3 | `S_sub_NH_sub_4` | S_NH_4 | ammonium nitrogen | mg N/L | Substrate for nitrification and nitrogen source for biomass synthesis. |
| 4 | `S_sub_NO_sub_2` | S_NO_2 | nitrite nitrogen | mg N/L | AOB product, NOB substrate, and denitrification electron acceptor. |
| 5 | `S_sub_NO_sub_3` | S_NO_3 | nitrate nitrogen | mg N/L | NOB product and common denitrification electron acceptor. |
| 6 | `S_sub_NH_sub_2OH` | S_NH_2OH | hydroxylamine | mg N/L | AOB nitrification intermediate linked to N2O formation. |
| 7 | `S_sub_N_sub_2` | S_N_2 | nitrogen gas | mg N/L | Final denitrification product. |
| 8 | `S_sub_N_sub_2O` | S_N_2O | nitrous oxide | mg N/L | Greenhouse-gas intermediate from nitrification and denitrification. |
| 9 | `S_sub_NO` | S_NO | nitric oxide | mg N/L | Short-lived nitrogen intermediate in AOB and denitrification pathways. |
| 10 | `S_sub_ALK` | S_ALK | alkalinity | mol HCO3-/m3 | pH-buffering capacity affected by nitrification and biomass growth. |
| 11 | `S_sub_O_sub_2` | S_O_2 | dissolved oxygen | mg O2/L | Electron acceptor for aerobic reactions and aeration target. |
| 12 | `X_sub_S` | X_S | slowly biodegradable particulate COD | mg COD/L | Particulate substrate that must hydrolyze before uptake. |
| 13 | `X_sub_I` | X_I | inert particulate COD | mg COD/L | Non-biodegradable particulate organic matter. |
| 14 | `X_sub_H` | X_H | heterotrophic biomass | mg COD/L | Biomass responsible for COD removal and denitrification. |
| 15 | `X_sub_AOB` | X_AOB | ammonia-oxidizing bacteria | mg COD/L | Autotrophic biomass for ammonia oxidation. |
| 16 | `X_sub_NOB` | X_NOB | nitrite-oxidizing bacteria | mg COD/L | Autotrophic biomass for nitrite oxidation. |
| 17 | `X_sub_STO` | X_STO | intracellular storage product | mg COD/L | Stored carbon used by heterotrophs under changing conditions. |
| 18 | `S_sub_PO_sub_4` | S_PO_4 | orthophosphate | mg P/L | Soluble phosphorus released and taken up in EBPR. |
| 19 | `X_sub_PP` | X_PP | polyphosphate | mg P/L | Intracellular phosphorus storage in PAOs. |
| 20 | `X_sub_PAO` | X_PAO | polyphosphate-accumulating organisms | mg COD/L | Biomass that drives EBPR. |
| 21 | `X_sub_PHA` | X_PHA | polyhydroxyalkanoate | mg COD/L | PAO storage polymer formed under anaerobic substrate uptake. |

## 3. Determine Biochemical Reactions

The selected model activates **41** reactions. The table summarizes each active reaction by reaction ID, category, consumed components, and produced components.

| Reaction ID | Category | Substrates | Products |
|---|---|---|---|
| `P1` | hydrolysis | `S_sub_S` | `X_sub_S` |
| `P2` | heterotrophic storage | `S_sub_NH_sub_4`, `S_sub_ALK`, `X_sub_STO` | `S_sub_S`, `S_sub_O_sub_2` |
| `P3` | heterotrophic growth | `S_sub_NH_sub_4`, `S_sub_NO_sub_2`, `S_sub_ALK`, `X_sub_STO` | `S_sub_S`, `S_sub_NO_sub_3` |
| `P4` | heterotrophic decay | `S_sub_NH_sub_4`, `S_sub_NO`, `S_sub_ALK`, `X_sub_STO` | `S_sub_S`, `S_sub_NO_sub_2` |
| `P5` | AOB nitrification | `S_sub_NH_sub_4`, `S_sub_N_sub_2O`, `S_sub_ALK`, `X_sub_STO` | `S_sub_S`, `S_sub_NO` |
| `P6` | AOB decay | `S_sub_NH_sub_4`, `S_sub_N_sub_2`, `S_sub_ALK`, `X_sub_STO` | `S_sub_S`, `S_sub_N_sub_2O` |
| `P7` | NOB nitrification | `X_sub_H` | `S_sub_NH_sub_4`, `S_sub_ALK`, `S_sub_O_sub_2`, `X_sub_STO` |
| `P8` | NOB decay | `S_sub_NO_sub_2`, `X_sub_H` | `S_sub_NH_sub_4`, `S_sub_NO_sub_3`, `S_sub_ALK`, `X_sub_STO` |
| `P9` | PAO storage | `S_sub_NO`, `S_sub_ALK`, `X_sub_H` | `S_sub_NH_sub_4`, `S_sub_NO_sub_2`, `X_sub_STO` |
| `P10` | PAO growth | `S_sub_N_sub_2O`, `X_sub_H` | `S_sub_NH_sub_4`, `S_sub_NO`, `S_sub_ALK`, `X_sub_STO` |
| `P11` | PAO decay | `S_sub_N_sub_2`, `X_sub_H` | `S_sub_NH_sub_4`, `S_sub_N_sub_2O`, `S_sub_ALK`, `X_sub_STO` |
| `P12` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_ALK`, `X_sub_I` | `S_sub_O_sub_2`, `X_sub_H` |
| `P13` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_NO_sub_2`, `S_sub_ALK`, `X_sub_I` | `S_sub_NO_sub_3`, `X_sub_H` |
| `P14` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_NO`, `S_sub_ALK`, `X_sub_I` | `S_sub_NO_sub_2`, `X_sub_H` |
| `P15` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_N_sub_2O`, `S_sub_ALK`, `X_sub_I` | `S_sub_NO`, `X_sub_H` |
| `P16` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_N_sub_2`, `S_sub_ALK`, `X_sub_I` | `S_sub_N_sub_2O`, `X_sub_H` |
| `P17` | biochemical reaction | - | `S_sub_O_sub_2`, `X_sub_STO` |
| `P18` | biochemical reaction | `S_sub_NO_sub_2` | `S_sub_NO_sub_3`, `X_sub_STO` |
| `P19` | biochemical reaction | `S_sub_NO`, `S_sub_ALK` | `S_sub_NO_sub_2`, `X_sub_STO` |
| `P20` | biochemical reaction | `S_sub_N_sub_2O` | `S_sub_NO`, `X_sub_STO` |
| `P21` | biochemical reaction | `S_sub_N_sub_2` | `S_sub_N_sub_2O`, `X_sub_STO` |
| `P22` | biochemical reaction | `S_sub_NH_sub_2OH` | `S_sub_NH_sub_4`, `S_sub_ALK`, `S_sub_O_sub_2` |
| `P23` | biochemical reaction | `S_sub_NO`, `X_sub_AOB` | `S_sub_NH_sub_4`, `S_sub_NH_sub_2OH`, `S_sub_ALK`, `S_sub_O_sub_2` |
| `P24` | biochemical reaction | `S_sub_NO_sub_2` | `S_sub_NO`, `S_sub_ALK`, `S_sub_O_sub_2` |
| `P25` | biochemical reaction | `S_sub_NO`, `S_sub_ALK` | `S_sub_NO_sub_2`, `S_sub_NH_sub_2OH` |
| `P26` | biochemical reaction | `S_sub_NO_sub_2`, `S_sub_N_sub_2O` | `S_sub_NH_sub_2OH`, `S_sub_NO`, `S_sub_ALK` |
| `P27` | biochemical reaction | `S_sub_NO` | `S_sub_NH_sub_2OH`, `S_sub_ALK` |
| `P28` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_ALK`, `X_sub_I` | `S_sub_O_sub_2`, `X_sub_AOB` |
| `P29` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_N_sub_2`, `S_sub_ALK`, `X_sub_I` | `S_sub_NO_sub_3`, `X_sub_AOB` |
| `P30` | biochemical reaction | `S_sub_NO_sub_3`, `X_sub_NOB` | `S_sub_NH_sub_4`, `S_sub_NO_sub_2`, `S_sub_ALK`, `S_sub_O_sub_2` |
| `P31` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_ALK`, `X_sub_I` | `S_sub_O_sub_2`, `X_sub_NOB` |
| `P32` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_N_sub_2`, `S_sub_ALK`, `X_sub_I` | `S_sub_NO_sub_3`, `X_sub_NOB` |
| `P33` | biochemical reaction | `S_sub_PO_sub_4`, `X_sub_PHA`, `S_sub_NH_sub_4`, `S_sub_ALK` | `S_sub_S`, `X_sub_PP` |
| `P34` | biochemical reaction | `X_sub_PP` | `S_sub_PO_sub_4`, `X_sub_PHA`, `S_sub_O_sub_2` |
| `P35` | biochemical reaction | `X_sub_PP`, `S_sub_N_sub_2`, `S_sub_ALK` | `S_sub_PO_sub_4`, `X_sub_PHA`, `S_sub_NO_sub_3` |
| `P36` | biochemical reaction | `X_sub_PAO` | `S_sub_NH_sub_4`, `S_sub_PO_sub_4`, `S_sub_O_sub_2`, `X_sub_PHA`, `S_sub_ALK` |
| `P37` | biochemical reaction | `S_sub_N_sub_2`, `X_sub_PAO`, `S_sub_ALK` | `S_sub_NH_sub_4`, `S_sub_PO_sub_4`, `S_sub_NO_sub_3`, `X_sub_PHA` |
| `P38` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_PO_sub_4`, `X_sub_I`, `S_sub_ALK` | `S_sub_O_sub_2`, `X_sub_PAO` |
| `P39` | biochemical reaction | `S_sub_NH_sub_4`, `S_sub_PO_sub_4`, `S_sub_N_sub_2`, `X_sub_I`, `S_sub_ALK` | `S_sub_NO_sub_3`, `X_sub_PAO` |
| `P40` | biochemical reaction | `S_sub_PO_sub_4` | `X_sub_PP` |
| `P41` | biochemical reaction | `S_sub_S` | `X_sub_PHA`, `S_sub_NH_sub_4`, `S_sub_ALK` |

## 4. Build the Stoichiometric Matrix

The stoichiometric matrix has **41 reactions x 21 components**. Positive coefficients produce a component, negative coefficients consume a component, and zeros are omitted from the compact table.

| Reaction | Component | Stoichiometric coefficient |
|---|---|---:|
| `P1` | `S_sub_S` | `1 - f_sub_SI` |
| `P1` | `S_sub_I` | `f_sub_SI` |
| `P1` | `S_sub_NH_sub_4` | `i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS` |
| `P1` | `S_sub_ALK` | `(i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS) / 14` |
| `P1` | `X_sub_S` | `-1` |
| `P2` | `S_sub_S` | `-1` |
| `P2` | `S_sub_NH_sub_4` | `i_sub_NSS` |
| `P2` | `S_sub_ALK` | `i_sub_NSS / 14` |
| `P2` | `S_sub_O_sub_2` | `-1 + Y_sub_STO_sep_O_sub_2` |
| `P2` | `X_sub_STO` | `Y_sub_STO_sep_O_sub_2` |
| `P3` | `S_sub_S` | `-1` |
| `P3` | `S_sub_NH_sub_4` | `i_sub_NSS` |
| `P3` | `S_sub_NO_sub_2` | `(1 - Y_sub_STO_sep_NO_sub_3) / 1.1429` |
| `P3` | `S_sub_NO_sub_3` | `-(1 - Y_sub_STO_sep_NO_sub_3) / 1.1429` |
| `P3` | `S_sub_ALK` | `i_sub_NSS / 14` |
| `P3` | `X_sub_STO` | `Y_sub_STO_sep_NO_sub_3` |
| `P4` | `S_sub_S` | `-1` |
| `P4` | `S_sub_NH_sub_4` | `i_sub_NSS` |
| `P4` | `S_sub_NO_sub_2` | `-(1 - Y_sub_STO_sep_NO_sub_2) / 0.5714` |
| `P4` | `S_sub_NO` | `(1 - Y_sub_STO_sep_NO_sub_2) / 0.5714` |
| `P4` | `S_sub_ALK` | `(i_sub_NSS + (1 - Y_sub_STO_sep_NO_sub_2) / 0.5714) / 14` |
| `P4` | `X_sub_STO` | `Y_sub_STO_sep_NO_sub_2` |
| `P5` | `S_sub_S` | `-1` |
| `P5` | `S_sub_NH_sub_4` | `i_sub_NSS` |
| `P5` | `S_sub_N_sub_2O` | `(1 - Y_sub_STO_sep_NO) / 0.5714` |
| `P5` | `S_sub_NO` | `-(1 - Y_sub_STO_sep_NO) / 0.5714` |
| `P5` | `S_sub_ALK` | `i_sub_NSS / 14` |
| `P5` | `X_sub_STO` | `Y_sub_STO_sep_NO` |
| `P6` | `S_sub_S` | `-1` |
| `P6` | `S_sub_NH_sub_4` | `i_sub_NSS` |
| `P6` | `S_sub_N_sub_2` | `(1 - Y_sub_STO_sep_N_sub_2O) / 0.5714` |
| `P6` | `S_sub_N_sub_2O` | `-(1 - Y_sub_STO_sep_N_sub_2O) / 0.5714` |
| `P6` | `S_sub_ALK` | `i_sub_NSS / 14` |
| `P6` | `X_sub_STO` | `Y_sub_STO_sep_N_sub_2O` |
| `P7` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P7` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P7` | `S_sub_O_sub_2` | `-1 / Y_sub_H_sep_O_sub_2 + 1` |
| `P7` | `X_sub_H` | `1` |
| `P7` | `X_sub_STO` | `-1 / Y_sub_H_sep_O_sub_2` |
| `P8` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P8` | `S_sub_NO_sub_2` | `(1 / Y_sub_H_sep_NO_sub_3 - 1) / 1.1429` |
| `P8` | `S_sub_NO_sub_3` | `-(1 / Y_sub_H_sep_NO_sub_3 - 1) / 1.1429` |
| `P8` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P8` | `X_sub_H` | `1` |
| `P8` | `X_sub_STO` | `-1 / Y_sub_H_sep_NO_sub_3` |
| `P9` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P9` | `S_sub_NO_sub_2` | `-(1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714` |
| `P9` | `S_sub_NO` | `(1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714` |
| `P9` | `S_sub_ALK` | `((1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714 - i_sub_NBM) / 14` |
| `P9` | `X_sub_H` | `1` |
| `P9` | `X_sub_STO` | `-1 / Y_sub_H_sep_NO_sub_2` |
| `P10` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P10` | `S_sub_N_sub_2O` | `(1 / Y_sub_H_sep_NO - 1) / 0.5714` |
| `P10` | `S_sub_NO` | `-(1 / Y_sub_H_sep_NO - 1) / 0.5714` |
| `P10` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P10` | `X_sub_H` | `1` |
| `P10` | `X_sub_STO` | `-1 / Y_sub_H_sep_NO` |
| `P11` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P11` | `S_sub_N_sub_2` | `(1 / Y_sub_H_sep_N_sub_2O - 1) / 0.5714` |
| `P11` | `S_sub_N_sub_2O` | `-(1 / Y_sub_H_sep_N_sub_2O - 1) / 0.5714` |
| `P11` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P11` | `X_sub_H` | `1` |
| `P11` | `X_sub_STO` | `-1 / Y_sub_H_sep_N_sub_2O` |
| `P12` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P12` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P12` | `S_sub_O_sub_2` | `-1 + f_sub_XI` |
| `P12` | `X_sub_I` | `f_sub_XI` |
| `P12` | `X_sub_H` | `-1` |
| `P13` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P13` | `S_sub_NO_sub_2` | `(1 - f_sub_XI) / 1.1429` |
| `P13` | `S_sub_NO_sub_3` | `-(1 - f_sub_XI) / 1.1429` |
| `P13` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P13` | `X_sub_I` | `f_sub_XI` |
| `P13` | `X_sub_H` | `-1` |
| `P14` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P14` | `S_sub_NO_sub_2` | `-(1 - f_sub_XI) / 0.5714` |
| `P14` | `S_sub_NO` | `(1 - f_sub_XI) / 0.5714` |
| `P14` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 0.5714) / 14` |
| `P14` | `X_sub_I` | `f_sub_XI` |
| `P14` | `X_sub_H` | `-1` |
| `P15` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P15` | `S_sub_N_sub_2O` | `(1 - f_sub_XI) / 0.5714` |
| `P15` | `S_sub_NO` | `-(1 - f_sub_XI) / 0.5714` |
| `P15` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P15` | `X_sub_I` | `f_sub_XI` |
| `P15` | `X_sub_H` | `-1` |
| `P16` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P16` | `S_sub_N_sub_2` | `(1 - f_sub_XI) / 0.5714` |
| `P16` | `S_sub_N_sub_2O` | `-(1 - f_sub_XI) / 0.5714` |
| `P16` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P16` | `X_sub_I` | `f_sub_XI` |
| `P16` | `X_sub_H` | `-1` |
| `P17` | `S_sub_O_sub_2` | `-1` |
| `P17` | `X_sub_STO` | `-1` |
| `P18` | `S_sub_NO_sub_2` | `1 / 1.1429` |
| `P18` | `S_sub_NO_sub_3` | `-1 / 1.1429` |
| `P18` | `X_sub_STO` | `-1` |
| `P19` | `S_sub_NO_sub_2` | `-1 / 0.5714` |
| `P19` | `S_sub_NO` | `1 / 0.5714` |
| `P19` | `S_sub_ALK` | `(1 / 0.5714) / 14` |
| `P19` | `X_sub_STO` | `-1` |
| `P20` | `S_sub_N_sub_2O` | `1 / 0.5714` |
| `P20` | `S_sub_NO` | `-1 / 0.5714` |
| `P20` | `X_sub_STO` | `-1` |
| `P21` | `S_sub_N_sub_2` | `1 / 0.5714` |
| `P21` | `S_sub_N_sub_2O` | `-1 / 0.5714` |
| `P21` | `X_sub_STO` | `-1` |
| `P22` | `S_sub_NH_sub_4` | `-1` |
| `P22` | `S_sub_NH_sub_2OH` | `1` |
| `P22` | `S_sub_ALK` | `-1 / 14` |
| `P22` | `S_sub_O_sub_2` | `-8 / 7` |
| `P23` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P23` | `S_sub_NH_sub_2OH` | `-1 / Y_sub_AOB` |
| `P23` | `S_sub_NO` | `1 / Y_sub_AOB` |
| `P23` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P23` | `S_sub_O_sub_2` | `-1.7143 / Y_sub_AOB + 1` |
| `P23` | `X_sub_AOB` | `1` |
| `P24` | `S_sub_NO_sub_2` | `1` |
| `P24` | `S_sub_NO` | `-1` |
| `P24` | `S_sub_ALK` | `-1 / 14` |
| `P24` | `S_sub_O_sub_2` | `-0.5714` |
| `P25` | `S_sub_NO_sub_2` | `-3` |
| `P25` | `S_sub_NH_sub_2OH` | `-1` |
| `P25` | `S_sub_NO` | `4` |
| `P25` | `S_sub_ALK` | `3 / 14` |
| `P26` | `S_sub_NO_sub_2` | `1` |
| `P26` | `S_sub_NH_sub_2OH` | `-1` |
| `P26` | `S_sub_N_sub_2O` | `4` |
| `P26` | `S_sub_NO` | `-4` |
| `P26` | `S_sub_ALK` | `-1 / 14` |
| `P27` | `S_sub_NH_sub_2OH` | `-1` |
| `P27` | `S_sub_NO` | `1` |
| `P27` | `S_sub_ALK` | `-3 / 14` |
| `P28` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P28` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P28` | `S_sub_O_sub_2` | `-1 + f_sub_XI` |
| `P28` | `X_sub_I` | `f_sub_XI` |
| `P28` | `X_sub_AOB` | `-1` |
| `P29` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P29` | `S_sub_NO_sub_3` | `-(1 - f_sub_XI) / 2.8571` |
| `P29` | `S_sub_N_sub_2` | `(1 - f_sub_XI) / 2.8571` |
| `P29` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14` |
| `P29` | `X_sub_I` | `f_sub_XI` |
| `P29` | `X_sub_AOB` | `-1` |
| `P30` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P30` | `S_sub_NO_sub_2` | `-1 / Y_sub_NOB` |
| `P30` | `S_sub_NO_sub_3` | `1 / Y_sub_NOB` |
| `P30` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P30` | `S_sub_O_sub_2` | `-1.1429 / Y_sub_NOB + 1` |
| `P30` | `X_sub_NOB` | `1` |
| `P31` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P31` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P31` | `S_sub_O_sub_2` | `-1 + f_sub_XI` |
| `P31` | `X_sub_I` | `f_sub_XI` |
| `P31` | `X_sub_NOB` | `-1` |
| `P32` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P32` | `S_sub_NO_sub_3` | `-(1 - f_sub_XI) / 2.8571` |
| `P32` | `S_sub_N_sub_2` | `(1 - f_sub_XI) / 2.8571` |
| `P32` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14` |
| `P32` | `X_sub_I` | `f_sub_XI` |
| `P32` | `X_sub_NOB` | `-1` |
| `P33` | `S_sub_S` | `-1` |
| `P33` | `S_sub_PO_sub_4` | `Y_sub_PO_sub_4_sep_PP` |
| `P33` | `X_sub_PP` | `-Y_sub_PO_sub_4_sep_PP` |
| `P33` | `X_sub_PHA` | `1` |
| `P33` | `S_sub_NH_sub_4` | `i_sub_NSS` |
| `P33` | `S_sub_ALK` | `i_sub_NSS / 14` |
| `P34` | `S_sub_PO_sub_4` | `-1` |
| `P34` | `X_sub_PP` | `1` |
| `P34` | `X_sub_PHA` | `-Y_sub_PHA_sep_PP_sep_O_sub_2` |
| `P34` | `S_sub_O_sub_2` | `-Y_sub_PHA_sep_PP_sep_O_sub_2` |
| `P35` | `S_sub_PO_sub_4` | `-1` |
| `P35` | `X_sub_PP` | `1` |
| `P35` | `X_sub_PHA` | `-Y_sub_PHA_sep_PP_sep_NO_sub_3` |
| `P35` | `S_sub_NO_sub_3` | `-Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571` |
| `P35` | `S_sub_N_sub_2` | `Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571` |
| `P35` | `S_sub_ALK` | `(Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571) / 14` |
| `P36` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P36` | `S_sub_PO_sub_4` | `-i_sub_PBM` |
| `P36` | `S_sub_O_sub_2` | `-1 / Y_sub_PAO_sep_O_sub_2 + 1` |
| `P36` | `X_sub_PHA` | `-1 / Y_sub_PAO_sep_O_sub_2` |
| `P36` | `X_sub_PAO` | `1` |
| `P36` | `S_sub_ALK` | `-i_sub_NBM / 14` |
| `P37` | `S_sub_NH_sub_4` | `-i_sub_NBM` |
| `P37` | `S_sub_PO_sub_4` | `-i_sub_PBM` |
| `P37` | `S_sub_NO_sub_3` | `-(1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571` |
| `P37` | `S_sub_N_sub_2` | `(1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571` |
| `P37` | `X_sub_PHA` | `-1 / Y_sub_PAO_sep_NO_sub_3` |
| `P37` | `X_sub_PAO` | `1` |
| `P37` | `S_sub_ALK` | `((1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571 - i_sub_NBM) / 14` |
| `P38` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P38` | `S_sub_PO_sub_4` | `-f_sub_XI * i_sub_PXI + i_sub_PBM` |
| `P38` | `S_sub_O_sub_2` | `-1 + f_sub_XI` |
| `P38` | `X_sub_I` | `f_sub_XI` |
| `P38` | `X_sub_PAO` | `-1` |
| `P38` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14` |
| `P39` | `S_sub_NH_sub_4` | `-f_sub_XI * i_sub_NXI + i_sub_NBM` |
| `P39` | `S_sub_PO_sub_4` | `-f_sub_XI * i_sub_PXI + i_sub_PBM` |
| `P39` | `S_sub_NO_sub_3` | `-(1 - f_sub_XI) / 2.8571` |
| `P39` | `S_sub_N_sub_2` | `(1 - f_sub_XI) / 2.8571` |
| `P39` | `X_sub_I` | `f_sub_XI` |
| `P39` | `X_sub_PAO` | `-1` |
| `P39` | `S_sub_ALK` | `(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14` |
| `P40` | `S_sub_PO_sub_4` | `1` |
| `P40` | `X_sub_PP` | `-1` |
| `P41` | `S_sub_S` | `1` |
| `P41` | `X_sub_PHA` | `-1` |
| `P41` | `S_sub_NH_sub_4` | `-i_sub_NSS` |
| `P41` | `S_sub_ALK` | `-i_sub_NSS / 14` |

## 5. Build Kinetic Rate Equations

Reaction rates combine Monod saturation, inhibition, switching factors, yields, and endogenous decay terms. The executable expressions below are taken directly from `asmlibrary.RATE_EQUATIONS` for the active reactions.

| Reaction ID | Category | Rate expression |
|---|---|---|
| `P1` | hydrolysis | `k_sub_H * ((X_sub_S / X_sub_H) / (K_sub_X + X_sub_S / X_sub_H)) * X_sub_H` |
| `P2` | heterotrophic storage | `k_sub_STO * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * X_sub_H` |
| `P3` | heterotrophic growth | `k_sub_STO * eta_sub_H_sep_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H` |
| `P4` | heterotrophic decay | `k_sub_STO * eta_sub_H_sep_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_H` |
| `P5` | AOB nitrification | `k_sub_STO * eta_sub_H_sep_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_H` |
| `P6` | AOB decay | `k_sub_STO * eta_sub_H_sep_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_H` |
| `P7` | NOB nitrification | `mu_sub_H * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * X_sub_H` |
| `P8` | NOB decay | `mu_sub_H * eta_sub_H_sep_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H` |
| `P9` | PAO storage | `mu_sub_H * eta_sub_H_sep_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_H` |
| `P10` | PAO growth | `mu_sub_H * eta_sub_H_sep_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_H` |
| `P11` | PAO decay | `mu_sub_H * eta_sub_H_sep_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_H` |
| `P12` | biochemical reaction | `b_sub_H_sep_O_sub_2 * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_H` |
| `P13` | biochemical reaction | `b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H` |
| `P14` | biochemical reaction | `b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_H` |
| `P15` | biochemical reaction | `b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_H` |
| `P16` | biochemical reaction | `b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_H` |
| `P17` | biochemical reaction | `b_sub_STO_sep_O_sub_2 * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_STO` |
| `P18` | biochemical reaction | `b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_STO` |
| `P19` | biochemical reaction | `b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_STO` |
| `P20` | biochemical reaction | `b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_STO` |
| `P21` | biochemical reaction | `b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_STO` |
| `P22` | biochemical reaction | `mu_sub_AOB_sup_AMO * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_AMO + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_AOB_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB` |
| `P23` | biochemical reaction | `mu_sub_AOB_sep_1_sup_HAO * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_HAO + S_sub_O_sub_2)) * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB` |
| `P24` | biochemical reaction | `mu_sub_AOB_sep_2_sup_HAO * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_HAO + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_AOB_sep_NO + S_sub_NO)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB` |
| `P25` | biochemical reaction | `mu_sub_AOB_sep_3_sup_HAO * eta_sub_AOB_sep_1 * (K_sub_AOB_sep_O_sub_2_sup_I / (K_sub_AOB_sep_O_sub_2_sup_I + S_sub_O_sub_2)) * (S_sub_NO_sub_2 / (K_sub_AOB_sep_NO_sub_2 + S_sub_NO_sub_2)) * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB` |
| `P26` | biochemical reaction | `mu_sub_AOB_sep_3_sup_HAO * eta_sub_AOB_sep_1 * (K_sub_AOB_sep_O_sub_2_sup_I / (K_sub_AOB_sep_O_sub_2_sup_I + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_AOB_sep_NO + S_sub_NO)) * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB` |
| `P27` | biochemical reaction | `q_sub_AOB_sep_1_sup_HAO * eta_sub_AOB_sep_2 * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (K_sub_AOB_sep_O_sub_2_sup_I_sep_P27 / (K_sub_AOB_sep_O_sub_2_sup_I_sep_P27 + S_sub_O_sub_2)) * X_sub_AOB` |
| `P28` | biochemical reaction | `b_sub_AOB * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_AOB` |
| `P29` | biochemical reaction | `b_sub_AOB * eta_sub_N_sep_end * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_AOB` |
| `P30` | biochemical reaction | `mu_sub_NOB * (S_sub_O_sub_2 / (K_sub_NOB_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_NO_sub_2 / (K_sub_NOB_sep_NO_sub_2 + S_sub_NO_sub_2)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_NOB` |
| `P31` | biochemical reaction | `b_sub_NOB * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_NOB` |
| `P32` | biochemical reaction | `b_sub_NOB * eta_sub_N_sep_end * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_NOB` |
| `P33` | biochemical reaction | `q_sub_PHA * (S_sub_S / (K_sub_PAO_sep_S + S_sub_S)) * ((X_sub_PP / X_sub_PAO) / (K_sub_PAO_sep_PP + X_sub_PP / X_sub_PAO)) * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (K_sub_PAO_sep_NO_sub_3_inh / (K_sub_PAO_sep_NO_sub_3_inh + S_sub_NO_sub_3)) * X_sub_PAO` |
| `P34` | biochemical reaction | `q_sub_PP * (S_sub_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PS + S_sub_PO_sub_4)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * ((K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO) / (K_sub_IPP + K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO)) * X_sub_PAO` |
| `P35` | biochemical reaction | `q_sub_PP * eta_sub_PAO_sep_NO_sub_3 * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_PAO_sep_NO_sub_3 + S_sub_NO_sub_3)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PS + S_sub_PO_sub_4)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * ((K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO) / (K_sub_IPP + K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO)) * X_sub_PAO` |
| `P36` | biochemical reaction | `mu_sub_PAO * (S_sub_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_PAO_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PO_sub_4 + S_sub_PO_sub_4)) * (S_sub_ALK / (K_sub_PAO_sep_ALK + S_sub_ALK)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * X_sub_PAO` |
| `P37` | biochemical reaction | `mu_sub_PAO * eta_sub_PAO_sep_NO_sub_3 * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_PAO_sep_NO_sub_3 + S_sub_NO_sub_3)) * (S_sub_NH_sub_4 / (K_sub_PAO_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PO_sub_4 + S_sub_PO_sub_4)) * (S_sub_ALK / (K_sub_PAO_sep_ALK + S_sub_ALK)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * X_sub_PAO` |
| `P38` | biochemical reaction | `b_sub_PAO * (S_sub_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_PAO` |
| `P39` | biochemical reaction | `b_sub_PAO * eta_sub_PAO_sep_end * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_PAO_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_PAO` |
| `P40` | biochemical reaction | `b_sub_PP * X_sub_PP` |
| `P41` | biochemical reaction | `b_sub_PHA * X_sub_PHA` |

Active kinetic/stoichiometric parameters used by this model: **95**.

| Parameter | Default value | Meaning |
|---|---:|---|
| `k_sub_H` | 0.0833 | reaction or hydrolysis rate coefficient |
| `K_sub_X` | 1 | half-saturation, affinity, or inhibition constant |
| `k_sub_STO` | 0.0396 | reaction or hydrolysis rate coefficient |
| `K_sub_H_sep_O_sub_2` | 0.2 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_SS` | 10 | half-saturation, affinity, or inhibition constant |
| `eta_sub_H_sep_NO_sub_3` | 0.6235 | switching or reduction factor |
| `K_sub_H_sep_O_sub_2_inh` | 0.1299 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_NO_sub_3` | 0.251 | half-saturation, affinity, or inhibition constant |
| `eta_sub_H_sep_NO_sub_2` | 0.9368 | switching or reduction factor |
| `K_sub_H_sep_NO_sub_2` | 0.81 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_NO_sup_I1` | 0.06 | half-saturation, affinity, or inhibition constant |
| `eta_sub_H_sep_NO` | 0.9883 | switching or reduction factor |
| `K_sub_H_sep_NO_sub_S` | 0.2 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_NO` | 0.21 | half-saturation, affinity, or inhibition constant |
| `eta_sub_H_sep_N_sub_2O` | 0.3912 | switching or reduction factor |
| `K_sub_H_sep_N_sub_2O` | 0.0052 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_NO_sup_I3` | 1.8801 | half-saturation, affinity, or inhibition constant |
| `mu_sub_H` | 0.125 | maximum specific growth or conversion rate |
| `K_sub_H_sep_NH_sub_4` | 0.01 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_ALK` | 0.1 | half-saturation, affinity, or inhibition constant |
| `K_sub_H_sep_STO` | 0.1 | half-saturation, affinity, or inhibition constant |
| `b_sub_H_sep_O_sub_2` | 0.0125 | endogenous decay or maintenance rate |
| `eta_sub_H_sep_end_NO_sub_3` | 0.4429 | switching or reduction factor |
| `eta_sub_H_sep_end_NO_sub_2` | 0.5 | switching or reduction factor |
| `eta_sub_H_sep_end_NO` | 0.2276 | switching or reduction factor |
| `eta_sub_H_sep_end_N_sub_2O` | 0.2306 | switching or reduction factor |
| `b_sub_STO_sep_O_sub_2` | 0.0125 | endogenous decay or maintenance rate |
| `mu_sub_AOB_sup_AMO` | 0.1605 | maximum specific growth or conversion rate |
| `K_sub_AOB_sep_O_sub_2_sup_AMO` | 0.6281 | half-saturation, affinity, or inhibition constant |
| `K_sub_AOB_sep_NH_sub_4` | 1.2815 | half-saturation, affinity, or inhibition constant |
| `mu_sub_AOB_sep_1_sup_HAO` | 0.085 | maximum specific growth or conversion rate |
| `mu_sub_AOB_sep_2_sup_HAO` | 0.167 | maximum specific growth or conversion rate |
| `mu_sub_AOB_sep_3_sup_HAO` | 0.085 | maximum specific growth or conversion rate |
| `K_sub_AOB_sep_O_sub_2_sup_HAO` | 0.74 | half-saturation, affinity, or inhibition constant |
| `K_sub_AOB_sep_NH_sub_2OH` | 0.2679 | half-saturation, affinity, or inhibition constant |
| `K_sub_N_sep_ALK` | 0.5 | half-saturation, affinity, or inhibition constant |
| `eta_sub_AOB_sep_1` | 0.074 | switching or reduction factor |
| `K_sub_AOB_sep_O_sub_2_sup_I` | 5.332 | half-saturation, affinity, or inhibition constant |
| `K_sub_AOB_sep_NO_sub_2` | 11.5123 | half-saturation, affinity, or inhibition constant |
| `K_sub_AOB_sep_NO` | 0.0052 | half-saturation, affinity, or inhibition constant |
| `eta_sub_AOB_sep_2` | 0.12 | switching or reduction factor |
| `b_sub_AOB` | 0.00625 | endogenous decay or maintenance rate |
| `eta_sub_N_sep_end` | 0.1 | switching or reduction factor |
| `q_sub_AOB_sep_1_sup_HAO` | 0.085 | ASM kinetic or stoichiometric parameter used by the active reactions |
| `K_sub_AOB_sep_O_sub_2_sup_I_sep_P27` | 1 | half-saturation, affinity, or inhibition constant |
| `mu_sub_NOB` | 0.0271 | maximum specific growth or conversion rate |
| `K_sub_NOB_sep_O_sub_2` | 1.5381 | half-saturation, affinity, or inhibition constant |
| `K_sub_NOB_sep_NO_sub_2` | 0.2048 | half-saturation, affinity, or inhibition constant |
| `b_sub_NOB` | 0.00917 | endogenous decay or maintenance rate |
| `f_sub_SI` | 0 | fraction coefficient |
| `i_sub_NXS` | 0.03 | composition coefficient |
| `i_sub_NSI` | 0.01 | composition coefficient |
| `i_sub_NSS` | 0.03 | composition coefficient |
| `Y_sub_STO_sep_O_sub_2` | 0.8 | yield coefficient |
| `Y_sub_STO_sep_NO_sub_3` | 0.7 | yield coefficient |
| `Y_sub_STO_sep_NO_sub_2` | 0.7 | yield coefficient |
| `Y_sub_STO_sep_NO` | 0.7 | yield coefficient |
| `Y_sub_STO_sep_N_sub_2O` | 0.7 | yield coefficient |
| `Y_sub_H_sep_O_sub_2` | 0.8 | yield coefficient |
| `i_sub_NBM` | 0.07 | composition coefficient |
| `Y_sub_H_sep_NO_sub_3` | 0.65 | yield coefficient |
| `Y_sub_H_sep_NO_sub_2` | 0.65 | yield coefficient |
| `Y_sub_H_sep_NO` | 0.65 | yield coefficient |
| `Y_sub_H_sep_N_sub_2O` | 0.65 | yield coefficient |
| `f_sub_XI` | 0.2 | fraction coefficient |
| `i_sub_NXI` | 0.04 | composition coefficient |
| `Y_sub_AOB` | 0.18 | yield coefficient |
| `Y_sub_NOB` | 0.06 | yield coefficient |
| `q_sub_PHA` | 0.125 | ASM kinetic or stoichiometric parameter used by the active reactions |
| `K_sub_PAO_sep_S` | 4 | half-saturation, affinity, or inhibition constant |
| `K_sub_PAO_sep_PP` | 0.01 | half-saturation, affinity, or inhibition constant |
| `K_sub_PAO_sep_O_sub_2` | 0.2 | half-saturation, affinity, or inhibition constant |
| `K_sub_PAO_sep_NO_sub_3_inh` | 0.5 | half-saturation, affinity, or inhibition constant |
| `q_sub_PP` | 0.0625 | ASM kinetic or stoichiometric parameter used by the active reactions |
| `K_sub_PAO_sep_PS` | 0.2 | half-saturation, affinity, or inhibition constant |
| `K_sub_PAO_sep_PHA` | 0.01 | half-saturation, affinity, or inhibition constant |
| `K_sub_PP_sep_MAX` | 0.34 | half-saturation, affinity, or inhibition constant |
| `K_sub_IPP` | 0.02 | half-saturation, affinity, or inhibition constant |
| `eta_sub_PAO_sep_NO_sub_3` | 0.6 | switching or reduction factor |
| `K_sub_PAO_sep_NO_sub_3` | 0.5 | half-saturation, affinity, or inhibition constant |
| `mu_sub_PAO` | 0.0417 | maximum specific growth or conversion rate |
| `K_sub_PAO_sep_NH_sub_4` | 0.05 | half-saturation, affinity, or inhibition constant |
| `K_sub_PAO_sep_PO_sub_4` | 0.01 | half-saturation, affinity, or inhibition constant |
| `K_sub_PAO_sep_ALK` | 0.1 | half-saturation, affinity, or inhibition constant |
| `b_sub_PAO` | 0.00833 | endogenous decay or maintenance rate |
| `eta_sub_PAO_sep_end` | 0.33 | switching or reduction factor |
| `b_sub_PP` | 0.00833 | endogenous decay or maintenance rate |
| `b_sub_PHA` | 0.00833 | endogenous decay or maintenance rate |
| `Y_sub_PAO_sep_O_sub_2` | 0.625 | yield coefficient |
| `Y_sub_PAO_sep_NO_sub_3` | 0.5 | yield coefficient |
| `Y_sub_PO_sub_4_sep_PP` | 0.4 | yield coefficient |
| `Y_sub_PHA_sep_PP_sep_O_sub_2` | 0.2 | yield coefficient |
| `Y_sub_PHA_sep_PP_sep_NO_sub_3` | 0.3 | yield coefficient |
| `i_sub_PBM` | 0.02 | composition coefficient |
| `i_sub_PXI` | 0.01 | composition coefficient |

## 6. Build Mass-Balance Equations

For each component j, the CSTR mass balance is `dC_j/dt = sum_k nu[j,k] * rho_k(C, theta) + B_j(t, C, env)`. The first term comes from stoichiometry and reaction kinetics; the second term is the sum of enabled boundary source/sink contributions.

### 6.1 Enabled Boundaries

| Boundary | Configuration |
|---|---|
| `aeration` | `K_L_a`=2, `S_O_sat`=8 |

### 6.2 Component Equations

- `d S_sub_S / dt = (1 - f_sub_SI)*rho_P1 + (-1)*rho_P2 + (-1)*rho_P3 + (-1)*rho_P4 + (-1)*rho_P5 + (-1)*rho_P6 + (-1)*rho_P33 + (1)*rho_P41`
- `d S_sub_I / dt = (f_sub_SI)*rho_P1`
- `d S_sub_NH_sub_4 / dt = (i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS)*rho_P1 + (i_sub_NSS)*rho_P2 + (i_sub_NSS)*rho_P3 + (i_sub_NSS)*rho_P4 + (i_sub_NSS)*rho_P5 + (i_sub_NSS)*rho_P6 + (-i_sub_NBM)*rho_P7 + (-i_sub_NBM)*rho_P8 + (-i_sub_NBM)*rho_P9 + (-i_sub_NBM)*rho_P10 + (-i_sub_NBM)*rho_P11 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P12 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P13 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P14 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P15 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P16 + (-1)*rho_P22 + (-i_sub_NBM)*rho_P23 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P28 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P29 + (-i_sub_NBM)*rho_P30 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P31 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P32 + (i_sub_NSS)*rho_P33 + (-i_sub_NBM)*rho_P36 + (-i_sub_NBM)*rho_P37 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P38 + (-f_sub_XI * i_sub_NXI + i_sub_NBM)*rho_P39 + (-i_sub_NSS)*rho_P41`
- `d S_sub_NO_sub_2 / dt = ((1 - Y_sub_STO_sep_NO_sub_3) / 1.1429)*rho_P3 + (-(1 - Y_sub_STO_sep_NO_sub_2) / 0.5714)*rho_P4 + ((1 / Y_sub_H_sep_NO_sub_3 - 1) / 1.1429)*rho_P8 + (-(1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714)*rho_P9 + ((1 - f_sub_XI) / 1.1429)*rho_P13 + (-(1 - f_sub_XI) / 0.5714)*rho_P14 + (1 / 1.1429)*rho_P18 + (-1 / 0.5714)*rho_P19 + (1)*rho_P24 + (-3)*rho_P25 + (1)*rho_P26 + (-1 / Y_sub_NOB)*rho_P30`
- `d S_sub_NO_sub_3 / dt = (-(1 - Y_sub_STO_sep_NO_sub_3) / 1.1429)*rho_P3 + (-(1 / Y_sub_H_sep_NO_sub_3 - 1) / 1.1429)*rho_P8 + (-(1 - f_sub_XI) / 1.1429)*rho_P13 + (-1 / 1.1429)*rho_P18 + (-(1 - f_sub_XI) / 2.8571)*rho_P29 + (1 / Y_sub_NOB)*rho_P30 + (-(1 - f_sub_XI) / 2.8571)*rho_P32 + (-Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571)*rho_P35 + (-(1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571)*rho_P37 + (-(1 - f_sub_XI) / 2.8571)*rho_P39`
- `d S_sub_NH_sub_2OH / dt = (1)*rho_P22 + (-1 / Y_sub_AOB)*rho_P23 + (-1)*rho_P25 + (-1)*rho_P26 + (-1)*rho_P27`
- `d S_sub_N_sub_2 / dt = ((1 - Y_sub_STO_sep_N_sub_2O) / 0.5714)*rho_P6 + ((1 / Y_sub_H_sep_N_sub_2O - 1) / 0.5714)*rho_P11 + ((1 - f_sub_XI) / 0.5714)*rho_P16 + (1 / 0.5714)*rho_P21 + ((1 - f_sub_XI) / 2.8571)*rho_P29 + ((1 - f_sub_XI) / 2.8571)*rho_P32 + (Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571)*rho_P35 + ((1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571)*rho_P37 + ((1 - f_sub_XI) / 2.8571)*rho_P39`
- `d S_sub_N_sub_2O / dt = ((1 - Y_sub_STO_sep_NO) / 0.5714)*rho_P5 + (-(1 - Y_sub_STO_sep_N_sub_2O) / 0.5714)*rho_P6 + ((1 / Y_sub_H_sep_NO - 1) / 0.5714)*rho_P10 + (-(1 / Y_sub_H_sep_N_sub_2O - 1) / 0.5714)*rho_P11 + ((1 - f_sub_XI) / 0.5714)*rho_P15 + (-(1 - f_sub_XI) / 0.5714)*rho_P16 + (1 / 0.5714)*rho_P20 + (-1 / 0.5714)*rho_P21 + (4)*rho_P26`
- `d S_sub_NO / dt = ((1 - Y_sub_STO_sep_NO_sub_2) / 0.5714)*rho_P4 + (-(1 - Y_sub_STO_sep_NO) / 0.5714)*rho_P5 + ((1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714)*rho_P9 + (-(1 / Y_sub_H_sep_NO - 1) / 0.5714)*rho_P10 + ((1 - f_sub_XI) / 0.5714)*rho_P14 + (-(1 - f_sub_XI) / 0.5714)*rho_P15 + (1 / 0.5714)*rho_P19 + (-1 / 0.5714)*rho_P20 + (1 / Y_sub_AOB)*rho_P23 + (-1)*rho_P24 + (4)*rho_P25 + (-4)*rho_P26 + (1)*rho_P27`
- `d S_sub_ALK / dt = ((i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS) / 14)*rho_P1 + (i_sub_NSS / 14)*rho_P2 + (i_sub_NSS / 14)*rho_P3 + ((i_sub_NSS + (1 - Y_sub_STO_sep_NO_sub_2) / 0.5714) / 14)*rho_P4 + (i_sub_NSS / 14)*rho_P5 + (i_sub_NSS / 14)*rho_P6 + (-i_sub_NBM / 14)*rho_P7 + (-i_sub_NBM / 14)*rho_P8 + (((1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714 - i_sub_NBM) / 14)*rho_P9 + (-i_sub_NBM / 14)*rho_P10 + (-i_sub_NBM / 14)*rho_P11 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P12 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P13 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 0.5714) / 14)*rho_P14 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P15 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P16 + ((1 / 0.5714) / 14)*rho_P19 + (-1 / 14)*rho_P22 + (-i_sub_NBM / 14)*rho_P23 + (-1 / 14)*rho_P24 + (3 / 14)*rho_P25 + (-1 / 14)*rho_P26 + (-3 / 14)*rho_P27 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P28 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14)*rho_P29 + (-i_sub_NBM / 14)*rho_P30 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P31 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14)*rho_P32 + (i_sub_NSS / 14)*rho_P33 + ((Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571) / 14)*rho_P35 + (-i_sub_NBM / 14)*rho_P36 + (((1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571 - i_sub_NBM) / 14)*rho_P37 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14)*rho_P38 + ((-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14)*rho_P39 + (-i_sub_NSS / 14)*rho_P41`
- `d S_sub_O_sub_2 / dt = (-1 + Y_sub_STO_sep_O_sub_2)*rho_P2 + (-1 / Y_sub_H_sep_O_sub_2 + 1)*rho_P7 + (-1 + f_sub_XI)*rho_P12 + (-1)*rho_P17 + (-8 / 7)*rho_P22 + (-1.7143 / Y_sub_AOB + 1)*rho_P23 + (-0.5714)*rho_P24 + (-1 + f_sub_XI)*rho_P28 + (-1.1429 / Y_sub_NOB + 1)*rho_P30 + (-1 + f_sub_XI)*rho_P31 + (-Y_sub_PHA_sep_PP_sep_O_sub_2)*rho_P34 + (-1 / Y_sub_PAO_sep_O_sub_2 + 1)*rho_P36 + (-1 + f_sub_XI)*rho_P38 + K_L_a*(S_O_sat-C)`
- `d X_sub_S / dt = (-1)*rho_P1`
- `d X_sub_I / dt = (f_sub_XI)*rho_P12 + (f_sub_XI)*rho_P13 + (f_sub_XI)*rho_P14 + (f_sub_XI)*rho_P15 + (f_sub_XI)*rho_P16 + (f_sub_XI)*rho_P28 + (f_sub_XI)*rho_P29 + (f_sub_XI)*rho_P31 + (f_sub_XI)*rho_P32 + (f_sub_XI)*rho_P38 + (f_sub_XI)*rho_P39`
- `d X_sub_H / dt = (1)*rho_P7 + (1)*rho_P8 + (1)*rho_P9 + (1)*rho_P10 + (1)*rho_P11 + (-1)*rho_P12 + (-1)*rho_P13 + (-1)*rho_P14 + (-1)*rho_P15 + (-1)*rho_P16`
- `d X_sub_AOB / dt = (1)*rho_P23 + (-1)*rho_P28 + (-1)*rho_P29`
- `d X_sub_NOB / dt = (1)*rho_P30 + (-1)*rho_P31 + (-1)*rho_P32`
- `d X_sub_STO / dt = (Y_sub_STO_sep_O_sub_2)*rho_P2 + (Y_sub_STO_sep_NO_sub_3)*rho_P3 + (Y_sub_STO_sep_NO_sub_2)*rho_P4 + (Y_sub_STO_sep_NO)*rho_P5 + (Y_sub_STO_sep_N_sub_2O)*rho_P6 + (-1 / Y_sub_H_sep_O_sub_2)*rho_P7 + (-1 / Y_sub_H_sep_NO_sub_3)*rho_P8 + (-1 / Y_sub_H_sep_NO_sub_2)*rho_P9 + (-1 / Y_sub_H_sep_NO)*rho_P10 + (-1 / Y_sub_H_sep_N_sub_2O)*rho_P11 + (-1)*rho_P17 + (-1)*rho_P18 + (-1)*rho_P19 + (-1)*rho_P20 + (-1)*rho_P21`
- `d S_sub_PO_sub_4 / dt = (Y_sub_PO_sub_4_sep_PP)*rho_P33 + (-1)*rho_P34 + (-1)*rho_P35 + (-i_sub_PBM)*rho_P36 + (-i_sub_PBM)*rho_P37 + (-f_sub_XI * i_sub_PXI + i_sub_PBM)*rho_P38 + (-f_sub_XI * i_sub_PXI + i_sub_PBM)*rho_P39 + (1)*rho_P40`
- `d X_sub_PP / dt = (-Y_sub_PO_sub_4_sep_PP)*rho_P33 + (1)*rho_P34 + (1)*rho_P35 + (-1)*rho_P40`
- `d X_sub_PAO / dt = (1)*rho_P36 + (1)*rho_P37 + (-1)*rho_P38 + (-1)*rho_P39`
- `d X_sub_PHA / dt = (1)*rho_P33 + (-Y_sub_PHA_sep_PP_sep_O_sub_2)*rho_P34 + (-Y_sub_PHA_sep_PP_sep_NO_sub_3)*rho_P35 + (-1 / Y_sub_PAO_sep_O_sub_2)*rho_P36 + (-1 / Y_sub_PAO_sep_NO_sub_3)*rho_P37 + (-1)*rho_P41`

## 7. Run Sensitivity Analysis with Data

Sensitivity analysis uses one-at-a-time parameter perturbation with +/-Delta = **0.1** on data file `F:/wyq/lunwen/lunwen24_AutoWWTP-asm/code/code/langgraph-en3132/input/data31.xlsx`. The configured target weights are `S_sub_NH_sub_4`=1, `S_sub_NO_sub_3`=1, `S_sub_PO_sub_4`=1, and the top **4** parameters are passed to calibration.

### 7.1 Top-K Parameters

| Rank | Parameter | Default | Combined sensitivity | S_sub_NH_sub_4 | S_sub_NO_sub_3 | S_sub_PO_sub_4 |
|---|---|---|---|---|---|---|
| 1 | `K_sub_PP_sep_MAX` | NA | 8.3726 | NA | NA | NA |
| 2 | `b_sub_H_sep_O_sub_2` | NA | 6.04892 | NA | NA | NA |
| 3 | `K_sub_H_sep_O_sub_2` | NA | 2.79228 | NA | NA | NA |
| 4 | `Y_sub_PAO_sep_O_sub_2` | NA | 2.42504 | NA | NA | NA |

## 8. Run Parameter Calibration

Weighted multi-target Nelder-Mead calibration minimizes the weighted sum of target NRMSE values.

- Calibration mode: **WeightedNRMSE**
- Target weights: `S_sub_NH_sub_4`=1, `S_sub_NO_sub_3`=1, `S_sub_PO_sub_4`=1
- Maximum iterations: **100**
- Calibrated parameter set: `K_sub_PP_sep_MAX`, `b_sub_H_sep_O_sub_2`, `K_sub_H_sep_O_sub_2`, `Y_sub_PAO_sep_O_sub_2`
- Final cost: **0.583962**
- Iterations: **100**
- Function evaluations: **170**
- Optimizer success: **False**

### 8.1 Parameter Changes

| Parameter | Initial | Calibrated | Relative change |
|---|---:|---:|---:|
| `K_sub_H_sep_O_sub_2` | 0.2 | 0.245068 | +22.5% |
| `K_sub_PP_sep_MAX` | 0.34 | 0.33554 | -1.3% |
| `Y_sub_PAO_sep_O_sub_2` | 0.625 | 0.527898 | -15.5% |
| `b_sub_H_sep_O_sub_2` | 0.0125 | 0.0131834 | +5.5% |

## 9. Interpret Calibration Results

The final objective value is **0.583962**, which is classified as **high error but still usable with caution** under the NRMSE thresholds.

### 9.1 Generated Figures

#### fig1_obs_vs_sim_baseline

![fig1_obs_vs_sim_baseline](figs/fig1_obs_vs_sim_baseline.png)

Input data and simulated trajectories.

#### fig2_r2

![fig2_r2](figs/fig2_r2.png)

Baseline versus calibrated model fit.

#### fig3_sensitivity_heatmap

![fig3_sensitivity_heatmap](figs/fig3_sensitivity_heatmap.png)

Sensitivity ranking.

#### fig4_topk_sensitivity

![fig4_topk_sensitivity](figs/fig4_topk_sensitivity.png)

Sensitivity heat map.

#### fig5_tornado

![fig5_tornado](figs/fig5_tornado.png)

Directional sensitivity response.

#### fig6_cost_convergence

![fig6_cost_convergence](figs/fig6_cost_convergence.png)

Calibration convergence.

#### fig7_cost_residual

![fig7_cost_residual](figs/fig7_cost_residual.png)

Pareto front or objective trade-off.

#### fig7_pareto_front

![fig7_pareto_front](figs/fig7_pareto_front.png)

Pareto front or objective trade-off.

#### fig8_pair_plot

![fig8_pair_plot](figs/fig8_pair_plot.png)

Calibrated-parameter relationship plot.

## 10. Modeling-Effect Analysis

### 10.1 Overall Assessment

The calibrated model reaches a final objective of **0.583962**. This indicates **high error but still usable with caution** for the configured target set: `S_sub_NH_sub_4`, `S_sub_NO_sub_3`, `S_sub_PO_sub_4`.
The optimizer did not report successful convergence, so the calibrated parameters should be treated as the best point found within the current budget rather than a stable optimum.

### 10.2 Identifiability and Next Steps

- Inspect the sensitivity ranking to confirm that calibrated parameters are identifiable for the selected targets.
- If NRMSE remains high, add missing boundary terms only when they are supported by process information, then rerun planning and calibration.
- If the optimizer stops early or parameters move to implausible values, reduce the calibrated parameter subset or add stronger engineering priors.
- If multiple targets conflict, prefer ParetoMOEA and compare representative solutions rather than forcing a single weighted compromise.
