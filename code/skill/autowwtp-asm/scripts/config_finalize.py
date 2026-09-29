"""Assemble and filter parameters for asm_config_before.json -> asm_config_after.json / asm_config.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asmlibrary import PARAMS, RATE_EQUATIONS, REACTIONS_BY_MODEL, STOICHIOMETRY  # noqa: E402


def _extract_model_params(modelcomplex: str, source_params: dict[str, float] | None = None) -> dict[str, float]:
    if modelcomplex not in REACTIONS_BY_MODEL:
        raise ValueError(f"Unknown modelcomplex: {modelcomplex}")

    source = PARAMS if source_params is None else source_params
    active_tokens: set[str] = set()
    for rid in REACTIONS_BY_MODEL[modelcomplex]:
        active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", RATE_EQUATIONS[rid]))
        for coeff_expr in STOICHIOMETRY[rid].values():
            if isinstance(coeff_expr, str):
                active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", coeff_expr))

    return {name: float(source[name]) for name in source if name in active_tokens}


def _project_param_subset(modelcomplex: str, source_params: dict[str, float]) -> dict[str, float]:
    """Keep only parameters relevant to the current modelcomplex."""
    return _extract_model_params(modelcomplex, source_params)


def _build_config(base_cfg: dict) -> dict:
    if not isinstance(base_cfg, dict):
        raise TypeError("base_cfg must be a dict")

    modelcomplex = base_cfg.get("modelcomplex")
    if not isinstance(modelcomplex, str) or not modelcomplex.strip():
        raise ValueError("base_cfg is missing a valid modelcomplex")

    params = _extract_model_params(modelcomplex)
    override_params = base_cfg.get("params")
    if isinstance(override_params, dict):
        for k, v in override_params.items():
            if k in params:
                params[k] = float(v)

    cfg = dict(base_cfg)
    cfg["params"] = params
    return cfg


def build_after_config(before_cfg: dict, param_meaning_md: str | None = None) -> dict:
    """Filter parameters from param.json by modelcomplex and append them to the after config."""
    return _build_config(before_cfg)


def build_final_config(after_cfg: dict, param_meaning_md: str | None = None) -> dict:
    """Normalize the after config into the final runnable config."""
    return _build_config(after_cfg)


def build_param_ori(cfg: dict) -> dict[str, float]:
    """Extract the original parameter subset for the current modelcomplex from default param.json."""
    modelcomplex = cfg.get("modelcomplex")
    if not isinstance(modelcomplex, str) or not modelcomplex.strip():
        raise ValueError("cfg is missing a valid modelcomplex")
    return _project_param_subset(modelcomplex, PARAMS)


def build_param_ref(cfg: dict, param_ori: dict[str, float]) -> dict[str, float]:
    """Generate the post-reflection parameter subset from param_ori and current cfg.params."""
    modelcomplex = cfg.get("modelcomplex")
    if not isinstance(modelcomplex, str) or not modelcomplex.strip():
        raise ValueError("cfg is missing a valid modelcomplex")
    ref = dict(param_ori)
    overrides = cfg.get("params")
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            if k in ref:
                ref[k] = float(v)
    return ref


def build_param_opt(param_ref: dict[str, float], optimized: dict[str, float] | None) -> dict[str, float]:
    """Overlay calibrated optimized parameters onto param_ref."""
    opt = dict(param_ref)
    if isinstance(optimized, dict):
        for k, v in optimized.items():
            if k in opt:
                opt[k] = float(v)
    return opt


def write_after_config(
    before_path: Path,
    after_path: Path,
    param_meaning_path: Path | None = None,
) -> dict:
    """Read the before config and generate asm_config_after.json."""
    before_cfg = json.loads(before_path.read_text(encoding="utf-8"))
    param_md = None
    if param_meaning_path is not None and param_meaning_path.exists():
        param_md = param_meaning_path.read_text(encoding="utf-8")
    after_cfg = build_after_config(before_cfg, param_md)
    after_path.parent.mkdir(parents=True, exist_ok=True)
    after_path.write_text(json.dumps(after_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return after_cfg


def write_final_config(
    after_path: Path,
    final_path: Path,
    param_meaning_path: Path | None = None,
) -> dict:
    """Read the after config and generate final asm_config.json."""
    after_cfg = json.loads(after_path.read_text(encoding="utf-8"))
    param_md = None
    if param_meaning_path is not None and param_meaning_path.exists():
        param_md = param_meaning_path.read_text(encoding="utf-8")
    final_cfg = build_final_config(after_cfg, param_md)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(final_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_cfg


def write_param_ori(cfg: dict, param_ori_path: Path) -> dict[str, float]:
    param_ori = build_param_ori(cfg)
    param_ori_path.parent.mkdir(parents=True, exist_ok=True)
    param_ori_path.write_text(json.dumps(param_ori, ensure_ascii=False, indent=2), encoding="utf-8")
    return param_ori


def write_param_ref(cfg: dict, param_ori_path: Path, param_ref_path: Path) -> dict[str, float]:
    if param_ori_path.exists():
        param_ori = json.loads(param_ori_path.read_text(encoding="utf-8"))
    else:
        param_ori = build_param_ori(cfg)
        param_ori_path.parent.mkdir(parents=True, exist_ok=True)
        param_ori_path.write_text(json.dumps(param_ori, ensure_ascii=False, indent=2), encoding="utf-8")
    param_ref = build_param_ref(cfg, param_ori)
    param_ref_path.parent.mkdir(parents=True, exist_ok=True)
    param_ref_path.write_text(json.dumps(param_ref, ensure_ascii=False, indent=2), encoding="utf-8")
    return param_ref


def write_param_opt(param_ref_path: Path, param_opt_path: Path, optimized: dict[str, float] | None) -> dict[str, float]:
    if param_ref_path.exists():
        param_ref = json.loads(param_ref_path.read_text(encoding="utf-8"))
    else:
        raise FileNotFoundError(f"param_ref.json does not exist: {param_ref_path}")
    param_opt = build_param_opt(param_ref, optimized)
    param_opt_path.parent.mkdir(parents=True, exist_ok=True)
    param_opt_path.write_text(json.dumps(param_opt, ensure_ascii=False, indent=2), encoding="utf-8")
    return param_opt
