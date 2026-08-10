# Parameter Meaning Guide

This document provides parameter semantics for validating and repairing `asm_config.json`.

## 1. Heterotroph-Related Parameters

- `k_sub_H`: baseline heterotrophic hydrolysis/conversion rate.
- `k_sub_STO`: heterotrophic storage rate.
- `mu_sub_H`: maximum heterotrophic growth rate.
- `b_sub_H_sep_O_sub_2`: aerobic heterotrophic decay rate.
- `K_sub_X`: half-saturation term related to the substrate/biomass ratio.
- `K_sub_H_*`: heterotrophic substrate, oxygen, nitrogen, alkalinity, or inhibition constants.
- `eta_sub_H_*`: efficiency reduction factors under anoxic or low-oxygen conditions.
- `Y_sub_H_*`: heterotrophic yield coefficients.
- `i_sub_NBM`, `i_sub_NXI`: nitrogen/phosphorus content of biomass or particulate matter.
- `f_sub_SI`, `i_sub_NXS`, `i_sub_NSI`, `i_sub_NSS`: hydrolysis and component-partition coefficients.

## 2. AOB / NOB Parameters

- `mu_sub_AOB_*`: maximum rates for AOB pathway steps.
- `q_sub_AOB_*`: AOB conversion-rate parameters.
- `b_sub_AOB`: AOB decay rate.
- `K_sub_AOB_*`: AOB oxygen, ammonium, hydroxylamine, or NOx affinity/inhibition constants.
- `eta_sub_AOB_*`: AOB condition-reduction factors.
- `mu_sub_NOB`: maximum NOB growth rate.
- `b_sub_NOB`: NOB decay rate.
- `K_sub_NOB_*`: NOB oxygen or nitrite affinity/inhibition constants.

## 3. PAO / EBPR Parameters

- `q_sub_PHA`: PHA formation/consumption rate.
- `q_sub_PP`: polyphosphate formation rate.
- `mu_sub_PAO`: maximum PAO growth rate.
- `b_sub_PAO`, `b_sub_PP`, `b_sub_PHA`: decay rates for PAO biomass, polyphosphate, and PHA.
- `K_sub_PAO_*`, `K_sub_PP_*`, `K_sub_IPP`: PAO metabolism and inhibition constants.
- `eta_sub_PAO_*`: PAO condition-reduction factors.
- `Y_sub_PAO_*`, `Y_sub_PO_sub_4_sep_PP`, `Y_sub_PHA_*`: PAO-related yield coefficients.
- `i_sub_PBM`, `i_sub_PXI`: elemental composition terms for PAO and particulate biomass.

## 4. General Rules

- `mu_*`, `k_*`, `b_*`, and `q_*` are usually rate parameters, often with units of `1/h`.
- `K_*` is usually a half-saturation or inhibition constant; larger values usually mean lower sensitivity at the same concentration.
- `eta_*` is a dimensionless reduction factor, usually in `0-1`.
- `Y_*` is a dimensionless yield coefficient.
- `i_*` and `f_*` are composition or partition coefficients, usually dimensionless.

## 5. Validation Reminders

- Do not force parameters from the full model into a simplified model.
- Parameter values should normally follow `param.json`; only reflection repair should adjust them.
- If a reaction class is inactive for the current `modelcomplex`, its corresponding parameters should not appear in final `params`.
