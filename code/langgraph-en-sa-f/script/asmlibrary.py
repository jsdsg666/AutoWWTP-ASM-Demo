"""ASM core library driven by data.xlsx for sensitivity analysis and calibration.

Component names, parameter names, and expression tokens use the PromptLibS16-style
identifier convention:
  - components: S_sub_S / S_sub_NH_sub_4 / X_sub_PAO
  - parameters: mu_sub_H / K_sub_H_sep_O_sub_2 / eta_sub_PAO_sep_NO_sub_3
  - naming rules: `_sub_` = subscript, `_sep_` = separator, `_sup_` = superscript

The implementation follows an ASM workflow:
  Step 1 boundary, component, and reaction scope are selected by modelcomplex.
  Step 2 stoichiometry is defined by STOICHIOMETRY.
  Step 3 kinetics are defined by RATE_EQUATIONS.
  Step 4 the CSTR mass balance is reaction terms plus boundary_terms.
  Step 5 initial values come from row 0 of data.xlsx; default rates use 1/h units.
  Step 6 solve_ivp/LSODA performs the baseline simulation on the t_h grid.
  Step 7 local OAT sensitivity ranks active parameters.
  Step 8 calibration fits the sensitivity-selected top-K parameters.

modelcomplex options are listed in COMPONENTS_BY_MODEL and REACTIONS_BY_MODEL.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.optimize import minimize


# ============================================================================
# 1. 21 components: full Level 4 set, aligned with Table S1 in PromptLibS16.md
# ============================================================================
COMPONENTS = [
    "S_sub_S",        "S_sub_I",         "S_sub_NH_sub_4", "S_sub_NO_sub_2",
    "S_sub_NO_sub_3", "S_sub_NH_sub_2OH","S_sub_N_sub_2",  "S_sub_N_sub_2O",
    "S_sub_NO",       "S_sub_ALK",       "S_sub_O_sub_2",
    "X_sub_S",        "X_sub_I",         "X_sub_H",
    "X_sub_AOB",      "X_sub_NOB",       "X_sub_STO",
    "S_sub_PO_sub_4", "X_sub_PP",        "X_sub_PAO",      "X_sub_PHA",
]

COMPONENT_UNITS = {
    "S_sub_S":         "mg COD/L",
    "S_sub_I":         "mg COD/L",
    "S_sub_NH_sub_4":  "mg N/L",
    "S_sub_NO_sub_2":  "mg N/L",
    "S_sub_NO_sub_3":  "mg N/L",
    "S_sub_NH_sub_2OH":"mg N/L",
    "S_sub_N_sub_2":   "mg N/L",
    "S_sub_N_sub_2O":  "mg N/L",
    "S_sub_NO":        "mg N/L",
    "S_sub_ALK":       "mol HCO3-/m3",
    "S_sub_O_sub_2":   "mg O2/L",
    "X_sub_S":         "mg COD/L",
    "X_sub_I":         "mg COD/L",
    "X_sub_H":         "mg COD/L",
    "X_sub_AOB":       "mg COD/L",
    "X_sub_NOB":       "mg COD/L",
    "X_sub_STO":       "mg COD/L",
    "S_sub_PO_sub_4":  "mg P/L",
    "X_sub_PP":        "mg P/L",
    "X_sub_PAO":       "mg COD/L",
    "X_sub_PHA":       "mg COD/L",
}


# ============================================================================
# 2. Stoichiometric matrix STOICHIOMETRY: 41 reactions by non-zero terms, stored as strings
# ============================================================================
STOICHIOMETRY = {
    "P1": {
        "S_sub_S":        "1 - f_sub_SI",
        "S_sub_I":        "f_sub_SI",
        "S_sub_NH_sub_4": "i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS",
        "S_sub_ALK":      "(i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS) / 14",
        "X_sub_S":        "-1",
    },
    "P2": {
        "S_sub_S":        "-1",
        "S_sub_NH_sub_4": "i_sub_NSS",
        "S_sub_ALK":      "i_sub_NSS / 14",
        "S_sub_O_sub_2":  "-1 + Y_sub_STO_sep_O_sub_2",
        "X_sub_STO":      "Y_sub_STO_sep_O_sub_2",
    },
    "P3": {
        "S_sub_S":        "-1",
        "S_sub_NH_sub_4": "i_sub_NSS",
        "S_sub_NO_sub_2": "(1 - Y_sub_STO_sep_NO_sub_3) / 1.1429",
        "S_sub_NO_sub_3": "-(1 - Y_sub_STO_sep_NO_sub_3) / 1.1429",
        "S_sub_ALK":      "i_sub_NSS / 14",
        "X_sub_STO":      "Y_sub_STO_sep_NO_sub_3",
    },
    "P4": {
        "S_sub_S":        "-1",
        "S_sub_NH_sub_4": "i_sub_NSS",
        "S_sub_NO_sub_2": "-(1 - Y_sub_STO_sep_NO_sub_2) / 0.5714",
        "S_sub_NO":       "(1 - Y_sub_STO_sep_NO_sub_2) / 0.5714",
        "S_sub_ALK":      "(i_sub_NSS + (1 - Y_sub_STO_sep_NO_sub_2) / 0.5714) / 14",
        "X_sub_STO":      "Y_sub_STO_sep_NO_sub_2",
    },
    "P5": {
        "S_sub_S":        "-1",
        "S_sub_NH_sub_4": "i_sub_NSS",
        "S_sub_N_sub_2O": "(1 - Y_sub_STO_sep_NO) / 0.5714",
        "S_sub_NO":       "-(1 - Y_sub_STO_sep_NO) / 0.5714",
        "S_sub_ALK":      "i_sub_NSS / 14",
        "X_sub_STO":      "Y_sub_STO_sep_NO",
    },
    "P6": {
        "S_sub_S":        "-1",
        "S_sub_NH_sub_4": "i_sub_NSS",
        "S_sub_N_sub_2":  "(1 - Y_sub_STO_sep_N_sub_2O) / 0.5714",
        "S_sub_N_sub_2O": "-(1 - Y_sub_STO_sep_N_sub_2O) / 0.5714",
        "S_sub_ALK":      "i_sub_NSS / 14",
        "X_sub_STO":      "Y_sub_STO_sep_N_sub_2O",
    },
    "P7": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "S_sub_O_sub_2":  "-1 / Y_sub_H_sep_O_sub_2 + 1",
        "X_sub_H":        "1",
        "X_sub_STO":      "-1 / Y_sub_H_sep_O_sub_2",
    },
    "P8": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_NO_sub_2": "(1 / Y_sub_H_sep_NO_sub_3 - 1) / 1.1429",
        "S_sub_NO_sub_3": "-(1 / Y_sub_H_sep_NO_sub_3 - 1) / 1.1429",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "X_sub_H":        "1",
        "X_sub_STO":      "-1 / Y_sub_H_sep_NO_sub_3",
    },
    "P9": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_NO_sub_2": "-(1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714",
        "S_sub_NO":       "(1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714",
        "S_sub_ALK":      "((1 / Y_sub_H_sep_NO_sub_2 - 1) / 0.5714 - i_sub_NBM) / 14",
        "X_sub_H":        "1",
        "X_sub_STO":      "-1 / Y_sub_H_sep_NO_sub_2",
    },
    "P10": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_N_sub_2O": "(1 / Y_sub_H_sep_NO - 1) / 0.5714",
        "S_sub_NO":       "-(1 / Y_sub_H_sep_NO - 1) / 0.5714",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "X_sub_H":        "1",
        "X_sub_STO":      "-1 / Y_sub_H_sep_NO",
    },
    "P11": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_N_sub_2":  "(1 / Y_sub_H_sep_N_sub_2O - 1) / 0.5714",
        "S_sub_N_sub_2O": "-(1 / Y_sub_H_sep_N_sub_2O - 1) / 0.5714",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "X_sub_H":        "1",
        "X_sub_STO":      "-1 / Y_sub_H_sep_N_sub_2O",
    },
    "P12": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "P13": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_NO_sub_2": "(1 - f_sub_XI) / 1.1429",
        "S_sub_NO_sub_3": "-(1 - f_sub_XI) / 1.1429",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "P14": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_NO_sub_2": "-(1 - f_sub_XI) / 0.5714",
        "S_sub_NO":       "(1 - f_sub_XI) / 0.5714",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 0.5714) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "P15": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_N_sub_2O": "(1 - f_sub_XI) / 0.5714",
        "S_sub_NO":       "-(1 - f_sub_XI) / 0.5714",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "P16": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_N_sub_2":  "(1 - f_sub_XI) / 0.5714",
        "S_sub_N_sub_2O": "-(1 - f_sub_XI) / 0.5714",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "P17": {"S_sub_O_sub_2": "-1", "X_sub_STO": "-1"},
    "P18": {"S_sub_NO_sub_2": "1 / 1.1429", "S_sub_NO_sub_3": "-1 / 1.1429", "X_sub_STO": "-1"},
    "P19": {
        "S_sub_NO_sub_2": "-1 / 0.5714",
        "S_sub_NO":       "1 / 0.5714",
        "S_sub_ALK":      "(1 / 0.5714) / 14",
        "X_sub_STO":      "-1",
    },
    "P20": {"S_sub_N_sub_2O": "1 / 0.5714", "S_sub_NO": "-1 / 0.5714", "X_sub_STO": "-1"},
    "P21": {"S_sub_N_sub_2": "1 / 0.5714", "S_sub_N_sub_2O": "-1 / 0.5714", "X_sub_STO": "-1"},
    "P22": {
        "S_sub_NH_sub_4":  "-1",
        "S_sub_NH_sub_2OH":"1",
        "S_sub_ALK":       "-1 / 14",
        "S_sub_O_sub_2":   "-8 / 7",
    },
    "P23": {
        "S_sub_NH_sub_4":  "-i_sub_NBM",
        "S_sub_NH_sub_2OH":"-1 / Y_sub_AOB",
        "S_sub_NO":        "1 / Y_sub_AOB",
        "S_sub_ALK":       "-i_sub_NBM / 14",
        "S_sub_O_sub_2":   "-1.7143 / Y_sub_AOB + 1",
        "X_sub_AOB":       "1",
    },
    "P24": {
        "S_sub_NO_sub_2": "1", "S_sub_NO": "-1",
        "S_sub_ALK": "-1 / 14", "S_sub_O_sub_2": "-0.5714",
    },
    "P25": {
        "S_sub_NO_sub_2":  "-3", "S_sub_NH_sub_2OH": "-1",
        "S_sub_NO": "4", "S_sub_ALK": "3 / 14",
    },
    "P26": {
        "S_sub_NO_sub_2":  "1",  "S_sub_NH_sub_2OH": "-1",
        "S_sub_N_sub_2O":  "4",  "S_sub_NO": "-4", "S_sub_ALK": "-1 / 14",
    },
    "P27": {"S_sub_NH_sub_2OH": "-1", "S_sub_NO": "1", "S_sub_ALK": "-3 / 14"},
    "P28": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_AOB":      "-1",
    },
    "P29": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_NO_sub_3": "-(1 - f_sub_XI) / 2.8571",
        "S_sub_N_sub_2":  "(1 - f_sub_XI) / 2.8571",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_AOB":      "-1",
    },
    "P30": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_NO_sub_2": "-1 / Y_sub_NOB",
        "S_sub_NO_sub_3": "1 / Y_sub_NOB",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "S_sub_O_sub_2":  "-1.1429 / Y_sub_NOB + 1",
        "X_sub_NOB":      "1",
    },
    "P31": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_NOB":      "-1",
    },
    "P32": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_NO_sub_3": "-(1 - f_sub_XI) / 2.8571",
        "S_sub_N_sub_2":  "(1 - f_sub_XI) / 2.8571",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_NOB":      "-1",
    },
    "P33": {
        "S_sub_S":        "-1",
        "S_sub_PO_sub_4": "Y_sub_PO_sub_4_sep_PP",
        "X_sub_PP":       "-Y_sub_PO_sub_4_sep_PP",
        "X_sub_PHA":      "1",
        "S_sub_NH_sub_4": "i_sub_NSS",
        "S_sub_ALK":      "i_sub_NSS / 14",
    },
    "P34": {
        "S_sub_PO_sub_4": "-1",
        "X_sub_PP":       "1",
        "X_sub_PHA":      "-Y_sub_PHA_sep_PP_sep_O_sub_2",
        "S_sub_O_sub_2":  "-Y_sub_PHA_sep_PP_sep_O_sub_2",
    },
    "P35": {
        "S_sub_PO_sub_4": "-1",
        "X_sub_PP":       "1",
        "X_sub_PHA":      "-Y_sub_PHA_sep_PP_sep_NO_sub_3",
        "S_sub_NO_sub_3": "-Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571",
        "S_sub_N_sub_2":  "Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571",
        "S_sub_ALK":      "(Y_sub_PHA_sep_PP_sep_NO_sub_3 / 2.8571) / 14",
    },
    "P36": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_PO_sub_4": "-i_sub_PBM",
        "S_sub_O_sub_2":  "-1 / Y_sub_PAO_sep_O_sub_2 + 1",
        "X_sub_PHA":      "-1 / Y_sub_PAO_sep_O_sub_2",
        "X_sub_PAO":      "1",
        "S_sub_ALK":      "-i_sub_NBM / 14",
    },
    "P37": {
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_PO_sub_4": "-i_sub_PBM",
        "S_sub_NO_sub_3": "-(1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571",
        "S_sub_N_sub_2":  "(1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571",
        "X_sub_PHA":      "-1 / Y_sub_PAO_sep_NO_sub_3",
        "X_sub_PAO":      "1",
        "S_sub_ALK":      "((1 / Y_sub_PAO_sep_NO_sub_3 - 1) / 2.8571 - i_sub_NBM) / 14",
    },
    "P38": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_PO_sub_4": "-f_sub_XI * i_sub_PXI + i_sub_PBM",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_PAO":      "-1",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
    },
    "P39": {
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_PO_sub_4": "-f_sub_XI * i_sub_PXI + i_sub_PBM",
        "S_sub_NO_sub_3": "-(1 - f_sub_XI) / 2.8571",
        "S_sub_N_sub_2":  "(1 - f_sub_XI) / 2.8571",
        "X_sub_I":        "f_sub_XI",
        "X_sub_PAO":      "-1",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14",
    },
    "P40": {"S_sub_PO_sub_4": "1", "X_sub_PP": "-1"},
    "P41": {
        "S_sub_S":        "1",
        "X_sub_PHA":      "-1",
        "S_sub_NH_sub_4": "-i_sub_NSS",
        "S_sub_ALK":      "-i_sub_NSS / 14",
    },
}


# ============================================================================
# 2b. Simplified-model stoichiometry SIMPLIFIED_STOICHIOMETRY: S1-S9 for SimplifiedCODN / EBPRCODN
#   - Does not expand NH2OH / NO / N2O intermediates and does not use X_STO.
#     This is an ASM1-style equivalent simplification, not a P1-P41 subset.
# ============================================================================
SIMPLIFIED_STOICHIOMETRY = {
    "S1": {  # X_S hydrolysis; same as P1
        "S_sub_S":        "1 - f_sub_SI",
        "S_sub_I":        "f_sub_SI",
        "S_sub_NH_sub_4": "i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS",
        "S_sub_ALK":      "(i_sub_NXS - f_sub_SI * i_sub_NSI - (1 - f_sub_SI) * i_sub_NSS) / 14",
        "X_sub_S":        "-1",
    },
    "S2": {  # X_H aerobic growth; directly consumes S_S, no STO
        "S_sub_S":        "-1 / Y_sub_H_sep_O_sub_2",
        "S_sub_O_sub_2":  "-(1 - Y_sub_H_sep_O_sub_2) / Y_sub_H_sep_O_sub_2",
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "X_sub_H":        "1",
    },
    "S3": {  # X_H anoxic denitrifying growth; S_S + NO3 -> N2 as one equivalent step
        "S_sub_S":        "-1 / Y_sub_H_sep_NO_sub_3",
        "S_sub_NO_sub_3": "-(1 - Y_sub_H_sep_NO_sub_3) / (2.8571 * Y_sub_H_sep_NO_sub_3)",
        "S_sub_N_sub_2":  "(1 - Y_sub_H_sep_NO_sub_3) / (2.8571 * Y_sub_H_sep_NO_sub_3)",
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_ALK":      "((1 - Y_sub_H_sep_NO_sub_3) / (2.8571 * Y_sub_H_sep_NO_sub_3) - i_sub_NBM) / 14",
        "X_sub_H":        "1",
    },
    "S4": {  # X_H aerobic endogenous respiration; same as P12
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "S5": {  # X_H anoxic endogenous respiration; NO3 -> N2 as one equivalent step
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_NO_sub_3": "-(1 - f_sub_XI) / 2.8571",
        "S_sub_N_sub_2":  "(1 - f_sub_XI) / 2.8571",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM + (1 - f_sub_XI) / 2.8571) / 14",
        "X_sub_I":        "f_sub_XI",
        "X_sub_H":        "-1",
    },
    "S6": {  # AOB ammonia-oxidizing growth; NH4 -> NO2 in one step, without expanding NH2OH/NO
        "S_sub_NH_sub_4": "-1 / Y_sub_AOB - i_sub_NBM",
        "S_sub_NO_sub_2": "1 / Y_sub_AOB",
        "S_sub_O_sub_2":  "-(3.4286 - Y_sub_AOB) / Y_sub_AOB",
        "S_sub_ALK":      "-(2 / Y_sub_AOB + i_sub_NBM) / 14",
        "X_sub_AOB":      "1",
    },
    "S7": {  # NOB nitrite-oxidizing growth; same as P30
        "S_sub_NH_sub_4": "-i_sub_NBM",
        "S_sub_NO_sub_2": "-1 / Y_sub_NOB",
        "S_sub_NO_sub_3": "1 / Y_sub_NOB",
        "S_sub_ALK":      "-i_sub_NBM / 14",
        "S_sub_O_sub_2":  "-1.1429 / Y_sub_NOB + 1",
        "X_sub_NOB":      "1",
    },
    "S8": {  # AOB endogenous respiration; same as P28
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_AOB":      "-1",
    },
    "S9": {  # NOB endogenous respiration; same as P31
        "S_sub_NH_sub_4": "-f_sub_XI * i_sub_NXI + i_sub_NBM",
        "S_sub_ALK":      "(-f_sub_XI * i_sub_NXI + i_sub_NBM) / 14",
        "S_sub_O_sub_2":  "-1 + f_sub_XI",
        "X_sub_I":        "f_sub_XI",
        "X_sub_NOB":      "-1",
    },
}


# ============================================================================
# 3. Reaction-rate equations RATE_EQUATIONS: 41 Python expressions
# ============================================================================
RATE_EQUATIONS = {
    "P1":  "k_sub_H * ((X_sub_S / X_sub_H) / (K_sub_X + X_sub_S / X_sub_H)) * X_sub_H",
    "P2":  "k_sub_STO * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * X_sub_H",
    "P3":  "k_sub_STO * eta_sub_H_sep_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H",
    "P4":  "k_sub_STO * eta_sub_H_sep_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_H",
    "P5":  "k_sub_STO * eta_sub_H_sep_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_H",
    "P6":  "k_sub_STO * eta_sub_H_sep_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_H",
    "P7":  "mu_sub_H * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * X_sub_H",
    "P8":  "mu_sub_H * eta_sub_H_sep_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H",
    "P9":  "mu_sub_H * eta_sub_H_sep_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_H",
    "P10": "mu_sub_H * eta_sub_H_sep_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_H",
    "P11": "mu_sub_H * eta_sub_H_sep_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * ((X_sub_STO / X_sub_H) / (K_sub_H_sep_STO + X_sub_STO / X_sub_H)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_H",
    "P12": "b_sub_H_sep_O_sub_2 * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_H",
    "P13": "b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H",
    "P14": "b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_H",
    "P15": "b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_H",
    "P16": "b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_H",
    "P17": "b_sub_STO_sep_O_sub_2 * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_STO",
    "P18": "b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_STO",
    "P19": "b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_2 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_2 / (K_sub_H_sep_NO_sub_2 + S_sub_NO_sub_2)) * (K_sub_H_sep_NO_sup_I1 / (K_sub_H_sep_NO_sup_I1 + S_sub_NO)) * X_sub_STO",
    "P20": "b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_NO * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_H_sep_NO_sub_S + S_sub_NO + S_sub_NO**2 / K_sub_H_sep_NO)) * X_sub_STO",
    "P21": "b_sub_STO_sep_O_sub_2 * eta_sub_H_sep_end_N_sub_2O * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_N_sub_2O / (K_sub_H_sep_N_sub_2O + S_sub_N_sub_2O)) * (K_sub_H_sep_NO_sup_I3 / (K_sub_H_sep_NO_sup_I3 + S_sub_NO)) * X_sub_STO",
    "P22": "mu_sub_AOB_sup_AMO * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_AMO + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_AOB_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB",
    "P23": "mu_sub_AOB_sep_1_sup_HAO * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_HAO + S_sub_O_sub_2)) * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB",
    "P24": "mu_sub_AOB_sep_2_sup_HAO * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_HAO + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_AOB_sep_NO + S_sub_NO)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB",
    "P25": "mu_sub_AOB_sep_3_sup_HAO * eta_sub_AOB_sep_1 * (K_sub_AOB_sep_O_sub_2_sup_I / (K_sub_AOB_sep_O_sub_2_sup_I + S_sub_O_sub_2)) * (S_sub_NO_sub_2 / (K_sub_AOB_sep_NO_sub_2 + S_sub_NO_sub_2)) * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB",
    "P26": "mu_sub_AOB_sep_3_sup_HAO * eta_sub_AOB_sep_1 * (K_sub_AOB_sep_O_sub_2_sup_I / (K_sub_AOB_sep_O_sub_2_sup_I + S_sub_O_sub_2)) * (S_sub_NO / (K_sub_AOB_sep_NO + S_sub_NO)) * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB",
    "P27": "q_sub_AOB_sep_1_sup_HAO * eta_sub_AOB_sep_2 * (S_sub_NH_sub_2OH / (K_sub_AOB_sep_NH_sub_2OH + S_sub_NH_sub_2OH)) * (K_sub_AOB_sep_O_sub_2_sup_I_sep_P27 / (K_sub_AOB_sep_O_sub_2_sup_I_sep_P27 + S_sub_O_sub_2)) * X_sub_AOB",
    "P28": "b_sub_AOB * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_AOB",
    "P29": "b_sub_AOB * eta_sub_N_sep_end * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_AOB",
    "P30": "mu_sub_NOB * (S_sub_O_sub_2 / (K_sub_NOB_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_NO_sub_2 / (K_sub_NOB_sep_NO_sub_2 + S_sub_NO_sub_2)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_NOB",
    "P31": "b_sub_NOB * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_NOB",
    "P32": "b_sub_NOB * eta_sub_N_sep_end * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_NOB",
    "P33": "q_sub_PHA * (S_sub_S / (K_sub_PAO_sep_S + S_sub_S)) * ((X_sub_PP / X_sub_PAO) / (K_sub_PAO_sep_PP + X_sub_PP / X_sub_PAO)) * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (K_sub_PAO_sep_NO_sub_3_inh / (K_sub_PAO_sep_NO_sub_3_inh + S_sub_NO_sub_3)) * X_sub_PAO",
    "P34": "q_sub_PP * (S_sub_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PS + S_sub_PO_sub_4)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * ((K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO) / (K_sub_IPP + K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO)) * X_sub_PAO",
    "P35": "q_sub_PP * eta_sub_PAO_sep_NO_sub_3 * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_PAO_sep_NO_sub_3 + S_sub_NO_sub_3)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PS + S_sub_PO_sub_4)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * ((K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO) / (K_sub_IPP + K_sub_PP_sep_MAX - X_sub_PP / X_sub_PAO)) * X_sub_PAO",
    "P36": "mu_sub_PAO * (S_sub_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_PAO_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PO_sub_4 + S_sub_PO_sub_4)) * (S_sub_ALK / (K_sub_PAO_sep_ALK + S_sub_ALK)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * X_sub_PAO",
    "P37": "mu_sub_PAO * eta_sub_PAO_sep_NO_sub_3 * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_PAO_sep_NO_sub_3 + S_sub_NO_sub_3)) * (S_sub_NH_sub_4 / (K_sub_PAO_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_PO_sub_4 / (K_sub_PAO_sep_PO_sub_4 + S_sub_PO_sub_4)) * (S_sub_ALK / (K_sub_PAO_sep_ALK + S_sub_ALK)) * ((X_sub_PHA / X_sub_PAO) / (K_sub_PAO_sep_PHA + X_sub_PHA / X_sub_PAO)) * X_sub_PAO",
    "P38": "b_sub_PAO * (S_sub_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_PAO",
    "P39": "b_sub_PAO * eta_sub_PAO_sep_end * (K_sub_PAO_sep_O_sub_2 / (K_sub_PAO_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_PAO_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_PAO",
    "P40": "b_sub_PP * X_sub_PP",
    "P41": "b_sub_PHA * X_sub_PHA",
}


# ============================================================================
# 3b. Simplified-model rates SIMPLIFIED_RATES: S1-S9
# ============================================================================
SIMPLIFIED_RATES = {
    "S1": "k_sub_H * ((X_sub_S / X_sub_H) / (K_sub_X + X_sub_S / X_sub_H)) * X_sub_H",
    "S2": "mu_sub_H * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * X_sub_H",
    "S3": "mu_sub_H * eta_sub_H_sep_NO_sub_3 * (S_sub_S / (K_sub_H_sep_SS + S_sub_S)) * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_ALK / (K_sub_H_sep_ALK + S_sub_ALK)) * X_sub_H",
    "S4": "b_sub_H_sep_O_sub_2 * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_H",
    "S5": "b_sub_H_sep_O_sub_2 * eta_sub_H_sep_end_NO_sub_3 * (K_sub_H_sep_O_sub_2_inh / (K_sub_H_sep_O_sub_2_inh + S_sub_O_sub_2)) * (S_sub_NO_sub_3 / (K_sub_H_sep_NO_sub_3 + S_sub_NO_sub_3)) * X_sub_H",
    "S6": "mu_sub_AOB_sup_AMO * (S_sub_NH_sub_4 / (K_sub_AOB_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_O_sub_2 / (K_sub_AOB_sep_O_sub_2_sup_AMO + S_sub_O_sub_2)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_AOB",
    "S7": "mu_sub_NOB * (S_sub_O_sub_2 / (K_sub_NOB_sep_O_sub_2 + S_sub_O_sub_2)) * (S_sub_NH_sub_4 / (K_sub_H_sep_NH_sub_4 + S_sub_NH_sub_4)) * (S_sub_NO_sub_2 / (K_sub_NOB_sep_NO_sub_2 + S_sub_NO_sub_2)) * (S_sub_ALK / (K_sub_N_sep_ALK + S_sub_ALK)) * X_sub_NOB",
    "S8": "b_sub_AOB * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_AOB",
    "S9": "b_sub_NOB * (S_sub_O_sub_2 / (K_sub_H_sep_O_sub_2 + S_sub_O_sub_2)) * X_sub_NOB",
}

# Merge so global STOICHIOMETRY / RATE_EQUATIONS include both P1-P41 and S1-S9.
STOICHIOMETRY.update(SIMPLIFIED_STOICHIOMETRY)
RATE_EQUATIONS.update(SIMPLIFIED_RATES)


# ============================================================================
# 4. Default parameter values PARAMS
#    Parameter values are externalized to script/param.json to avoid embedding large parameter blocks in source code.
# ============================================================================


def _load_params() -> dict[str, float]:
    param_path = Path(__file__).resolve().parent / "param.json"
    if not param_path.exists():
        raise FileNotFoundError(f"Parameter file is missing: {param_path}")
    raw = json.loads(param_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("The top level of param.json must be a JSON object")
    return {str(k): float(v) for k, v in raw.items()}


PARAMS = _load_params()


def _extract_model_param_subset(modelcomplex: str, source_params: dict[str, float]) -> dict[str, float]:
    """Extract the parameter subset relevant to the current modelcomplex."""
    if modelcomplex not in REACTIONS_BY_MODEL:
        raise ValueError(f"Unknown modelcomplex={modelcomplex}")
    active_tokens: set[str] = set()
    for rid in REACTIONS_BY_MODEL[modelcomplex]:
        active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", RATE_EQUATIONS[rid]))
        for coeff_expr in STOICHIOMETRY[rid].values():
            if isinstance(coeff_expr, str):
                active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", coeff_expr))
    return {name: float(source_params[name]) for name in source_params if name in active_tokens}


# ============================================================================
# 4b. Model-complexity configuration COMPONENTS_BY_MODEL / REACTIONS_BY_MODEL
#   SimplifiedCODN  : simplified COD-nitrogen model: 13 components / 9 equivalent reactions
#   CompleteNRN2O   : complete denitrification + N2O: 17 components / P1-P32
#   EBPRCODN        : simplified COD-nitrogen + EBPR phosphorus removal: 17 components / S1-S9 + P33-P41
#   IntegratedNPR   : complete extended ASM2d/ASM3: 21 components / P1-P41
# ============================================================================
COMPONENTS_BY_MODEL = {
    "SimplifiedCODN": [
        "S_sub_S", "S_sub_I", "X_sub_S", "X_sub_I",
        "S_sub_NH_sub_4", "S_sub_NO_sub_2", "S_sub_NO_sub_3", "S_sub_N_sub_2",
        "S_sub_O_sub_2", "S_sub_ALK",
        "X_sub_H", "X_sub_AOB", "X_sub_NOB",
    ],
    "CompleteNRN2O": [
        "S_sub_S", "S_sub_I", "X_sub_S", "X_sub_I",
        "S_sub_NH_sub_4", "S_sub_NO_sub_2", "S_sub_NO_sub_3",
        "S_sub_NH_sub_2OH", "S_sub_NO", "S_sub_N_sub_2O", "S_sub_N_sub_2",
        "S_sub_O_sub_2", "S_sub_ALK",
        "X_sub_H", "X_sub_AOB", "X_sub_NOB",
        "X_sub_STO",
    ],
    "EBPRCODN": [
        "S_sub_S", "S_sub_I", "X_sub_S", "X_sub_I",
        "S_sub_NH_sub_4", "S_sub_NO_sub_2", "S_sub_NO_sub_3", "S_sub_N_sub_2",
        "S_sub_O_sub_2", "S_sub_ALK",
        "X_sub_H", "X_sub_AOB", "X_sub_NOB",
        "S_sub_PO_sub_4", "X_sub_PP", "X_sub_PAO", "X_sub_PHA",
    ],
    "IntegratedNPR": list(COMPONENTS),
}

REACTIONS_BY_MODEL = {
    "SimplifiedCODN": [f"S{i}" for i in range(1, 10)],
    "CompleteNRN2O":  [f"P{i}" for i in range(1, 33)],
    "EBPRCODN":       [f"S{i}" for i in range(1, 10)] + [f"P{i}" for i in range(33, 42)],
    "IntegratedNPR":  [f"P{i}" for i in range(1, 42)],
}


# ============================================================================
# 5. Expression precompilation: rates + stoichiometry, strings -> code objects for faster eval
# ============================================================================
_SAFE_FUNCS = {"exp": math.exp, "log": math.log, "sqrt": math.sqrt,
               "max": max, "min": min, "abs": abs}
_SAFE_GLOBALS = {"__builtins__": {}, **_SAFE_FUNCS}
_EPS = 1e-9
_BIOMASS_NAMES = ("X_sub_H", "X_sub_PAO", "X_sub_AOB", "X_sub_NOB")

# Precompile all rate and stoichiometry expressions once at startup; later eval calls use code objects directly.
_COMPILED_RATES = {k: compile(v, f"<rate:{k}>", "eval") for k, v in RATE_EQUATIONS.items()}
_COMPILED_STOICH = {
    rid: {c: (compile(v, f"<stoich:{rid}:{c}>", "eval") if isinstance(v, str) else float(v))
          for c, v in coeffs.items()}
    for rid, coeffs in STOICHIOMETRY.items()
}


# ============================================================================
# 6. ODE right-hand-side factory
#   - Stoichiometric coefficients depend only on PARAMS and are evaluated once into nu_table during factory construction.
#   - The rhs hot path evaluates only active precompiled rates, then applies dy[j] += nu * rho.
#   - Callers must rebuild rhs after PARAMS changes; _solve in this file wraps that behavior.
# ============================================================================
def make_rhs(components: list, stoich: dict, rates: dict,
             boundary_terms=None, params_env: dict | None = None):
    n_comp = len(components)
    comp_index = {c: i for i, c in enumerate(components)}
    biom_idx = [comp_index[b] for b in _BIOMASS_NAMES if b in comp_index]

    # Precompute stoichiometric coefficients once with the current PARAMS, yielding a flat (comp_idx, nu) table.
    params_env = dict(PARAMS) if params_env is None else dict(params_env)
    rate_codes = []
    nu_table = []
    for rid in rates:
        rate_codes.append(_COMPILED_RATES[rid])
        per_rxn = []
        for c, coeff in _COMPILED_STOICH[rid].items():
            j = comp_index.get(c)
            if j is None:
                continue
            nu = coeff if isinstance(coeff, float) else float(eval(coeff, _SAFE_GLOBALS, params_env))
            per_rxn.append((j, nu))
        nu_table.append(per_rxn)

    def rhs(t, y):
        state = {}
        for i, c in enumerate(components):
            v = y[i]
            state[c] = v if v > 0.0 else 0.0
        for i in biom_idx:
            c = components[i]
            if state[c] < _EPS:
                state[c] = _EPS

        env = {**params_env, **state}
        dy = [0.0] * n_comp
        for k, code in enumerate(rate_codes):
            rho = eval(code, _SAFE_GLOBALS, env)
            for j, nu in nu_table[k]:
                dy[j] += nu * rho
        if boundary_terms is not None:
            try:
                extra = boundary_terms(t, state, env) or {}
            except Exception:
                extra = {}
            for c, v in extra.items():
                j = comp_index.get(c)
                if j is not None:
                    try:
                        dy[j] += float(v)
                    except (TypeError, ValueError):
                        pass
        return dy
    return rhs


# ============================================================================
# 6a. Six boundary types as mass-conservation addenda. Any None parameter disables that term; non-empty values are assembled into bt.
#   Fixed form: dC/dt += [aeration] + [internal_recycle] + [RAS] + [hydraulic] + [carbon_dose] + [chem_dose]
# ============================================================================
def _build_boundary_terms(
    *,
    components: list,
    initial_state: dict,
    df_first_row: dict,
    aeration: dict | None = None,
    internal_recycle: dict | None = None,
    ras_recycle: dict | None = None,
    hydraulic: dict | None = None,
    carbon_dose: dict | None = None,
    chem_dose: dict | None = None,
):
    # Pre-freeze constants
    C_RAS = None
    if ras_recycle is not None:
        factor = ras_recycle.get("factor", 2.0)
        C_RAS = {c: factor * initial_state.get(c, 0.0)
                 for c in components if c.startswith("X_sub_")}
    C_in = None
    if hydraulic is not None:
        C_in = hydraulic.get("C_in") or {c: df_first_row.get(c, 0.0) for c in components}

    def bt(t, state, env):
        extra: dict = {}
        # 1. Aeration, strong or low: K_L_a * (S_O_sat - S_O2), applied only to S_sub_O_sub_2
        if aeration is not None:
            kla = float(aeration["K_L_a"])
            sat = float(aeration["S_O_sat"])
            extra["S_sub_O_sub_2"] = extra.get("S_sub_O_sub_2", 0.0) + kla * (sat - state.get("S_sub_O_sub_2", 0.0))
        # 2. Internal recycle: k_r * (C_ref - C); keys other than k_r are target components and reference concentrations.
        if internal_recycle is not None:
            k_r = float(internal_recycle["k_r"])
            for c, ref in internal_recycle.items():
                if c == "k_r" or c not in state:
                    continue
                extra[c] = extra.get(c, 0.0) + k_r * (float(ref) - state[c])
        # 3. Sludge recycle: k_RAS * (C_RAS - C), all X_sub_*; C_RAS = factor * y0(X_*)
        if ras_recycle is not None:
            k_RAS = float(ras_recycle["k_RAS"])
            for c, c_ras in C_RAS.items():
                if c in state:
                    extra[c] = extra.get(c, 0.0) + k_RAS * (c_ras - state[c])
        # 4. Hydraulic connection: k_HRT * (C_in - C), all 21 components; C_in defaults to the first xlsx row.
        if hydraulic is not None:
            k_HRT = float(hydraulic["k_HRT"])
            for c, c_in in C_in.items():
                if c in state:
                    extra[c] = extra.get(c, 0.0) + k_HRT * (float(c_in) - state[c])
        # 5. External carbon dosing: constant source term r_dose, applied only to S_sub_S and always positive.
        if carbon_dose is not None:
            extra["S_sub_S"] = extra.get("S_sub_S", 0.0) + float(carbon_dose["r_dose"])
        # 6. Chemical dosing: constant sink term r_chem, applied only to S_sub_PO_sub_4 and always negative.
        if chem_dose is not None:
            extra["S_sub_PO_sub_4"] = extra.get("S_sub_PO_sub_4", 0.0) + float(chem_dose["r_chem"])
        return extra

    return bt


# ============================================================================
# 6b. Intermediate process plots: 8 figures, fig1-fig8, dpi=600
#   Common across calibmode: fig1 obs vs baseline, fig2 fitted R2 (single/total), fig3 sensitivity heatmap, fig4 Top-K bar, fig5 tornado
#   fig6 total cost convergence, shared by all modes; ParetoMOEA uses sum(NRMSEs)
#   fig7: SingleNRMSE -> residual_timeseries; WeightedNRMSE -> cost_residual; ParetoMOEA -> pareto_front
#   fig8 parameter pair plot, shared by all modes and based on each mode's parameter trajectory in history
# ============================================================================
PARETO_R2_MIN = 0.30


def _r2_scores_for_traj(*, traj, target_names, components, df_obs):
    scores = {}
    for tgt in target_names:
        j = components.index(tgt)
        obs = df_obs[tgt].to_numpy()
        sim = traj[j]
        ss_res = float(np.sum((obs - sim) ** 2))
        ss_tot = float(np.sum((obs - obs.mean()) ** 2))
        scores[tgt] = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    overall = float(np.mean(list(scores.values()))) if scores else 0.0
    return scores, overall


def _select_pareto_representative(*, pareto_F, pareto_trajs, target_names,
                                  components, df_obs, r2_min=PARETO_R2_MIN):
    """Pick the Pareto point used as the representative fitted solution.

    Rule: first require every target R2 >= r2_min, then minimize sum(NRMSE).
    If no point satisfies the R2 floor, fall back to the smallest sum(NRMSE)
    and mark the selection as unqualified so exports make the issue visible.
    """
    F = np.atleast_2d(pareto_F)
    rows = []
    eligible = []
    for i, (fi, traj) in enumerate(zip(F, pareto_trajs)):
        r2_scores, r2_overall = _r2_scores_for_traj(
            traj=traj, target_names=target_names, components=components, df_obs=df_obs)
        sum_nrmse = float(np.sum(fi))
        qualified = all(float(r2_scores[t]) >= r2_min for t in target_names)
        row = {
            "pareto_idx": i,
            "sum_nrmse": sum_nrmse,
            "r2": r2_scores,
            "r2_overall_mean": r2_overall,
            "r2_min": float(min(r2_scores.values())) if r2_scores else 0.0,
            "r2_qualified": bool(qualified),
        }
        rows.append(row)
        if qualified:
            eligible.append(i)

    if eligible:
        best_idx = min(eligible, key=lambda i: rows[i]["sum_nrmse"])
        reason = f"all_targets_r2_ge_{r2_min:g}_then_min_sum_nrmse"
    else:
        best_idx = int(np.argmin([row["sum_nrmse"] for row in rows]))
        reason = f"fallback_no_point_met_all_targets_r2_ge_{r2_min:g}_min_sum_nrmse"

    return best_idx, rows, reason


def _make_plots(*, calibmode, target_names, components, t_eval_h, df_obs, Y_baseline,
                sens_records, topk_names, history, recovered_traj,
                pareto_X, pareto_F, pareto_trajs, figs_dir: Path):
    import matplotlib.pyplot as plt

    figs_dir.mkdir(parents=True, exist_ok=True)
    n_tgt = len(target_names)
    pareto_selection = None

    # ---- fig1: obs vs baseline sim (A2) ----
    fig, axes = plt.subplots(1, n_tgt, figsize=(5 * n_tgt, 4), squeeze=False)
    for k, tgt in enumerate(target_names):
        ax = axes[0, k]
        j = components.index(tgt)
        ax.plot(t_eval_h, df_obs[tgt].to_numpy(), "o", markersize=4, label="obs")
        ax.plot(t_eval_h, Y_baseline[j], "-", label="sim (baseline)")
        ax.set_xlabel("t (h)")
        ax.set_ylabel(tgt)
        ax.set_title(f"{tgt}: obs vs baseline sim")
        ax.legend()
        ax.grid(alpha=0.3)
    fig.tight_layout()
    # data export (fig1): long format
    _rows = []
    for tgt in target_names:
        j = components.index(tgt)
        for i, t in enumerate(t_eval_h):
            _rows.append({"t_h": float(t), "target": tgt,
                          "obs": float(df_obs[tgt].iloc[i]),
                          "sim_baseline": float(Y_baseline[j, i])})
    pd.DataFrame(_rows).to_excel(figs_dir / "fig1_data.xlsx", index=False)
    fig.savefig(figs_dir / "fig1_obs_vs_sim_baseline.png", dpi=600)
    plt.close(fig)

    # ---- fig2: coefficient of determination R2 (baseline vs fitted, single target + total) ----
    if recovered_traj is not None:
        fitted_traj = recovered_traj
        fitted_source = "recovered"
    elif pareto_trajs and pareto_F is not None and len(pareto_trajs) > 0:
        best_idx, pareto_rows, selection_reason = _select_pareto_representative(
            pareto_F=pareto_F,
            pareto_trajs=pareto_trajs,
            target_names=target_names,
            components=components,
            df_obs=df_obs,
        )
        fitted_traj = pareto_trajs[best_idx]
        fitted_source = f"pareto_r2_floor_sum_nrmse_{best_idx + 1}"
        pareto_selection = {
            "rule": f"all target R2 >= {PARETO_R2_MIN:g}, then minimize sum(NRMSE)",
            "r2_min_threshold": PARETO_R2_MIN,
            "selected_pareto_idx": best_idx,
            "selected_point_number": best_idx + 1,
            "selection_reason": selection_reason,
            **pareto_rows[best_idx],
        }
    else:
        fitted_traj = Y_baseline
        fitted_source = "baseline_fallback"

    r2_baseline, r2_baseline_overall = _r2_scores_for_traj(
        traj=Y_baseline, target_names=target_names, components=components, df_obs=df_obs)
    r2_fitted, r2_fitted_overall = _r2_scores_for_traj(
        traj=fitted_traj, target_names=target_names, components=components, df_obs=df_obs)

    fig, ax = plt.subplots(figsize=(max(6, n_tgt * 2), 5))
    labels = list(target_names) + ["Overall (mean)"]
    x = np.arange(len(labels))
    width = 0.38
    baseline_values = [r2_baseline[t] for t in target_names] + [r2_baseline_overall]
    fitted_values = [r2_fitted[t] for t in target_names] + [r2_fitted_overall]
    bars_base = ax.bar(x - width / 2, baseline_values, width, label="before fit")
    bars_fit = ax.bar(x + width / 2, fitted_values, width, label="after fit")
    for b, v in list(zip(bars_base, baseline_values)) + list(zip(bars_fit, fitted_values)):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.3f}",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("R²")
    ax.set_title("R² before vs after fitting: per-target and overall (mean)")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    # data export (fig2): baseline and fitted per-target R² + overall mean
    (figs_dir / "fig2_data.json").write_text(
        json.dumps({
            "baseline": {"source": "baseline", "per_target": r2_baseline,
                         "overall_mean": r2_baseline_overall},
            "fitted": {"source": fitted_source, "per_target": r2_fitted,
                       "overall_mean": r2_fitted_overall},
            "pareto_selection": pareto_selection,
        },
                   ensure_ascii=False, indent=2), encoding="utf-8")
    fig.savefig(figs_dir / "fig2_r2.png", dpi=600)
    plt.close(fig)

    # ---- fig3: all-parameter by target sensitivity heatmap (A5) ----
    all_params = [r["parameter"] for r in sens_records]
    mat = np.array([[r[t] for t in target_names] for r in sens_records])
    fig, ax = plt.subplots(figsize=(max(4, n_tgt * 2), max(6, len(all_params) * 0.22)))
    im = ax.imshow(mat, aspect="auto", cmap="viridis")
    ax.set_xticks(range(n_tgt))
    ax.set_xticklabels(target_names, rotation=30, ha="right")
    ax.set_yticks(range(len(all_params)))
    ax.set_yticklabels(all_params, fontsize=6)
    plt.colorbar(im, ax=ax, label="|sensitivity|")
    ax.set_title("Sensitivity heatmap: all params × targets")
    fig.tight_layout()
    # data export (fig3): full sens matrix (params × targets)
    pd.DataFrame(mat, index=all_params, columns=target_names).to_excel(
        figs_dir / "fig3_data.xlsx", index_label="parameter")
    fig.savefig(figs_dir / "fig3_sensitivity_heatmap.png", dpi=600)
    plt.close(fig)

    # ---- fig4: Top-K combined sensitivity bar chart (A3) ----
    topk_recs = [r for r in sens_records if r["parameter"] in topk_names]
    topk_recs.sort(key=lambda r: r["combined"])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh([r["parameter"] for r in topk_recs], [r["combined"] for r in topk_recs])
    ax.set_xlabel("combined |sensitivity|")
    ax.set_title("Top-K parameters by combined sensitivity")
    fig.tight_layout()
    # data export (fig4): topk parameters with combined sensitivity, ascending order aligned with the plot
    pd.DataFrame([{"parameter": r["parameter"], "combined": r["combined"]}
                  for r in topk_recs]).to_excel(
        figs_dir / "fig4_data.xlsx", index=False)
    fig.savefig(figs_dir / "fig4_topk_sensitivity.png", dpi=600)
    plt.close(fig)

    # ---- fig5: Tornado (A6, signed, top-K) ----
    # Each parameter occupies 2*n_tgt independent subrows: (t1 +delta, t1 -delta, t2 +delta, t2 -delta, ...)
    n_sub = 2 * max(1, n_tgt)
    fig, ax = plt.subplots(figsize=(8, max(4, len(topk_names) * n_sub * 0.45)))
    y_pos = np.arange(len(topk_names))
    width = 0.85 / n_sub
    for k, tgt in enumerate(target_names):
        plus_vals, minus_vals = [], []
        for name in topk_names:
            rec = next(r for r in sens_records if r["parameter"] == name)
            plus_vals.append(rec["signed"][tgt]["plus"])
            minus_vals.append(rec["signed"][tgt]["minus"])
        # Row 0 is the top row; row n_sub-1 is the bottom row.
        offset_plus = ((n_sub - 1) / 2 - 2 * k) * width
        offset_minus = ((n_sub - 1) / 2 - (2 * k + 1)) * width
        ax.barh(y_pos + offset_plus, plus_vals, height=width * 0.85,
                color=f"C{2 * k}", alpha=0.85, label=f"{tgt}: +δ")
        ax.barh(y_pos + offset_minus, minus_vals, height=width * 0.85,
                color=f"C{2 * k + 1}", alpha=0.85, label=f"{tgt}: −δ")
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(topk_names)
    ax.set_xlabel("normalized response (signed)")
    ax.set_title("Tornado: signed response of top-K params")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    # data export (fig5): topk × target × ±δ signed responses
    _rows = []
    for name in topk_names:
        rec = next(r for r in sens_records if r["parameter"] == name)
        for tgt in target_names:
            sgn = rec["signed"][tgt]
            _rows.append({"parameter": name, "target": tgt,
                          "plus_delta": float(sgn["plus"]),
                          "minus_delta": float(sgn["minus"])})
    pd.DataFrame(_rows).to_excel(figs_dir / "fig5_data.xlsx", index=False)
    fig.savefig(figs_dir / "fig5_tornado.png", dpi=600)
    plt.close(fig)

    # ---- fig6: total cost convergence, history shared across all modes ----
    costs = [h["cost"] for h in history]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(range(len(costs)), costs)
    ax.set_xlabel("evaluation #")
    if calibmode == "ParetoMOEA":
        ax.set_ylabel("total cost (sum of NRMSEs)")
        ax.set_title("Total cost convergence (NSGA-II)")
    else:
        ax.set_ylabel("cost (weighted NRMSE)")
        ax.set_title("Cost convergence (Nelder-Mead)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    # data export (fig6): eval_idx + cost + per-target NRMSE
    _rows = [{"eval_idx": i, "cost": float(h["cost"]),
              **{t: float(h[t]) for t in target_names}}
             for i, h in enumerate(history)]
    pd.DataFrame(_rows).to_excel(figs_dir / "fig6_data.xlsx", index=False)
    fig.savefig(figs_dir / "fig6_cost_convergence.png", dpi=600)
    plt.close(fig)

    # ---- fig7: branch by calibmode ----
    if calibmode == "SingleNRMSE":
        # Residual time series: per-target NRMSE degenerates for a single target, so residuals are used instead.
        tgt = target_names[0]
        j = components.index(tgt)
        obs = df_obs[tgt].to_numpy()
        sim = recovered_traj[j]
        residual = obs - sim
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(t_eval_h, residual, "o-", label="obs − sim (recovered)")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_xlabel("t (h)")
        ax.set_ylabel(f"residual {tgt}")
        ax.set_title("Recovered-fit residual time series")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        # data export (fig7-SingleNRMSE)
        pd.DataFrame({"t_h": t_eval_h.astype(float),
                      "obs": obs.astype(float),
                      "sim_recovered": sim.astype(float),
                      "residual": residual.astype(float)}).to_excel(
            figs_dir / "fig7_data.xlsx", index=False)
        fig.savefig(figs_dir / "fig7_residual_timeseries.png", dpi=600)
        plt.close(fig)
    elif calibmode == "WeightedNRMSE":
        # Cost residual (optimality gap): cost(i) - cost_min, with log Y-axis to show convergence rate.
        cost_min = min(costs)
        eps = 1e-12
        residuals = [max(c - cost_min, eps) for c in costs]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.semilogy(range(len(residuals)), residuals)
        ax.set_xlabel("evaluation #")
        ax.set_ylabel("cost − cost_min (log scale)")
        ax.set_title("Cost residual (optimality gap)")
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout()
        # data export (fig7-WeightedNRMSE)
        pd.DataFrame({"eval_idx": list(range(len(residuals))),
                      "cost": [float(c) for c in costs],
                      "cost_min": [float(cost_min)] * len(residuals),
                      "residual": [float(r) for r in residuals]}).to_excel(
            figs_dir / "fig7_data.xlsx", index=False)
        fig.savefig(figs_dir / "fig7_cost_residual.png", dpi=600)
        plt.close(fig)
    else:  # ParetoMOEA
        # Pareto-front scatter, moved from the original fig6
        fig, ax = plt.subplots(figsize=(7, 6))
        best_idx = None
        pareto_rows = []
        selection_reason = None
        if pareto_trajs and pareto_F is not None and len(pareto_trajs) > 0:
            best_idx, pareto_rows, selection_reason = _select_pareto_representative(
                pareto_F=pareto_F,
                pareto_trajs=pareto_trajs,
                target_names=target_names,
                components=components,
                df_obs=df_obs,
            )
        if n_tgt >= 2:
            ax.scatter(pareto_F[:, 0], pareto_F[:, 1], s=60, c="red", edgecolor="black")
            if best_idx is not None:
                ax.scatter(pareto_F[best_idx, 0], pareto_F[best_idx, 1],
                           s=180, marker="*", c="gold", edgecolor="black",
                           linewidth=1.0, label="selected: R2 floor + min sum NRMSE", zorder=5)
            ax.set_xlabel(f"{target_names[0]} (NRMSE)")
            ax.set_ylabel(f"{target_names[1]} (NRMSE)")
        else:
            ax.scatter(range(len(pareto_F)), pareto_F[:, 0], s=60, c="red", edgecolor="black")
            if best_idx is not None:
                ax.scatter(best_idx, pareto_F[best_idx, 0],
                           s=180, marker="*", c="gold", edgecolor="black",
                           linewidth=1.0, label="selected: R2 floor + min sum NRMSE", zorder=5)
            ax.set_xlabel("solution index")
            ax.set_ylabel(f"{target_names[0]} (NRMSE)")
        ax.set_title("Pareto front (NSGA-II)")
        if best_idx is not None:
            ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        # data export (fig7-ParetoMOEA): Pareto X (parameters) + F (objective values)
        _rows = []
        for i in range(len(pareto_F)):
            row = {"pareto_idx": i}
            for k, name in enumerate(topk_names):
                row[name] = float(pareto_X[i, k])
            for k, t in enumerate(target_names):
                row[f"{t}_NRMSE"] = float(pareto_F[i, k])
            if pareto_rows:
                row["sum_NRMSE"] = float(pareto_rows[i]["sum_nrmse"])
                row["r2_min_threshold"] = float(PARETO_R2_MIN)
                row["r2_qualified"] = bool(pareto_rows[i]["r2_qualified"])
                row["selected_for_fig2"] = bool(i == best_idx)
                row["selection_reason"] = selection_reason if i == best_idx else ""
                row["R2_overall_mean"] = float(pareto_rows[i]["r2_overall_mean"])
                row["R2_min"] = float(pareto_rows[i]["r2_min"])
                for t in target_names:
                    row[f"{t}_R2"] = float(pareto_rows[i]["r2"][t])
            _rows.append(row)
        pd.DataFrame(_rows).to_excel(figs_dir / "fig7_data.xlsx", index=False)
        fig.savefig(figs_dir / "fig7_pareto_front.png", dpi=600)
        plt.close(fig)

    # ---- fig8: parameter pair plot, shared by all modes and using each mode's parameter trajectory in history ----
    from pandas.plotting import scatter_matrix
    df_h = pd.DataFrame({n: [h["x"][k] for h in history] for k, n in enumerate(topk_names)})
    df_h["cost"] = costs
    # data export (fig8): topk parameter trajectory + cost
    df_h.to_excel(figs_dir / "fig8_data.xlsx", index_label="eval_idx")
    axes_pp = scatter_matrix(df_h, diagonal="hist", figsize=(8, 8), s=10, alpha=0.5)
    fig_pp = axes_pp[0, 0].figure
    traj_label = "NSGA-II trajectory" if calibmode == "ParetoMOEA" else "Nelder-Mead trajectory"
    fig_pp.suptitle(f"Parameter pair plot ({traj_label})", y=0.98)
    fig_pp.tight_layout()
    fig_pp.savefig(figs_dir / "fig8_pair_plot.png", dpi=600)
    plt.close(fig_pp)


# ============================================================================
# 7. Main workflow: baseline simulation + Step 7 sensitivity + Step 8 equal-weight calibration
# ============================================================================
_BOUNDARY_KEYS = ("aeration", "internal_recycle", "ras_recycle",
                  "hydraulic", "carbon_dose", "chem_dose")


def _validate_boundaries_schema(boundaries: dict | None) -> None:
    """Validate boundary shape; numeric conversion happens during assembly/computation."""
    if boundaries is None:
        return
    if not isinstance(boundaries, dict):
        raise TypeError("boundaries must be a dict or None")
    extra = [k for k in boundaries if k not in _BOUNDARY_KEYS]
    if extra:
        raise ValueError(f"boundaries contains illegal keys {extra}; only {list(_BOUNDARY_KEYS)} are allowed")
    for k in _BOUNDARY_KEYS:
        v = boundaries.get(k)
        if v is not None and not isinstance(v, dict):
            raise TypeError(f"boundaries[{k}] must be a dict or None")


def _resolve_run_root(sens_path: Path | None, calib_path: Path | None, figs_dir: Path | None) -> Path:
    if sens_path is not None:
        return Path(sens_path).resolve().parent.parent
    if calib_path is not None:
        return Path(calib_path).resolve().parent.parent
    if figs_dir is not None:
        return Path(figs_dir).resolve().parent
    return Path(__file__).resolve().parent.parent


def run_pipeline(
    *,
    # Ordered by first use within the function body:
    modelcomplex: str = "IntegratedNPR",  # ["SimplifiedCODN","CompleteNRN2O","EBPRCODN","IntegratedNPR"]
    calibmode: str = "WeightedNRMSE",     # ["SingleNRMSE","WeightedNRMSE","ParetoMOEA"]
    sens_targets: dict,                   # {target_name: weight, ...}; carries both targets and weights
    xlsx_path: Path,
    sens_delta: float,
    senstopk: int = 4,
    maxiter: int = 100,
    npareto_target: int = 10,
    boundary_terms=None,
    params: dict | None = None,
    # sens_path / calib_path default to <project root>/midoutput; task runners may override them to <task dir>/midoutput.
    # Six boundary types, default None means disabled. Any non-None value enables and assembles the term into boundary_terms.
    aeration: dict | None = None,           # {"K_L_a": ..., "S_O_sat": ...}; only S_sub_O_sub_2
    internal_recycle: dict | None = None,   # {"k_r": ..., "<comp>": <ref>, ...}; multiple components
    ras_recycle: dict | None = None,        # {"k_RAS": ..., "factor": 2.0}; all X_sub_*
    hydraulic: dict | None = None,          # {"k_HRT": ..., "C_in": dict | None}; None means first xlsx row
    carbon_dose: dict | None = None,        # {"r_dose": ...}; only S_sub_S
    chem_dose: dict | None = None,          # {"r_chem": ...}; only S_sub_PO_sub_4
    # Nested six-boundary form, default None means all six items are empty. When provided, keys override the six separate kwargs above.
    # Example: {"aeration": None, "internal_recycle": None,
    #       "ras_recycle": {"k_RAS": 0.5, "factor": 2.0},
    #       "hydraulic": None, "carbon_dose": None, "chem_dose": None}
    boundaries: dict | None = None,
    figs_dir: Path | None = None,
    sens_path: Path | None = None,
    calib_path: Path | None = None,
):
    # ---- sens_path / calib_path default location, relative to this file: ../midoutput/; task-dir runners may override it ----
    _root = Path(__file__).resolve().parent.parent
    sens_path = Path(sens_path) if sens_path is not None else _root / "midoutput" / "sensitivity.json"
    calib_path = Path(calib_path) if calib_path is not None else _root / "midoutput" / "calibration.json"
    sens_path.parent.mkdir(parents=True, exist_ok=True)
    calib_path.parent.mkdir(parents=True, exist_ok=True)
    run_root = _resolve_run_root(sens_path, calib_path, figs_dir)
    mid_dir = run_root / "midoutput"
    mid_dir.mkdir(parents=True, exist_ok=True)
    param_ori_path = mid_dir / "param_ori.json"
    param_ref_path = mid_dir / "param_ref.json"
    param_opt_path = mid_dir / "param_opt.json"

    # ---- Unpack nested boundaries: when provided, keys override the six separate kwargs ----
    _validate_boundaries_schema(boundaries)
    if boundaries is not None:
        aeration = boundaries.get("aeration", aeration)
        internal_recycle = boundaries.get("internal_recycle", internal_recycle)
        ras_recycle = boundaries.get("ras_recycle", ras_recycle)
        hydraulic = boundaries.get("hydraulic", hydraulic)
        carbon_dose = boundaries.get("carbon_dose", carbon_dose)
        chem_dose = boundaries.get("chem_dose", chem_dose)
    if params is not None and not isinstance(params, dict):
        raise TypeError("params must be a dict or None")
    # ---- Model-complexity selection: active components / reactions ----
    if modelcomplex not in COMPONENTS_BY_MODEL:
        raise ValueError(
            f"Unknown modelcomplex={modelcomplex}; options are {list(COMPONENTS_BY_MODEL)}"
        )
    components = COMPONENTS_BY_MODEL[modelcomplex]
    rxn_keys = REACTIONS_BY_MODEL[modelcomplex]
    stoich = {k: STOICHIOMETRY[k] for k in rxn_keys}
    rates = {k: RATE_EQUATIONS[k] for k in rxn_keys}
    print(f"[model] modelcomplex={modelcomplex}: {len(components)} components, {len(rxn_keys)} reactions")
    model_params = dict(PARAMS)
    if params is not None:
        for k, v in params.items():
            if k in model_params:
                model_params[k] = float(v)
    param_ori = _extract_model_param_subset(modelcomplex, PARAMS)
    param_ref = _extract_model_param_subset(modelcomplex, model_params)
    param_ori_path.write_text(json.dumps(param_ori, ensure_ascii=False, indent=2), encoding="utf-8")
    param_ref_path.write_text(json.dumps(param_ref, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Calibration-mode validation; weight sums are not checked and remain caller-reviewed ----
    if calibmode not in ("SingleNRMSE", "WeightedNRMSE", "ParetoMOEA"):
        raise ValueError(
            f"Unknown calibmode={calibmode}; options are ['SingleNRMSE','WeightedNRMSE','ParetoMOEA']"
        )
    if not isinstance(sens_targets, dict):
        raise TypeError("sens_targets must be a dict shaped as {target: weight, ...}")
    if calibmode == "SingleNRMSE" and len(sens_targets) != 1:
        raise ValueError(f"SingleNRMSE requires exactly 1 sens_targets key; got {list(sens_targets)}")

    target_names = list(sens_targets.keys())
    weights_dict = {t: float(sens_targets[t]) for t in target_names}
    print(f"[calib] calibmode={calibmode}, targets={target_names}, weights={weights_dict}")

    # ---- Read data.xlsx: row 0 = initial values; t_h column = time grid; target columns = observations ----
    df_obs = pd.read_excel(xlsx_path)
    if "t_h" not in df_obs.columns:
        raise ValueError(f"{xlsx_path.name} is missing the 't_h' column")
    df_obs["t_h"] = pd.to_numeric(df_obs["t_h"], errors="coerce")
    df_obs = (
        df_obs.dropna(subset=["t_h"])
        .sort_values("t_h", kind="mergesort")
        .drop_duplicates(subset=["t_h"], keep="first")
        .reset_index(drop=True)
    )
    missing = [c for c in components if c not in df_obs.columns]
    if missing:
        raise ValueError(f"{xlsx_path.name} is missing component columns: {missing}")
    for tgt in target_names:
        if tgt not in components:
            raise ValueError(f"sens_target {tgt} is not active for modelcomplex={modelcomplex}")

    t_eval_h = df_obs["t_h"].to_numpy(dtype=float)
    T_END_H = float(t_eval_h[-1])
    initial_state = {c: float(df_obs[c].iloc[0]) for c in components}
    y0 = [initial_state[c] for c in components]

    # ---- Assemble six boundary types: any non-None value enables a term; explicit boundary_terms take precedence ----
    if boundary_terms is None and any(b is not None for b in (
        aeration, internal_recycle, ras_recycle, hydraulic, carbon_dose, chem_dose
    )):
        df_first_row = {c: float(df_obs[c].iloc[0]) for c in components}
        boundary_terms = _build_boundary_terms(
            components=components, initial_state=initial_state, df_first_row=df_first_row,
            aeration=aeration, internal_recycle=internal_recycle, ras_recycle=ras_recycle,
            hydraulic=hydraulic, carbon_dose=carbon_dose, chem_dose=chem_dose,
        )

    # ---- Step 6: baseline simulation + closure, rerun with temporary PARAMS replacement ----
    #   _solve: runs solve_ivp once under params_override. After PARAMS changes, rhs must be rebuilt
    #           because nu_table is frozen as a constant table inside make_rhs and depends on PARAMS at that time.
    def _solve(params_override):
        backup = {k: model_params[k] for k in params_override if k in model_params}
        model_params.update(params_override)
        try:
            rhs = make_rhs(components, stoich, rates,
                           boundary_terms=boundary_terms, params_env=model_params)
            return solve_ivp(rhs, (0.0, T_END_H), y0,
                             method="LSODA", rtol=1e-6, atol=1e-9, t_eval=t_eval_h)
        finally:
            model_params.update(backup)

    def _simulate_trajectory(params_override):
        sol2 = _solve(params_override)
        return np.clip(sol2.y, 0.0, None) if sol2.success else None

    def _simulate_finals(params_override):
        Y2 = _simulate_trajectory(params_override)
        if Y2 is None:
            return None
        return {c: float(Y2[i, -1]) for i, c in enumerate(components)}

    # Baseline simulation, used as the normalization baseline for Step 7 sensitivity.
    sol = _solve({})
    if not sol.success:
        raise RuntimeError(f"ODE solve failed: {sol.message}")
    Y = np.clip(sol.y, 0.0, None)
    final_state = {c: float(Y[i, -1]) for i, c in enumerate(components)}

    print(f"[input] {xlsx_path.name}: t=0->{T_END_H} h, {len(t_eval_h)} rows")

    # ---- Step 7: sensitivity analysis (OAT +/- sens_delta), iterating only PARAMS used by active reactions ----
    print(f"[sens] Starting sensitivity analysis: OAT +/-{sens_delta*100:.0f}%, targets={target_names}")
    active_tokens: set = set()
    for expr in rates.values():
        active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expr))
    for sd in stoich.values():
        for coeff_expr in sd.values():
            if isinstance(coeff_expr, str):
                active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", coeff_expr))
    active_param_names = [p for p in model_params if p in active_tokens]

    sens_records = []
    for pname in active_param_names:
        pval = model_params[pname]
        if pval == 0.0:
            continue
        dp = pval * sens_delta
        f_plus = _simulate_finals({pname: pval + dp})
        f_minus = _simulate_finals({pname: pval - dp})
        if f_plus is None or f_minus is None:
            continue
        s_per_tgt = {}
        signed_per_tgt = {}
        for tgt in target_names:
            y0_t = final_state[tgt]
            if abs(y0_t) < 1e-12:
                s_per_tgt[tgt] = 0.0
                signed_per_tgt[tgt] = {"plus": 0.0, "minus": 0.0}
            else:
                # Normalized perturbation response (signed), required for the tornado plot; mean absolute value = combined sensitivity.
                s_plus = (f_plus[tgt] - y0_t) / y0_t / sens_delta
                s_minus = (f_minus[tgt] - y0_t) / y0_t / sens_delta
                s_per_tgt[tgt] = abs((s_plus - s_minus) / 2.0)
                signed_per_tgt[tgt] = {"plus": float(s_plus), "minus": float(s_minus)}
        s_combined = sum(weights_dict[t] * s_per_tgt[t] for t in target_names)
        rec = {"parameter": pname, "value": float(pval)}
        rec.update(s_per_tgt)
        rec["combined"] = s_combined
        rec["signed"] = signed_per_tgt
        sens_records.append(rec)

    sens_records.sort(key=lambda r: r["combined"], reverse=True)
    topk = sens_records[:senstopk]
    topk_names = [r["parameter"] for r in topk]

    sens_out = {
        "_note": (
            f"Local OAT sensitivity (central difference, +/-{int(sens_delta*100)}%); "
            f"targets = {target_names}; weights = {weights_dict}; "
            "S_i = |(DeltaY/Y0)/(Deltap/p0)|; larger combined means stronger overall influence."
        ),
        "modelcomplex": modelcomplex,
        "calibmode": calibmode,
        "targets": target_names,
        "weights": weights_dict,
        "delta": sens_delta,
        "senstopk": senstopk,
        "topk": topk,
        "ranking": sens_records,
    }
    sens_path.write_text(json.dumps(sens_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {sens_path.name}  (top-{senstopk}: {topk_names})")

    # ---- Step 8: parameter calibration, with three branches by calibmode ----
    # obs_data: target columns directly from data.xlsx, aligned with t_eval_h.
    obs_data = {tgt: df_obs[tgt].to_numpy(dtype=float) for tgt in target_names}

    def _nrmse(obs, sim):
        denom = obs.mean() if obs.mean() > 1e-9 else 1.0
        return float(np.sqrt(np.mean((sim - obs) ** 2)) / denom)

    def _r2_scores(traj):
        per_target = {}
        for tgt in target_names:
            obs = obs_data[tgt]
            sim = traj[components.index(tgt)]
            ss_res = float(np.sum((obs - sim) ** 2))
            ss_tot = float(np.sum((obs - obs.mean()) ** 2))
            per_target[tgt] = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
        return {
            "per_target": per_target,
            "overall_mean": float(np.mean(list(per_target.values()))) if per_target else 0.0,
        }

    x0_cal = np.array([float(model_params[n]) for n in topk_names], dtype=float)

    # Placeholders assigned only in the corresponding branch; _make_plots consumes them by calibmode at the end.
    history = None
    recovered_traj = None
    pareto_X = None
    pareto_F = None
    pareto_trajs = None

    if calibmode in ("SingleNRMSE", "WeightedNRMSE"):
        # Single target is a special case of WeightedNRMSE with weights_dict={single target: 1.0}.
        print(f"[calib] Starting parameter calibration: {calibmode} (Nelder-Mead), maxiter={maxiter}, params={topk_names}")
        history = []

        def _objective(x):
            override = {n: float(v) for n, v in zip(topk_names, x)}
            if any(v <= 0 for v in override.values()):
                return 1e6
            traj = _simulate_trajectory(override)
            if traj is None:
                return 1e6
            per_tgt = {}
            cost = 0.0
            for tgt in target_names:
                j = components.index(tgt)
                e = _nrmse(obs_data[tgt], traj[j])
                per_tgt[tgt] = e
                cost += weights_dict[tgt] * e
            history.append({"x": [float(v) for v in x], "cost": cost, **per_tgt})
            return cost

        res = minimize(_objective, x0_cal, method="Nelder-Mead",
                       options={"xatol": 1e-6, "fatol": 1e-6, "maxiter": maxiter, "disp": False})

        x_best = np.array(res.x, dtype=float)
        recovered = {n: float(v) for n, v in zip(topk_names, x_best)}
        recovered_traj = _simulate_trajectory(recovered)

        calib_out = {
            "_note": (
                f"{calibmode}: weighted NRMSE objective (scipy Nelder-Mead); "
                "obs_data = target columns from data.xlsx aligned with t_h; "
                "initial values = current PARAMS defaults."
            ),
            "modelcomplex": modelcomplex,
            "calibmode": calibmode,
            "targets": target_names,
            "weights": weights_dict,
            "params": topk_names,
            "x0": {n: float(x0_cal[i]) for i, n in enumerate(topk_names)},
            "recovered": recovered,
            "final_cost": float(res.fun),
            "n_iter": int(res.nit),
            "n_eval": int(res.nfev),
            "success": bool(res.success),
            "message": str(res.message),
            "history_len": len(history),
            "r2_recovered": _r2_scores(recovered_traj),
        }
        calib_path.write_text(json.dumps(calib_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {calib_path.name}")
        print(f"     final cost={res.fun:.5f}, iters={res.nit}, nfev={res.nfev}")
        for i, n in enumerate(topk_names):
            print(f"     {n}: x0={x0_cal[i]:.6g}  recovered={recovered[n]:.6g}")

    else:  # ParetoMOEA (NSGA-II via pymoo)
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.core.problem import ElementwiseProblem
        from pymoo.termination.max_gen import MaximumGenerationTermination
        from pymoo.optimize import minimize as pymoo_minimize

        POP_SIZE = 15
        N_GEN = max(1, maxiter // 2)
        xlb = x0_cal * 0.5      # Parameter search range: +/-50% around x0
        xub = x0_cal * 1.5

        termination = MaximumGenerationTermination(N_GEN)
        print(f"[calib] Starting parameter calibration: ParetoMOEA (NSGA-II), pop_size={POP_SIZE}, n_gen={N_GEN}, "
              f"no early stop, n_eval<={POP_SIZE*N_GEN}, params={topk_names}")

        history = []            # Track each evaluation: {"x": [...], "cost": sum(NRMSEs), <target>: NRMSE, ...}

        class _CalibProblem(ElementwiseProblem):
            def __init__(self):
                super().__init__(n_var=len(x0_cal), n_obj=len(target_names),
                                 xl=xlb, xu=xub)

            def _evaluate(self, x, out, *args, **kwargs):
                override = {n: float(v) for n, v in zip(topk_names, x)}
                traj = _simulate_trajectory(override)
                if traj is None:
                    f_vals = [1e6] * len(target_names)
                else:
                    f_vals = [_nrmse(obs_data[t], traj[components.index(t)])
                              for t in target_names]
                out["F"] = f_vals
                per_tgt = {t: float(f_vals[k]) for k, t in enumerate(target_names)}
                history.append({"x": [float(v) for v in x],
                                "cost": float(sum(f_vals)),
                                **per_tgt})

        res = pymoo_minimize(_CalibProblem(), NSGA2(pop_size=POP_SIZE),
                             termination, seed=42, verbose=False)

        # pymoo returns 1D for a single solution and 2D for multiple solutions; normalize to (n_pareto, n_var/n_obj).
        pareto_X = np.atleast_2d(res.X)
        pareto_F = np.atleast_2d(res.F)
        pareto_front = []
        pareto_trajs = []
        for xi, fi in zip(pareto_X, pareto_F):
            pt = {n: float(xi[k]) for k, n in enumerate(topk_names)}
            pt.update({t: float(fi[k]) for k, t in enumerate(target_names)})
            pareto_front.append(pt)
            traj = _simulate_trajectory({n: float(xi[k]) for k, n in enumerate(topk_names)})
            pareto_trajs.append(traj)

        calib_out = {
            "_note": (
                f"ParetoMOEA (NSGA-II via pymoo): pop_size={POP_SIZE}, n_gen={N_GEN}; "
                "search range = x0 +/-50%; obs_data = target columns from data.xlsx."
            ),
            "modelcomplex": modelcomplex,
            "calibmode": calibmode,
            "targets": target_names,
            "weights": None,
            "params": topk_names,
            "x0": {n: float(x0_cal[i]) for i, n in enumerate(topk_names)},
            "bounds": {n: [float(xlb[i]), float(xub[i])] for i, n in enumerate(topk_names)},
            "pop_size": POP_SIZE,
            "n_gen": N_GEN,
            "n_gen_actual": int(res.algorithm.n_gen),
            "n_eval_actual": int(res.algorithm.evaluator.n_eval),
            "npareto_target": npareto_target,
            "n_pareto": len(pareto_front),
            "early_stopped": False,
            "pareto_front": pareto_front,
        }
        calib_path.write_text(json.dumps(calib_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {calib_path.name}  [NSGA-II: {len(pareto_front)} Pareto points]")
        for pt in pareto_front:
            objs = " | ".join(f"{t}={pt[t]:.4f}" for t in target_names)
            print(f"     {objs}")

    optimized_subset: dict[str, float] | None = None
    if recovered_traj is not None and "recovered" in locals():
        optimized_subset = recovered
    elif pareto_X is not None and pareto_F is not None and pareto_trajs:
        best_idx, _, _ = _select_pareto_representative(
            pareto_F=pareto_F,
            pareto_trajs=pareto_trajs,
            target_names=target_names,
            components=components,
            df_obs=df_obs,
        )
        optimized_subset = {n: float(pareto_X[best_idx, i]) for i, n in enumerate(topk_names)}

    if optimized_subset is not None:
        param_opt = dict(param_ref)
        for k, v in optimized_subset.items():
            if k in param_opt:
                param_opt[k] = float(v)
        param_opt_path.write_text(json.dumps(param_opt, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Intermediate process plots, fig1-fig8 at dpi=600, saved next to calib_path ----
    _make_plots(
        calibmode=calibmode,
        target_names=target_names,
        components=components,
        t_eval_h=t_eval_h,
        df_obs=df_obs,
        Y_baseline=Y,
        sens_records=sens_records,
        topk_names=topk_names,
        history=history,
        recovered_traj=recovered_traj,
        pareto_X=pareto_X,
        pareto_F=pareto_F,
        pareto_trajs=pareto_trajs,
        figs_dir=figs_dir if figs_dir is not None else calib_path.parent / "figs",
    )
    print(f"  -> figs/fig1-8_*.png (dpi=600)")


# ============================================================================
# 8. Entry point: all tunable parameters are centralized here (paths / simulation duration / oxygen transfer / sensitivity and calibration settings)
# ============================================================================
if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parent

    # Sensitivity and calibration targets. One dict carries both targets and weights; weights are not forced to sum to 1 and remain caller-reviewed.
    # Typical forms for the three calibmode values:
    #   SingleNRMSE   -> {"S_sub_NO_sub_3": 1}
    #   WeightedNRMSE -> {"S_sub_NO_sub_3": 0.3, "S_sub_PO_sub_4": 0.3}
    #   ParetoMOEA    -> {"S_sub_NO_sub_3": 0.5, "S_sub_PO_sub_4": 0.5}
    # When sens_path / calib_path are not passed explicitly, default output is <project root>/midoutput/{sensitivity,calibration}.json
    run_pipeline(
        modelcomplex="IntegratedNPR",  # ["SimplifiedCODN","CompleteNRN2O","EBPRCODN","IntegratedNPR"]
        calibmode="WeightedNRMSE",     # ["SingleNRMSE","WeightedNRMSE","ParetoMOEA"]
        sens_targets={"S_sub_NO_sub_3": 0.3, "S_sub_PO_sub_4": 0.7},
        xlsx_path=ROOT / "data.xlsx",
        sens_delta=0.10,
        senstopk=4,
        maxiter=100,
        boundaries={
            "aeration": None,           # {"K_L_a": ..., "S_O_sat": ...}
            "internal_recycle": None,   # {"k_r": ..., "<comp>": <ref>, ...}
            "ras_recycle": None,        # {"k_RAS": ..., "factor": 2.0}
            "hydraulic": None,          # {"k_HRT": ..., "C_in": dict | None}
            "carbon_dose": None,        # {"r_dose": ...}
            "chem_dose": None,          # {"r_chem": ...}
        },
    )
