"""Secret scan, kernel package, and the fact that training images are not in git."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCAN = REPO / "kaggle" / "scan_secrets.py"
PREPARE = REPO / "kaggle" / "prepare_kernel.py"

pytestmark = pytest.mark.pipeline


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scanner_flags_a_planted_token(tmp_path):
    planted = "KGAT_" + ("b" * 24)
    (tmp_path / "leak.py").write_text(f'token = "{planted}"\n')
    scan = _load(SCAN, "scan_secrets")
    assert scan.find_secrets(tmp_path) == ["leak.py:1"]


@pytest.mark.secrets
def test_repository_has_no_secrets():
    scan = _load(SCAN, "scan_secrets_repo")
    assert scan.find_secrets(REPO, scan.tracked_files(REPO)) == []


def test_agent_rules_and_ci_gates_stay_in_place():
    """Coding agents follow these files and do not delete the gates."""
    rules = (REPO / "AGENTS.md").read_text()
    locked = (REPO / ".cursor/rules/locked-agent-rules.mdc").read_text()
    ports = (REPO / "ai-interpreter/AGENTS.md").read_text()
    workflow = (REPO / ".github/workflows/ci.yml").read_text()
    for text in (rules, locked, ports):
        assert "Do not edit" in text
    assert "alwaysApply: true" in locked
    for gate in (
        "secret-scan",
        "name: type check",
        "name: code injection",
        "name: memory",
        "name: ai response contract",
        "name: all tests passed",
        "name: push training job to kaggle",
        "KAGGLE_API_TOKEN",
        "KAGGLE_KERNEL_SLUG",
        "KAGGLE_DATASET",
    ):
        assert gate in workflow
    assert (REPO / "ai-interpreter/tests/test_ports.py").is_file()


def test_training_images_are_not_tracked():
    tracked = subprocess.run(
        ["git", "ls-files", "ai-interpreter/data"],
        cwd=REPO, check=True, capture_output=True, text=True,
    )
    assert tracked.stdout.strip() == ""


def test_kernel_package_excludes_env_files_and_records_a_missing_dataset(tmp_path):
    dest = tmp_path / "kernel"
    subprocess.run([sys.executable, str(PREPARE), str(dest)], cwd=REPO, check=True)
    assert (dest / "train.py").is_file()
    assert (dest / "app/services/interpreter.py").is_file()
    assert (dest / "scripts/finetune_via.py").is_file()
    assert list(dest.rglob(".env*")) == []
    metadata = json.loads((dest / "kernel-metadata.json").read_text())
    assert metadata["dataset_sources"] == []
    assert metadata["enable_gpu"] is True
    assert "would not train" in (dest / "DATASET.txt").read_text()


def test_kernel_package_attaches_the_dataset_slug(tmp_path):
    dest = tmp_path / "kernel"
    subprocess.run(
        [sys.executable, str(PREPARE), str(dest), "owner/viscan-via-train", "owner/malhari-via"],
        cwd=REPO, check=True,
    )
    metadata = json.loads((dest / "kernel-metadata.json").read_text())
    assert metadata["id"] == "owner/viscan-via-train"
    assert metadata["dataset_sources"] == ["owner/malhari-via"]


def test_kernel_entry_sees_a_mounted_manifest(tmp_path, monkeypatch):
    manifest_dir = tmp_path / "input" / "malhari"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.csv").write_text("path,label\n")
    monkeypatch.setenv("VISCAN_DATA_DIR", str(manifest_dir))
    train = _load(REPO / "kaggle/viscan-train/train.py", "viscan_train")
    assert train.dataset_dir() == manifest_dir


def test_kernel_entry_rejects_a_flat_folder_without_grades(tmp_path):
    flat = tmp_path / "input"
    flat.mkdir()
    (flat / "P01_1.jpg").write_bytes(b"jpg")
    (flat / "P02_1.jpg").write_bytes(b"jpg")
    train = _load(REPO / "kaggle/viscan-train/train.py", "viscan_train_flat")
    reason = train.unlabeled_reason(flat)
    assert reason is not None
    assert "CIN1" in reason
    graded = tmp_path / "graded"
    (graded / "colposcopic" / "CIN1").mkdir(parents=True)
    (graded / "colposcopic" / "CIN1" / "P01_1.jpg").write_bytes(b"jpg")
    (graded / "manifest.csv").write_text("path,label\n")
    assert train.unlabeled_reason(graded) is None


def test_kernel_entry_reports_when_no_dataset_is_mounted(tmp_path, monkeypatch):
    monkeypatch.delenv("VISCAN_DATA_DIR", raising=False)
    train = _load(REPO / "kaggle/viscan-train/train.py", "viscan_train_empty")
    monkeypatch.setattr(train, "ROOT", tmp_path / "missing-repo")
    assert train.dataset_dir(mount=tmp_path / "missing-mount") is None
