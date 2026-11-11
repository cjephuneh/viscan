"""Build the folder a Kaggle kernel push uploads.

Copies the interpreter source and the fine-tune script. Does not copy weights,
images, or env files. Training images stay on Kaggle as a dataset attachment.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from scan_secrets import find_secrets

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ai-interpreter"


def prepare(dest: Path, kernel_slug: str = "", dataset_slug: str = "") -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy(ROOT / "kaggle/viscan-train/train.py", dest / "train.py")
    shutil.copy(APP / "requirements.txt", dest / "requirements.txt")
    shutil.copy(APP / "requirements-model.txt", dest / "requirements-model.txt")
    shutil.copytree(
        APP / "app",
        dest / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env"),
    )
    scripts = dest / "scripts"
    scripts.mkdir()
    (scripts / "__init__.py").write_text("")
    shutil.copy(APP / "scripts/finetune_via.py", scripts / "finetune_via.py")

    leaked = [path.name for path in dest.rglob(".env*")]
    if leaked:
        shutil.rmtree(dest)
        raise SystemExit(f"Refusing to package env files: {leaked}")
    secrets = find_secrets(dest)
    if secrets:
        shutil.rmtree(dest)
        raise SystemExit("Refusing to package secrets:\n" + "\n".join(secrets))

    metadata = {
        "id": kernel_slug or "owner/viscan-via-train",
        "title": "viscan-via-train",
        "code_file": "train.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": False,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [dataset_slug] if dataset_slug else [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (dest / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    notice = (
        f"Training dataset attached by CI: {dataset_slug}\n"
        if dataset_slug
        else "No KAGGLE_DATASET was set. This package has no Malhari images, so a push would not train.\n"
    )
    (dest / "DATASET.txt").write_text(notice)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: prepare_kernel.py DEST [kernel_slug] [dataset_slug]")
    prepare(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else "")


if __name__ == "__main__":
    main()
