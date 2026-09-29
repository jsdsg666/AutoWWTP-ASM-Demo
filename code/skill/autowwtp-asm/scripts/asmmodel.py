# script/asmmodel.py - static runner template copied to midoutput/model.py during prepare.
"""Runner template: read asm_config.json -> run_pipeline(**cfg) -> write asm_report.md / .pdf.

asm_config.json directly carries the nested boundaries dictionary. run_pipeline assembles
boundary_terms internally. If markdown_pdf is missing or PDF rendering fails, the runner
still writes the Markdown report and does not block the workflow.
"""
import json
import sys
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = None
for candidate in [RUN_ROOT, RUN_ROOT.parent, RUN_ROOT.parent.parent, RUN_ROOT.parent.parent.parent]:
    if (candidate / "script").is_dir():
        PROJECT_ROOT = candidate
        break
if PROJECT_ROOT is None:
    PROJECT_ROOT = RUN_ROOT
sys.path.insert(0, str(PROJECT_ROOT / "script"))
from asmlibrary import run_pipeline
from report_template import build_report_md

CFG_PATH = RUN_ROOT / "midoutput" / "asm_config.json"


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")
    cfg_obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cfg_obj, dict):
        raise TypeError("The top level of asm_config.json must be a JSON object")
    required = (
        "modelcomplex", "calibmode", "sens_targets", "xlsx_path",
        "sens_delta", "senstopk", "maxiter", "boundaries",
    )
    missing = [k for k in required if k not in cfg_obj]
    if missing:
        raise ValueError(f"asm_config.json is missing required fields: {missing}")
    if not isinstance(cfg_obj["boundaries"], dict):
        raise TypeError("asm_config.json field boundaries must be an object")
    if "params" in cfg_obj and not isinstance(cfg_obj["params"], dict):
        raise TypeError("asm_config.json field params must be an object or omitted")
    return cfg_obj


def _resolve_xlsx_path(path_text: str) -> Path:
    raw = Path(path_text)
    candidate = raw if raw.is_absolute() else PROJECT_ROOT / raw
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise ValueError(f"xlsx_path must not point outside the project directory: {path_text}")
    if resolved.suffix.lower() != ".xlsx":
        raise ValueError(f"xlsx_path must point to an .xlsx file: {path_text}")
    if not resolved.exists():
        raise FileNotFoundError(f"xlsx_path file does not exist: {resolved}")
    return resolved


cfg = _load_config(CFG_PATH)

SENS_PATH = RUN_ROOT / "midoutput" / "sensitivity.json"
CALIB_PATH = RUN_ROOT / "midoutput" / "calibration.json"

OUT_DIR = RUN_ROOT
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIGS_DIR = OUT_DIR / "figs"

xlsx_path = _resolve_xlsx_path(cfg["xlsx_path"])

run_pipeline(
    modelcomplex=cfg["modelcomplex"],
    calibmode=cfg["calibmode"],
    sens_targets=cfg["sens_targets"],
    xlsx_path=xlsx_path,
    sens_delta=cfg["sens_delta"],
    senstopk=cfg["senstopk"],
    maxiter=cfg["maxiter"],
    boundaries=cfg.get("boundaries"),
    params=cfg.get("params"),
    figs_dir=FIGS_DIR,
    sens_path=SENS_PATH,
    calib_path=CALIB_PATH,
)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
REPORT_MD = OUT_DIR / "asm_report.md"
REPORT_PDF = OUT_DIR / "asm_report.pdf"


def _safe_load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_param_changes(param_ref: dict | None, param_opt: dict | None) -> tuple[int | None, int | None]:
    if not isinstance(param_ref, dict) or not isinstance(param_opt, dict):
        return None, None
    keys = sorted(set(param_ref) | set(param_opt))
    changed = 0
    for key in keys:
        if key not in param_ref or key not in param_opt:
            changed += 1
            continue
        try:
            if abs(float(param_ref[key]) - float(param_opt[key])) > 1e-12:
                changed += 1
        except Exception:
            if param_ref.get(key) != param_opt.get(key):
                changed += 1
    return changed, len(keys)


def _update_final_result() -> None:
    final_path = RUN_ROOT / "final_result.json"
    current = _safe_load(final_path)
    if not isinstance(current, dict):
        current = {}
    param_ref = _safe_load(RUN_ROOT / "midoutput" / "param_ref.json")
    param_opt = _safe_load(RUN_ROOT / "midoutput" / "param_opt.json")
    fig2_data = _safe_load(RUN_ROOT / "figs" / "fig2_data.json")
    changed_count, total_count = _count_param_changes(param_ref, param_opt)
    updates = {
        "status": "ok",
        "final_config_path": str(CFG_PATH),
        "param_change_count": changed_count,
        "param_changed_count": changed_count,
        "param_total_count": total_count,
        "artifacts": {
            **(current.get("artifacts") if isinstance(current.get("artifacts"), dict) else {}),
            "report_md": str(REPORT_MD),
            "report_pdf": str(REPORT_PDF),
            "calibration": str(CALIB_PATH),
            "sensitivity": str(SENS_PATH),
            "asm_config": str(CFG_PATH),
        },
    }
    if isinstance(fig2_data, dict):
        baseline = fig2_data.get("baseline")
        fitted = fig2_data.get("fitted")
        if isinstance(baseline, dict):
            updates["r2_before"] = baseline
            updates["r2_before_overall"] = baseline.get("overall_mean")
        if isinstance(fitted, dict):
            updates["r2_after"] = fitted
            updates["r2_after_overall"] = fitted.get("overall_mean")
            updates["r2"] = fitted.get("overall_mean")
    current.update(updates)
    final_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_pdf(md_text: str, pdf_path: Path) -> bool:
    """Build the English PDF with markdown_pdf; return False on failure.

    Relative image links in Markdown are resolved by Section(root=RUN_ROOT).
    """
    try:
        from markdown_pdf import MarkdownPdf, Section
    except Exception as e:
        print(f"[report] markdown_pdf is unavailable; skipping PDF: {e}")
        return False

    css = (
        "body { font-family: 'SimHei', 'Microsoft YaHei', 'PingFang SC', sans-serif; "
        "font-size: 10pt; line-height: 1.45; }"
        "h1 { font-size: 18pt; } h2 { font-size: 14pt; } h3 { font-size: 12pt; }"
        "table { border-collapse: collapse; margin: 6pt 0; }"
        "th, td { border: 1px solid #888; padding: 4px 6px; font-size: 9pt; }"
        "th { background: #eee; }"
        "img { max-width: 100%; }"
    )

    try:
        pdf = MarkdownPdf(toc_level=2)
        pdf.add_section(Section(md_text, root=str(RUN_ROOT)), user_css=css)
        pdf.save(str(pdf_path))
        return True
    except Exception as e:
        print(f"[report] PDF build failed: {e}")
        return False


print("[report] Building asm_report.md / asm_report.pdf ...")
sens = _safe_load(SENS_PATH)
calib = _safe_load(CALIB_PATH)
md_text = build_report_md(cfg, sens, calib, root=RUN_ROOT)
REPORT_MD.write_text(md_text, encoding="utf-8")
print(f"[report] -> {REPORT_MD.relative_to(RUN_ROOT).as_posix()} ({len(md_text)} characters)")

if _build_pdf(md_text, REPORT_PDF):
    print(f"[report] -> {REPORT_PDF.relative_to(RUN_ROOT).as_posix()}")
else:
    print("[report] PDF skipped; only Markdown was generated")

_update_final_result()
