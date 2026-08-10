"""Global configuration for langgraph-en.

Directory conventions:
  - input/        raw data such as data.xlsx
  - output/task-YYYYMMDD-HHMMSS-ffffff/midoutput/
                  intermediate artifacts such as process context, ASM plan, sensitivity.json, calibration.json
  - output/task-YYYYMMDD-HHMMSS-ffffff/
                  final artifacts such as asm_report.md, asm_report.pdf, and figs/
  - script/       asmlibrary.py, asmmodel.py, report_template.py, and Vtolatex.py
  - references/   WWTPProcessGuide.md
  - task/         task examples
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
VARIANT_NAME = BASE_DIR.name
INPUT_DIR = BASE_DIR / "input"
OUTPUT_ROOT_DIR = BASE_DIR / "output"
RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
RUN_DIR = OUTPUT_ROOT_DIR / f"task-{RUN_ID}"
MID_DIR = RUN_DIR / "midoutput"
OUT_DIR = RUN_DIR
SCRIPT_DIR = BASE_DIR / "script"
REFERENCES_DIR = BASE_DIR / "references"
TASK_DIR = BASE_DIR / "task"

# Key intermediate artifacts
KNOWLEDGE_PATH = MID_DIR / "WWTPProcessContext.md"
PLAN_PATH = MID_DIR / "asm_plan.md"
ASM_CONFIG_BEFORE_PATH = MID_DIR / "asm_config_before.json"  # Raw extraction from modeling_agent
ASM_CONFIG_AFTER_PATH = MID_DIR / "asm_config_after.json"     # Candidate config assembled by modeling_agent with parameter files
ASM_CONFIG_PATH = MID_DIR / "asm_config.json"   # Final config assembled by processing functions under script
CANDIDATE_CONFIG_PATH = MID_DIR / "candidate_config.json"  # Initial LLM config for one-pass ASVR evaluation
PARAM_ORI_PATH = MID_DIR / "param_ori.json"   # Original parameter subset extracted from script/param.json by modelcomplex
PARAM_REF_PATH = MID_DIR / "param_ref.json"   # Parameter subset after reflection
PARAM_OPT_PATH = MID_DIR / "param_opt.json"   # Optimized parameter subset after calibration
SENS_PATH = MID_DIR / "sensitivity.json"
CALIB_PATH = MID_DIR / "calibration.json"
REPORT_MD_PATH = OUT_DIR / "asm_report.md"
REPORT_PDF_PATH = OUT_DIR / "asm_report.pdf"
FINAL_RESULT_PATH = OUT_DIR / "final_result.json"
EXEC_TRACE_PATH = OUT_DIR / "execution_trace.json"
PROCESS_CHECKS_PATH = OUT_DIR / "process_checks.json"
FIGS_DIR = OUT_DIR / "figs"  # asmlibrary writes here through the figs_dir argument

# Input data
XLSX_PATH = INPUT_DIR / "data.xlsx"

# script / references
ASM_LIBRARY_PATH = SCRIPT_DIR / "asmlibrary.py"      # Core library
ASM_TEMPLATE_PATH = SCRIPT_DIR / "asmmodel.py"       # Static runner template; copied during prepare, no placeholders
REPORT_TEMPLATE_PATH = SCRIPT_DIR / "report_template.py"
VTOLATEX_PATH = SCRIPT_DIR / "Vtolatex.py"
PARAM_JSON_PATH = SCRIPT_DIR / "param.json"
PARAM_MEANING_PATH = SCRIPT_DIR / "param_meaning.md"
WWTP_GUIDE_PATH = REFERENCES_DIR / "WWTPProcessGuide.md"
MODEL_PY_PATH = MID_DIR / "model.py"                 # Copied from asmmodel.py during prepare; subprocess entry point


def start_new_run() -> None:
    """Refresh output paths for one ASM modeling run."""
    global RUN_ID, RUN_DIR, MID_DIR, OUT_DIR
    global KNOWLEDGE_PATH, PLAN_PATH, ASM_CONFIG_BEFORE_PATH, ASM_CONFIG_AFTER_PATH, ASM_CONFIG_PATH, CANDIDATE_CONFIG_PATH
    global PARAM_ORI_PATH, PARAM_REF_PATH, PARAM_OPT_PATH, SENS_PATH, CALIB_PATH
    global REPORT_MD_PATH, REPORT_PDF_PATH, FINAL_RESULT_PATH, EXEC_TRACE_PATH, PROCESS_CHECKS_PATH, FIGS_DIR, MODEL_PY_PATH

    RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    RUN_DIR = OUTPUT_ROOT_DIR / f"task-{RUN_ID}"
    MID_DIR = RUN_DIR / "midoutput"
    OUT_DIR = RUN_DIR
    KNOWLEDGE_PATH = MID_DIR / "WWTPProcessContext.md"
    PLAN_PATH = MID_DIR / "asm_plan.md"
    ASM_CONFIG_BEFORE_PATH = MID_DIR / "asm_config_before.json"
    ASM_CONFIG_AFTER_PATH = MID_DIR / "asm_config_after.json"
    ASM_CONFIG_PATH = MID_DIR / "asm_config.json"
    CANDIDATE_CONFIG_PATH = MID_DIR / "candidate_config.json"
    PARAM_ORI_PATH = MID_DIR / "param_ori.json"
    PARAM_REF_PATH = MID_DIR / "param_ref.json"
    PARAM_OPT_PATH = MID_DIR / "param_opt.json"
    SENS_PATH = MID_DIR / "sensitivity.json"
    CALIB_PATH = MID_DIR / "calibration.json"
    REPORT_MD_PATH = OUT_DIR / "asm_report.md"
    REPORT_PDF_PATH = OUT_DIR / "asm_report.pdf"
    FINAL_RESULT_PATH = OUT_DIR / "final_result.json"
    EXEC_TRACE_PATH = OUT_DIR / "execution_trace.json"
    PROCESS_CHECKS_PATH = OUT_DIR / "process_checks.json"
    FIGS_DIR = OUT_DIR / "figs"
    MODEL_PY_PATH = MID_DIR / "model.py"

# ---------------------------------------------------------------------------
# LLM configuration currently active
# Usage: uncomment the provider block you want to use and comment out the others
# ---------------------------------------------------------------------------


LLM_BASE_URL = os.environ.get("AUTOWWTP_LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("AUTOWWTP_LLM_MODEL", "")
LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
LLM_MESSAGE_CLASS = os.environ.get("AUTOWWTP_LLM_MESSAGE_CLASS", "openai")
LLM_TEMPERATURE = float(os.environ.get("AUTOWWTP_LLM_TEMPERATURE", "1.0"))


# #1 opus4.8
# LLM_BASE_URL = "https://runapi.co/v1/messages"
# LLM_MODEL = "claude-opus-4-8"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "anthropic"
# LLM_TEMPERATURE = 1.0

# #2 gpt-5.5
# LLM_BASE_URL = "https://runapi.co/v1"
# LLM_MODEL = "gpt-5.5"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0

# #3 gemini-3.5-flash
# LLM_BASE_URL = "https://runapi.co"
# LLM_MODEL = " gemini-3.5-flash"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "gemini"
# LLM_TEMPERATURE = 1.0

# #4 grok-4.3
# LLM_BASE_URL = "https://runapi.co/v1"
# LLM_MODEL = "grok-4.3"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0


# #5 kimi-k2.6
# LLM_BASE_URL = "https://api.moonshot.cn/v1"
# LLM_MODEL = "kimi-k2.6"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0

# #6 deepseek-v4
# LLM_BASE_URL = "https://api.deepseek.com"
# LLM_MODEL = "deepseek-v4-pro[1m]"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0

# #7 glm-5.1
# LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
# LLM_MODEL = "glm-5.1"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0

# #8 qwen3.7-max
# LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# LLM_MODEL = "qwen3.7-max"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0

# #9 MiniMax M3
# LLM_BASE_URL = "https://api.minimaxi.com/v1"
# LLM_MODEL = "MiniMax M3"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0

# #10 doubao-seed-2.0-pro
# LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
# LLM_MODEL = "doubao-seed-2.0-pro"
# LLM_API_KEY = os.environ.get("AUTOWWTP_LLM_API_KEY", "")
# LLM_MESSAGE_CLASS = "openai"
# LLM_TEMPERATURE = 1.0


# ---------------------------------------------------------------------------
# Flow control
# ---------------------------------------------------------------------------
# This project does not perform inner or outer retry loops. The fixed runner
# script/model.py runs once and then emits the report.

# ---------------------------------------------------------------------------
# Human-In-The-Loop: only after plan_agent
#   True  -> pause after the artifact is generated, prompt the user to edit files,
#            continue only when the user enters yes; any other input terminates the workflow
#   False -> skip HITL for this stage and enter the next node directly
# ---------------------------------------------------------------------------
HITL_AFTER_PLAN = False           # Whether to confirm asm_plan.md manually after generation; disabled by default, enabled by main.py --hitl-plan

PYTHON_EXEC = os.environ.get("AUTOWWTP_PYTHON_EXEC", sys.executable or "python")


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------
def _build_openai(base_url: str, api_key: str, model: str, temperature: float = 1.0):
    from langchain_openai import ChatOpenAI
    kwargs = {
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
        "timeout": 600,
        "max_retries": 2,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def _build_anthropic(api_key: str, model: str, temperature: float = 1.0, base_url: str | None = None):
    from langchain_anthropic import ChatAnthropic
    kwargs = {
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
        "timeout": 600,
        "max_retries": 2,
    }
    if base_url:
        url = base_url
        if url.endswith("/messages"):
            url = url[: -len("/messages")]
        if url.endswith("/v1"):
            url = url[: -len("/v1")]
        kwargs["anthropic_api_url"] = url
    return ChatAnthropic(**kwargs)


def _build_gemini(api_key: str, model: str, temperature: float = 1.0, base_url: str | None = None):
    from langchain_google_genai import ChatGoogleGenerativeAI
    kwargs = {
        "google_api_key": api_key,
        "model": model,
        "temperature": temperature,
        "timeout": 600,
        "max_retries": 2,
    }
    if base_url:
        kwargs["client_options"] = {"api_endpoint": base_url}
    return ChatGoogleGenerativeAI(**kwargs)


_llm_cache: dict[float, object] = {}


def get_llm(temperature: float | None = None):
    """Unified LLM factory. Select the SDK from LLM_MESSAGE_CLASS and cache instances."""
    t = LLM_TEMPERATURE if temperature is None else temperature
    if t in _llm_cache:
        return _llm_cache[t]
    msg_class = LLM_MESSAGE_CLASS.lower()

    if msg_class == "openai":
        llm = _build_openai(LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, t)
    elif msg_class == "anthropic":
        llm = _build_anthropic(LLM_API_KEY, LLM_MODEL, t, LLM_BASE_URL)
    elif msg_class == "gemini":
        llm = _build_gemini(LLM_API_KEY, LLM_MODEL, t, LLM_BASE_URL)
    else:
        raise ValueError(f"Unsupported LLM_MESSAGE_CLASS: {LLM_MESSAGE_CLASS}")

    _llm_cache[t] = llm
    return llm


def ensure_dirs() -> None:
    """Ensure all output directories exist."""
    for p in [OUTPUT_ROOT_DIR, RUN_DIR, MID_DIR, OUT_DIR, FIGS_DIR, SCRIPT_DIR, REFERENCES_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def check_api_key() -> None:
    """Check that an API key is configured; exit with a clear message if missing."""
    if not LLM_API_KEY:
        print("[ERROR] API key is not set. Set AUTOWWTP_LLM_API_KEY.")
        raise SystemExit(1)
