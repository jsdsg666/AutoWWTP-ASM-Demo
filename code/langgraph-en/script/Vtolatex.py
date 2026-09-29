import re
import subprocess
import tempfile
import os
import sys

# ---------------------------------------------------------------------------
# 1.  LaTeX symbol -> Python identifier (CFtoV rules)
# ---------------------------------------------------------------------------

GREEK = {'\\mu': 'mu', '\\eta': 'eta', '\\rho': 'rho'}


def find_matching_brace(s: str, start: int) -> int:
    assert s[start] == '{'
    count = 0
    for i in range(start, len(s)):
        if s[i] == '{':
            count += 1
        elif s[i] == '}':
            count -= 1
            if count == 0:
                return i
    return len(s) - 1


def preprocess(expr: str) -> str:
    # keep dots inside chemical/formula fragments (do NOT turn them into commas)
    expr = expr.strip()
    for old, new in GREEK.items():
        expr = expr.replace(old, new)
    return expr


def parse_base_sub_sup(expr: str):
    i = 0
    base = ''
    # Handle leading brace-wrapped base, e.g. {NO}_{3}^{-}
    if i < len(expr) and expr[i] == '{':
        j = find_matching_brace(expr, i)
        inner = expr[i + 1:j]
        if '_' not in inner and '^' not in inner:
            base = inner
            i = j + 1
    if not base:
        while i < len(expr) and expr[i].isalpha():
            base += expr[i]
            i += 1

    subs = []
    sups = []
    tail = ''
    while i < len(expr):
        if expr[i] == '_' and i + 1 < len(expr) and expr[i + 1] == '{':
            j = find_matching_brace(expr, i + 1)
            subs.append(expr[i + 2:j])
            i = j + 1
        elif expr[i] == '^' and i + 1 < len(expr) and expr[i + 1] == '{':
            j = find_matching_brace(expr, i + 1)
            sups.append(expr[i + 2:j])
            i = j + 1
        elif expr[i] == '_':
            i += 1
            part = ''
            while i < len(expr) and expr[i].isalnum():
                part += expr[i]
                i += 1
            subs.append(part)
        elif expr[i] == '^':
            i += 1
            part = ''
            while i < len(expr) and expr[i].isalnum():
                part += expr[i]
                i += 1
            sups.append(part)
        else:
            tail += expr[i]
            i += 1
    return base, subs, sups, tail


def split_by_top_level_comma(s: str):
    parts = []
    current = ''
    depth = 0
    for ch in s:
        if ch == '{':
            depth += 1
            current += ch
        elif ch == '}':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            parts.append(current)
            current = ''
        else:
            current += ch
    if current:
        parts.append(current)
    return parts


def convert_chemical(text: str) -> str:
    text = text.replace('.', '_')
    text = re.sub(r'(?<=[A-Za-z])_(\d+)', r'_sub_\1', text)
    return text


def convert_superscript(text: str) -> str:
    text = text.strip()
    if text == '-':
        return '1minus'
    if text == '+':
        return '1plus'
    if text == '2-':
        return '2minus'
    if text == '2+':
        return '2plus'
    return text.replace('{', '').replace('}', '')


def to_python(latex_expr: str):
    """Convert a single LaTeX symbol (without surrounding $) to Python name."""
    expr = latex_expr.strip().strip('$')
    if not expr:
        return None
    expr = preprocess(expr)

    # strip outermost braces when they wrap the *whole* expression
    if expr.startswith('{') and expr.endswith('}'):
        j = find_matching_brace(expr, 0)
        if j == len(expr) - 1:
            return to_python(expr[1:-1])

    base, subs, sups, tail = parse_base_sub_sup(expr)
    if not base:
        return convert_chemical(expr)

    sub_strs = []
    for sub in subs:
        sub = sub.strip()
        if not sub:
            continue
        parts = split_by_top_level_comma(sub)
        converted_parts = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if '_{' in part or '^{' in part:
                converted = to_python(part)
                if converted is None:
                    converted = convert_chemical(part)
                converted_parts.append(converted)
            elif '_' in part and '.' not in part:
                # bare underscore like S_I, X_H, NO_2 – treat as nested symbol
                converted = to_python(part)
                if converted is None:
                    converted = convert_chemical(part)
                converted_parts.append(converted)
            else:
                converted_parts.append(convert_chemical(part))
        sub_strs.append('_sep_'.join(converted_parts))

    sup_strs = []
    for sup in sups:
        sup = sup.strip()
        if sup:
            sup_strs.append(convert_superscript(sup))

    result = base
    if sub_strs:
        result += '_sub_' + '_sub_'.join(sub_strs)
    if sup_strs:
        result += '_sup_' + '_sup_'.join(sup_strs)
    if tail:
        result += convert_chemical(tail)
    return result


# ---------------------------------------------------------------------------
# 2.  Reverse mapping: Python -> canonical LaTeX
# ---------------------------------------------------------------------------

def to_latex(py_name: str) -> str:
    """Best-effort reverse mapping (single-pass heuristic)."""
    s = py_name
    # undo sub / sup / sep
    s = s.replace('_sub_', '_{').replace('_sup_', '^{').replace('_sep_', ',')
    # close braces for subscripts and superscripts
    # This is only a rough reconstruction; full reverse is ambiguous.
    # We add } after every { that was introduced for a sub/sup.
    # Because the original may have nested braces, this is heuristic.
    # For display purposes we simply wrap the whole sub/sup block.
    # A simpler way: rebuild from parsed segments – not needed for checking.
    return s


# ---------------------------------------------------------------------------
# 3.  Extraction helpers
# ---------------------------------------------------------------------------

def extract_math_blocks(md_text: str):
    blocks = re.findall(r'\$\$?(.*?)\$?\$', md_text)
    return [b.strip() for b in blocks]


def is_likely_independent_symbol(expr: str) -> bool:
    if any(cmd in expr for cmd in ('\\frac', '\\bullet', '\\left', '\\right', '\\ ', '\\times')):
        return False
    if '=' in expr:
        return False
    # strip sub/sup contents
    temp = re.sub(r'[_^]\{[^}]*\}', '', expr)
    temp = re.sub(r'[_^][A-Za-z0-9]', '', temp)
    if any(c in temp for c in '+-*/=()[]{}\\'):
        return False
    if ' ' in temp.strip():
        return False
    return True


def extract_symbols_from_docx(docx_path: str):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(['pandoc', docx_path, '-t', 'markdown', '-o', tmp_path],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(tmp_path, 'r', encoding='utf-8') as f:
            md_text = f.read()
    finally:
        os.unlink(tmp_path)

    symbols = set()
    for expr in extract_math_blocks(md_text):
        if not expr:
            continue
        if is_likely_independent_symbol(expr):
            py_name = to_python(expr)
            if py_name and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', py_name):
                symbols.add(py_name)
    return symbols


def extract_py_vars_from_md(md_path: str):
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()
    vars_set = set()

    # 1. Inline backticks – strip code blocks first so ``` doesn't swallow content
    text_without_blocks = re.sub(r'```(?:python|text)?\n.*?```', '', text, flags=re.DOTALL)
    for m in re.finditer(r'`([^`\n]+)`', text_without_blocks):
        token = m.group(1).strip()
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', token):
            vars_set.add(token)
        else:
            # compound expression (e.g. reaction equations in Table S2)
            for subtoken in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', token):
                vars_set.add(subtoken)

    # 2. Code blocks – only keep tokens that look like CFtoV identifiers
    for m in re.finditer(r'```(?:python|text)?\n(.*?)```', text, re.DOTALL):
        block = m.group(1)
        for token in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', block):
            if '_' in token or re.fullmatch(r'rho_\d+', token) or token in ('a', 'b', 'c', 'd', 'e', 'f'):
                vars_set.add(token)

    # Remove labels like WWTP-P1
    filtered = {v for v in vars_set if not v.startswith('WWTP')}
    return filtered


def load_yingshebiao_mapping(yb_path: str):
    mapping = {}
    with open(yb_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('|'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4:
                continue
            latex_raw = parts[1]
            py_raw = parts[2]
            if '---' in latex_raw or 'Python' in py_raw or 'Original symbol' in latex_raw:
                continue
            m_py = re.search(r'`([^`]+)`', py_raw)
            if not m_py:
                continue
            py_name = m_py.group(1)
            latex_clean = latex_raw.strip().strip('$').replace('`', '')
            if latex_clean and py_name:
                mapping[py_name] = latex_clean
    return mapping


# ---------------------------------------------------------------------------
# 4.  Check routine
# ---------------------------------------------------------------------------

def check(auto_path: str, docx_path: str, yb_path: str = None):
    if yb_path is None:
        yb_path = os.path.join(os.path.dirname(auto_path), 'yingshebiao.md')

    py_vars = extract_py_vars_from_md(auto_path)
    docx_extracted = extract_symbols_from_docx(docx_path)
    yb_mapping = load_yingshebiao_mapping(yb_path)
    docx_expected = set(yb_mapping.keys())

    print(f"Loaded {len(py_vars)} identifiers from {auto_path}")
    print(f"Loaded {len(docx_expected)} mapped symbols from {yb_path}")
    print(f"Auto-extracted {len(docx_extracted)} symbols from {docx_path}")

    # 4a. authoritative comparison (AutoWWTP  vs  yingshebiao)
    only_in_auto_yb = sorted(py_vars - docx_expected)
    only_in_yb_auto = sorted(docx_expected - py_vars)
    mismatched = []
    for py in sorted(py_vars & docx_expected):
        latex = yb_mapping[py]
        converted = to_python(latex)
        if converted != py:
            mismatched.append((latex, py, converted))

    print("\n=== Authoritative check: AutoWWTP-ASM.md  vs  yingshebiao.md ===")
    if only_in_auto_yb:
        print(f"\nOnly in AutoWWTP-ASM.md ({len(only_in_auto_yb)}):")
        for v in only_in_auto_yb:
            print(f"  {v}")
    else:
        print("\nNo variables only in AutoWWTP-ASM.md.")

    if only_in_yb_auto:
        print(f"\nOnly in yingshebiao.md / missing in AutoWWTP-ASM.md ({len(only_in_yb_auto)}):")
        for v in only_in_yb_auto:
            print(f"  {v}  (source LaTeX: {yb_mapping.get(v, '?')})")
    else:
        print("\nNo symbols only in yingshebiao.md.")

    if mismatched:
        print(f"\nMismatched conversions ({len(mismatched)}):")
        for latex, py_expected, py_got in mismatched:
            print(f"  LaTeX: {latex}")
            print(f"    expected Python: {py_expected}")
            print(f"    to_python gives: {py_got}")
    else:
        print("\nAll common symbols convert consistently.")

    # 4b. cross-check against raw docx auto-extraction
    only_in_auto_ex = sorted(py_vars - docx_extracted)
    only_in_ex_auto = sorted(docx_extracted - py_vars)
    print("\n=== Cross-check: AutoWWTP-ASM.md  vs  auto-extracted from test.docx ===")
    if only_in_auto_ex:
        print(f"\nIn AutoWWTP but not auto-extracted from docx ({len(only_in_auto_ex)}):")
        for v in only_in_auto_ex:
            print(f"  {v}")
    else:
        print("\nAuto-extraction covers all AutoWWTP identifiers.")
    if only_in_ex_auto:
        print(f"\nAuto-extracted from docx but not in AutoWWTP ({len(only_in_ex_auto)}):")
        for v in only_in_ex_auto:
            print(f"  {v}")
    else:
        print("\nNo extra symbols in auto-extraction.")

    return {
        'only_in_auto_yb': only_in_auto_yb,
        'only_in_yb_auto': only_in_yb_auto,
        'mismatched': mismatched,
        'only_in_auto_ex': only_in_auto_ex,
        'only_in_ex_auto': only_in_ex_auto,
    }


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        auto = sys.argv[1]
        docx = sys.argv[2]
        yb = sys.argv[3] if len(sys.argv) >= 4 else None
        check(auto, docx, yb)
    else:
        base = os.getcwd()
        check(os.path.join(base, 'AutoWWTP-ASM.md'),
              os.path.join(base, 'test.docx'),
              os.path.join(base, 'yingshebiao.md'))
