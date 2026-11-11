"""Kaggle entry point. CI copies this next to app/ and scripts/ after the tests pass.

AI developers change the training settings here. The pipeline starts this file
only when the secret scan, type check, and test jobs are green, and when the
repository variable KAGGLE_DATASET names a real dataset.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# prepare_kernel.py replaces this with a base64 zip of app/ and scripts/.
# The Kaggle session does not fetch that code over the network.
BUNDLED_SOURCE = ""

# Free Kaggle GPUs fit this model. Set VISCAN_BASE_MODEL to a larger id when the GPU can hold it.
DEFAULT_BASE_MODEL = "HuggingFaceTB/SmolVLM-256M-Instruct"


GRADES = ("CIN1", "CIN2", "CIN3")


def unlabeled_reason(root: Path) -> str | None:
    """A flat upload keeps the pictures and drops the grade.

    Malhari repeats patient numbers inside each grade, so P01_1.jpg can be
    CIN1 or CIN2. Training needs the grade in the folder path, plus manifest.csv.
    """
    images = [path for path in root.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    if not images:
        return None
    graded = [path for path in images if any(part in GRADES for part in path.parts)]
    manifest = next(root.rglob("manifest.csv"), None)
    if graded and manifest is not None:
        return None
    return (
        f"Found {len(images)} images and no CIN folders. "
        "Names like P01_1.jpg do not say CIN1, CIN2, or CIN3, so this layout cannot train a classifier. "
        "On the laptop run `python scripts/malhari.py download`, zip that folder, and upload the zip "
        "as a new version of the Kaggle dataset. Kaggle keeps the folders that are inside a zip. "
        "The dataset page has no button to create those folders."
    )


def dataset_dir(mount: Path | None = None) -> Path | None:
    override = os.environ.get("VISCAN_DATA_DIR")
    if override and (Path(override) / "manifest.csv").is_file():
        return Path(override)
    mounted = mount if mount is not None else Path("/kaggle/input")
    if mounted.is_dir():
        found = sorted(mounted.glob("**/manifest.csv"))
        if found:
            return found[0].parent
    local = ROOT / "data" / "malhari"
    if (local / "manifest.csv").is_file():
        return local
    return None


def _is_project(path: Path) -> bool:
    return (path / "scripts" / "finetune_via.py").is_file() and (path / "app").is_dir()


def _unpack_bundle() -> Path | None:
    """Unpack the training code carried inside this file. No network call."""
    if not BUNDLED_SOURCE:
        return None
    import base64
    import io
    import zipfile

    working = Path("/kaggle/working")
    dest = working / "viscan-src" if working.is_dir() else Path(__file__).resolve().parent / "viscan-src"
    if _is_project(dest):
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(BUNDLED_SOURCE))) as archive:
        archive.extractall(dest)
    if not _is_project(dest):
        raise SystemExit(f"The bundled source at {dest} has no scripts package.")
    return dest


def project_root() -> Path:
    """Find ai-interpreter without contacting GitHub.

    Kaggle runs this file by itself at /kaggle/src/script.py. The package is
    either beside a local checkout or zipped into BUNDLED_SOURCE by CI.
    """
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        if _is_project(candidate):
            return candidate
        if _is_project(candidate / "ai-interpreter"):
            return candidate / "ai-interpreter"
    source = os.environ.get("VISCAN_SOURCE", "")
    if source:
        checkout = Path(source)
        if _is_project(checkout):
            return checkout
        if _is_project(checkout / "ai-interpreter"):
            return checkout / "ai-interpreter"
    for base in (Path("/kaggle/src"), Path("/kaggle/working"), Path("/kaggle/input")):
        if not base.is_dir():
            continue
        for manifest in base.rglob("scripts/finetune_via.py"):
            package = manifest.parents[1]
            if _is_project(package):
                return package
    bundled = _unpack_bundle()
    if bundled is not None:
        return bundled
    raise SystemExit(
        "This file is running alone, with no scripts package beside it and no bundled source. "
        "The kernel package is built by kaggle/prepare_kernel.py."
    )


def _ensure_model_libraries(project: Path) -> None:
    try:
        import peft  # noqa: F401
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(project / "requirements-model.txt"),
        ])


def main() -> None:
    data = dataset_dir()
    mount = Path("/kaggle/input")
    if data is None:
        reason = unlabeled_reason(mount) if mount.is_dir() else None
        sys.exit(
            reason
            or "No training dataset. Attach Malhari on this kernel "
            "(manifest.csv plus colposcopic/CIN1, CIN2, and CIN3). This run will not learn."
        )
    os.environ["VISCAN_DATA_DIR"] = str(data)
    project = project_root()
    sys.path.insert(0, str(project))
    _ensure_model_libraries(project)
    output = os.environ.get("VISCAN_OUTPUT", "/kaggle/working/viscan-via-adapter")
    sys.argv = [
        "finetune_via.py",
        "--base-model", os.environ.get("VISCAN_BASE_MODEL", DEFAULT_BASE_MODEL),
        "--max-steps", os.environ.get("VISCAN_MAX_STEPS", "200"),
        "--output", output,
    ]
    from scripts.finetune_via import main as train_main

    train_main()
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    repo = os.environ.get("HF_MODEL_REPO", "")
    if token and repo and Path(output).is_dir():
        from huggingface_hub import HfApi

        HfApi(token=token).upload_folder(folder_path=output, repo_id=repo, repo_type="model")
        print(f"Uploaded adapter to {repo}")
    else:
        print("Adapter saved on the kernel disk. Set Kaggle secrets HF_TOKEN and HF_MODEL_REPO to upload it.")


if __name__ == "__main__":
    main()
