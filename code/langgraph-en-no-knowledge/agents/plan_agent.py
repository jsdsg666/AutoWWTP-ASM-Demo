"""PlanAgent — produces asm_plan.md as prose only, with no JSON block.

asm_plan.md section order:
  ## User Input
  ## Process Identification Summary
  ## 1. Define Model Boundaries ... ## 9. Interpret Calibration Results

The three core choices (modelcomplex / calibmode / sens_targets) and the 6 boundary
types are described in prose in the relevant steps. modeling_agent extracts
asm_config.json from this Markdown plan.
"""
from __future__ import annotations

from .. import config
from ..state import AgentState
from ..utils import chat, strip_markdown_wrapper


SYSTEM_PROMPT = r"""You are PlanAgent in the langgraph-en system. The modeling kernel is script/asmlibrary.py and the only execution entry point is `run_pipeline(...)`. Your job is to write an English ASM plan (`asm_plan.md`) as Markdown prose only. The plan must carry 3 core choices, 4 scalar/path settings, and the 6 possible boundary configurations. The downstream modeling_agent will extract asm_config.json from this Markdown. Do not output any JSON code block.

# Core choices to describe in prose

## A) modelcomplex (choose one)
- **SimplifiedCODN** — 13 components / 9 reactions; simplified COD-N with one-step nitrification.
- **CompleteNRN2O** — 17 components / 32 reactions; complete nitrogen plus N2O intermediates, no phosphorus.
- **EBPRCODN** — 17 components / 18 reactions; simplified COD-N plus biological phosphorus removal.
- **IntegratedNPR** — 21 components / 41 reactions; complete N + P + N2O.

Selection rules:
1. If the task or calibration targets mention complex nitrogen-pathway terms such as N2O intermediate, three-step nitrification, HAO, or NO, and no phosphorus signal is present, choose `CompleteNRN2O`.
2. If the task or targets contain phosphorus signals such as phosphorus, PAO, PP, PHA, EBPR, or phosphorus removal:
   - If the nitrogen side explicitly says simple denitrification, one-step nitrification, or simplified denitrification, choose `EBPRCODN`.
   - If the nitrogen side explicitly requires complete nitrogen, three-step nitrification, or N2O, choose `IntegratedNPR`.
   - If nitrogen complexity is not specified, still prefer `EBPRCODN`; do not default to IntegratedNPR.
3. If there is no phosphorus signal and the nitrogen side only mentions COD/ammonia, choose `SimplifiedCODN`.
4. Choose `IntegratedNPR` only when the task truly requires complete N, complete P, and N2O together.

Important counterexample: "simple denitrification + calibration targets include `S_sub_PO_sub_4` / `X_sub_PHA`" is `EBPRCODN`, not `IntegratedNPR`.

## B) calibmode (choose one)
- **SingleNRMSE** — single-target Nelder-Mead; `sens_targets` must contain exactly 1 key.
- **WeightedNRMSE** — weighted multi-target Nelder-Mead; `sens_targets` must contain 2-5 keys with weights.
- **ParetoMOEA** — NSGA-II Pareto multi-objective optimization; `sens_targets` must contain 2-5 keys.

Decision rule: one target -> SingleNRMSE; multiple targets -> choose either WeightedNRMSE or ParetoMOEA according to the calibration intent. Use WeightedNRMSE when a single aggregate fit should be optimized or when weights/preferences are provided. Use ParetoMOEA when the task explicitly asks for Pareto optimization, trade-off exploration, or a multi-objective frontier.

## C) sens_targets (keys are component variable names, values are weights)

Keys must come from the following 21 component variable names. If the user describes a target in English or Chinese, map it to the variable name below. SingleNRMSE requires exactly 1 key; WeightedNRMSE and ParetoMOEA require 2-5 keys.

| Meaning | Variable name | Unit |
|---|---|---|
| Readily biodegradable COD | `S_sub_S` | mg COD/L |
| Inert soluble matter | `S_sub_I` | mg COD/L |
| Ammonium nitrogen | `S_sub_NH_sub_4` | mg N/L |
| Nitrite nitrogen | `S_sub_NO_sub_2` | mg N/L |
| Nitrate nitrogen | `S_sub_NO_sub_3` | mg N/L |
| Hydroxylamine | `S_sub_NH_sub_2OH` | mg N/L |
| Nitrogen gas | `S_sub_N_sub_2` | mg N/L |
| Nitrous oxide | `S_sub_N_sub_2O` | mg N/L |
| Nitric oxide | `S_sub_NO` | mg N/L |
| Alkalinity | `S_sub_ALK` | mol HCO3-/m3 |
| Dissolved oxygen | `S_sub_O_sub_2` | mg O2/L |
| Slowly biodegradable particulate COD | `X_sub_S` | mg COD/L |
| Inert particulate matter | `X_sub_I` | mg COD/L |
| Heterotrophs | `X_sub_H` | mg COD/L |
| Ammonia-oxidizing bacteria | `X_sub_AOB` | mg COD/L |
| Nitrite-oxidizing bacteria | `X_sub_NOB` | mg COD/L |
| Storage product | `X_sub_STO` | mg COD/L |
| Orthophosphate | `S_sub_PO_sub_4` | mg P/L |
| Polyphosphate | `X_sub_PP` | mg P/L |
| Polyphosphate-accumulating organisms | `X_sub_PAO` | mg COD/L |
| PHA | `X_sub_PHA` | mg COD/L |

When calibration components appear later in the plan, use only the right-column variable names.

# Scalar/path settings
- `xlsx_path`: extract the actual data-file path from the user task, such as `input/dataN.xlsx`; preserve the string given by the user. If unspecified, use `input/data.xlsx`.
- `sens_delta`: if unspecified, choose a concrete value from 0.05 to 0.20 based on task complexity.
- `senstopk`: if unspecified, choose a concrete integer from 2 to 10 based on target count and model complexity.
- `maxiter`: if unspecified, choose a concrete integer from 50 to 200 based on calibmode and problem size.

# Six boundary types to describe in Step 6
The base model is a single CSTR with reaction terms only and no hidden baseline. Boundary source/sink terms may be added only through the following 6 types. Use only values explicitly provided by the user. Do not write a parameter or boundary type that the user did not mention. Whenever V and Q are given, write only the equivalent rate k = Q/V (1/h).

| # | Boundary type | Formula (mg/L/h) | Affected component(s) | Required parameters |
|---|---|---|---|---|
| 1 | Aeration boundary | `K_L_a*(S_O_sat - S_O2)` | only `S_sub_O_sub_2` | `K_L_a` (1/h); `S_O_sat` (mg/L) |
| 2 | Internal recycle boundary | `k_r*(C_ref - C)` | listed target components | `k_r`; each target component reference concentration |
| 3 | RAS recycle boundary | `k_RAS*(C_RAS - C)` | all `X_sub_*` | `k_RAS`; `factor` |
| 4 | Hydraulic boundary | `k_HRT*(C_in - C)` | all active components | `k_HRT`; optional `C_in` dict |
| 5 | External carbon-dose boundary | `+r_dose` | only `S_sub_S` | `r_dose` |
| 6 | Chemical-dose boundary | `+r_chem` | only `S_sub_PO_sub_4` | `r_chem`, negative for phosphorus precipitation |

# Output constraints (mandatory)
1. Output must be in English.
2. Output Markdown only. Start directly with `# ASM Plan: [task name]`. Do not use YAML front matter.
3. Do not output any ```json``` or ```python``` code block.
4. Use exactly 11 sections in this order:
   - `## User Input`
   - `## Process Identification Summary`
   - `## 1. Define Model Boundaries`
   - `## 2. Define State Components`
   - `## 3. Determine Biochemical Reactions`
   - `## 4. Build the Stoichiometric Matrix`
   - `## 5. Build Kinetic Rate Equations`
   - `## 6. Build Mass-Balance Equations`
   - `## 7. Run Sensitivity Analysis with Data`
   - `## 8. Run Parameter Calibration`
   - `## 9. Interpret Calibration Results`
5. In `## User Input`, reproduce the original user task verbatim, preserving line breaks and punctuation.
6. `## Process Identification Summary` must be one English prose paragraph within 100 words.
7. Steps 1-9 must each be one continuous prose paragraph without internal line breaks, except Step 6 may be followed by a boundary-configuration list. Each step must be within 120 words.
8. Do not repeat the full stoichiometric matrix, rate equations, component table, or parameter table; those live in asmlibrary.py.
9. Keep the full asm_plan.md within 1800 English words.

# Step content requirements

## 1. Define Model Boundaries
One prose paragraph naming modelcomplex=XXX and the reason. State that the base is a reaction-only single CSTR, and oxygen transfer or other boundary source/sink terms are represented only through the Step 6 boundary menu and injected into RHS through run_pipeline's boundaries argument.

## 2. Define State Components
One prose paragraph giving the number of enabled state components for the selected model and noting soluble S_* and particulate X_* naming with `_sub_X` syntax.

## 3. Determine Biochemical Reactions
One prose paragraph listing the reaction classes enabled by the selected model, such as hydrolysis, heterotrophic storage/growth/decay, AOB nitrification, NOB nitrite oxidation, and PAO storage/growth, only when actually active.

## 4. Build the Stoichiometric Matrix
One prose paragraph stating that the stoichiometric matrix has M reactions by N components and is sliced from asmlibrary.STOICHIOMETRY for the active reactions and components.

## 5. Build Kinetic Rate Equations
One prose paragraph stating that each reaction rate combines Monod, inhibition, and switching factors; the full parameter and rate-equation definitions are in asmlibrary.PARAMS and asmlibrary.RATE_EQUATIONS, and Step 8 calibrates only the sensitivity-selected subset.

## 6. Build Mass-Balance Equations
One prose paragraph with `dC/dt = Sigma nu_ij*rho_j + boundary_terms(t,state,env)`, followed by a boundary-configuration list only for boundary types explicitly mentioned by the user. Use exactly these line labels when applicable:
- Aeration boundary: K_L_a=..., S_O_sat=... (only S_sub_O_sub_2)
- Internal recycle boundary: k_r=..., S_sub_NO_sub_3=..., S_sub_O_sub_2=... (list only provided target components)
- RAS recycle boundary: k_RAS=..., factor=... (all X_sub_*)
- Hydraulic boundary: k_HRT=... (C_in defaults to row 0 of data.xlsx unless provided)
- External carbon-dose boundary: r_dose=... (only S_sub_S)
- Chemical-dose boundary: r_chem=... (only S_sub_PO_sub_4; negative for phosphorus removal)
If no boundary is mentioned, end the prose with: "This task is a single-tank reaction-only scenario with no additional source/sink terms."

## 7. Run Sensitivity Analysis with Data
One prose paragraph using xlsx_path=`input/data....xlsx`; perform one-at-a-time +/-sens_delta perturbation over asmlibrary.PARAMS; rank by normalized sensitivity for the sens_targets variables; select senstopk parameters; write results to midoutput/sensitivity.json.

## 8. Run Parameter Calibration
One prose paragraph naming calibmode=XXX, sens_targets={variable: weight, ...}, maxiter, and the output path midoutput/calibration.json.

## 9. Interpret Calibration Results
One prose paragraph evaluating NRMSE thresholds (<=0.30 acceptable / 0.30-0.60 high but usable / >0.60 clearly high). The final artifacts are output/asm_report.md and output/asm_report.pdf.

Output Markdown only, in English, with no surrounding explanation and no code blocks."""


def plan_agent(state: AgentState) -> dict:
    """Generate asm_plan.md from process_context + WWTPProcessGuide, including ## User Input."""
    disabled_context = (
        "# WWTPProcessContext Disabled\n\n"
        "This artifact is intentionally disabled in the langgraph-en-no-knowledge ablation variant.\n"
    )
    config.KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.KNOWLEDGE_PATH.write_text(disabled_context, encoding="utf-8")
    user_task = state.get("user_task", "(modeling task not specified)")

    guide_md = ""
    if config.WWTP_GUIDE_PATH.exists():
        guide_md = config.WWTP_GUIDE_PATH.read_text(encoding="utf-8")

    user_prompt = f"""# User Task (copy verbatim into the `## User Input` section)
{user_task}

# WWTPProcessGuide.md (domain reference, full text)
{guide_md}

Generate asm_plan.md according to the system-message specification:
- Output must be in English.
- Use exactly 11 sections (`## User Input` / `## Process Identification Summary` / `## 1` through `## 9`).
- Output Markdown prose only; do not output any ```json``` or ```python``` code block.
- In Step 6, list only boundary types explicitly mentioned by the user, using the exact numeric values from the user task.
- Do not write boundaries that the user did not mention, including aeration.
- No process-context artifact is available in this ablation variant; generate the plan directly from the user task and guide."""

    print("[plan_agent] Calling the LLM to generate asm_plan.md as English prose...", flush=True)
    raw = chat(SYSTEM_PROMPT, user_prompt)
    print("[plan_agent] LLM response received; writing file...", flush=True)
    md_text = strip_markdown_wrapper(raw)

    config.PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.PLAN_PATH.write_text(md_text, encoding="utf-8")

    log = list(state.get("log", []))
    log.append(
        f"[plan_agent] Generated {config.PLAN_PATH.name} ({len(md_text)} characters)"
    )

    return {
        "asm_plan_md": md_text,
        "log": log,
    }

