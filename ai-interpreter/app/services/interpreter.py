import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image

SYSTEM_PROMPT = """You are VIScan, a clinical decision-support assistant that interprets \
cervical images taken 1 minute after applying 3-5% acetic acid (VIA: Visual Inspection with \
Acetic acid). You support trained clinicians; you never replace them.

First identify image_modality. VIA criteria apply ONLY to white-light photos of the cervix \
after acetic acid ("acetic_acid"). If the image is a green/red-free filter view, Lugol's iodine \
(VILI, mahogany/yellow staining), a native/saline view without acetowhitening, a microscopy \
or cytology slide, or not a cervix, set via_result to INADEQUATE and explain why.

Apply standard VIA criteria (WHO / IARC):
- VIA_NEGATIVE: no acetowhite lesions; or faint, translucent, patchy or line-like whitening; \
acetowhite areas far from the squamocolumnar junction (SCJ); nabothian cysts, polyps, \
cervicitis, or ectropion without distinct acetowhite epithelium.
- VIA_POSITIVE: distinct, well-defined, dense (opaque / "dull white") acetowhite areas \
touching or adjacent to the SCJ, or dense acetowhitening of a polyp's surface.
- SUSPICIOUS_FOR_CANCER: cauliflower-like / fungating mass, ulceration, contact bleeding, \
or an irregular raised growth.
- INADEQUATE: cervix not fully visible, SCJ cannot be assessed, heavy blood/mucus/discharge, \
poor focus or lighting, or the image is not a cervix after acetic acid.

Blood alone is not a sign of cancer: bleeding from speculum or swab contact on an otherwise \
smooth cervix is common. Reserve SUSPICIOUS_FOR_CANCER for a visible mass, exophytic or \
fungating growth, or a true ulcer with irregular raised margins.

Describe lesion location using clock positions (12 = anterior lip at the top of the image). \
Estimate the percentage of the cervix (ectocervix) covered by lesions. Report whether the \
lesion extends into the endocervical canal. Classify the transformation zone: type_1 (fully \
ectocervical, fully visible), type_2 (endocervical component, fully visible), type_3 \
(endocervical, not fully visible).

Lesions: list each distinct acetowhite or suspicious area separately (empty list if none). \
bbox is an APPROXIMATE box in normalised image coordinates (0-1, origin top-left).

Swede score components (iodine is not assessed in VIA):
- acetowhiteness: 0 none/transparent, 1 thin/milky, 2 distinct/opaque/stearin
- margins_surface: 0 diffuse, 1 sharp but irregular/jagged or satellites, 2 sharp and even \
with surface level difference (cuffing)
- vessels: 0 fine/regular, 1 absent, 2 coarse or atypical
- lesion_size: 0 <5 mm, 1 5-15 mm or 2 quadrants, 2 >15 mm or 3-4 quadrants or undefined \
endocervically
Use 0 for every component when there is no lesion.

histology_likelihood is your estimated probability distribution (sums to 1) of the most \
severe histology if this cervix were biopsied. differential lists alternative explanations \
for what is seen. key_observations are short factual bullet points for the clinician. \
recommended_checks are concrete things the clinician should verify at the bedside. \
patient_explanation is 2-3 calm, plain-language sentences a nurse could read to the patient, \
with no jargon and no definitive cancer statements.

Be calibrated: confidence is your probability that a VIA-trained expert panel would assign \
the same via_result. If uncertain between NEGATIVE and POSITIVE, lean POSITIVE (screening \
favours sensitivity) and lower your confidence. Return only the requested JSON."""


def _enum(*values):
    return {"type": "string", "enum": list(values)}


def _obj(properties: dict) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


_STR_LIST = {"type": "array", "items": {"type": "string"}}
_SCORE = {"type": "integer"}

VIA_SCHEMA = {
    "name": "via_interpretation",
    "strict": True,
    "schema": _obj({
        "image_modality": _enum("acetic_acid", "green_filter", "lugol_iodine", "native_saline",
                                "cytology_microscopy", "not_cervix", "unclear"),
        "via_result": _enum("VIA_NEGATIVE", "VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER", "INADEQUATE"),
        "confidence": {"type": "number"},
        "image_adequacy": _obj({"adequate": {"type": "boolean"}, "issues": _STR_LIST}),
        "image_quality": _obj({
            "cervix_fully_visible": {"type": "boolean"},
            "focus": _enum("good", "acceptable", "poor"),
            "lighting": _enum("good", "acceptable", "poor"),
            "glare": _enum("none", "mild", "significant"),
            "obscured_by": {"type": "array", "items": _enum(
                "blood", "mucus", "discharge", "speculum", "vaginal_walls", "instrument", "none")},
        }),
        "scj_visibility": _enum("fully_visible", "partially_visible", "not_visible"),
        "transformation_zone_type": _enum("type_1", "type_2", "type_3", "undetermined"),
        "findings": _obj({
            "acetowhite_present": {"type": "boolean"},
            "acetowhite_density": _enum("none", "faint", "moderate", "dense"),
            "lesion_margins": _enum("none", "diffuse", "sharp", "raised_irregular"),
            "lesion_clock_positions": {"type": "array", "items": {"type": "integer"}},
            "cervix_area_involved_percent": {"type": "integer"},
            "extends_into_canal": {"type": "boolean"},
            "other_findings": _STR_LIST,
        }),
        "lesions": {"type": "array", "items": _obj({
            "clock_start": {"type": "integer"},
            "clock_end": {"type": "integer"},
            "area_percent": {"type": "integer"},
            "density": _enum("faint", "moderate", "dense"),
            "margins": _enum("diffuse", "sharp", "raised_irregular"),
            "surface": _enum("smooth", "irregular", "raised", "ulcerated"),
            "vessel_pattern": _enum("none_visible", "fine_punctation", "coarse_punctation",
                                    "fine_mosaic", "coarse_mosaic", "atypical_vessels"),
            "touches_scj": {"type": "boolean"},
            "extends_into_canal": {"type": "boolean"},
            "bbox": _obj({"x": {"type": "number"}, "y": {"type": "number"},
                          "width": {"type": "number"}, "height": {"type": "number"}}),
            "description": {"type": "string"},
        })},
        "cancer_red_flags": _obj({
            "mass_or_exophytic_growth": {"type": "boolean"},
            "ulceration": {"type": "boolean"},
            "contact_bleeding": {"type": "boolean"},
            "atypical_vessels": {"type": "boolean"},
            "necrosis": {"type": "boolean"},
            "irregular_contour": {"type": "boolean"},
        }),
        "benign_findings": {"type": "array", "items": _enum(
            "ectropion", "nabothian_cysts", "polyp", "cervicitis", "leukoplakia", "condyloma",
            "atrophy", "immature_metaplasia", "discharge", "iud_strings", "none")},
        "swede": _obj({"acetowhiteness": _SCORE, "margins_surface": _SCORE,
                       "vessels": _SCORE, "lesion_size": _SCORE}),
        "histology_likelihood": _obj({
            "normal_or_benign": {"type": "number"}, "cin1": {"type": "number"},
            "cin2_plus": {"type": "number"}, "invasive_cancer": {"type": "number"},
        }),
        "differential": {"type": "array", "items": _obj({
            "diagnosis": {"type": "string"}, "likelihood": _enum("low", "moderate", "high"),
        })},
        "key_observations": _STR_LIST,
        "recommended_checks": _STR_LIST,
        "patient_explanation": {"type": "string"},
        "rationale": {"type": "string"},
    }),
}

NON_VIA_MODALITIES = {"green_filter", "lugol_iodine", "native_saline", "cytology_microscopy", "not_cervix"}

_DEFAULT_SWEDE = {"acetowhiteness": 0, "margins_surface": 0, "vessels": 0, "lesion_size": 0}

EMPTY_EXTENDED: dict[str, Any] = {
    "image_quality": {"cervix_fully_visible": False, "focus": "acceptable", "lighting": "acceptable",
                      "glare": "none", "obscured_by": []},
    "lesions": [],
    "cancer_red_flags": {"mass_or_exophytic_growth": False, "ulceration": False, "contact_bleeding": False,
                         "atypical_vessels": False, "necrosis": False, "irregular_contour": False},
    "benign_findings": [],
    "swede": dict(_DEFAULT_SWEDE),
    "histology_likelihood": None,
    "differential": [],
    "key_observations": [],
    "recommended_checks": [],
    "patient_explanation": "",
}


def with_defaults(result: dict) -> dict:
    for key, value in EMPTY_EXTENDED.items():
        result.setdefault(key, json.loads(json.dumps(value)))
    return result


def _normalise(result: dict) -> dict:
    result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    for key, value in result["swede"].items():
        result["swede"][key] = max(0, min(2, int(value)))
    probs = result.get("histology_likelihood")
    if probs:
        total = sum(max(0.0, float(v)) for v in probs.values()) or 1.0
        result["histology_likelihood"] = {k: round(max(0.0, float(v)) / total, 3) for k, v in probs.items()}
    for lesion in result["lesions"]:
        box = lesion["bbox"]
        for k in box:
            box[k] = round(max(0.0, min(1.0, float(box[k]))), 3)
    return result


@dataclass
class ReferenceExample:
    image_id: int
    image_bytes: bytes
    via_result: str
    notes: str = ""


class ViaInterpreter(Protocol):
    """The port. Pipeline, API, and rules depend on this, never on a GPU runtime."""

    engine: str
    model: str
    uses_references: bool

    def interpret(self, image_bytes: bytes, context: dict, examples: list[ReferenceExample],
                  before_bytes: bytes | None = None) -> dict: ...


LOCAL_JSON_INSTRUCTION = (
    "Return only one JSON object, with no markdown. It must include image_modality, via_result, "
    "confidence, image_adequacy, image_quality, scj_visibility, transformation_zone_type, findings, "
    "lesions, cancer_red_flags, benign_findings, swede, histology_likelihood, differential, "
    "key_observations, recommended_checks, patient_explanation and rationale."
)

_WEIGHT_FILES = (
    "model.safetensors", "model.safetensors.index.json",
    "pytorch_model.bin", "pytorch_model.bin.index.json",
)


def _open_image(image_bytes: bytes, max_side: int = 1024) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side))
    return img


def weights_ready(path) -> bool:
    folder = Path(path) if path else None
    if folder is None or not (folder / "config.json").is_file():
        return False
    return any((folder / name).is_file() for name in _WEIGHT_FILES) or any(folder.glob("*.safetensors"))


def adapter_ready(path) -> bool:
    return bool(path) and (Path(path) / "adapter_config.json").is_file()


def running_model_name(config) -> str:
    model_dir = Path(config.get("LOCAL_MODEL_DIR") or "")
    source = model_dir / "viscan-source.txt"
    base = source.read_text().strip() if source.is_file() else model_dir.name
    adapter = config.get("LOCAL_ADAPTER_DIR") or ""
    if adapter_ready(adapter):
        return f"{base}+{Path(adapter).name}"
    return base


def resolve_engine(config) -> tuple[str, str | None]:
    """Which engine a request will use, without loading weights."""
    mode = (config.get("INTERPRETER_MODE") or "auto").strip().lower()
    if mode in ("remote", "colab"):
        return "remote", "remote"
    ready = weights_ready(config.get("LOCAL_MODEL_DIR"))
    if mode == "local" or (mode == "auto" and ready):
        return ("local", running_model_name(config)) if ready else ("local", None)
    if mode in ("auto", "heuristic"):
        return "heuristic", HeuristicInterpreter.model
    raise RuntimeError(f"Unknown INTERPRETER_MODE={mode!r}. Use auto, local, remote, or heuristic.")


def build_messages(context: dict, examples: list[ReferenceExample],
                   before_bytes: bytes | None, image_bytes: bytes) -> list[dict]:
    """Chat messages for the local vision model. Image parts carry a PIL image."""
    content: list[dict] = []
    if examples:
        content.append({
            "type": "text",
            "text": "Reference cases verified by clinicians at this programme "
                    "(use them to calibrate to local camera and lighting conditions):",
        })
        for ex in examples:
            label = f"Reference case - clinician result: {ex.via_result}."
            if ex.notes:
                label += f" Notes: {ex.notes}"
            content.append({"type": "text", "text": label})
            content.append({"type": "image", "image": _open_image(ex.image_bytes, 512)})
    if before_bytes:
        content.append({
            "type": "text",
            "text": "Baseline: native (pre-acetic-acid) view of the same cervix, taken before acetic acid "
                    "was applied. Whitening that is present ONLY in the post-acetic-acid image below is "
                    "acetowhite change; whiteness already visible here (e.g. mucus, leukoplakia, glare, "
                    "nabothian cysts) is not. Interpret and report on the post-acetic-acid image only.",
        })
        content.append({"type": "image", "image": _open_image(before_bytes, 768)})
    content.append({
        "type": "text",
        "text": ("Interpret this new VIA image (1 minute after acetic acid)." if before_bytes
                 else "Interpret this new VIA image.") + f" {_context_text(context)}",
    })
    content.append({"type": "image", "image": _open_image(image_bytes)})
    return [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT + "\n\n" + LOCAL_JSON_INSTRUCTION}]},
        {"role": "user", "content": content},
    ]


def _parse_json(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None
        start = raw.find("{")
        if start >= 0:
            depth = 0
            for index, char in enumerate(raw[start:], start):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            value = json.loads(raw[start:index + 1])
                        except json.JSONDecodeError:
                            value = None
                        break
        if value is None:
            raise RuntimeError(f"Local model did not return JSON. Output started: {raw[:300]!r}")
    if not isinstance(value, dict):
        raise RuntimeError("Local model returned JSON that is not an object.")
    return value


def _coerce(result: dict) -> dict:
    if "via_result" not in result or "confidence" not in result:
        raise RuntimeError("Local model JSON is missing via_result or confidence.")
    try:
        result["confidence"] = float(result["confidence"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Local model JSON has a non-numeric confidence.") from exc
    result.setdefault("image_modality", "unclear")
    result.setdefault("image_adequacy", {"adequate": True, "issues": []})
    result.setdefault("scj_visibility", "partially_visible")
    result.setdefault("transformation_zone_type", "undetermined")
    result.setdefault("findings", {})
    result.setdefault("rationale", "")
    swede = dict(_DEFAULT_SWEDE)
    incoming = result.get("swede") or {}
    if isinstance(incoming, dict):
        for key in swede:
            try:
                swede[key] = int(incoming.get(key, 0) or 0)
            except (TypeError, ValueError):
                swede[key] = 0
    result["swede"] = swede
    lesions = []
    for lesion in result.get("lesions") or []:
        if not isinstance(lesion, dict):
            continue
        raw_box = lesion.get("bbox")
        box = raw_box if isinstance(raw_box, dict) else {}
        lesion["bbox"] = {k: box.get(k, 0) for k in ("x", "y", "width", "height")}
        lesions.append(lesion)
    result["lesions"] = lesions
    result = with_defaults(result)
    return _normalise(result)


class LocalVisionInterpreter:
    """On-device vision model. Loads the base weights once, plus a LoRA adapter when one has been trained."""

    engine = "local"
    uses_references = True
    _cache: dict[tuple[str, str], tuple] = {}

    def __init__(self, model_dir: str, adapter_dir: str = "", max_new_tokens: int = 700):
        self.model_dir = str(model_dir)
        self.adapter_dir = str(adapter_dir) if adapter_ready(adapter_dir) else ""
        self.model = running_model_name({
            "LOCAL_MODEL_DIR": self.model_dir,
            "LOCAL_ADAPTER_DIR": self.adapter_dir,
        })
        self.max_new_tokens = max_new_tokens

    def _ensure_loaded(self):
        key = (self.model_dir, self.adapter_dir)
        if key in self._cache:
            return self._cache[key]
        import torch
        from transformers import AutoProcessor

        try:
            from transformers import AutoModelForImageTextToText as AutoModel
        except ImportError:
            from transformers import AutoModelForVision2Seq as AutoModel

        torch.set_num_threads(min(4, os.cpu_count() or 1))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        processor = AutoProcessor.from_pretrained(self.model_dir)
        try:
            net = AutoModel.from_pretrained(self.model_dir, dtype=dtype, low_cpu_mem_usage=True)
        except TypeError:
            net = AutoModel.from_pretrained(self.model_dir, dtype=dtype, low_cpu_mem_usage=True)
        if self.adapter_dir:
            from peft import PeftModel

            net = PeftModel.from_pretrained(net, self.adapter_dir)
        net.to(device)
        net.eval()
        self._cache[key] = (processor, net)
        return processor, net

    def generate(self, messages: list[dict]) -> str:
        processor, net = self._ensure_loaded()
        import torch

        images = [
            part["image"]
            for message in messages
            for part in message["content"]
            if isinstance(part, dict) and part.get("type") == "image" and "image" in part
        ]
        try:
            inputs = processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            )
        except (TypeError, ValueError):
            prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = processor(text=prompt, images=images or None, return_tensors="pt")
        if not isinstance(inputs, dict):
            inputs = dict(inputs)
        device = next(net.parameters()).device
        dtype = next(net.parameters()).dtype
        moved = {}
        for key, value in inputs.items():
            if hasattr(value, "to"):
                value = value.to(device=device, dtype=dtype) if value.is_floating_point() else value.to(device)
            moved[key] = value
        inputs = moved
        input_len = inputs["input_ids"].shape[-1]
        with torch.inference_mode():
            output = net.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        return processor.decode(output[0][input_len:], skip_special_tokens=True)

    def interpret(self, image_bytes: bytes, context: dict, examples: list[ReferenceExample],
                  before_bytes: bytes | None = None) -> dict:
        text = self.generate(build_messages(context, examples, before_bytes, image_bytes))
        result = _coerce(_parse_json(text))
        if result["image_modality"] in NON_VIA_MODALITIES and result["via_result"] != "INADEQUATE":
            result["image_adequacy"]["issues"].append(
                f"Image appears to be {result['image_modality'].replace('_', ' ')}, not a white-light "
                f"acetic-acid photo (model had suggested {result['via_result']})."
            )
            result["via_result"] = "INADEQUATE"
            result["image_adequacy"]["adequate"] = False
        return result


def _context_text(context: dict) -> str:
    parts = []
    if context.get("age"):
        parts.append(f"age {context['age']}")
    if context.get("hiv_status") and context["hiv_status"] != "unknown":
        parts.append(f"HIV {context['hiv_status']}")
    if context.get("hpv_status") and context["hpv_status"] != "unknown":
        parts.append(f"HPV {context['hpv_status']}")
    if context.get("pregnant"):
        parts.append("pregnant")
    if context.get("previously_treated"):
        parts.append("previously treated for cervical precancer")
    symptoms = [s for s in context.get("symptoms") or [] if s != "none"]
    if symptoms:
        parts.append("symptoms: " + ", ".join(s.replace("_", " ") for s in symptoms))
    if context.get("previous_screening_result"):
        parts.append(f"last recorded VIA result: {context['previous_screening_result']}")
    prior = context.get("previous_screens") or []
    if prior:
        # Newest-first longitudinal history so the model can compare change over time.
        summary = "; ".join(
            f"{p.get('date') or 'unknown date'}: {p.get('via_result')} "
            f"({'clinician-confirmed' if p.get('source') == 'clinician' else 'AI, unconfirmed'})"
            for p in prior[:5]
        )
        parts.append(f"prior screens for this patient (newest first): {summary}")
    return ("Patient context: " + "; ".join(parts) + ".") if parts else "No patient context provided."


class HeuristicInterpreter:
    """Offline colour-based baseline: estimates dense acetowhite epithelium as bright,
    low-saturation pixels in the central (cervical) region. Used for demos, tests and as
    a fallback. Confidence is capped low so every result is routed to clinician review."""

    engine = "heuristic"
    uses_references = False
    model = "acetowhite-hsv-baseline-v1"

    def interpret(self, image_bytes: bytes, context: dict, examples: list[ReferenceExample],
                  before_bytes: bytes | None = None) -> dict:
        # The baseline frame is ignored by the colour heuristic; only the VIA frame is read.
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((512, 512))
        hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
        rgb = np.asarray(img, dtype=np.float32)
        h, w = hsv.shape[:2]

        yy, xx = np.mgrid[0:h, 0:w]
        cy, cx = h / 2, w / 2
        ry, rx = h * 0.42, w * 0.42
        region = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0

        glare = rgb.min(axis=2) > 245
        acetowhite = (hsv[..., 2] > 0.72) & (hsv[..., 1] < 0.22) & ~glare & region
        fraction = float(acetowhite.sum() / max(region.sum(), 1))

        clock_positions = []
        if acetowhite.any():
            angles = np.degrees(np.arctan2(xx[acetowhite] - cx, cy - yy[acetowhite])) % 360
            hours = ((np.round(angles / 30).astype(int) - 1) % 12) + 1
            counts = np.bincount(hours, minlength=13)[1:]
            threshold = max(counts.sum() * 0.1, 1)
            clock_positions = [i + 1 for i, c in enumerate(counts) if c >= threshold]

        if fraction < 0.03:
            via_result, density, margins = "VIA_NEGATIVE", ("none" if fraction < 0.005 else "faint"), "none"
            confidence = 0.55
        else:
            via_result = "VIA_POSITIVE"
            density = "dense" if fraction > 0.12 else "moderate"
            margins = "sharp" if fraction > 0.12 else "diffuse"
            confidence = min(0.6, 0.4 + fraction)

        area_pct = int(round(min(100.0, fraction * 100 * 1.5)))
        lesions = []
        if via_result == "VIA_POSITIVE":
            ys, xs = np.nonzero(acetowhite)
            lesions.append({
                "clock_start": min(clock_positions) if clock_positions else 12,
                "clock_end": max(clock_positions) if clock_positions else 12,
                "area_percent": area_pct,
                "density": density if density != "none" else "faint",
                "margins": margins if margins != "none" else "diffuse",
                "surface": "smooth",
                "vessel_pattern": "none_visible",
                "touches_scj": True,
                "extends_into_canal": False,
                "bbox": {"x": round(xs.min() / w, 3), "y": round(ys.min() / h, 3),
                         "width": round((xs.max() - xs.min()) / w, 3), "height": round((ys.max() - ys.min()) / h, 3)},
                "description": "Bright low-saturation region (heuristic).",
            })
        result = with_defaults({
            "image_modality": "unclear",
            "via_result": via_result,
            "confidence": round(confidence, 2),
            "image_adequacy": {"adequate": True, "issues": []},
            "scj_visibility": "partially_visible",
            "transformation_zone_type": "undetermined",
            "findings": {
                "acetowhite_present": via_result == "VIA_POSITIVE",
                "acetowhite_density": density,
                "lesion_margins": margins,
                "lesion_clock_positions": clock_positions,
                "cervix_area_involved_percent": area_pct,
                "extends_into_canal": False,
                "other_findings": [],
            },
            "lesions": lesions,
            "differential": [],
            "rationale": (
                f"Heuristic baseline (no vision model): {fraction:.1%} of the central region shows "
                "bright, low-saturation pixels consistent with acetowhitening. Not a clinical "
                "interpretation; clinician review required."
            ),
        })
        result["swede"] = {
            "acetowhiteness": {"none": 0, "faint": 1, "moderate": 1, "dense": 2}[density],
            "margins_surface": {"none": 0, "diffuse": 0, "sharp": 2}[margins],
            "vessels": 0,
            "lesion_size": 0 if area_pct < 10 else 1 if area_pct < 40 else 2,
        }
        return result


class RemoteInterpreter:
    """Sends the VIA image to a model server. The server can be Colab, Kaggle, or any other GPU."""

    engine = "remote"
    uses_references = True
    model = "remote"

    def __init__(self, base_url: str, token: str = "", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def interpret(self, image_bytes: bytes, context: dict, examples: list[ReferenceExample],
                  before_bytes: bytes | None = None) -> dict:
        import urllib.error
        import urllib.request

        fields = {
            "context": json.dumps(context),
            "examples": json.dumps([
                {"via_result": ex.via_result, "notes": ex.notes} for ex in examples
            ]),
        }
        files = [("image", "via.jpg", image_bytes)]
        if before_bytes:
            files.append(("image_before", "before.jpg", before_bytes))
        for index, ex in enumerate(examples):
            files.append((f"example_{index}", f"example_{index}.jpg", ex.image_bytes))
        body, content_type = _multipart(fields, files)
        request = urllib.request.Request(
            self.base_url + "/interpret",
            data=body,
            method="POST",
            headers={"Content-Type": content_type, "Authorization": f"Bearer {self.token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:400]
            raise RuntimeError(f"Remote model returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach the model server at {self.base_url}. "
                "That runtime may have stopped, or REMOTE_MODEL_URL is from an older session."
            ) from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Remote model returned non-JSON: {raw[:200]!r}") from exc
        if not isinstance(result, dict) or "via_result" not in result:
            message = result.get("error") if isinstance(result, dict) else "empty response"
            raise RuntimeError(f"Remote model failed: {message}")
        return result


def _multipart(fields: dict[str, str], files: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = "viscan" + os.urandom(8).hex()
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    for name, filename, data in files:
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n".encode()
            + data + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def build_interpreter(config) -> ViaInterpreter:
    engine, name = resolve_engine(config)
    if engine == "remote":
        url = (config.get("REMOTE_MODEL_URL") or config.get("COLAB_MODEL_URL") or "").strip()
        if not url:
            raise RuntimeError(
                "INTERPRETER_MODE=remote but REMOTE_MODEL_URL is empty. "
                "Start the model server on the GPU you want to use and paste its URL."
            )
        return RemoteInterpreter(
            url,
            config.get("REMOTE_MODEL_TOKEN") or config.get("COLAB_TOKEN") or "",
            int(config.get("REMOTE_MODEL_TIMEOUT_SECONDS") or config.get("COLAB_TIMEOUT_SECONDS") or 300),
        )
    if engine == "local":
        if name is None:
            raise RuntimeError(
                "INTERPRETER_MODE=local but no weights were found in LOCAL_MODEL_DIR. "
                "Run: python scripts/pull_model.py"
            )
        return LocalVisionInterpreter(
            config["LOCAL_MODEL_DIR"],
            config.get("LOCAL_ADAPTER_DIR") or "",
            int(config.get("LOCAL_MAX_NEW_TOKENS") or 700),
        )
    return HeuristicInterpreter()


def clock_label(positions: list[int]) -> str:
    return ", ".join(f"{p} o'clock" for p in sorted(set(positions))) if positions else "none"
