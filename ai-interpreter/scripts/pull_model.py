"""Download the local VIA vision weights. Does not upload anything.

  python scripts/pull_model.py
  python scripts/pull_model.py --model HuggingFaceTB/SmolVLM-256M-Instruct

The default model is small enough to load on this machine (no NVIDIA GPU, 8 GB RAM).
A Kaggle run can download meta-llama/Llama-3.2-11B-Vision-Instruct instead and
point LOCAL_MODEL_DIR at that folder. Llama 3.2 Vision is gated: accept the
licence on Hugging Face and export HF_TOKEN before pulling it.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_ID = "HuggingFaceTB/SmolVLM-256M-Instruct"


def pull(repo_id: str, dest: Path) -> None:
    from huggingface_hub import snapshot_download

    dest.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(dest),
        ignore_patterns=["*.md", "*.gitattributes", "onnx/*", "flax_model*", "tf_model*", "rust_model*"],
    )
    (dest / "viscan-source.txt").write_text(repo_id + "\n")
    weights = sorted(p for p in dest.rglob("*") if p.is_file() and p.suffix in {".safetensors", ".bin"})
    total = sum(p.stat().st_size for p in weights)
    print(f"Pulled {repo_id}")
    print(f"  folder: {dest}")
    print(f"  weights: {total / 1e6:.0f} MB across {len(weights)} file(s)")


def main() -> None:
    from app.config import Config

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=os.getenv("LOCAL_MODEL_ID", Config.LOCAL_MODEL_ID))
    parser.add_argument("--dest", type=Path, default=Path(Config.LOCAL_MODEL_DIR))
    args = parser.parse_args()
    pull(args.model, args.dest)


if __name__ == "__main__":
    main()
