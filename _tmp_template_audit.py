# -*- coding: utf-8 -*-
# Temporary audit script – delete after use.
import ast
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"c:\Utvikling\kildekode\systemoversikt")
APP = ROOT / "systemoversikt"
TPL_DIRS = [APP / "templates", ROOT / "templates"]

# --- templates ---
templates = {}
for td in TPL_DIRS:
    if not td.exists():
        continue
    for p in td.rglob("*.html"):
        rel = p.relative_to(td).as_posix()
        templates[rel] = str(p.relative_to(ROOT)).replace("\\", "/")

include_re = re.compile(r"""\{%\s*(include|extends)\s+['\"]([^'\"]+)['\"]""")
included_by = defaultdict(set)
extends_of = defaultdict(set)
for name, path in templates.items():
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    for m in include_re.finditer(text):
        kind, target = m.group(1), m.group(2)
        if kind == "include":
            included_by[target].add(name)
        else:
            extends_of[target].add(name)

# --- URLs via AST ---
urls_src = (APP / "urls.py").read_text(encoding="utf-8")
urls_tree = ast.parse(urls_src)
reachable = set()  # (module_alias, func_name)


def call_attr_chain(node):
    """views.foo or admin.site.login -> ('views','foo') or ('admin','site.login')"""
    if isinstance(node, ast.Name):
        return (node.id, None)
    if isinstance(node, ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            parts.reverse()
            return (parts[0], ".".join(parts[1:]))
    return None


class UrlVisitor(ast.NodeVisitor):
    def visit_Call(self, node):
        # re_path(...) or path(...)
        if isinstance(node.func, ast.Name) and node.func.id in ("re_path", "path"):
            if len(node.args) >= 2:
                view = node.args[1]
                chain = call_attr_chain(view)
                if chain and chain[1]:
                    reachable.add(chain)
                elif isinstance(view, ast.Name):
                    # local name like favicon_view
                    reachable.add(("<local>", view.id))
        self.generic_visit(node)


UrlVisitor().visit(urls_tree)

# --- Python template refs ---
# Exclude temp scripts and migrations
py_refs = defaultdict(list)  # tpl -> list of (file, outer_func, line, kind, module)
dyn_patterns = []


def module_level_func_at(source_lines, lineno):
    """Return name of module-level function containing lineno (outermost def at indent 0)."""
    current = "<module>"
    for i, line in enumerate(source_lines, 1):
        m = re.match(r"^def\s+(\w+)", line)
        if m:
            current = m.group(1)
        if i >= lineno:
            return current
    return current


STRING_RE = re.compile(r"""['\"]([a-zA-Z0-9_./\-]+\.html)['\"]""")

py_files = []
for p in APP.rglob("*.py"):
    if "migrations" in p.parts:
        continue
    if p.name.startswith("_tmp"):
        continue
    py_files.append(p)

for py in py_files:
    text = py.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    rel = str(py.relative_to(ROOT)).replace("\\", "/")
    mod = py.stem  # views, views_risiko, ...

    for m in STRING_RE.finditer(text):
        tpl = m.group(1)
        lineno = text[: m.start()].count("\n") + 1
        outer = module_level_func_at(lines, lineno)
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 80)
        ctx = text[start:end]
        kind = "string_literal"
        if (
            re.search(r"render\s*\(|TemplateResponse\s*\(", ctx)
            or "template_name" in ctx
            or "render_to_string" in ctx
            or "get_template" in ctx
            or "select_template" in ctx
            or re.search(r"template\s*=", ctx)
        ):
            kind = "renderish"
        py_refs[tpl].append((rel, outer, lineno, kind, mod))

    # dynamic: snapshot_template_name / % formatting returning html paths
    for m in re.finditer(
        r"""['\"]([^'\"]*%(?:s|d|\(\w+\)\w)[^'\"]*\.html)['\"]""", text
    ):
        lineno = text[: m.start()].count("\n") + 1
        outer = module_level_func_at(lines, lineno)
        dyn_patterns.append((rel, outer, lineno, m.group(1), mod))

    for m in re.finditer(r"""f['\"]([^'\"]+\.html)['\"]""", text):
        if "{" in m.group(1):
            lineno = text[: m.start()].count("\n") + 1
            outer = module_level_func_at(lines, lineno)
            dyn_patterns.append((rel, outer, lineno, "f:" + m.group(1), mod))

# snapshot_template_name('...', 'base.html') -> risk_snapshots/vN/base.html
# From risk_snapshot.py: return 'risk_snapshots/v%d/%s' % (template_version, base_name)
# Call sites pass base_name literals
snap_bases = set()
for py in py_files:
    text = py.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(
        r"""snapshot_template_name\s*\(\s*[^,]+,\s*['\"]([^'\"]+\.html)['\"]""", text
    ):
        snap_bases.add(m.group(1))
        lineno = text[: m.start()].count("\n") + 1
        outer = module_level_func_at(text.splitlines(), lineno)
        mod = py.stem
        rel = str(py.relative_to(ROOT)).replace("\\", "/")
        # Match existing versioned templates
        for tname in templates:
            if tname.startswith("risk_snapshots/v") and tname.endswith("/" + m.group(1)):
                py_refs[tname].append((rel, outer, lineno, "dynamic_snapshot", mod))

# Also mark pattern function itself
for tname in list(templates):
    if tname.startswith("risk_snapshots/v") and "/" in tname[16:]:
        base = tname.split("/", 2)[-1]
        if base in snap_bases:
            pass  # already added

# Check which reachable aliases exist
# Import aliases in urls: views, views_risiko, ...
# Module stem must match import alias

no_python = []
partial_only = []
python_not_url = []
page_reachable = []

for tname in sorted(templates):
    refs = [r for r in py_refs.get(tname, []) if not r[0].startswith("_tmp")]
    is_included = tname in included_by or tname in extends_of
    has_py = bool(refs)

    reachable_funcs = []
    unreachable_funcs = []
    for rel, func, lineno, kind, mod in refs:
        # Match (mod, func) against reachable; also auto_oidc etc.
        key = (mod, func)
        # admin templates special-cased later
        if key in reachable:
            reachable_funcs.append((rel, func, lineno, kind, mod))
        else:
            unreachable_funcs.append((rel, func, lineno, kind, mod))

    if not has_py and not is_included:
        no_python.append(tname)
    elif not has_py and is_included:
        partial_only.append(tname)
    elif has_py and not reachable_funcs:
        python_not_url.append((tname, unreachable_funcs, is_included))
    else:
        page_reachable.append(tname)

print("===COUNTS===")
print("total", len(templates))
print("no_python_no_include", len(no_python))
print("partial_only_no_python", len(partial_only))
print("python_not_url", len(python_not_url))
print("page_reachable", len(page_reachable))
print("reachable_pairs", len(reachable))
print("dyn_patterns", dyn_patterns)
print("snap_bases", snap_bases)

print("\n===NO_PYTHON===")
for t in no_python:
    print(t)

print("\n===PARTIAL_ONLY (%d)===" % len(partial_only))
for t in partial_only:
    parents = sorted(included_by.get(t, set()) | extends_of.get(t, set()))
    print("%s <- %s" % (t, ", ".join(parents[:6]) + ("..." if len(parents) > 6 else "")))

print("\n===PYTHON_NOT_URL===")
for t, urefs, is_inc in python_not_url:
    print("%s | included=%s" % (t, is_inc))
    for r in urefs:
        print("   ", r)

# Partials only included from unused pages
print("\n===ORPHAN_PARTIALS===")
no_py_set = set(no_python)
# Also treat python_not_url-with-no-reachable as dead page roots for orphan calc
dead_roots = set(no_python) | {t for t, _, inc in python_not_url if not inc}
# iterative: mark partials whose all parents are dead
changed = True
while changed:
    changed = False
    for t in partial_only:
        if t in dead_roots:
            continue
        parents = included_by.get(t, set()) | extends_of.get(t, set())
        if parents and parents <= dead_roots:
            dead_roots.add(t)
            changed = True
            print("orphan_partial", t, "only_from", parents)

print("\n===SPECIAL_CHECKS===")
# 404/500/403/csrf – django defaults
for t in ["403.html", "404.html", "500.html", "csrf403.html"]:
    print(t, "in_templates", t in templates, "py_refs", len(py_refs.get(t, [])), "included", t in included_by or t in extends_of)

# admin
for t in ["admin/base.html", "admin/login.html"]:
    print(t, "py", py_refs.get(t, []), "extends_of", extends_of.get(t), "included_by", included_by.get(t))

# Verify a few known URL views render expected templates
checks = [
    ("views", "recursive_group_members"),
    ("views", "cmdb_firewall"),
    ("views", "rapport_entra_id_auth"),
    ("views", "home_chart"),
    ("views", "alle_systemer_forvaltere"),
    ("views", "virksomhet_enheter"),
    ("views", "virksomhet_sikkerhetsavvik"),
    ("views", "o365_avvik"),
    ("views", "rapport_named_locations"),
    ("views", "adgruppe_graf"),
    ("views_risiko", "_render_risk_access_denied"),
    ("views_risk_snapshot", "risiko_scope_snapshot_rapport"),
    ("views_risk_snapshot", "risiko_sammenstilling_snapshot_detail"),
    ("auto_oidc", "render_access_denied"),
]
print("\n===REACHABLE_CHECK===")
for c in checks:
    print(c, "reachable=", c in reachable)

# For PYTHON_NOT_URL items, show if helper is called from reachable view (manual notes)
print("\n===HELPER_CALLERS (risiko_access_denied)===")
vr = (APP / "views_risiko.py").read_text(encoding="utf-8")
for m in re.finditer(r"_render_risk_access_denied|_deny_scope_access", vr):
    pass
print("deny helpers used:", len(re.findall(r"_render_risk_access_denied|_deny_", vr)))

# List templates referenced in render by reachable views - count
print("\n===MISSING_TEMPLATE_FILES===")
for t, refs in sorted(py_refs.items()):
    if t not in templates and any(r[3] == "renderish" for r in refs):
        print(t, refs[0])
