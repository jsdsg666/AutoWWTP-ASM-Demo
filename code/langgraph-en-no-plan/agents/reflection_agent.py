"""ReflectionAgent — validates that asm_config.json can be passed to run_pipeline.

Two validation layers:
  1. Static Python validation: required fields, types, allowed values, sens_targets
     compatibility with modelcomplex, 6-key boundaries shape, and numeric ranges.
  2. LLM semantic fallback: compare asm_config.json against asm_plan.md to confirm
     that modelcomplex / calibmode / sens_targets / boundaries match the plan.

verdict:
  - approved        → run_model
  - needs_revision  -> return to modeling_agent with reflection_issues
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .. import config
from ..state import AgentState
from ..utils import chat, extract_json_block

# Import modelcomplex -> active component names
sys.path.insert(0, str(config.SCRIPT_DIR))
from asmlibrary import COMPONENTS_BY_MODEL, PARAMS  # noqa: E402
from config_finalize import (  # noqa: E402
    build_final_config,
    write_after_config,
    write_final_config,
    write_param_ori,
    write_param_ref,
)


VALID_MODELCOMPLEX = {"SimplifiedCODN", "CompleteNRN2O", "EBPRCODN", "IntegratedNPR"}
VALID_CALIBMODE = {"SingleNRMSE", "WeightedNRMSE", "ParetoMOEA"}
ALL_COMPONENTS = set(COMPONENTS_BY_MODEL["IntegratedNPR"])  # Full 21-component set
PARAM_MEANING_PATH = config.PARAM_MEANING_PATH

BOUNDARY_KEYS = ("aeration", "internal_recycle", "ras_recycle",
                 "hydraulic", "carbon_dose", "chem_dose")

# Required subfields for each boundary type
_BND_REQUIRED = {
    "aeration":         ("K_L_a", "S_O_sat"),
    "internal_recycle": ("k_r",),   # At least k_r plus one or more component reference concentrations
    "ras_recycle":      ("k_RAS", "factor"),
    "hydraulic":        ("k_HRT",),  # C_in is optional
    "carbon_dose":      ("r_dose",),
    "chem_dose":        ("r_chem",),
}

REPAIR_SYSTEM_PROMPT = r"""You are the ReflectionAgent repair submodule in the langgraph-en system. Use asm_plan.md, the parameter-meaning Markdown, the current asm_config.json, and the issue list to output a corrected complete JSON configuration.

# Output requirements

- Output only one JSON object, with no explanatory text.
- Preserve these top-level fields: modelcomplex / calibmode / sens_targets / xlsx_path / sens_delta / senstopk / maxiter / boundaries / params.
- params must be the parameter dictionary for the current modelcomplex; keys must be parameter names and values must be numeric.
- If issues involve modelcomplex, calibmode, sens_targets, boundaries, or parameter values, fix them together.
- When uncertain, prefer consistency with asm_plan.md instead of expanding the model or boundaries without evidence.
"""


# ---------------------------------------------------------------------------
# Static validation
# ---------------------------------------------------------------------------
def _validate_static(cfg: dict) -> list[str]:
    """Return a list of issues; an empty list means pass."""
    issues: list[str] = []

    # 1. Required fields
    required = ("modelcomplex", "calibmode", "sens_targets", "xlsx_path",
                "sens_delta", "senstopk", "maxiter", "boundaries")
    for k in required:
        if k not in cfg:
            issues.append(f"Missing required field `{k}`")
    if issues:
        return issues  # Return early when fields are missing; later checks require these keys.

    # 2. modelcomplex
    mc = cfg.get("modelcomplex")
    if mc not in VALID_MODELCOMPLEX:
        issues.append(f"modelcomplex={mc!r} is not in {sorted(VALID_MODELCOMPLEX)}")
        active = ALL_COMPONENTS
    else:
        active = set(COMPONENTS_BY_MODEL[mc])

    # 3. calibmode
    cm = cfg.get("calibmode")
    if cm not in VALID_CALIBMODE:
        issues.append(f"calibmode={cm!r} is not in {sorted(VALID_CALIBMODE)}")

    # 4. sens_targets
    st = cfg.get("sens_targets")
    if not isinstance(st, dict) or not st:
        issues.append("sens_targets must be a non-empty dict (keys=component variable names, values=weights)")
    else:
        for k, v in st.items():
            if k not in ALL_COMPONENTS:
                issues.append(f"sens_targets key `{k}` is not in the 21-component variable-name set")
            elif k not in active:
                issues.append(f"sens_targets key `{k}` is not active for modelcomplex={mc}")
            try:
                float(v)
            except (TypeError, ValueError):
                issues.append(f"sens_targets[{k}] weight {v!r} is not numeric")
        if cm == "SingleNRMSE" and len(st) != 1:
            issues.append(f"SingleNRMSE requires exactly 1 sens_targets key; current count is {len(st)}")
        if cm in ("WeightedNRMSE", "ParetoMOEA") and not (2 <= len(st) <= 5):
            issues.append(f"{cm} requires 2-5 sens_targets keys; current count is {len(st)}")

    # 5. xlsx_path
    xp = cfg.get("xlsx_path")
    if not isinstance(xp, str) or not xp.strip():
        issues.append("xlsx_path must be a non-empty string such as input/data.xlsx")
    else:
        try:
            resolved_xp = _resolve_project_path(xp)
            if not resolved_xp.exists():
                issues.append(f"xlsx_path points to a missing file: {xp}")
            if resolved_xp.suffix.lower() != ".xlsx":
                issues.append(f"xlsx_path must point to an .xlsx file; current value is: {xp}")
        except ValueError as e:
            issues.append(str(e))

    # 6. Numeric values
    sd = cfg.get("sens_delta")
    if not isinstance(sd, (int, float)) or not (0.05 <= float(sd) <= 0.20):
        issues.append(f"sens_delta={sd!r} must be numeric within [0.05,0.20]")
    sk = cfg.get("senstopk")
    if not isinstance(sk, int) or sk < 2 or sk > 10:
        issues.append(f"senstopk={sk!r} must be an integer within [2,10]")
    mi = cfg.get("maxiter")
    if not isinstance(mi, int) or mi < 50 or mi > 200:
        issues.append(f"maxiter={mi!r} must be an integer within [50,200]")

    # 7. params: final config must include the model-specific parameter subset
    params = cfg.get("params")
    if not isinstance(params, dict) or not params:
        issues.append("params must be a non-empty dict for the model-specific parameter subset")
    else:
        bad_keys = [k for k in params if k not in PARAMS]
        if bad_keys:
            issues.append(f"params contains illegal keys {bad_keys}")
        for k, v in params.items():
            try:
                float(v)
            except (TypeError, ValueError):
                issues.append(f"params[{k}] value {v!r} is not numeric")

    # 8. boundaries: all 6 keys present; each item is None or a dict with required subfields
    bnd = cfg.get("boundaries")
    if not isinstance(bnd, dict):
        issues.append("boundaries must be a dict with 6 fixed keys")
    else:
        for k in BOUNDARY_KEYS:
            if k not in bnd:
                issues.append(f"boundaries is missing key `{k}`; disabled boundaries must still be explicit null")
        extra = [k for k in bnd if k not in BOUNDARY_KEYS]
        if extra:
            issues.append(f"boundaries contains illegal keys {extra}; only {list(BOUNDARY_KEYS)} are allowed")
        for k in BOUNDARY_KEYS:
            v = bnd.get(k)
            if v is None:
                continue
            if not isinstance(v, dict):
                issues.append(f"boundaries[{k}] must be null or dict; current type is {type(v).__name__}")
                continue
            for sub in _BND_REQUIRED.get(k, ()):
                if sub not in v:
                    issues.append(f"boundaries[{k}] is missing subfield `{sub}`")
            if k == "internal_recycle":
                # At least one component reference concentration
                comp_keys = [x for x in v if x != "k_r"]
                if not comp_keys:
                    issues.append("boundaries[internal_recycle] must include at least 1 component reference concentration besides k_r")
                bad = [x for x in comp_keys if x not in ALL_COMPONENTS]
                if bad:
                    issues.append(f"boundaries[internal_recycle] component keys {bad} are not in the 21-component set")

    return issues


def _resolve_project_path(path_text: str) -> Path:
    """Resolve a config path and prevent it from escaping the project directory."""
    raw = Path(path_text)
    candidate = raw if raw.is_absolute() else config.BASE_DIR / raw
    resolved = candidate.resolve()
    base = config.BASE_DIR.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"xlsx_path must not point outside the project directory: {path_text}")
    return resolved


def _load_param_meaning_md() -> str:
    if not PARAM_MEANING_PATH.exists():
        return ""
    try:
        return PARAM_MEANING_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def _ensure_after_config(log: list[str]) -> dict | None:
    """Prefer generating asm_config_after.json from asm_config_before.json."""
    if config.ASM_CONFIG_BEFORE_PATH.exists():
        try:
            return write_after_config(
                config.ASM_CONFIG_BEFORE_PATH,
                config.ASM_CONFIG_AFTER_PATH,
                config.PARAM_MEANING_PATH,
            )
        except Exception as e:
            log.append(f"[reflection_agent] [FAIL] Failed to assemble asm_config_after.json: {e}")
            return None
    if config.ASM_CONFIG_AFTER_PATH.exists():
        try:
            return json.loads(config.ASM_CONFIG_AFTER_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            log.append(f"[reflection_agent] [FAIL] Failed to read asm_config_after.json: {e}")
    return None


def _repair_config(asm_plan_md: str, cfg: dict, issues: list[str], param_meaning_md: str) -> dict | None:
    """Ask the LLM to repair the complete final config; return a dict on success."""
    cfg_pretty = json.dumps(cfg, ensure_ascii=False, indent=2)
    issues_block = "\n".join(f"- {x}" for x in issues)
    user_prompt = f"""# asm_plan.md

{asm_plan_md}

# Parameter-meaning Markdown

{param_meaning_md}

# Current asm_config_after.json

```json
{cfg_pretty}
```

# Issue List

{issues_block}

Repair the configuration above. Output the corrected complete JSON object directly. Preserve the params field."""

    print("[reflection_agent] Requesting LLM repair for asm_config.json...", flush=True)
    raw = chat(REPAIR_SYSTEM_PROMPT, user_prompt)
    candidate = (extract_json_block(raw) or raw).strip()
    m = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
    if m:
        candidate = m.group(0)
    try:
        obj = json.loads(candidate)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    try:
        return build_final_config(obj, param_meaning_md)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LLM semantic fallback
# ---------------------------------------------------------------------------
SEMANTIC_SYSTEM_PROMPT = r"""You are ReflectionAgent in the langgraph-en system. An asm_config.json that passed static validation may still diverge from asm_plan.md. Your job is to compare asm_config.json against asm_plan.md and decide whether the key choices implement the plan.

# Main comparison points

1. **modelcomplex** matches Step 1 prose.
2. **calibmode** matches Step 8 prose.
3. **sens_targets** covers the calibration components named in the plan.
4. **xlsx_path** matches the path in Step 7 prose.
5. **params** matches the parameter-meaning Markdown and modelcomplex.
6. **boundaries** corresponds one-to-one with the Step 6 boundary-configuration list. Missing planned boundaries or invented unplanned boundaries are inconsistencies.

# Approval principles

- Ignore style and insignificant numeric-format differences such as sens_delta=0.1 vs 0.10.
- Do not reject content that static validation already accepted unless it truly contradicts the plan.
- Return needs_revision only when a key choice conflicts with the plan.
- If uncertain, return approved.

# Output (strict JSON, one line is fine)

```
{"verdict": "approved", "issues": []}
```

or:

```
{"verdict": "needs_revision",
 "issues": ["modelcomplex does not match the plan: plan=IntegratedNPR, config=SimplifiedCODN",
            "boundaries is missing ras_recycle listed in the plan (factor=2.0, k_RAS=0.5)"]}
```

Field constraints:
- `verdict`: must be `"approved"` or `"needs_revision"`.
- `issues`: array of strings. For needs_revision, provide at least one concrete, repairable issue; modeling_agent will regenerate based on these issues.
"""


def _semantic_check(asm_plan_md: str, cfg: dict, param_meaning_md: str) -> tuple[str, list[str]]:
    """LLM semantic comparison; parsing failure defaults to approved."""
    cfg_pretty = json.dumps(cfg, ensure_ascii=False, indent=2)
    user_prompt = f"""# asm_plan.md (plan_agent output, 11 prose sections)

{asm_plan_md}

# Parameter-meaning Markdown

{param_meaning_md}

# asm_config_after.json (extracted by modeling_agent; static validation already passed)

```json
{cfg_pretty}
```

Judge whether asm_config.json implements the asm_plan.md description according to the comparison points in the system message. Output strict JSON only."""

    print("[reflection_agent] Static validation passed; running LLM semantic comparison...", flush=True)
    raw = chat(SEMANTIC_SYSTEM_PROMPT, user_prompt)

    candidate = (extract_json_block(raw) or raw).strip()
    m = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
    if m:
        candidate = m.group(0)
    try:
        obj = json.loads(candidate)
    except Exception:
        return "approved", []
    verdict = obj.get("verdict", "approved")
    if verdict not in ("approved", "needs_revision"):
        verdict = "approved"
    issues = obj.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    issues = [str(x).strip() for x in issues if str(x).strip()]
    return verdict, issues


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def reflection_agent(state: AgentState) -> dict:
    """Static-validate asm_config.json, then run LLM semantic comparison. Failures go into reflection_issues."""
    log = list(state.get("log", []))

    cfg = _ensure_after_config(log)
    if cfg is None:
        cfg = state.get("asm_config")
    if not isinstance(cfg, dict):
        if config.ASM_CONFIG_AFTER_PATH.exists():
            try:
                cfg = json.loads(config.ASM_CONFIG_AFTER_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                log.append(f"[reflection_agent] [FAIL] Failed to parse asm_config_after.json: {e}")
                cfg = None
    if not isinstance(cfg, dict):
        retry = int(state.get("reflection_retry_count", 0)) + 1
        log.append(f"[reflection_agent] [NEEDS_REVISION] asm_config_after.json is missing or not a dict; retry={retry}")
        return {
            "config_ok": False,
            "reflection_issues": ["asm_config_after.json is missing or not a dict, so it cannot be validated"],
            "reflection_retry_count": retry,
            "log": log,
        }

    asm_plan_md = state.get("asm_plan_md") or (
        config.PLAN_PATH.read_text(encoding="utf-8") if config.PLAN_PATH.exists() else ""
    )
    param_meaning_md = _load_param_meaning_md()

    # 1. Static validation
    static_issues = _validate_static(cfg)
    if getattr(config, "VARIANT_NAME", "") == "langgraph-en-no-plan":
        if static_issues:
            retry = int(state.get("reflection_retry_count", 0)) + 1
            log.append(f"[reflection_agent] [FAIL] Static validation failed in no-plan ablation with {len(static_issues)} issue(s); retry={retry}")
            for s in static_issues:
                log.append(f"  - {s}")
            return {
                "config_ok": False,
                "reflection_issues": static_issues,
                "reflection_retry_count": retry,
                "status": "failed",
                "fatal_error": "Static validation failed in no-plan ablation",
                "log": log,
            }
        write_final_config(
            config.ASM_CONFIG_AFTER_PATH,
            config.ASM_CONFIG_PATH,
            config.PARAM_MEANING_PATH,
        )
        write_param_ori(cfg, config.PARAM_ORI_PATH)
        write_param_ref(cfg, config.PARAM_ORI_PATH, config.PARAM_REF_PATH)
        log.append("[reflection_agent] [OK] Static validation passed; semantic plan comparison skipped for no-plan ablation")
        return {"config_ok": True, "reflection_issues": [], "log": log}

    if static_issues:
        repaired = _repair_config(asm_plan_md, cfg, static_issues, param_meaning_md)
        if isinstance(repaired, dict):
            cfg = repaired
            static_issues = _validate_static(cfg)
        if static_issues:
            retry = int(state.get("reflection_retry_count", 0)) + 1
            log.append(f"[reflection_agent] [NEEDS_REVISION] Static validation failed with {len(static_issues)} issue(s); retry={retry}")
            for s in static_issues:
                log.append(f"  - {s}")
            return {
                "config_ok": False,
                "reflection_issues": static_issues,
                "reflection_retry_count": retry,
                "log": log,
            }
        log.append("[reflection_agent] [OK] Static validation passed after repair")
    log.append("[reflection_agent] [OK] Static validation passed (8 fields and complete 6-key boundaries structure)")

    # 2. LLM semantic comparison
    if not asm_plan_md.strip():
        write_final_config(
            config.ASM_CONFIG_AFTER_PATH,
            config.ASM_CONFIG_PATH,
            config.PARAM_MEANING_PATH,
        )
        write_param_ori(cfg, config.PARAM_ORI_PATH)
        write_param_ref(cfg, config.PARAM_ORI_PATH, config.PARAM_REF_PATH)
        log.append("[reflection_agent] asm_plan.md is missing; skipping LLM semantic comparison and approving")
        return {"config_ok": True, "reflection_issues": [], "log": log}

    verdict, sem_issues = _semantic_check(asm_plan_md, cfg, param_meaning_md)
    if verdict == "approved":
        write_final_config(
            config.ASM_CONFIG_AFTER_PATH,
            config.ASM_CONFIG_PATH,
            config.PARAM_MEANING_PATH,
        )
        write_param_ori(cfg, config.PARAM_ORI_PATH)
        write_param_ref(cfg, config.PARAM_ORI_PATH, config.PARAM_REF_PATH)
        log.append("[reflection_agent] [OK] LLM semantic comparison passed")
        return {"config_ok": True, "reflection_issues": [], "log": log}

    repaired = _repair_config(asm_plan_md, cfg, sem_issues, param_meaning_md)
    if isinstance(repaired, dict):
        cfg = repaired
        static_issues = _validate_static(cfg)
        if not static_issues:
            verdict, sem_issues = _semantic_check(asm_plan_md, cfg, param_meaning_md)
            if verdict == "approved":
                config.ASM_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                write_param_ori(cfg, config.PARAM_ORI_PATH)
                write_param_ref(cfg, config.PARAM_ORI_PATH, config.PARAM_REF_PATH)
                log.append("[reflection_agent] [OK] LLM semantic comparison passed after repair")
                return {"config_ok": True, "reflection_issues": [], "log": log}

    retry = int(state.get("reflection_retry_count", 0)) + 1
    log.append(f"[reflection_agent] [NEEDS_REVISION] LLM semantic comparison failed with {len(sem_issues)} issue(s); retry={retry}")
    for s in sem_issues:
        log.append(f"  - {s}")
    return {
        "config_ok": False,
        "reflection_issues": sem_issues,
        "reflection_retry_count": retry,
        "log": log,
    }
