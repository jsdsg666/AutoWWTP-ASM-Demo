"""Main LangGraph scheduler for the asmlibrary.run_pipeline workflow.

Workflow:
  START → prepare_environment → knowledge_agent
        → plan_agent → human_confirm
        → modeling_agent (asm_plan.md → asm_config_before.json)
        → reflection_agent (build asm_config.json, then static + semantic validation)
            -> ok                     -> run_model
            -> bad + retry < limit    -> modeling_agent
            -> bad + retry >= limit   -> run_model
        -> run_model (subprocess runs midoutput/model.py)
        → report_summary → END
"""
from __future__ import annotations

import json
import shutil

from langgraph.graph import END, START, StateGraph

from . import config
from .agents import knowledge_agent, modeling_agent, plan_agent, reflection_agent
from .state import AgentState
from .utils import run_python


# Maximum retry count for reflection_agent -> modeling_agent fallback loops.
MAX_REFLECTION_RETRY = 5


# ---------------------------------------------------------------------------
# Control nodes
# ---------------------------------------------------------------------------
def prepare_environment(state: AgentState) -> dict:
    """Clear previous artifacts and copy the static runner template into midoutput/model.py."""
    print("[prepare] Clearing previous intermediate artifacts...", flush=True)
    config.ensure_dirs()

    cleanup_globs = [
        (config.MID_DIR, "*.md"),
        (config.MID_DIR, "*.xlsx"),
        (config.MID_DIR, "*.json"),
        (config.MID_DIR, "*.npy"),
        (config.MID_DIR, "*.pdf"),
        (config.MID_DIR, "*.py"),
        (config.OUT_DIR, "*.md"),
        (config.OUT_DIR, "*.pdf"),
        (config.FIGS_DIR, "*.png"),
        (config.FIGS_DIR, "*.xlsx"),
        (config.FIGS_DIR, "*.json"),
    ]
    removed = 0
    cleanup_errors: list[str] = []
    for folder, pattern in cleanup_globs:
        for f in folder.glob(pattern):
            try:
                f.unlink()
                removed += 1
            except OSError as e:
                cleanup_errors.append(f"[prepare] [WARN] Failed to delete: {f} ({e})")

    # Copy the static runner template (asmmodel.py -> midoutput/model.py).
    try:
        shutil.copyfile(config.ASM_TEMPLATE_PATH, config.MODEL_PY_PATH)
        copied_msg = f"Copied runner template -> {config.MODEL_PY_PATH.relative_to(config.BASE_DIR).as_posix()}"
    except Exception as e:
        copied_msg = f"[FATAL] Failed to copy runner template: {e}"

    log = list(state.get("log", []))
    log.append(f"[prepare] Cleared {removed} previous intermediate artifact files")
    log.extend(cleanup_errors)
    log.append(f"[prepare] {copied_msg}")
    if copied_msg.startswith("[FATAL]"):
        return {"log": log, "status": "failed", "fatal_error": copied_msg}
    return {"log": log, "status": "running"}


def _hitl_prompt(stage_tag: str, hint: str) -> str:
    """Unified HITL prompt. Loop until yes/no is received."""
    print("\n" + "=" * 60)
    print(f"[HITL · {stage_tag}] {hint}")
    print("Review or edit the corresponding file in another window.")
    print("Type yes here to continue, or no to abort. Other input will be ignored.")
    print("=" * 60)
    while True:
        try:
            ans = input("> ").strip().lower()
        except EOFError:
            return "no"
        if ans in ("yes", "no"):
            return ans


def human_confirm(state: AgentState) -> dict:
    """Human confirmation after plan_agent. Skipped when HITL_AFTER_PLAN=False.

    The user may edit asm_plan.md before modeling_agent extracts asm_config.json.
    """
    log = list(state.get("log", []))
    if not config.HITL_AFTER_PLAN:
        log.append("[human_confirm] HITL_AFTER_PLAN=False; skipping human confirmation")
        return {"log": log}

    ans = _hitl_prompt(
        "ASM Plan",
        f"Generated {config.PLAN_PATH} (11-section English prose plan with ## User Input / ## Process Identification Summary / Steps 1-9)",
    )
    if ans == "no":
        log.append("[human_confirm] User entered no; aborting workflow")
        return {"log": log, "status": "aborted", "fatal_error": "User did not confirm asm_plan.md"}
    log.append("[human_confirm] User confirmed asm_plan.md")
    return {"log": log}


def run_model(state: AgentState) -> dict:
    """Run midoutput/model.py in a subprocess."""
    log = list(state.get("log", []))
    if not config.MODEL_PY_PATH.exists():
        log.append(f"[run_model] {config.MODEL_PY_PATH} does not exist; skipping execution")
        return {
            "log": log,
            "last_returncode": -1,
            "last_stdout": "",
            "last_stderr": f"{config.MODEL_PY_PATH} does not exist",
            "ode_solver_success": False,
        }
    if not config.ASM_CONFIG_PATH.exists():
        log.append(f"[run_model] {config.ASM_CONFIG_PATH} does not exist; skipping execution")
        return {
            "log": log,
            "last_returncode": -1,
            "last_stdout": "",
            "last_stderr": f"{config.ASM_CONFIG_PATH} does not exist",
            "ode_solver_success": False,
        }
    try:
        print("[run_model] Running generated model code...", flush=True)
        log.append("[run_model] Running generated model code...")
        rc, out, err = run_python(config.MODEL_PY_PATH, cwd=config.BASE_DIR, timeout=3600)
    except Exception as e:
        log.append(f"[run_model] Failed to start Python: {e}")
        return {
            "log": log,
            "last_returncode": -1,
            "last_stdout": "",
            "last_stderr": str(e),
            "ode_solver_success": False,
        }

    log.append(f"[run_model] Finished (rc={rc}, stdout {len(out)} chars, stderr {len(err)} chars)")
    if rc != 0:
        tail = (err or "")[-500:]
        log.append(f"[run_model] [WARN] midoutput/model.py failed (rc={rc}); stderr tail: {tail}")
    return {
        "last_returncode": rc,
        "last_stdout": out,
        "last_stderr": err,
        "ode_solver_success": (rc == 0),
        "log": log,
    }


def report_summary(state: AgentState) -> dict:
    """Print the artifact list before END."""
    log = list(state.get("log", []))
    if state.get("last_returncode") == 0:
        final_status = "ok"
    else:
        final_status = state.get("status") or "ok"
    if (
        state.get("config_ok") is False
        and int(state.get("reflection_retry_count", 0)) >= MAX_REFLECTION_RETRY
    ):
        final_status = "failed"
        log.append("[summary] Reflection retry limit reached; model execution was skipped.")
    if state.get("fatal_error"):
        final_status = "failed"

    # Write a visible provisional final_result.json; main.py overwrites it with a fuller result.
    provisional_final_result = {
        "run_id": config.RUN_ID,
        "run_dir": str(config.RUN_DIR),
        "variant": getattr(config, "VARIANT_NAME", config.BASE_DIR.name),
        "status": final_status,
        "fatal_error": state.get("fatal_error"),
        "last_returncode": state.get("last_returncode"),
        "process_checks_passed": bool(state.get("process_checks_passed", False)),
    }
    config.FINAL_RESULT_PATH.write_text(
        json.dumps(provisional_final_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log.append("[summary] Workflow finished. Artifact list:")
    artifacts = [
        config.KNOWLEDGE_PATH,
        config.PLAN_PATH,
        config.ASM_CONFIG_BEFORE_PATH,
        config.ASM_CONFIG_AFTER_PATH,
        config.ASM_CONFIG_PATH,
        config.PARAM_ORI_PATH,
        config.PARAM_REF_PATH,
        config.PARAM_OPT_PATH,
        config.SENS_PATH,
        config.CALIB_PATH,
        config.REPORT_MD_PATH,
        config.REPORT_PDF_PATH,
        config.FINAL_RESULT_PATH,
    ]
    if config.MODEL_PY_PATH.exists():
        artifacts.append(config.MODEL_PY_PATH)
    if config.FIGS_DIR.exists():
        artifacts.extend(sorted(config.FIGS_DIR.glob("fig*.png")))

    for a in artifacts:
        try:
            rel = a.relative_to(config.BASE_DIR)
        except ValueError:
            rel = a
        log.append(f"  {'[OK]' if a.exists() else '[--]'} {rel}")

    return {"log": log, "status": final_status}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
def route_after_human(state: AgentState):
    """plan_agent -> HITL -> modeling_agent; user abort routes directly to summary."""
    if state.get("fatal_error") or state.get("status") == "aborted":
        return "report_summary"
    return "modeling_agent"


def route_after_prepare(state: AgentState):
    """End directly if prepare fails."""
    if state.get("fatal_error") or state.get("status") == "failed":
        return "report_summary"
    return "knowledge_agent"


def route_after_reflection(state: AgentState):
    """Route after reflection_agent.

    - config_ok=True                 -> run_model
    - config_ok=False and retry < max -> modeling_agent
    - config_ok=False and retry >= max -> report_summary
    """
    if state.get("config_ok"):
        return "run_model"
    retry = int(state.get("reflection_retry_count", 0))
    if retry >= MAX_REFLECTION_RETRY:
        return "report_summary"
    return "modeling_agent"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def build_graph():
    g = StateGraph(AgentState)

    g.add_node("prepare_environment", prepare_environment)
    g.add_node("knowledge_agent", knowledge_agent)
    g.add_node("plan_agent", plan_agent)
    g.add_node("human_confirm", human_confirm)
    g.add_node("modeling_agent", modeling_agent)
    g.add_node("reflection_agent", reflection_agent)
    g.add_node("run_model", run_model)
    g.add_node("report_summary", report_summary)

    g.add_edge(START, "prepare_environment")
    g.add_conditional_edges(
        "prepare_environment",
        route_after_prepare,
        {"knowledge_agent": "knowledge_agent", "report_summary": "report_summary"},
    )
    g.add_edge("knowledge_agent", "plan_agent")
    g.add_edge("plan_agent", "human_confirm")
    g.add_conditional_edges(
        "human_confirm",
        route_after_human,
        {"modeling_agent": "modeling_agent", "report_summary": "report_summary"},
    )
    g.add_edge("modeling_agent", "reflection_agent")
    g.add_conditional_edges(
        "reflection_agent",
        route_after_reflection,
        {"run_model": "run_model", "modeling_agent": "modeling_agent", "report_summary": "report_summary"},
    )
    g.add_edge("run_model", "report_summary")
    g.add_edge("report_summary", END)

    return g.compile()
