"""LoRA fine-tune for the VIScan VIA interpreter. Saves an adapter on disk only.

  python scripts/malhari.py download
  python scripts/finetune_via.py --max-steps 20

On a Kaggle GPU, after the GitHub tests pass, train Llama 3.2 Vision with the
same script and leave the adapter for a later Hugging Face upload:

  python scripts/finetune_via.py \\
    --base-model meta-llama/Llama-3.2-11B-Vision-Instruct \\
    --output /kaggle/working/viscan-via-adapter \\
    --max-steps 200

The backend loads models/viscan-via-adapter automatically when that folder
contains adapter_config.json. This script does not push to GitHub or Hugging Face.
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.interpreter import build_messages  # noqa: E402

DATA_DIR = Path(os.environ.get("VISCAN_DATA_DIR", ROOT / "data" / "malhari"))
MANIFEST = DATA_DIR / "manifest.csv"
CIN2_PLUS = {"CIN2", "CIN3"}


def _rows(include_pap: bool) -> list[dict]:
    if not MANIFEST.is_file():
        sys.exit(
            "No Malhari manifest at "
            f"{MANIFEST}. Download it with `python scripts/malhari.py download` "
            "or set VISCAN_DATA_DIR to the mounted dataset. "
            "This repository does not contain the training images."
        )
    with MANIFEST.open() as handle:
        rows = list(csv.DictReader(handle))
    rows = [row for row in rows if include_pap or row["modality"] == "colposcopic"]
    present = [row for row in rows if (DATA_DIR / row["path"]).is_file()]
    if not present:
        sys.exit(f"Manifest lists {len(rows)} images but none are on disk under {DATA_DIR}.")
    return present

# Text-only Llama cannot read a cervix photo. The vision checkpoint is the one
# a Kaggle GPU should train; it does not fit in 8 GB of CPU RAM.
KAGGLE_BASE_MODEL = "meta-llama/Llama-3.2-11B-Vision-Instruct"


def supervision(row: dict) -> dict:
    """VIA JSON the adapter should emit for one Malhari image.

    The dataset grades colposcopy as CIN1/CIN2/CIN3 and has no bounding boxes,
    so the target carries the grade and leaves lesion geometry empty.
    """
    label, modality = row["label"], row["modality"]
    if modality == "pap":
        via, image_modality, density = "INADEQUATE", "cytology_microscopy", "none"
        histo = {"normal_or_benign": 0.25, "cin1": 0.25, "cin2_plus": 0.25, "invasive_cancer": 0.25}
        rationale = "Microscopy slide, not a white-light acetic-acid photo."
    elif label in CIN2_PLUS:
        via, image_modality, density = "VIA_POSITIVE", "acetic_acid", "dense"
        histo = {"normal_or_benign": 0.05, "cin1": 0.15, "cin2_plus": 0.75, "invasive_cancer": 0.05}
        rationale = f"Colposcopic image labelled {label} in the Malhari dataset."
    elif label == "CIN1":
        via, image_modality, density = "VIA_POSITIVE", "acetic_acid", "moderate"
        histo = {"normal_or_benign": 0.1, "cin1": 0.7, "cin2_plus": 0.18, "invasive_cancer": 0.02}
        rationale = "Colposcopic image labelled CIN1 in the Malhari dataset."
    else:
        via, image_modality, density = "INADEQUATE", "unclear", "none"
        histo = {"normal_or_benign": 0.25, "cin1": 0.25, "cin2_plus": 0.25, "invasive_cancer": 0.25}
        rationale = f"Unmapped dataset label {label}."
    positive = via == "VIA_POSITIVE"
    return {
        "image_modality": image_modality,
        "via_result": via,
        "confidence": 0.7 if positive else 0.9,
        "image_adequacy": {"adequate": positive, "issues": [] if positive else ["not a VIA frame"]},
        "scj_visibility": "partially_visible",
        "transformation_zone_type": "undetermined",
        "findings": {
            "acetowhite_present": positive,
            "acetowhite_density": density,
            "lesion_margins": "sharp" if label in CIN2_PLUS else "none",
            "lesion_clock_positions": [],
            "cervix_area_involved_percent": 0,
            "extends_into_canal": False,
            "other_findings": [f"dataset label {label}"],
        },
        "lesions": [],
        "histology_likelihood": histo,
        "differential": [{"diagnosis": label, "likelihood": "high"}],
        "key_observations": [rationale],
        "recommended_checks": ["Clinician confirms this reading before any treatment."],
        "patient_explanation": "A clinician still needs to look at this result with you.",
        "rationale": rationale,
    }


def _conversation(row: dict) -> list[dict]:
    messages = build_messages({}, [], None, (DATA_DIR / row["path"]).read_bytes())
    messages.append({
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(supervision(row), separators=(",", ":"))}],
    })
    return messages


def _prompt_length(processor, messages) -> int:
    prompt = messages[:-1]
    tokenized = processor.apply_chat_template(
        prompt, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt",
    )
    return int(tokenized["input_ids"].shape[-1])


def train(base_model: str, output: Path, max_steps: int, rows: list[dict], lr: float) -> None:
    import torch
    from peft import LoraConfig, get_peft_model
    from torch.optim import AdamW
    from transformers import AutoProcessor

    try:
        from transformers import AutoModelForImageTextToText as AutoModel
    except ImportError:
        from transformers import AutoModelForVision2Seq as AutoModel

    print(f"Loading {base_model} for {max_steps} LoRA steps ...")
    processor = AutoProcessor.from_pretrained(base_model)
    try:
        net = AutoModel.from_pretrained(base_model, dtype=torch.float32, low_cpu_mem_usage=True)
    except TypeError:
        net = AutoModel.from_pretrained(base_model, torch_dtype=torch.float32, low_cpu_mem_usage=True)
    net = get_peft_model(net, LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj"],
    ))
    net.train()
    optim = AdamW((p for p in net.parameters() if p.requires_grad), lr=lr)

    for step in range(1, max_steps + 1):
        messages = _conversation(rows[(step - 1) % len(rows)])
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=False, tokenize=True, return_dict=True, return_tensors="pt",
        )
        labels = inputs["input_ids"].clone()
        prompt_len = min(_prompt_length(processor, messages), labels.shape[-1] - 1)
        labels[:, :prompt_len] = -100
        optim.zero_grad()
        loss = net(**inputs, labels=labels).loss
        loss.backward()
        optim.step()
        print(f"  step {step}/{max_steps}  loss {loss.item():.4f}")

    output.mkdir(parents=True, exist_ok=True)
    net.save_pretrained(output)
    processor.save_pretrained(output)
    print(f"Adapter saved to {output}")
    print("The running interpreter picks it up from LOCAL_ADAPTER_DIR. Nothing was uploaded.")


def main() -> None:
    from app.config import Config

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-model", default=str(Config.LOCAL_MODEL_DIR),
                        help=f"Local folder or Hugging Face id. Kaggle target: {KAGGLE_BASE_MODEL}")
    parser.add_argument("--output", type=Path, default=Path(Config.LOCAL_ADAPTER_DIR))
    parser.add_argument("--max-steps", type=int, required=True)
    parser.add_argument("--include-pap", action="store_true")
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()
    train(args.base_model, args.output, args.max_steps, _rows(args.include_pap), args.lr)


if __name__ == "__main__":
    main()
