"""The screening core must not grow a dependency on a model runtime.

A new GPU host is a new adapter behind ViaInterpreter, selected in
build_interpreter. These tests fail when that boundary is crossed.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ROOTS = {"torch", "transformers", "peft", "huggingface_hub", "openai", "kaggle"}
ADAPTERS = {
    ROOT / "app/services/interpreter.py",
    ROOT / "scripts/model_server.py",
    ROOT / "scripts/finetune_via.py",
    ROOT / "scripts/pull_model.py",
}
CORE = (
    "app/api.py",
    "app/web.py",
    "app/services/pipeline.py",
    "app/services/rules.py",
)


def _modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _forbidden(module: str) -> bool:
    root = module.split(".", 1)[0]
    return root in FORBIDDEN_ROOTS or module.startswith("google.colab")


def test_only_adapters_import_a_model_runtime():
    offenders = []
    for folder in ("app", "scripts"):
        for path in (ROOT / folder).rglob("*.py"):
            if path.resolve() in {item.resolve() for item in ADAPTERS}:
                continue
            bad = sorted({name for name in _modules(path) if _forbidden(name)})
            if bad:
                offenders.append(f"{path.relative_to(ROOT)} imports {bad}")
    assert not offenders, "Keep model runtimes behind app/services/interpreter.py:\n" + "\n".join(offenders)


def test_screening_core_does_not_name_a_runtime():
    banned = ("colab", "kaggle", "openai", "cuda", "torch", "transformers")
    offenders = []
    for relative in CORE:
        text = (ROOT / relative).read_text().lower()
        hits = [word for word in banned if word in text]
        if hits:
            offenders.append(f"{relative} mentions {hits}")
    assert not offenders, "Choose a runtime only in build_interpreter:\n" + "\n".join(offenders)


def test_adapter_classes_implement_the_port():
    tree = ast.parse((ROOT / "app/services/interpreter.py").read_text())
    missing = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("Interpreter"):
            continue
        if node.name == "ViaInterpreter":
            continue
        methods = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
        assigned = set()
        for item in node.body:
            targets = item.targets if isinstance(item, ast.Assign) else []
            if isinstance(item, ast.AnnAssign):
                targets = [item.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
        # Class assignments can also be AnnAssign; engine and uses_references are plain assigns.
        if "interpret" not in methods or "engine" not in assigned or "uses_references" not in assigned:
            missing.append(node.name)
    assert not missing, f"Adapters must set engine, uses_references, and interpret(): {missing}"
