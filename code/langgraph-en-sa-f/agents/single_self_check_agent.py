"""Single-agent self-check ablation: one repair pass, no multi-agent reflection loop."""
from __future__ import annotations

import json
import re

from .. import config
from ..state import AgentState
from ..utils import chat, extract_json_block
from .reflection_agent import _validate_static


SYSTEM_PROMPT = r"""You are the self-check pass in langgraph-en-sa-f. Repair the generated asm_config.json once.

Output only one JSON object, with no Markdown fence and no explanation. The JSON must be a complete runnable configuration containing modelcomplex, calibmode, sens_targets, xlsx_path, sens_delta, senstopk, maxiter, boundaries, and params.

Do not introduce new task assumptions. Fix only the issues listed by the static checker."""


def _load_json(path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _parse_json(raw: str) -> dict | None:
    candidate = (extract_json_block(raw) or raw).strip()
    m = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
    if m:
        candidate = m.group(0)
    try:
        obj = json.loads(candidate)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def single_self_check_agent(state: AgentState) -> dict:
    """Run one static-check driven repair pass; fail if still invalid."""
    log = list(state.get("log", []))
    cfg = _load_json(config.ASM_CONFIG_PATH)
    if not isinstance(cfg, dict):
        msg = "asm_config.json is missing or not a JSON object before self-check"
        log.append(f"[single_self_check] [FATAL] {msg}")
        return {"log": log, "status": "failed", "fatal_error": msg}

    issues = _validate_static(cfg)
    if not issues:
        log.append("[single_self_check] Static validation passed; no repair needed")
        return {"log": log, "config_ok": True, "reflection_retry_count": 0}

    user_task = state.get("user_task", "(modeling task not specified)")
    context_md = config.KNOWLEDGE_PATH.read_text(encoding="utf-8") if config.KNOWLEDGE_PATH.exists() else ""
    plan_md = config.PLAN_PATH.read_text(encoding="utf-8") if config.PLAN_PATH.exists() else ""
    cfg_pretty = json.dumps(cfg, ensure_ascii=False, indent=2)
    issues_text = "\n".join(f"- {x}" for x in issues)

    user_prompt = f"""# User Task
{user_task}

# Generated Process Context
{context_md}

# Generated ASM Plan
{plan_md}

# Current asm_config.json
```json
{cfg_pretty}
```

# Static Issues
{issues_text}

Repair the JSON once. Output only the corrected complete JSON object."""

    print("[single_self_check] Calling the LLM for one repair pass...", flush=True)
    repaired = _parse_json(chat(SYSTEM_PROMPT, user_prompt))
    if not isinstance(repaired, dict):
        msg = "self-check output could not be parsed as JSON"
        log.append(f"[single_self_check] [FATAL] {msg}")
        return {"log": log, "status": "failed", "fatal_error": msg, "reflection_retry_count": 1}

    final_issues = _validate_static(repaired)
    if final_issues:
        msg = "self-check repaired config still failed static validation"
        log.append(f"[single_self_check] [FATAL] {msg}")
        for issue in final_issues:
            log.append(f"  - {issue}")
        return {
            "log": log,
            "status": "failed",
            "fatal_error": msg,
            "reflection_issues": final_issues,
            "reflection_retry_count": 1,
            "config_ok": False,
        }

    config.ASM_CONFIG_BEFORE_PATH.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
    config.ASM_CONFIG_AFTER_PATH.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
    config.ASM_CONFIG_PATH.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
    log.append("[single_self_check] Repaired asm_config.json in one self-check pass")
    return {
        "asm_config_before": repaired,
        "asm_config": repaired,
        "config_ok": True,
        "reflection_retry_count": 1,
        "reflection_issues": [],
        "log": log,
    }
