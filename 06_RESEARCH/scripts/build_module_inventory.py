"""AS-CODED architecture audit — module inventory builder (read-only).

Scans ``04_SRC/smc/**/*.py`` with the ``ast`` module and emits a
machine-readable inventory:

    {
      "module": "smc.orchestration.engine",
      "path": "04_SRC/smc/orchestration/engine.py",
      "docstring": "<first non-empty docstring line>",
      "classes": [...],
      "functions": [...],            # module-level public functions
      "locked_constants": [...],     # names imported from smc.config.locked_constants
      "locked_constants_anywhere": [...],  # incl. attribute access / string mentions
      "referenced_by_smc": [...],    # smc modules importing this one
      "referenced_by_tests": [...],
      "referenced_by_research": [...],
      "reference_class": "smc" | "tests_only" | "research_only" | "unreferenced"
    }

Evidence source is the code itself (AST + import strings) — no doc reading,
no inference from LOCKED notes. Output goes to
``06_RESEARCH/results/architecture_audit/module_inventory.json``.

Usage:
    python 06_RESEARCH/scripts/build_module_inventory.py
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SMC_ROOT = os.path.join(REPO_ROOT, "04_SRC", "smc")
OUT_PATH = os.path.join(
    REPO_ROOT, "06_RESEARCH", "results", "architecture_audit",
    "module_inventory.json",
)


def _rel(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


def _module_name(path: str) -> str:
    rel = os.path.relpath(path, os.path.join(REPO_ROOT, "04_SRC"))
    rel = rel.replace(os.sep, "/")
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[: -len(".py")]
    return rel.replace("/", ".")


def _iter_py(root: str):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _first_docline(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


class _Collector(ast.NodeVisitor):
    """Collect top-level classes/functions and imported smc module names."""

    def __init__(self) -> None:
        self.classes: list[str] = []
        self.functions: list[str] = []
        self.imported_smc: set[str] = set()
        self.locked_names: set[str] = set()

    # --- imports ------------------------------------------------------- #
    def _record_import(self, module: str | None, names: list[str]) -> None:
        if module:
            self.imported_smc.add(module)
            if module == "smc.config.locked_constants":
                self.locked_names.update(names)
        for name in names:
            if name.startswith("smc."):
                self.imported_smc.add(name)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            if alias.name.startswith("smc"):
                self.imported_smc.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = node.module or ""
        level = node.level or 0
        if level:
            # Relative import: resolve against the package path is overkill
            # for an inventory; record it verbatim as a relative marker.
            self.imported_smc.add(f"{'.' * level}{module}")
            return
        if module.startswith("smc"):
            self._record_import(module, [a.name for a in node.names])

    # --- definitions --------------------------------------------------- #
    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        if not node.name.startswith("_"):
            self.functions.append(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self.functions.append(node.name)
        self.generic_visit(node)


# Trees scanned for IMPORT references (the inventory itself is smc-only).
REFERENCE_ROOTS = (
    os.path.join(REPO_ROOT, "04_SRC", "smc"),
    os.path.join(REPO_ROOT, "04_SRC", "tests"),
    os.path.join(REPO_ROOT, "06_RESEARCH"),
)


def build() -> dict:
    modules: list[dict] = []
    text_by_path: dict[str, str] = {}
    tree_by_path: dict[str, ast.AST] = {}

    for path in _iter_py(SMC_ROOT):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        text_by_path[path] = text
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:  # pragma: no cover - defensive
            print(f"[warn] unparsable {_rel(path)}: {exc}", file=sys.stderr)
            continue
        tree_by_path[path] = tree
        collector = _Collector()
        collector.visit(tree)
        # locked_constants mentions anywhere in the module text (imports,
        # attribute access, comments) — the "silent constant" evidence.
        mentions = sorted(
            set(re.findall(r"\b([A-Z][A-Z0-9_]{3,})\b", text))
        )
        modules.append({
            "module": _module_name(path),
            "path": _rel(path),
            "docstring": _first_docline(tree),
            "classes": sorted(set(collector.classes)),
            "functions": sorted(set(collector.functions)),
            "imports_smc": sorted(collector.imported_smc),
            "locked_constants": sorted(collector.locked_names),
            "locked_constants_anywhere": mentions,
        })

    # --- reference classification ------------------------------------- #
    for root in REFERENCE_ROOTS[1:]:
        for path in _iter_py(root):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text_by_path[path] = fh.read()

    def importers_of(target_module: str) -> dict[str, list[str]]:
        out = {"smc": [], "tests": [], "research": []}
        for path, text in text_by_path.items():
            if _module_name(path) == target_module:
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            collector = _Collector()
            collector.visit(tree)
            hits = {
                name for name in collector.imported_smc
                if name == target_module or name.startswith(target_module + ".")
            }
            if not hits:
                continue
            rel = _rel(path)
            if rel.startswith("04_SRC/smc/"):
                out["smc"].append(rel)
            elif rel.startswith("04_SRC/tests/"):
                out["tests"].append(rel)
            elif rel.startswith("06_RESEARCH/"):
                out["research"].append(rel)
        return out

    def string_importers_of(target_module: str) -> list[str]:
        """Files that mention the module path as a STRING (dynamic imports)."""
        pattern = target_module.replace(".", r"\.")
        hits = []
        for path, text in text_by_path.items():
            if re.search(pattern + r"\b", text):
                hits.append(_rel(path))
        return sorted(hits)

    for module in modules:
        refs = importers_of(module["module"])
        module["referenced_by_smc"] = sorted(refs["smc"])
        module["referenced_by_tests"] = sorted(refs["tests"])
        module["referenced_by_research"] = sorted(refs["research"])
        module["mentioned_as_string"] = [
            p for p in string_importers_of(module["module"])
            if p not in set(refs["smc"]) | set(refs["tests"]) | set(refs["research"])
        ][:12]
        if refs["smc"]:
            module["reference_class"] = "smc"
        elif refs["tests"]:
            module["reference_class"] = "tests_only"
        elif refs["research"]:
            module["reference_class"] = "research_only"
        elif module["mentioned_as_string"]:
            module["reference_class"] = "string_mention_only"
        else:
            module["reference_class"] = "unreferenced"

    # Static imports miss dynamic/string lookups (e.g. getattr seams,
    # research scripts that import by package path); the caller-side note
    # lives in the report, not here — this file is the raw scan.
    return {
        "generated_by": "06_RESEARCH/scripts/build_module_inventory.py",
        "root": "04_SRC/smc",
        "module_count": len(modules),
        "modules": modules,
    }


def main() -> None:
    inventory = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(inventory, fh, indent=2, sort_keys=False)
        fh.write("\n")
    counts: dict[str, int] = {}
    for module in inventory["modules"]:
        counts[module["reference_class"]] = counts.get(
            module["reference_class"], 0) + 1
    print(f"wrote {_rel(OUT_PATH)} ({inventory['module_count']} modules)")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")


if __name__ == "__main__":
    main()
