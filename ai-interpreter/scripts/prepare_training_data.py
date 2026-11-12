"""Build data/training/manifest.csv from the public sets stored under data/.

Images stay on this machine. This script does not download gated sets and does
not commit anything.

  python scripts/prepare_training_data.py
"""

import csv
import hashlib
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "training" / "manifest.csv"
FIELDS = ["path", "modality", "label", "patient", "sha256", "notes"]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row(path: Path, modality: str, label: str, patient: str, notes: str = "") -> dict:
    return {
        "path": path.relative_to(DATA).as_posix(),
        "modality": modality,
        "label": label,
        "patient": patient,
        "sha256": _sha(path),
        "notes": notes,
    }


def _has_acetowhite(path: Path) -> bool:
    image = Image.open(path).convert("RGBA")
    image.thumbnail((400, 400))
    count = 0
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    for red, green, blue, alpha in pixels:
        if alpha < 30:
            continue
        if red > 80 and blue > 80 and green < 140 and (red + blue) > (2 * green + 40):
            count += 1
            if count >= 25:
                return True
    return False


def _swede_scores(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def add_annocerv(rows: list[dict]) -> None:
    dataset = DATA / "annocerv" / "dataset"
    if not dataset.is_dir():
        print("skipped AnnoCerv (clone not finished)")
        return
    scores = _swede_scores(dataset / "swede_scores.csv")
    for image in sorted(dataset.glob("Case */*.jpg")):
        case = image.parent.name
        number = case.split()[-1]
        patient = f"annocerv-{number}"
        score = ""
        if number.isdigit() and scores and int(number) <= len(scores):
            score = f"Swede total {scores[int(number) - 1]}"
        name = image.name.lower()
        if "aceto" in name:
            mask = image.with_suffix(".png")
            positive = mask.is_file() and _has_acetowhite(mask)
            rows.append(_row(
                image, "colposcopic",
                "ACETO_POSITIVE" if positive else "ACETO_NEGATIVE",
                patient, score,
            ))
        elif "iod" in name:
            rows.append(_row(image, "iodine", "IODINE", patient, score))
        elif "green" in name:
            rows.append(_row(image, "green", "GREEN", patient, score))


def add_intelkamat(rows: list[dict]) -> None:
    table = DATA / "intelkamat" / "images.csv"
    if not table.is_file():
        print("skipped INTELKAMAT (download not finished)")
        return
    with table.open() as handle:
        images = list(csv.DictReader(handle))
    chosen: dict[str, dict] = {}
    for image in images:
        patient = image["patient_id"]
        current = chosen.get(patient)
        if current is None or image.get("is_reference_view") == "yes":
            chosen[patient] = image
    zone = {"Type 1": "TZ1", "Type 2": "TZ2", "Type 3": "TZ3"}
    root = DATA / "intelkamat"
    for image in chosen.values():
        path = next(root.rglob(image["image_id"]), None)
        label = zone.get(image.get("patient_tz_type", ""), "")
        if path is None or not label:
            continue
        findings = "; ".join(
            part for part in (image.get("patient_findings", ""), image.get("patient_clinical_notes", "")) if part
        )
        rows.append(_row(path, "colposcopic", label, image["patient_id"], findings))


def add_malhari(rows: list[dict]) -> None:
    manifest = DATA / "malhari" / "manifest.csv"
    archive = DATA / "malhari.zip"
    if not manifest.is_file() and archive.is_file():
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(DATA)
    if not manifest.is_file():
        print("skipped Malhari (manifest not on disk)")
        return
    with manifest.open() as handle:
        for record in csv.DictReader(handle):
            path = DATA / "malhari" / record["path"]
            if path.is_file():
                rows.append(_row(path, record["modality"], record["label"], record.get("patient", ""), "Malhari grade"))


def main() -> None:
    rows: list[dict] = []
    add_malhari(rows)
    add_annocerv(rows)
    add_intelkamat(rows)
    if not rows:
        raise SystemExit("No images found under data/. Finish a download, then run this again.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")
    for key, count in sorted(Counter((row["label"], row["modality"]) for row in rows).items()):
        print(f"  {key[0]:16s} {key[1]:12s} {count}")


if __name__ == "__main__":
    main()
