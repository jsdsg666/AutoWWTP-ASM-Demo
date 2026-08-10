"""Common utility functions.

Provides:
  - LLM call wrapper (system + user)
  - Markdown / code-block extraction
  - subprocess execution
  - data preview for KnowledgeAgent
"""
from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from . import config


# ---------------------------------------------------------------------------
# Token accounting (global, thread-safe)
# ---------------------------------------------------------------------------
_token_stats = {"input_tokens": 0, "output_tokens": 0}
_stats_lock = threading.Lock()


def reset_token_stats() -> None:
    with _stats_lock:
        _token_stats["input_tokens"] = 0
        _token_stats["output_tokens"] = 0


def get_token_stats() -> dict[str, int]:
    with _stats_lock:
        return dict(_token_stats)


def _estimate_tokens(llm, text: str) -> int:
    try:
        return llm.get_num_tokens(text)
    except Exception:
        return len(text)


def _estimate_input_tokens(llm, messages: list) -> int:
    try:
        return llm.get_num_tokens_from_messages(messages)
    except Exception:
        return sum(len(m.content) for m in messages if hasattr(m, "content"))


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
def chat(system_prompt: str, user_prompt: str, temperature: float | None = None) -> str:
    """Single-turn system + user call. Prefer streaming; fall back to invoke."""
    llm = config.get_llm(temperature=temperature)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    input_tokens = _estimate_input_tokens(llm, messages)
    output_tokens = 0
    result = ""

    try:
        chunks: list[str] = []
        last_chunk = None
        for chunk in llm.stream(messages):
            last_chunk = chunk
            c = chunk.content
            if isinstance(c, str):
                chunks.append(c)
            elif isinstance(c, list):
                chunks.extend(part.get("text", "") for part in c if isinstance(part, dict))
        result = "".join(chunks).strip()

        if last_chunk is not None:
            usage_meta = getattr(last_chunk, "response_metadata", {})
            usage = usage_meta.get("token_usage", usage_meta.get("usage", {}))
            if usage:
                output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
                if output_tokens:
                    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", input_tokens))
        if not output_tokens:
            output_tokens = _estimate_tokens(llm, result)
    except Exception as e:
        print(f"[utils.chat] stream failed; falling back to invoke: {type(e).__name__}: {e}")
        resp = llm.invoke(messages)
        c = resp.content
        if isinstance(c, str):
            result = c.strip()
        elif isinstance(c, list):
            result = "".join(part.get("text", "") for part in c if isinstance(part, dict)).strip()
        else:
            result = str(c).strip()

        usage = getattr(resp, "response_metadata", {}).get("token_usage", {})
        if usage:
            input_tokens = usage.get("prompt_tokens", input_tokens)
            output_tokens = usage.get("completion_tokens", 0)
        else:
            output_tokens = _estimate_tokens(llm, result)

    with _stats_lock:
        _token_stats["input_tokens"] += input_tokens
        _token_stats["output_tokens"] += output_tokens
    return result


# ---------------------------------------------------------------------------
# Output cleaning / code-block extraction
# ---------------------------------------------------------------------------
_CODE_FENCE_RE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```",
    flags=re.DOTALL | re.IGNORECASE,
)


def strip_code_fence(text: str, language: str | None = None) -> str:
    """Extract the last fenced code block, optionally matching a language."""
    matches = _CODE_FENCE_RE.findall(text)
    if not matches:
        return text.strip()
    return matches[-1].rstrip()


def strip_markdown_wrapper(text: str) -> str:
    """Strip an enclosing ```markdown ... ``` wrapper."""
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)```\s*$", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", flags=re.DOTALL | re.IGNORECASE)


def extract_json_block(text: str) -> str | None:
    """Extract the last ```json ... ``` block from Markdown without parsing."""
    matches = _JSON_FENCE_RE.findall(text)
    if not matches:
        return None
    return matches[-1].strip()


# ---------------------------------------------------------------------------
# Subprocess
# ---------------------------------------------------------------------------
def run_python(script_path: Path, cwd: Path | None = None, timeout: int = 1800) -> tuple[int, str, str]:
    """Synchronously run `python script_path`, returning (returncode, stdout, stderr).

    Force MPLBACKEND=Agg to avoid matplotlib multiprocessing issues on Windows.
    """
    import os

    cwd = cwd or config.BASE_DIR
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = subprocess.run(
            [config.PYTHON_EXEC, str(script_path)],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = e.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        err = f"{err}\n[TIMEOUT] Python subprocess exceeded {timeout} seconds and was terminated.".strip()
        return 124, out, err


# ---------------------------------------------------------------------------
# Data preview for KnowledgeAgent
# ---------------------------------------------------------------------------
def preview_inputs(n_rows: int = 5, max_files: int = 8) -> str:
    """Read the first n rows from .xlsx/.csv files under input/ and format a text preview."""
    import pandas as pd

    snippets: list[str] = []
    data_files = sorted(config.INPUT_DIR.glob("*.xlsx")) + sorted(config.INPUT_DIR.glob("*.csv"))
    for f in data_files[:max_files]:
        try:
            if f.suffix == ".csv":
                df = pd.read_csv(f, nrows=n_rows)
            else:
                df = pd.read_excel(f, nrows=n_rows)
            snippets.append(f"### {f.name}\nShape preview: first {n_rows} rows only\nColumns: {list(df.columns)}\n\n{df.to_string(index=False)}")
        except Exception as e:
            snippets.append(f"### {f.name}\nRead failed: {e}")
    if len(data_files) > max_files:
        snippets.append(f"### Too many input files\nOnly the first {max_files} files are previewed; {len(data_files) - max_files} remaining files are omitted.")
    return "\n\n".join(snippets) if snippets else "(No .xlsx/.csv data files found under input/)"
