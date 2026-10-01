import base64
import io
import json
from dataclasses import dataclass

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

EMPTY_EXTENDED = {
    "image_quality": {"cervix_fully_visible": False, "focus": "acceptable", "lighting": "acceptable",
                      "glare": "none", "obscured_by": []},
    "lesions": [],
    "cancer_red_flags": {"mass_or_exophytic_growth": False, "ulceration": False, "contact_bleeding": False,
                         "atypical_vessels": False, "necrosis": False, "irregular_contour": False},
    "benign_findings": [],
    "swede": {"acetowhiteness": 0, "margins_surface": 0, "vessels": 0, "lesion_size": 0},
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


def _to_data_url(image_bytes: bytes, max_side: int = 1536) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


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


class OpenAIInterpreter:
    engine = "openai"

    def __init__(self, api_key: str, model: str, reasoning_effort: str = ""):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.reasoning_effort = reasoning_effort

    def interpret(self, image_bytes: bytes, context: dict, examples: list[ReferenceExample],
                  before_bytes: bytes | None = None) -> dict:
        content = []
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
                content.append({"type": "image_url", "image_url": {"url": _to_data_url(ex.image_bytes, 768), "detail": "low"}})

        if before_bytes:
            content.append({
                "type": "text",
                "text": "Baseline: native (pre-acetic-acid) view of the same cervix, taken before acetic acid "
                        "was applied. Whitening that is present ONLY in the post-acetic-acid image below is "
                        "acetowhite change; whiteness already visible here (e.g. mucus, leukoplakia, glare, "
                        "nabothian cysts) is not. Interpret and report on the post-acetic-acid image only.",
            })
            content.append({"type": "image_url", "image_url": {"url": _to_data_url(before_bytes, 1024), "detail": "high"}})
        content.append({
            "type": "text",
            "text": ("Interpret this new VIA image (1 minute after acetic acid)." if before_bytes
                     else "Interpret this new VIA image.") + f" {_context_text(context)}",
        })
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(image_bytes), "detail": "high"}})

        is_reasoning = self.model.startswith(("gpt-5", "o1", "o3", "o4"))
        options = {}
        if not is_reasoning:
            options["temperature"] = 0
        elif self.reasoning_effort:
            options["reasoning_effort"] = self.reasoning_effort
        response = self.client.chat.completions.create(
            model=self.model,
            **options,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_schema", "json_schema": VIA_SCHEMA},
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise RuntimeError(f"Model refused to interpret image: {message.refusal}")
        result = _normalise(json.loads(message.content))
        if result["image_modality"] in NON_VIA_MODALITIES and result["via_result"] != "INADEQUATE":
            result["image_adequacy"]["issues"].append(
                f"Image appears to be {result['image_modality'].replace('_', ' ')}, not a white-light "
                f"acetic-acid photo (model had suggested {result['via_result']})."
            )
            result["via_result"] = "INADEQUATE"
            result["image_adequacy"]["adequate"] = False
        return result


class HeuristicInterpreter:
    """Offline colour-based baseline: estimates dense acetowhite epithelium as bright,
    low-saturation pixels in the central (cervical) region. Used for demos, tests and as
    a fallback. Confidence is capped low so every result is routed to clinician review."""

    engine = "heuristic"
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


def build_interpreter(config) -> OpenAIInterpreter | HeuristicInterpreter:
    mode = config.get("INTERPRETER_MODE", "auto")
    key = config.get("OPENAI_API_KEY")
    if mode == "openai" or (mode == "auto" and key):
        if not key:
            raise RuntimeError("INTERPRETER_MODE=openai but OPENAI_API_KEY is not set.")
        return OpenAIInterpreter(key, config["OPENAI_MODEL"], config.get("OPENAI_REASONING_EFFORT", ""))
    return HeuristicInterpreter()


def clock_label(positions: list[int]) -> str:
    return ", ".join(f"{p} o'clock" for p in sorted(set(positions))) if positions else "none"
