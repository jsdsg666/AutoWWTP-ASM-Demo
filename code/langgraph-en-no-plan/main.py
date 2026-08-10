"""Entry point for langgraph-en.

Usage:
    python main.py
    python main.py --hitl-plan          # enable human confirmation after plan_agent

By default, starts CLI chat mode.
When a message contains "autowwtp-asm", the multi-agent ASM workflow is triggered.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

# The directory name contains "-" (langgraph-en), so it is not a valid Python
# module name. Register the current directory as virtual package
# `autowwtp_asm` so internal `from . import ...` imports keep working.
_PKG_DIR = Path(__file__).resolve().parent
_PKG_NAME = "autowwtp_asm"
if _PKG_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _PKG_NAME,
        _PKG_DIR / "__init__.py",
        submodule_search_locations=[str(_PKG_DIR)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_PKG_NAME] = _mod
    _spec.loader.exec_module(_mod)

from autowwtp_asm import config  # noqa: E402
from autowwtp_asm.coordinator_agent import build_graph  # noqa: E402
from autowwtp_asm.utils import chat, get_token_stats, reset_token_stats  # noqa: E402


TRIGGER_PHRASE = "autowwtp-asm"


def _configure_stdio() -> None:
    """Make Windows console and piped input robust for Unicode task text."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _clean_input_text(text: str) -> str:
    """Remove invalid surrogate code points before trigger matching or LLM calls."""
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def _extract_task_text(text: str) -> str:
    """Accept either raw task text or text prefixed by the ASM trigger phrase."""
    text = _clean_input_text(text).strip()
    if TRIGGER_PHRASE in text:
        text = text.split(TRIGGER_PHRASE, 1)[1].strip(" \t\r\n。．.，,：:")
    return text


def _safe_load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_param_changes(param_ori: dict | None, param_opt: dict | None) -> tuple[int | None, int | None]:
    if not isinstance(param_ori, dict) or not isinstance(param_opt, dict):
        return None, None
    keys = sorted(set(param_ori) | set(param_opt))
    changed = 0
    for k in keys:
        if k not in param_ori or k not in param_opt:
            changed += 1
            continue
        a = param_ori.get(k)
        b = param_opt.get(k)
        try:
            if abs(float(a) - float(b)) > 1e-12:
                changed += 1
        except Exception:
            if a != b:
                changed += 1
    return changed, len(keys)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _active_model_scope(modelcomplex: str) -> tuple[set[str], set[str]]:
    """Return active components and parameter names for the selected modelcomplex."""
    if str(config.SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(config.SCRIPT_DIR))
    from asmlibrary import COMPONENTS_BY_MODEL, PARAMS, RATE_EQUATIONS, REACTIONS_BY_MODEL, STOICHIOMETRY

    components = set(COMPONENTS_BY_MODEL.get(modelcomplex, []))
    active_tokens: set[str] = set()
    for rid in REACTIONS_BY_MODEL.get(modelcomplex, []):
        active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", RATE_EQUATIONS[rid]))
        for coeff_expr in STOICHIOMETRY[rid].values():
            if isinstance(coeff_expr, str):
                active_tokens.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", coeff_expr))
    params = {name for name in PARAMS if name in active_tokens}
    return components, params


def _param_diff_keys(left: dict | None, right: dict | None) -> list[str]:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return []
    changed: list[str] = []
    for k in sorted(set(left) | set(right)):
        if k not in left or k not in right:
            changed.append(k)
            continue
        try:
            if abs(float(left[k]) - float(right[k])) > 1e-12:
                changed.append(k)
        except Exception:
            if left.get(k) != right.get(k):
                changed.append(k)
    return changed


def _write_process_checks(user_task: str) -> dict:
    """Write file-backed process checks for hallucination-prone workflow stages."""
    cfg = _safe_load_json(config.ASM_CONFIG_PATH) or {}
    before_cfg = _safe_load_json(config.ASM_CONFIG_BEFORE_PATH) or {}
    sens = _safe_load_json(config.SENS_PATH) or {}
    param_ori = _safe_load_json(config.PARAM_ORI_PATH)
    param_ref = _safe_load_json(config.PARAM_REF_PATH)
    param_opt = _safe_load_json(config.PARAM_OPT_PATH)

    checks: list[dict] = []

    sens_targets_obj = cfg.get("sens_targets") if isinstance(cfg, dict) else None
    targets = list(sens_targets_obj.keys()) if isinstance(sens_targets_obj, dict) else []
    knowledge_text = _read_text(config.KNOWLEDGE_PATH)
    target_hits = [t for t in targets if t in knowledge_text]
    checks.append({
        "id": "knowledge_context_bound_to_targets",
        "file": str(config.KNOWLEDGE_PATH),
        "passed": config.KNOWLEDGE_PATH.exists() and len(knowledge_text.strip()) >= 200 and len(target_hits) >= max(1, min(2, len(targets))),
        "details": {
            "file_exists": config.KNOWLEDGE_PATH.exists(),
            "char_count": len(knowledge_text),
            "target_hits": target_hits,
        },
    })

    plan_text = _read_text(config.PLAN_PATH)
    modelcomplex = cfg.get("modelcomplex")
    calibmode = cfg.get("calibmode")
    senstopk = cfg.get("senstopk")
    def _contains_choice(label: str, value) -> bool:
        if value is None:
            return False
        text = str(value)
        patterns = [
            f"{label}={text}",
            f"{label} = {text}",
            f"{label} is {text}",
            f"{label} **{text}**",
            f"{label}: {text}",
        ]
        haystack = plan_text.lower()
        return any(p.lower() in haystack for p in patterns)

    plan_hits = {
        "modelcomplex": _contains_choice("modelcomplex", modelcomplex),
        "calibmode": _contains_choice("calibmode", calibmode),
        "senstopk": _contains_choice("senstopk", senstopk),
        "user_task_echo": bool(user_task.strip() and user_task.strip()[:20] in plan_text),
    }
    if getattr(config, "VARIANT_NAME", "") == "langgraph-en-no-plan":
        checks.append({
            "id": "config_declares_core_choices",
            "file": str(config.ASM_CONFIG_BEFORE_PATH),
            "passed": all(v is not None for v in (modelcomplex, calibmode, senstopk)) and bool(cfg.get("sens_targets")),
            "skipped_replacement_for": "plan_declares_core_choices",
            "details": {
                "modelcomplex": modelcomplex,
                "calibmode": calibmode,
                "senstopk": senstopk,
                "sens_targets": cfg.get("sens_targets"),
            },
        })
    else:
        checks.append({
            "id": "plan_declares_core_choices",
            "file": str(config.PLAN_PATH),
            "passed": config.PLAN_PATH.exists() and all(plan_hits.values()),
            "details": plan_hits,
        })

    required_fields = {
        "modelcomplex", "calibmode", "sens_targets", "xlsx_path",
        "sens_delta", "senstopk", "maxiter", "boundaries",
    }
    boundary_keys = {
        "aeration", "internal_recycle", "ras_recycle",
        "hydraulic", "carbon_dose", "chem_dose",
    }
    before_fields = set(before_cfg) if isinstance(before_cfg, dict) else set()
    before_boundaries = before_cfg.get("boundaries") if isinstance(before_cfg, dict) else None
    checks.append({
        "id": "modeling_json_required_shape",
        "file": str(config.ASM_CONFIG_BEFORE_PATH),
        "passed": (
            config.ASM_CONFIG_BEFORE_PATH.exists()
            and required_fields.issubset(before_fields)
            and isinstance(before_boundaries, dict)
            and boundary_keys.issubset(set(before_boundaries))
        ),
        "details": {
            "missing_fields": sorted(required_fields - before_fields),
            "missing_boundary_keys": sorted(boundary_keys - set(before_boundaries or {})),
            "extra_fields": sorted(before_fields - required_fields),
        },
    })

    active_components: set[str] = set()
    active_params: set[str] = set()
    scope_error = None
    if isinstance(modelcomplex, str):
        try:
            active_components, active_params = _active_model_scope(modelcomplex)
        except Exception as e:
            scope_error = str(e)
    params_obj = cfg.get("params") if isinstance(cfg, dict) else None
    cfg_params = set(params_obj.keys()) if isinstance(params_obj, dict) else set()
    cfg_targets = set(sens_targets_obj.keys()) if isinstance(sens_targets_obj, dict) else set()
    checks.append({
        "id": "final_config_matches_active_model_scope",
        "file": str(config.ASM_CONFIG_PATH),
        "passed": (
            config.ASM_CONFIG_PATH.exists()
            and bool(active_params)
            and cfg_params == active_params
            and cfg_targets.issubset(active_components)
        ),
        "details": {
            "modelcomplex": modelcomplex,
            "scope_error": scope_error,
            "unexpected_params": sorted(cfg_params - active_params),
            "missing_params": sorted(active_params - cfg_params),
            "invalid_targets": sorted(cfg_targets - active_components),
            "param_count": len(cfg_params),
        },
    })

    topk = sens.get("topk") if isinstance(sens, dict) else None
    topk_names = [
        str(x.get("parameter"))
        for x in (topk or [])
        if isinstance(x, dict) and x.get("parameter") is not None
    ]
    changed_ref_to_opt = _param_diff_keys(param_ref, param_opt)
    checks.append({
        "id": "sensitivity_topk_drives_optimized_params",
        "file": str(config.SENS_PATH),
        "passed": (
            config.SENS_PATH.exists()
            and config.PARAM_OPT_PATH.exists()
            and isinstance(topk, list)
            and len(topk_names) == int(senstopk or -1)
            and sorted(changed_ref_to_opt) == sorted(topk_names)
        ),
        "details": {
            "senstopk": senstopk,
            "topk_names": topk_names,
            "changed_ref_to_opt": changed_ref_to_opt,
            "param_ori_ref_diff": _param_diff_keys(param_ori, param_ref),
        },
    })

    result = {
        "run_id": config.RUN_ID,
        "all_passed": all(bool(c.get("passed")) for c in checks),
        "checks": checks,
    }
    config.PROCESS_CHECKS_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _write_execution_trace(final: dict, elapsed: float) -> dict:
    """Write shared trace fields used by ASVR across all experiment variants."""
    log = [str(x) for x in final.get("log", [])]
    needs_revision_count = sum("NEEDS_REVISION" in x for x in log)
    json_parse_error_count = sum(("could not be parsed" in x or "Failed to parse" in x) for x in log)
    trace = {
        "run_id": config.RUN_ID,
        "variant": getattr(config, "VARIANT_NAME", config.BASE_DIR.name),
        "status": final.get("status"),
        "fatal_error": final.get("fatal_error"),
        "elapsed_seconds": round(float(elapsed), 6),
        "candidate_config_path": str(config.CANDIDATE_CONFIG_PATH),
        "final_config_path": str(config.ASM_CONFIG_PATH),
        "repair_count": int(final.get("reflection_retry_count", 0) or 0),
        "needs_revision_count": int(needs_revision_count),
        "json_parse_error_count": int(json_parse_error_count),
        "model_returncode": final.get("last_returncode"),
        "ode_solver_success": bool(final.get("ode_solver_success", False)),
    }
    config.EXEC_TRACE_PATH.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return trace


def _derive_fail_fast_status(final: dict, process_checks: dict | None) -> tuple[str, str | None]:
    """Derive strict ablation status; do not turn failed artifacts into an ok run."""
    if final.get("fatal_error"):
        return "failed", str(final.get("fatal_error"))
    rc = final.get("last_returncode")
    if rc not in (0, None):
        return "failed", f"run_model failed with returncode={rc}"
    if final.get("ode_solver_success") is False:
        return "failed", "ODE solver did not report success"
    if isinstance(process_checks, dict) and process_checks.get("all_passed") is False:
        return "failed", "process_checks did not pass"
    return final.get("status") or "ok", None


def _prompt_user_task() -> str:
    """Interactively read one ASM task; blank line ends input."""
    print("=" * 70)
    print("langgraph-en - multi-agent ASM mechanistic modeling pipeline")
    print("Enter the ASM modeling task. Paste multiple lines, then submit a blank line.")
    print("Recommended task details:")
    print("  1) Dataset path              (for example: input/data.xlsx)")
    print("  2) Simulated tank/process    (for example: A2/O aerobic tank, single CSTR, SBR)")
    print("  3) Main model relationships  (for example: COD-N coupling, N2O intermediates, EBPR)")
    print("  4) Mass-balance boundaries   (6 types: aeration K_L_a/S_O_sat, internal recycle k_r plus component references,")
    print("                                RAS k_RAS/factor, hydraulic k_HRT, carbon dose r_dose, chemical dose r_chem;")
    print("                                write 'no additional boundaries' for a reaction-only scenario)")
    print("  5) Calibration targets/weights (for example: nitrate + orthophosphate weights 0.3/0.7; one target for single-objective, 2-5 for weighted/Pareto)")
    print("  6) Calibration mode          (for example: single-target NRMSE, weighted multi-target, Pareto MOEA)")
    print("=" * 70)

    lines: list[str] = []
    try:
        while True:
            line = _clean_input_text(input())
            if line.strip() == "":
                break
            lines.append(line)
    except (KeyboardInterrupt, EOFError):
        print("\nInput cancelled by user.")
        return ""

    user_task = "\n".join(lines).strip()
    if not user_task:
        print("[ERROR] No task text was entered.")
        return ""
    return user_task


def _run_multi_agent(user_task: str) -> int:
    """Run the multi-agent ASM workflow."""
    config.start_new_run()
    config.ensure_dirs()

    print("\n" + "=" * 70)
    print("Modeling task:", user_task)
    print(f"Base directory: {config.BASE_DIR}")
    print(f"LLM     : {config.LLM_BASE_URL} / {config.LLM_MODEL} (T={config.LLM_TEMPERATURE})")
    print(f"Python  : {config.PYTHON_EXEC}")
    print("=" * 70)

    start_time = time.perf_counter()
    print("\n[start] Compiling LangGraph workflow...")
    graph = build_graph()
    print("[start] Workflow is running. LLM calls may take seconds to minutes...\n")
    final = graph.invoke(
        {"user_task": user_task, "log": []},
        config={"recursion_limit": 50},
    )

    elapsed = time.perf_counter() - start_time
    tokens = get_token_stats()
    calib = _safe_load_json(config.CALIB_PATH)
    fig2 = _safe_load_json(config.FIGS_DIR / "fig2_data.json")
    r2_value = None
    if isinstance(fig2, dict):
        fitted = fig2.get("fitted") or {}
        if isinstance(fitted, dict) and fitted.get("overall_mean") is not None:
            r2_value = fitted.get("overall_mean")
    if r2_value is None and isinstance(calib, dict):
        r2_map = calib.get("r2_recovered")
        if isinstance(r2_map, dict) and r2_map:
            try:
                r2_value = sum(float(v) for v in r2_map.values()) / len(r2_map)
            except Exception:
                r2_value = None

    execution_trace = _write_execution_trace(final, elapsed)
    r2_before = None
    r2_after = None
    if isinstance(fig2, dict):
        baseline = fig2.get("baseline")
        fitted = fig2.get("fitted")
        if isinstance(baseline, dict):
            r2_before = baseline
        if isinstance(fitted, dict):
            r2_after = fitted
    if r2_after is None and isinstance(calib, dict):
        recovered = calib.get("r2_recovered")
        if isinstance(recovered, dict):
            r2_after = recovered

    param_ori = _safe_load_json(config.PARAM_ORI_PATH)
    param_ref = _safe_load_json(config.PARAM_REF_PATH)
    param_opt = _safe_load_json(config.PARAM_OPT_PATH)
    changed_count, total_count = _count_param_changes(param_ori, param_opt)
    process_checks = _write_process_checks(user_task)
    strict_status, strict_error = _derive_fail_fast_status(final, process_checks)
    execution_trace["process_checks_path"] = str(config.PROCESS_CHECKS_PATH)
    execution_trace["process_checks_passed"] = bool(process_checks.get("all_passed"))
    execution_trace["status"] = strict_status
    if strict_error:
        execution_trace["fatal_error"] = strict_error
    config.EXEC_TRACE_PATH.write_text(
        json.dumps(execution_trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    final_result = {
        "run_id": config.RUN_ID,
        "run_dir": str(config.RUN_DIR),
        "variant": getattr(config, "VARIANT_NAME", config.BASE_DIR.name),
        "user_task": user_task,
        "status": strict_status,
        "fatal_error": strict_error or final.get("fatal_error"),
        "elapsed_seconds": round(float(elapsed), 6),
        "input_tokens": int(tokens.get("input_tokens", 0)),
        "output_tokens": int(tokens.get("output_tokens", 0)),
        "r2_before": r2_before,
        "r2_after": r2_after,
        "r2_before_overall": (r2_before or {}).get("overall_mean"),
        "r2_after_overall": (r2_after or {}).get("overall_mean"),
        "r2": (r2_after or {}).get("overall_mean", r2_value),
        "param_change_count": changed_count,
        "param_changed_count": changed_count,
        "param_total_count": total_count,
        "execution_trace": str(config.EXEC_TRACE_PATH),
        "process_checks": str(config.PROCESS_CHECKS_PATH),
        "process_checks_passed": bool(process_checks.get("all_passed")),
        "artifacts": {
            "report_md": str(config.REPORT_MD_PATH),
            "report_pdf": str(config.REPORT_PDF_PATH),
            "calibration": str(config.CALIB_PATH),
            "fig2_data": str(config.FIGS_DIR / "fig2_data.json"),
            "param_ori": str(config.PARAM_ORI_PATH),
            "param_ref": str(config.PARAM_REF_PATH),
            "param_opt": str(config.PARAM_OPT_PATH),
            "candidate_config": str(config.CANDIDATE_CONFIG_PATH),
            "asm_config_before": str(config.ASM_CONFIG_BEFORE_PATH),
            "asm_config_after": str(config.ASM_CONFIG_AFTER_PATH),
            "asm_config": str(config.ASM_CONFIG_PATH),
        },
    }
    config.FINAL_RESULT_PATH.write_text(
        json.dumps(final_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n========== Scheduler Log ==========")
    for line in final.get("log", []):
        print(line)

    print("\n========== Task Statistics ==========")
    print(f"Elapsed time       : {elapsed:.2f} seconds")
    print(f"Total input tokens : {tokens['input_tokens']}")
    print(f"Total output tokens: {tokens['output_tokens']}")
    print(f"Changed parameters : {changed_count}/{total_count}")
    print(f"execution_trace: {config.EXEC_TRACE_PATH}")
    print(f"process_checks : {config.PROCESS_CHECKS_PATH} (all_passed={process_checks.get('all_passed')})")
    print(f"final_result   : {config.FINAL_RESULT_PATH}")

    if strict_status == "failed":
        if strict_error:
            print(f"\n[FATAL] {strict_error}")
        return 1

    print(f"\n[STATUS] {final.get('status')}")
    return 0


def _chat_loop() -> int:
    """Persistent CLI: chat normally; trigger the multi-agent workflow on the trigger phrase."""
    system_prompt = (
        "You are a concise English CLI assistant. "
        f"When the user message contains \"{TRIGGER_PHRASE}\", extract only the content after it as the ASM modeling task. "
        "If no content follows, ask the user to provide the task description."
    )
    history: list[object] = []
    print("=" * 70)
    print("langgraph-en CLI started")
    print(f'Enter normal messages to chat; include "{TRIGGER_PHRASE}" to trigger ASM modeling.')
    print("Enter `exit` or `quit` to exit.")
    print("=" * 70)

    while True:
        try:
            user_msg = _clean_input_text(input("you> ")).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return 0

        if not user_msg:
            continue
        if user_msg.lower() in {"exit", "quit"}:
            print("Exiting.")
            return 0

        if TRIGGER_PHRASE in user_msg:
            task = user_msg.split(TRIGGER_PHRASE, 1)[1].strip(" \t\r\n。．.，,：:")
            if not task:
                print(f'assistant> Please add the modeling task after "{TRIGGER_PHRASE}".')
                continue
            reset_token_stats()
            rc = _run_multi_agent(task)
            if rc != 0:
                print(f"assistant> ASM modeling workflow finished with exit code: {rc}")
            print("\nassistant> Back to CLI chat mode.")
            reset_token_stats()
            continue

        history.append(HumanMessage(content=user_msg))
        resp = chat(system_prompt, user_msg)
        print(f"assistant> {resp}")


def main():
    _configure_stdio()

    ap = argparse.ArgumentParser(description="langgraph-en multi-agent ASM modeling runner")
    ap.add_argument("--hitl-plan", action="store_true", help="Enable human confirmation after the ASM plan is generated")
    ap.add_argument("--once", action="store_true", help="Legacy mode: read one task interactively, then run the multi-agent workflow")
    ap.add_argument("--task", help="Pass one ASM modeling task directly for non-interactive execution")
    ap.add_argument("--task-file", help="Read a task Markdown file for non-interactive execution")
    args = ap.parse_args()

    if args.hitl_plan:
        config.HITL_AFTER_PLAN = True

    config.check_api_key()
    reset_token_stats()

    if args.task_file:
        task_path = Path(args.task_file)
        if not task_path.is_absolute():
            task_path = config.BASE_DIR / task_path
        if not task_path.exists():
            print(f"[ERROR] Task file does not exist: {task_path}")
            return 1
        user_task = _extract_task_text(task_path.read_text(encoding="utf-8"))
        if not user_task:
            print(f'[ERROR] Task file is empty or missing the task description after "{TRIGGER_PHRASE}": {task_path}')
            return 1
        return _run_multi_agent(user_task)

    if args.task:
        user_task = _extract_task_text(args.task)
        if not user_task:
            print("[ERROR] --task is empty.")
            return 1
        return _run_multi_agent(user_task)

    if args.once:
        user_task = _prompt_user_task()
        if not user_task:
            print("[ERROR] No task was entered; exiting.")
            return 1
        return _run_multi_agent(user_task)

    return _chat_loop()


if __name__ == "__main__":
    raise SystemExit(main())
