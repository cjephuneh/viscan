"""Malhari cervical image dataset (CC0, Kalbhor & Shinde, doi:10.17632/m5kxdj7m36.1).

  python scripts/malhari.py download [--include-pap]
  python scripts/malhari.py evaluate [--limit N] [--include-pap]
  python scripts/malhari.py import

The colposcopic subset (CIN1/CIN2/CIN3 after acetic acid) is the part relevant to VIA.
The pap subset is cytology (microscopy) and is only used as an out-of-distribution check:
a good interpreter should call those images INADEQUATE.
"""

import argparse
import csv
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATASET_ID = "m5kxdj7m36"
API = f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}"
DATA_DIR = ROOT / "data" / "malhari"
MANIFEST = DATA_DIR / "manifest.csv"
CIN2_PLUS = {"CIN2", "CIN3"}
SCREEN_POSITIVE = {"VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"}


def _open(url: str, timeout: int = 60):
    request = urllib.request.Request(url, headers={"User-Agent": "viscan-dataset-fetcher/1.0"})
    return urllib.request.urlopen(request, timeout=timeout)


def _get_json(url: str):
    with _open(url) as resp:
        return json.load(resp)


def _number(name: str) -> str:
    match = re.search(r"\d+", name)
    return match.group() if match else re.sub(r"\W+", "", name)


def download(include_pap: bool, per_label: int | None = None) -> None:
    meta = _get_json(API)
    folders = {f["id"]: f for f in _get_json(f"{API}/folders/{meta['version']}")}

    def folder_path(fid):
        parts = []
        while fid in folders:
            parts.append(folders[fid]["name"])
            fid = folders[fid].get("parent_id")
        return parts[::-1]

    jobs = []
    for f in meta["files"]:
        parts = folder_path(f["folder_id"])
        if "colposcopic" in parts:
            modality = "colposcopic"
        elif "pap" in parts and include_pap:
            modality = "pap"
        else:
            continue
        label = parts[parts.index(modality) + 1]
        patient = next((p for p in parts if p.startswith("P (")), "P (0)")
        rel = Path(modality) / label / f"P{int(_number(patient)):02d}_{_number(f['filename'])}.jpg"
        jobs.append({
            "path": rel.as_posix(),
            "modality": modality,
            "label": label,
            "patient": f"{label}-P{int(_number(patient)):02d}",
            "sha256": f["content_details"]["sha256_hash"],
            "url": f["content_details"]["download_url"],
        })

    if per_label:
        grouped = defaultdict(list)
        for job in jobs:
            grouped[(job["modality"], job["label"])].append(job)
        rng = random.Random(7)
        jobs = [j for group in grouped.values() for j in rng.sample(group, min(per_label, len(group)))]

    def fetch(job):
        dest = DATA_DIR / job["path"]
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == job["sha256"]:
            return "cached"
        dest.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                data = subprocess.run(
                    ["curl", "-sfL", "--max-time", "120", job["url"]],
                    check=True, capture_output=True,
                ).stdout
                if hashlib.sha256(data).hexdigest() != job["sha256"]:
                    raise ValueError("checksum mismatch")
                dest.write_bytes(data)
                return "downloaded"
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))

    print(f"Fetching {len(jobs)} files into {DATA_DIR} ...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = Counter(pool.map(fetch, jobs))
    print(dict(statuses))

    with MANIFEST.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "modality", "label", "patient", "sha256"])
        writer.writeheader()
        for job in sorted(jobs, key=lambda j: j["path"]):
            writer.writerow({k: job[k] for k in writer.fieldnames})
    for (modality, label), n in sorted(Counter((j["modality"], j["label"]) for j in jobs).items()):
        print(f"  {modality:12s} {label:5s} {n:4d}")


def _manifest(include_pap: bool) -> list[dict]:
    if not MANIFEST.exists():
        sys.exit("No manifest found; run `python scripts/malhari.py download` first.")
    with MANIFEST.open() as fh:
        rows = list(csv.DictReader(fh))
    return [r for r in rows if include_pap or r["modality"] == "colposcopic"]


def evaluate(limit: int | None, include_pap: bool, seed: int) -> None:
    from PIL import Image

    from app.config import Config
    from app.services.interpreter import build_interpreter
    from app.services.quality import assess_quality

    rows = _manifest(include_pap)
    if limit:
        by_label = defaultdict(list)
        for r in rows:
            by_label[(r["modality"], r["label"])].append(r)
        rng = random.Random(seed)
        per_group = max(1, limit // len(by_label))
        rows = [r for group in by_label.values() for r in rng.sample(group, min(per_group, len(group)))]

    config = {k: getattr(Config, k) for k in dir(Config) if k.isupper()}
    interpreter = build_interpreter(config)
    print(f"Evaluating {len(rows)} images with {interpreter.engine} ({interpreter.model}) ...")

    def run(row):
        data = (DATA_DIR / row["path"]).read_bytes()
        quality = assess_quality(Image.open(DATA_DIR / row["path"]))
        if not quality["acceptable"]:
            return row, {"via_result": "INADEQUATE", "confidence": 1.0,
                         "rationale": "; ".join(quality["blocking_issues"])}
        try:
            return row, interpreter.interpret(data, {}, [])
        except Exception as exc:
            return row, {"via_result": "ERROR", "confidence": 0.0, "rationale": str(exc)[:300]}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, rows))

    out = DATA_DIR / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    with out.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["path", "modality", "label", "image_modality", "via_result", "confidence", "tz_type",
                         "area_pct", "rationale"])
        for row, ai in results:
            fx = ai.get("findings") or {}
            writer.writerow([row["path"], row["modality"], row["label"], ai.get("image_modality"),
                             ai["via_result"], ai.get("confidence"),
                             ai.get("transformation_zone_type"), fx.get("cervix_area_involved_percent"),
                             ai.get("rationale", "")])

    table = defaultdict(Counter)
    for row, ai in results:
        table[(row["modality"], row["label"])][ai["via_result"]] += 1
    print("\nAI result distribution per dataset label:")
    for key in sorted(table):
        print(f"  {key[0]:12s} {key[1]:5s} {dict(table[key])}")

    colpo = [(r, a) for r, a in results if r["modality"] == "colposcopic" and a["via_result"] not in ("ERROR", "INADEQUATE")]
    cin2 = [a for r, a in colpo if r["label"] in CIN2_PLUS]
    cin1 = [a for r, a in colpo if r["label"] == "CIN1"]
    if cin2:
        hits = sum(a["via_result"] in SCREEN_POSITIVE for a in cin2)
        print(f"\nSensitivity for CIN2+ (screen-positive): {hits}/{len(cin2)} = {hits / len(cin2):.0%}")
    if cin1:
        pos = sum(a["via_result"] in SCREEN_POSITIVE for a in cin1)
        print(f"CIN1 called screen-positive: {pos}/{len(cin1)} = {pos / len(cin1):.0%}")
    pap = [a for r, a in results if r["modality"] == "pap"]
    if pap:
        rejected = sum(a["via_result"] == "INADEQUATE" for a in pap)
        print(f"Pap (microscopy) correctly rejected as INADEQUATE: {rejected}/{len(pap)} = {rejected / len(pap):.0%}")
    errors = sum(a["via_result"] == "ERROR" for _, a in results)
    if errors:
        print(f"Errors: {errors} (see {out})")
    print("\nSpecificity cannot be measured: the dataset has no normal colposcopic images.")
    print(f"Per-image results: {out}")


def import_cases() -> None:
    from PIL import Image

    from app import create_app
    from app.models import ClinicianAnnotation, DiagnosisRecord, Patient, ViaImage, db
    from app.services.quality import assess_quality

    rows = _manifest(include_pap=False)
    app = create_app()
    created = skipped = 0
    with app.app_context():
        upload_dir = Path(app.config["UPLOAD_DIR"])
        for row in rows:
            src = DATA_DIR / row["path"]
            if ViaImage.query.filter_by(sha256=row["sha256"]).first():
                skipped += 1
                continue
            filename = f"{row['sha256']}.jpg"
            if not (upload_dir / filename).exists():
                shutil.copyfile(src, upload_dir / filename)

            external_id = f"MALHARI-{row['patient']}"
            patient = Patient.query.filter_by(external_id=external_id).first()
            if patient is None:
                patient = Patient(external_id=external_id, hiv_status="unknown")
                db.session.add(patient)

            img = Image.open(src)
            image = ViaImage(patient=patient, filename=filename, sha256=row["sha256"], mime_type="image/jpeg",
                             width=img.width, height=img.height, site="Malhari dataset (CC0)",
                             device="colposcope", quality=assess_quality(img))
            db.session.add(image)
            db.session.flush()

            db.session.add(DiagnosisRecord(
                patient_id=patient.id, image_id=image.id, method="colposcopy", result=row["label"],
                notes="Label from the Malhari dataset (doi:10.17632/m5kxdj7m36.1).",
            ))
            if row["label"] in CIN2_PLUS:
                db.session.add(ClinicianAnnotation(
                    image_id=image.id, clinician_id="dataset:malhari", via_result="VIA_POSITIVE",
                    notes=f"Derived from dataset label {row['label']} (colposcopic image); not a live clinician review.",
                ))
            created += 1
        db.session.commit()
    print(f"Imported {created} colposcopic cases ({skipped} already present).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_dl = sub.add_parser("download")
    p_dl.add_argument("--include-pap", action="store_true")
    p_dl.add_argument("--per-label", type=int, help="Only fetch a random sample of N images per label")
    p_ev = sub.add_parser("evaluate")
    p_ev.add_argument("--limit", type=int)
    p_ev.add_argument("--include-pap", action="store_true")
    p_ev.add_argument("--seed", type=int, default=7)
    sub.add_parser("import")
    args = parser.parse_args()

    if args.command == "download":
        download(args.include_pap, args.per_label)
    elif args.command == "evaluate":
        evaluate(args.limit, args.include_pap, args.seed)
    else:
        import_cases()


if __name__ == "__main__":
    main()
