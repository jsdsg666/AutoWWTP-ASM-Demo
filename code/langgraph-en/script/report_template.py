"""English ASM report template.

build_report_md(cfg, sens, calib, root) returns a complete Markdown report with:
  1. model boundary definition
  2. state components
  3. biochemical reactions
  4. stoichiometric matrix
  5. kinetic rate equations
  6. mass-balance equations
  7. sensitivity analysis
  8. parameter calibration
  9. calibration-result interpretation
 10. modeling-effect analysis
"""
from __future__ import annotations

import re
from pathlib import Path

from asmlibrary import (
    COMPONENT_UNITS,
    COMPONENTS_BY_MODEL,
    PARAMS,
    RATE_EQUATIONS,
    REACTIONS_BY_MODEL,
    STOICHIOMETRY,
)


_GREEK_BASE = {"mu": "mu", "eta": "eta", "rho": "rho"}


def _fmt_num(x, nd: int = 6) -> str:
    try:
        v = float(x)
    except Exception:
        return "NA" if x is None else str(x)
    if abs(v) >= 1000 or (0 < abs(v) < 1e-4):
        return f"{v:.{nd}e}"
    return f"{v:.{nd}g}"


def _py_to_plain(name: str) -> str:
    """Convert CFtoV-style identifiers into a readable plain-text formula."""
    tokens = re.split(r"(_sub_|_sup_|_sep_)", name)
    out: list[str] = []
    pending = ""
    for i, tok in enumerate(tokens):
        if tok == "_sub_":
            pending = "_"
        elif tok == "_sup_":
            pending = "^"
        elif tok == "_sep_":
            out.append(",")
            pending = ""
        else:
            part = _GREEK_BASE.get(tok, tok) if i == 0 else tok
            if pending:
                out.append(f"{pending}{part}")
                pending = ""
            else:
                out.append(part)
    return "".join(out)


def _classify_stoich(stoich: dict) -> tuple[list[str], list[str]]:
    locs = {k: (1.0 if v is None else v) for k, v in PARAMS.items()}
    products: list[str] = []
    substrates: list[str] = []
    for comp, expr in stoich.items():
        try:
            val = float(expr) if isinstance(expr, (int, float)) else float(
                eval(str(expr), {"__builtins__": {}}, locs)
            )
        except Exception:
            val = None
        if val is None or abs(val) < 1e-12:
            continue
        if val > 0:
            products.append(comp)
        else:
            substrates.append(comp)
    return products, substrates


def _active_params(modelcomplex: str) -> list[str]:
    rxns = REACTIONS_BY_MODEL.get(modelcomplex, [])
    used: set[str] = set()
    pat = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    for rid in rxns:
        texts = [RATE_EQUATIONS.get(rid, "") or ""]
        texts.extend(str(v) for v in STOICHIOMETRY.get(rid, {}).values())
        for text in texts:
            for tok in pat.findall(text):
                if tok in PARAMS:
                    used.add(tok)
    return [k for k in PARAMS if k in used]


MODELCOMPLEX_DESC = {
    "SimplifiedCODN": "Simplified COD-N model with 13 components and 9 effective reactions, including one-step nitrification.",
    "CompleteNRN2O": "Complete nitrogen and N2O model with 17 components and 32 reactions, excluding phosphorus biology.",
    "EBPRCODN": "Simplified COD-N plus biological phosphorus removal model with 17 components and 18 reactions.",
    "IntegratedNPR": "Full nitrogen, phosphorus, and N2O model with 21 components and 41 reactions.",
}


COMPONENT_DESC = {
    "S_sub_S": ("readily biodegradable soluble COD", "Direct heterotrophic substrate and PAO anaerobic carbon source."),
    "S_sub_I": ("inert soluble COD", "Soluble organic matter that is not biologically converted."),
    "S_sub_NH_sub_4": ("ammonium nitrogen", "Substrate for nitrification and nitrogen source for biomass synthesis."),
    "S_sub_NO_sub_2": ("nitrite nitrogen", "AOB product, NOB substrate, and denitrification electron acceptor."),
    "S_sub_NO_sub_3": ("nitrate nitrogen", "NOB product and common denitrification electron acceptor."),
    "S_sub_NH_sub_2OH": ("hydroxylamine", "AOB nitrification intermediate linked to N2O formation."),
    "S_sub_N_sub_2": ("nitrogen gas", "Final denitrification product."),
    "S_sub_N_sub_2O": ("nitrous oxide", "Greenhouse-gas intermediate from nitrification and denitrification."),
    "S_sub_NO": ("nitric oxide", "Short-lived nitrogen intermediate in AOB and denitrification pathways."),
    "S_sub_ALK": ("alkalinity", "pH-buffering capacity affected by nitrification and biomass growth."),
    "S_sub_O_sub_2": ("dissolved oxygen", "Electron acceptor for aerobic reactions and aeration target."),
    "X_sub_S": ("slowly biodegradable particulate COD", "Particulate substrate that must hydrolyze before uptake."),
    "X_sub_I": ("inert particulate COD", "Non-biodegradable particulate organic matter."),
    "X_sub_H": ("heterotrophic biomass", "Biomass responsible for COD removal and denitrification."),
    "X_sub_AOB": ("ammonia-oxidizing bacteria", "Autotrophic biomass for ammonia oxidation."),
    "X_sub_NOB": ("nitrite-oxidizing bacteria", "Autotrophic biomass for nitrite oxidation."),
    "X_sub_STO": ("intracellular storage product", "Stored carbon used by heterotrophs under changing conditions."),
    "S_sub_PO_sub_4": ("orthophosphate", "Soluble phosphorus released and taken up in EBPR."),
    "X_sub_PP": ("polyphosphate", "Intracellular phosphorus storage in PAOs."),
    "X_sub_PAO": ("polyphosphate-accumulating organisms", "Biomass that drives EBPR."),
    "X_sub_PHA": ("polyhydroxyalkanoate", "PAO storage polymer formed under anaerobic substrate uptake."),
}


PARAM_DESC = {
    "mu": "maximum specific growth or conversion rate",
    "K": "half-saturation, affinity, or inhibition constant",
    "Y": "yield coefficient",
    "b": "endogenous decay or maintenance rate",
    "eta": "switching or reduction factor",
    "f": "fraction coefficient",
    "i": "composition coefficient",
    "k": "reaction or hydrolysis rate coefficient",
}


MODE_DESC = {
    "SingleNRMSE": "Single-target Nelder-Mead calibration minimizes one normalized RMSE objective.",
    "WeightedNRMSE": "Weighted multi-target Nelder-Mead calibration minimizes the weighted sum of target NRMSE values.",
    "ParetoMOEA": "NSGA-II Pareto calibration searches for non-dominated trade-off solutions across multiple targets.",
}


BOUNDARY_DESC = {
    "aeration": "Oxygen transfer source/sink acting only on S_sub_O_sub_2.",
    "internal_recycle": "Internal recycle source/sink that drives selected components toward recycle reference concentrations.",
    "ras_recycle": "Return activated sludge effect on particulate X_sub_* components.",
    "hydraulic": "Hydraulic exchange that drives active components toward influent or upstream concentrations.",
    "carbon_dose": "External biodegradable carbon addition acting on S_sub_S.",
    "chem_dose": "Chemical phosphorus-removal source/sink acting on S_sub_PO_sub_4.",
}


REACTION_CATEGORY = {
    "P1": "hydrolysis",
    "P2": "heterotrophic storage",
    "P3": "heterotrophic growth",
    "P4": "heterotrophic decay",
    "P5": "AOB nitrification",
    "P6": "AOB decay",
    "P7": "NOB nitrification",
    "P8": "NOB decay",
    "P9": "PAO storage",
    "P10": "PAO growth",
    "P11": "PAO decay",
}


def _reaction_category(rid: str) -> str:
    m = re.match(r"(P\d+)", rid)
    return REACTION_CATEGORY.get(m.group(1), "biochemical reaction") if m else "biochemical reaction"


def _param_meaning(name: str) -> str:
    first = name.split("_", 1)[0]
    if first in PARAM_DESC:
        return PARAM_DESC[first]
    if name.startswith("K_"):
        return PARAM_DESC["K"]
    return "ASM kinetic or stoichiometric parameter used by the active reactions"


def _quality_label(nrmse) -> str:
    try:
        v = float(nrmse)
    except Exception:
        return "not interpretable"
    if v <= 0.30:
        return "acceptable fit"
    if v <= 0.60:
        return "high error but still usable with caution"
    return "clearly high error"


def _target_weights(cfg: dict) -> str:
    targets = cfg.get("sens_targets") or {}
    if not isinstance(targets, dict) or not targets:
        return "none"
    return ", ".join(f"`{k}`={_fmt_num(v)}" for k, v in targets.items())


def _section_1(cfg: dict) -> list[str]:
    model = cfg.get("modelcomplex", "UNKNOWN")
    boundaries = cfg.get("boundaries") or {}
    active = {k: v for k, v in boundaries.items() if v is not None}
    lines = ["## 1. Define Model Boundaries", ""]
    lines.append(f"The selected modelcomplex is **{model}**. {MODELCOMPLEX_DESC.get(model, 'No model description is available.')}")
    lines.append("")
    lines.append("The reactor basis is a single completely stirred tank reactor (CSTR). Biological reaction terms define the internal conversion rates, while optional boundary source/sink terms are injected through the `boundaries` argument of `run_pipeline`.")
    lines.append("")
    if active:
        lines.append("### 1.1 Enabled Boundary Source/Sink Terms")
        lines.append("")
        lines.append("| Boundary | Configuration | Interpretation |")
        lines.append("|---|---|---|")
        for key, val in active.items():
            params = ", ".join(f"`{k}`={_fmt_num(v)}" for k, v in (val or {}).items())
            lines.append(f"| `{key}` | {params or 'enabled'} | {BOUNDARY_DESC.get(key, '')} |")
    else:
        lines.append("No boundary source/sink term is enabled; the task is treated as a reaction-only single-tank scenario.")
    lines.append("")
    return lines


def _section_2(cfg: dict) -> list[str]:
    model = cfg.get("modelcomplex", "IntegratedNPR")
    comps = COMPONENTS_BY_MODEL.get(model, [])
    lines = ["## 2. Define State Components", ""]
    lines.append(f"The ODE state vector contains **{len(comps)}** active components for `{model}`. Soluble components use the `S_sub_*` prefix and particulate components use the `X_sub_*` prefix.")
    lines.append("")
    lines.append("| # | Component | Formula label | Meaning | Unit | Role |")
    lines.append("|---:|---|---|---|---|---|")
    for i, comp in enumerate(comps, 1):
        meaning, role = COMPONENT_DESC.get(comp, ("component", "Active ASM state component."))
        lines.append(f"| {i} | `{comp}` | {_py_to_plain(comp)} | {meaning} | {COMPONENT_UNITS.get(comp, 'NA')} | {role} |")
    lines.append("")
    return lines


def _section_3(cfg: dict) -> list[str]:
    model = cfg.get("modelcomplex", "IntegratedNPR")
    rxns = REACTIONS_BY_MODEL.get(model, [])
    lines = ["## 3. Determine Biochemical Reactions", ""]
    lines.append(f"The selected model activates **{len(rxns)}** reactions. The table summarizes each active reaction by reaction ID, category, consumed components, and produced components.")
    lines.append("")
    lines.append("| Reaction ID | Category | Substrates | Products |")
    lines.append("|---|---|---|---|")
    for rid in rxns:
        subs, prods = _classify_stoich(STOICHIOMETRY.get(rid, {}))
        lines.append(
            f"| `{rid}` | {_reaction_category(rid)} | "
            f"{', '.join(f'`{x}`' for x in subs) or '-'} | "
            f"{', '.join(f'`{x}`' for x in prods) or '-'} |"
        )
    lines.append("")
    return lines


def _section_4(cfg: dict) -> list[str]:
    model = cfg.get("modelcomplex", "IntegratedNPR")
    comps = COMPONENTS_BY_MODEL.get(model, [])
    rxns = REACTIONS_BY_MODEL.get(model, [])
    lines = ["## 4. Build the Stoichiometric Matrix", ""]
    lines.append(f"The stoichiometric matrix has **{len(rxns)} reactions x {len(comps)} components**. Positive coefficients produce a component, negative coefficients consume a component, and zeros are omitted from the compact table.")
    lines.append("")
    lines.append("| Reaction | Component | Stoichiometric coefficient |")
    lines.append("|---|---|---:|")
    for rid in rxns:
        for comp, coeff in STOICHIOMETRY.get(rid, {}).items():
            if comp in comps:
                lines.append(f"| `{rid}` | `{comp}` | `{coeff}` |")
    lines.append("")
    return lines


def _section_5(cfg: dict) -> list[str]:
    model = cfg.get("modelcomplex", "IntegratedNPR")
    rxns = REACTIONS_BY_MODEL.get(model, [])
    params = _active_params(model)
    lines = ["## 5. Build Kinetic Rate Equations", ""]
    lines.append("Reaction rates combine Monod saturation, inhibition, switching factors, yields, and endogenous decay terms. The executable expressions below are taken directly from `asmlibrary.RATE_EQUATIONS` for the active reactions.")
    lines.append("")
    lines.append("| Reaction ID | Category | Rate expression |")
    lines.append("|---|---|---|")
    for rid in rxns:
        expr = str(RATE_EQUATIONS.get(rid, "")).replace("|", "\\|")
        lines.append(f"| `{rid}` | {_reaction_category(rid)} | `{expr}` |")
    lines.append("")
    lines.append(f"Active kinetic/stoichiometric parameters used by this model: **{len(params)}**.")
    lines.append("")
    lines.append("| Parameter | Default value | Meaning |")
    lines.append("|---|---:|---|")
    for name in params:
        lines.append(f"| `{name}` | {_fmt_num(PARAMS.get(name))} | {_param_meaning(name)} |")
    lines.append("")
    return lines


def _boundary_term_for_component(comp: str, boundaries: dict) -> list[str]:
    terms: list[str] = []
    aer = boundaries.get("aeration")
    if comp == "S_sub_O_sub_2" and isinstance(aer, dict):
        terms.append("K_L_a*(S_O_sat-C)")
    internal = boundaries.get("internal_recycle")
    if isinstance(internal, dict) and comp in internal:
        terms.append(f"k_r*({comp}_ref-C)")
    ras = boundaries.get("ras_recycle")
    if isinstance(ras, dict) and comp.startswith("X_sub_"):
        terms.append("k_RAS*(factor*C0-C)")
    hyd = boundaries.get("hydraulic")
    if isinstance(hyd, dict):
        terms.append("k_HRT*(C_in-C)")
    carbon = boundaries.get("carbon_dose")
    if comp == "S_sub_S" and isinstance(carbon, dict):
        terms.append("r_dose")
    chem = boundaries.get("chem_dose")
    if comp == "S_sub_PO_sub_4" and isinstance(chem, dict):
        terms.append("r_chem")
    return terms


def _section_6(cfg: dict) -> list[str]:
    model = cfg.get("modelcomplex", "IntegratedNPR")
    comps = COMPONENTS_BY_MODEL.get(model, [])
    rxns = REACTIONS_BY_MODEL.get(model, [])
    boundaries = cfg.get("boundaries") or {}
    active = {k: v for k, v in boundaries.items() if v is not None}
    lines = ["## 6. Build Mass-Balance Equations", ""]
    lines.append("For each component j, the CSTR mass balance is `dC_j/dt = sum_k nu[j,k] * rho_k(C, theta) + B_j(t, C, env)`. The first term comes from stoichiometry and reaction kinetics; the second term is the sum of enabled boundary source/sink contributions.")
    lines.append("")
    if active:
        lines.append("### 6.1 Enabled Boundaries")
        lines.append("")
        lines.append("| Boundary | Configuration |")
        lines.append("|---|---|")
        for key, val in active.items():
            params = ", ".join(f"`{k}`={_fmt_num(v)}" for k, v in (val or {}).items())
            lines.append(f"| `{key}` | {params or 'enabled'} |")
    else:
        lines.append("All boundary entries are null, so B is zero for every component.")
    lines.append("")
    lines.append("### 6.2 Component Equations")
    lines.append("")
    for comp in comps:
        reaction_terms = []
        for rid in rxns:
            coeff = STOICHIOMETRY.get(rid, {}).get(comp)
            if coeff is not None:
                reaction_terms.append(f"({coeff})*rho_{rid}")
        boundary_terms = _boundary_term_for_component(comp, boundaries)
        rhs = " + ".join(reaction_terms + boundary_terms) or "0"
        lines.append(f"- `d {comp} / dt = {rhs}`")
    lines.append("")
    return lines


def _section_7(cfg: dict, sens: dict | None) -> list[str]:
    lines = ["## 7. Run Sensitivity Analysis with Data", ""]
    delta = cfg.get("sens_delta")
    topk_target = cfg.get("senstopk")
    lines.append(f"Sensitivity analysis uses one-at-a-time parameter perturbation with +/-Delta = **{_fmt_num(delta)}** on data file `{cfg.get('xlsx_path')}`. The configured target weights are {_target_weights(cfg)}, and the top **{topk_target}** parameters are passed to calibration.")
    lines.append("")
    if not isinstance(sens, dict):
        lines.append("Sensitivity results are not available.")
        lines.append("")
        return lines
    topk = sens.get("topk") or []
    if topk:
        lines.append("### 7.1 Top-K Parameters")
        lines.append("")
        header = ["Rank", "Parameter", "Default", "Combined sensitivity"]
        target_names = list((cfg.get("sens_targets") or {}).keys())
        header.extend(target_names)
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for i, row in enumerate(topk, 1):
            vals = [
                str(i),
                f"`{row.get('parameter', '')}`",
                _fmt_num(row.get("default")),
                _fmt_num(row.get("combined")),
            ]
            vals.extend(_fmt_num((row.get("by_target") or {}).get(t)) for t in target_names)
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")
    else:
        lines.append("No Top-K sensitivity table was found in sensitivity.json.")
        lines.append("")
    return lines


def _section_8(cfg: dict, calib: dict | None) -> list[str]:
    mode = cfg.get("calibmode")
    lines = ["## 8. Run Parameter Calibration", ""]
    lines.append(MODE_DESC.get(mode, "Calibration mode is not recognized."))
    lines.append("")
    lines.append(f"- Calibration mode: **{mode}**")
    lines.append(f"- Target weights: {_target_weights(cfg)}")
    lines.append(f"- Maximum iterations: **{cfg.get('maxiter')}**")
    if not isinstance(calib, dict):
        lines.append("- calibration.json is not available.")
        lines.append("")
        return lines
    params = calib.get("params") or calib.get("topk_params") or []
    if params:
        lines.append("- Calibrated parameter set: " + ", ".join(f"`{p}`" for p in params))
    if mode in ("SingleNRMSE", "WeightedNRMSE"):
        lines.append(f"- Final cost: **{_fmt_num(calib.get('final_cost'))}**")
        lines.append(f"- Iterations: **{calib.get('n_iter')}**")
        lines.append(f"- Function evaluations: **{calib.get('n_eval')}**")
        lines.append(f"- Optimizer success: **{calib.get('success')}**")
    elif mode == "ParetoMOEA":
        lines.append(f"- Actual generations: **{calib.get('n_gen_actual')}**")
        lines.append(f"- Function evaluations: **{calib.get('n_eval_actual')}**")
        lines.append(f"- Pareto front size: **{len(calib.get('pareto_front', []) or [])}**")
    x0 = calib.get("x0") or calib.get("param_ref") or {}
    rec = calib.get("recovered") or calib.get("best_params") or calib.get("param_opt") or {}
    if isinstance(x0, dict) and isinstance(rec, dict) and rec:
        lines.append("")
        lines.append("### 8.1 Parameter Changes")
        lines.append("")
        lines.append("| Parameter | Initial | Calibrated | Relative change |")
        lines.append("|---|---:|---:|---:|")
        for name in sorted(set(x0) | set(rec)):
            v0 = x0.get(name)
            v1 = rec.get(name)
            try:
                rel = (float(v1) - float(v0)) / float(v0) * 100 if abs(float(v0)) > 1e-12 else None
            except Exception:
                rel = None
            rel_str = "NA" if rel is None else f"{rel:+.1f}%"
            lines.append(f"| `{name}` | {_fmt_num(v0)} | {_fmt_num(v1)} | {rel_str} |")
    lines.append("")
    return lines


def _section_9(cfg: dict, calib: dict | None, root: Path) -> list[str]:
    lines = ["## 9. Interpret Calibration Results", ""]
    if not isinstance(calib, dict):
        lines.append("No calibration result is available for interpretation.")
        lines.append("")
        return lines
    mode = cfg.get("calibmode")
    if mode in ("SingleNRMSE", "WeightedNRMSE"):
        cost = calib.get("final_cost")
        lines.append(f"The final objective value is **{_fmt_num(cost)}**, which is classified as **{_quality_label(cost)}** under the NRMSE thresholds.")
    else:
        front = calib.get("pareto_front") or []
        if front:
            targets = list((cfg.get("sens_targets") or {}).keys())
            lines.append("The Pareto front contains the following single-target best NRMSE values:")
            lines.append("")
            lines.append("| Target | Best NRMSE | Interpretation |")
            lines.append("|---|---:|---|")
            for target in targets:
                vals = []
                for point in front:
                    try:
                        vals.append(float(point.get(target)))
                    except Exception:
                        pass
                best = min(vals) if vals else None
                lines.append(f"| `{target}` | {_fmt_num(best)} | {_quality_label(best)} |")
        else:
            lines.append("The Pareto front is empty or unavailable.")
    lines.append("")
    figs_dir = root / "figs"
    fig_desc = {
        "fig1": "Input data and simulated trajectories.",
        "fig2": "Baseline versus calibrated model fit.",
        "fig3": "Sensitivity ranking.",
        "fig4": "Sensitivity heat map.",
        "fig5": "Directional sensitivity response.",
        "fig6": "Calibration convergence.",
        "fig7": "Pareto front or objective trade-off.",
        "fig8": "Calibrated-parameter relationship plot.",
    }
    pngs = sorted(figs_dir.glob("*.png")) if figs_dir.exists() else []
    if pngs:
        lines.append("### 9.1 Generated Figures")
        lines.append("")
        for img in pngs:
            stem = img.stem.split("_")[0]
            rel = img.relative_to(root).as_posix()
            title = fig_desc.get(stem, img.stem)
            lines.append(f"#### {img.stem}")
            lines.append("")
            lines.append(f"![{img.stem}]({rel})")
            lines.append("")
            lines.append(title)
            lines.append("")
    return lines


def _section_10(cfg: dict, calib: dict | None) -> list[str]:
    lines = ["## 10. Modeling-Effect Analysis", ""]
    if not isinstance(calib, dict):
        lines.append("The modeling effect cannot be assessed because calibration results are unavailable.")
        lines.append("")
        return lines
    mode = cfg.get("calibmode")
    targets = list((cfg.get("sens_targets") or {}).keys())
    lines.append("### 10.1 Overall Assessment")
    lines.append("")
    if mode in ("SingleNRMSE", "WeightedNRMSE"):
        cost = calib.get("final_cost")
        lines.append(f"The calibrated model reaches a final objective of **{_fmt_num(cost)}**. This indicates **{_quality_label(cost)}** for the configured target set: {', '.join(f'`{t}`' for t in targets) or 'none'}.")
        if calib.get("success") is False:
            lines.append("The optimizer did not report successful convergence, so the calibrated parameters should be treated as the best point found within the current budget rather than a stable optimum.")
    else:
        front = calib.get("pareto_front") or []
        lines.append(f"The multi-objective run produced **{len(front)}** Pareto solutions for {', '.join(f'`{t}`' for t in targets) or 'the configured targets'}. A broad front indicates meaningful trade-offs; a collapsed front indicates strongly aligned targets or limited identifiability.")
    lines.append("")
    lines.append("### 10.2 Identifiability and Next Steps")
    lines.append("")
    lines.append("- Inspect the sensitivity ranking to confirm that calibrated parameters are identifiable for the selected targets.")
    lines.append("- If NRMSE remains high, add missing boundary terms only when they are supported by process information, then rerun planning and calibration.")
    lines.append("- If the optimizer stops early or parameters move to implausible values, reduce the calibrated parameter subset or add stronger engineering priors.")
    lines.append("- If multiple targets conflict, prefer ParetoMOEA and compare representative solutions rather than forcing a single weighted compromise.")
    lines.append("")
    return lines


def build_report_md(cfg: dict, sens: dict | None, calib: dict | None, root) -> str:
    root = Path(root)
    lines: list[str] = []
    lines.append("# ASM Mechanistic Modeling Report (9-Step Workflow + Effect Analysis)")
    lines.append("")
    lines.append("This report is generated from `midoutput/asm_config.json`, `midoutput/sensitivity.json`, and `midoutput/calibration.json`. All executable model definitions come from `script/asmlibrary.py`.")
    lines.append("")
    lines.extend(_section_1(cfg))
    lines.extend(_section_2(cfg))
    lines.extend(_section_3(cfg))
    lines.extend(_section_4(cfg))
    lines.extend(_section_5(cfg))
    lines.extend(_section_6(cfg))
    lines.extend(_section_7(cfg, sens))
    lines.extend(_section_8(cfg, calib))
    lines.extend(_section_9(cfg, calib, root))
    lines.extend(_section_10(cfg, calib))
    return "\n".join(lines).rstrip() + "\n"
