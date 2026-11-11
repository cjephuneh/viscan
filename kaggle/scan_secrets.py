"""Fail when a high-confidence secret is committed.

The CI secret-scan job runs this before a Kaggle push. Patterns are built at
runtime so this file does not itself contain a token.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "models", "dist", "build", ".next", "coverage",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".zip", ".gz",
    ".tgz", ".woff", ".woff2", ".ico", ".sqlite", ".db", ".safetensors",
    ".bin", ".pt", ".pyc",
}
MAX_BYTES = 1_000_000


def _patterns() -> list[re.Pattern[str]]:
    token = "KGAT_" + r"[A-Za-z0-9]{10,}"
    hub = "hf_" + r"[A-Za-z0-9]{20,}"
    openai_proj = "sk-proj-" + r"[A-Za-z0-9]{10,}"
    openai = "sk-" + r"[A-Za-z0-9]{20,}"
    aws = "AKIA" + r"[0-9A-Z]{16}"
    github = "github_pat_" + r"[A-Za-z0-9_]{20,}"
    private_key = r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"
    return [re.compile(item) for item in (token, hub, openai_proj, openai, aws, github, private_key)]


def tracked_files(root: Path) -> list[Path]:
    """Files git would push. A gitignored .env stays on the laptop and is not a CI finding."""
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True,
    )
    return [root / name.decode() for name in result.stdout.split(b"\0") if name]


def find_secrets(root: Path, files: list[Path] | None = None) -> list[str]:
    """Return `path:line` hits. Skips virtualenvs, weights, and binaries."""
    patterns = _patterns()
    hits: list[str] = []
    candidates = files if files is not None else list(root.rglob("*"))
    for path in candidates:
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in patterns):
                hits.append(f"{path.relative_to(root)}:{number}")
    return hits


def main() -> None:
    hits = find_secrets(ROOT, tracked_files(ROOT))
    if hits:
        print("Secret scan failed. Remove these before the Kaggle job can start:")
        print("\n".join(hits))
        sys.exit(1)
    print("Secret scan passed.")


if __name__ == "__main__":
    main()
