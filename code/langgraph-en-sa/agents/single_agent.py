"""SingleAgent one-shot ablation: generate all workflow artifacts in one LLM call."""
from __future__ import annotations

import json
import re

from .. import config
from ..state import AgentState
from ..utils import chat, extract_json_block, preview_inputs, strip_markdown_wrapper


SYSTEM_PROMPT = r"""You are the only agent in the langgraph-en-sa ablation system. Generate every workflow artifact in one response.

Output exactly these five sections, using the section markers verbatim:

<<<WWTPProcessContext.md>>>
English Markdown process context.

<<<asm_plan.md>>>
English Markdown ASM plan.

<<<asm_config_before.json>>>
```json
{...}
```

<<<asm_config_after.json>>>
```json
{...}
```

<<<asm_config.json>>>
```json
{...}
```

The three JSON artifacts must be valid JSON objects. asm_config.json must be directly runnable by script/asmmodel.py and include the 8 run_pipeline fields: modelcomplex, calibmode, sens_targets, xlsx_path, sens_delta, senstopk, maxiter, boundaries. Include params if you can infer the model parameter subset. Do not output any text outside the five marked sections."""


_MARKERS = (
    "WWTPProcessContext.md",
    "asm_plan.md",
    "asm_config_before.json",
    "asm_config_after.json",
    "asm_config.json",
)


def _section(raw: str, marker: str) -> str | None:
    pattern = rf"<<<{re.escape(marker)}>>>\s*(.*?)(?=\n<<<[^>]+>>>|\Z)"
    m = re.search(pattern, raw, flags=re.DOTALL)
    return m.group(1).strip() if m else None


def _json_section(raw: str, marker: str) -> dict | None:
    text = _section(raw, marker)
    if not text:
        return None
    candidate = extract_json_block(text) or text
    try:
        obj = json.loads(candidate)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _basic_config_issues(cfg: dict) -> list[str]:
    """Minimal runnable-shape check for one-shot ablation; no repair or normalization."""
    required = {
        "modelcomplex", "calibmode", "sens_targets", "xlsx_path",
        "sens_delta", "senstopk", "maxiter", "boundaries",
    }
    issues: list[str] = []
    missing = sorted(required - set(cfg))
    if missing:
        issues.append(f"missing required fields: {missing}")
    if "sens_targets" in cfg and not isinstance(cfg.get("sens_targets"), dict):
        issues.append("sens_targets must be a dict shaped as {component: weight}")
    if "boundaries" in cfg and not isinstance(cfg.get("boundaries"), dict):
        issues.append("boundaries must be a dict")
    xlsx_path = cfg.get("xlsx_path")
    if isinstance(xlsx_path, str):
        resolved = (config.BASE_DIR / xlsx_path).resolve()
        try:
            resolved.relative_to(config.BASE_DIR.resolve())
        except ValueError:
            issues.append("xlsx_path must not point outside the project directory")
        if resolved.suffix.lower() != ".xlsx":
            issues.append("xlsx_path must point to an .xlsx file")
        if not resolved.exists():
            issues.append(f"xlsx_path does not exist: {xlsx_path}")
    elif "xlsx_path" in cfg:
        issues.append("xlsx_path must be a string")
    return issues


def single_agent(state: AgentState) -> dict:
    """Generate all artifacts once; fail immediately on missing or malformed output."""
    log = list(state.get("log", []))
    user_task = state.get("user_task", "(modeling task not specified)")
    guide_md = config.WWTP_GUIDE_PATH.read_text(encoding="utf-8") if config.WWTP_GUIDE_PATH.exists() else ""
    param_md = config.PARAM_MEANING_PATH.read_text(encoding="utf-8") if config.PARAM_MEANING_PATH.exists() else ""
    preview = preview_inputs(n_rows=5)

    user_prompt = f"""# User Task
{user_task}

# Data Preview
{preview}

# WWTPProcessGuide.md
{guide_md}

# Parameter Meanings
{param_md}

Generate the five marked artifacts in one response. Do not rely on any later agent or repair step."""

    print("[single_agent] Calling the LLM for one-shot artifact generation...", flush=True)
    raw = chat(SYSTEM_PROMPT, user_prompt)
    print("[single_agent] LLM response received; parsing artifacts...", flush=True)

    context_md = _section(raw, "WWTPProcessContext.md")
    plan_md = _section(raw, "asm_plan.md")
    before_cfg = _json_section(raw, "asm_config_before.json")
    after_cfg = _json_section(raw, "asm_config_after.json")
    final_cfg = _json_section(raw, "asm_config.json")

    missing = []
    if not context_md:
        missing.append("WWTPProcessContext.md")
    if not plan_md:
        missing.append("asm_plan.md")
    if before_cfg is None:
        missing.append("asm_config_before.json")
    if after_cfg is None:
        missing.append("asm_config_after.json")
    if final_cfg is None:
        missing.append("asm_config.json")
    if missing:
        msg = f"Single-agent output is missing or malformed: {', '.join(missing)}"
        log.append(f"[single_agent] [FATAL] {msg}")
        return {"log": log, "status": "failed", "fatal_error": msg}

    config.MID_DIR.mkdir(parents=True, exist_ok=True)
    config.KNOWLEDGE_PATH.write_text(strip_markdown_wrapper(context_md), encoding="utf-8")
    config.PLAN_PATH.write_text(strip_markdown_wrapper(plan_md), encoding="utf-8")
    config.ASM_CONFIG_BEFORE_PATH.write_text(json.dumps(before_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    config.ASM_CONFIG_AFTER_PATH.write_text(json.dumps(after_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    config.ASM_CONFIG_PATH.write_text(json.dumps(final_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    config.CANDIDATE_CONFIG_PATH.write_text(json.dumps(before_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    issues = _basic_config_issues(final_cfg)
    if issues:
        msg = "Single-agent config failed minimal runnable-shape check: " + "; ".join(issues)
        log.append(f"[single_agent] [FATAL] {msg}")
        return {
            "process_context_md": context_md,
            "asm_plan_md": plan_md,
            "asm_config_before": before_cfg,
            "asm_config": final_cfg,
            "config_ok": False,
            "reflection_retry_count": 0,
            "status": "failed",
            "fatal_error": msg,
            "log": log,
        }

    log.append("[single_agent] Generated all five artifacts in one LLM call")
    return {
        "process_context_md": context_md,
        "asm_plan_md": plan_md,
        "asm_config_before": before_cfg,
        "asm_config": final_cfg,
        "config_ok": True,
        "reflection_retry_count": 0,
        "log": log,
    }
