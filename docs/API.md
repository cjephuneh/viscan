# VIScan API

AI-assisted interpretation of VIA (Visual Inspection with Acetic acid) cervical screening images.
Upload a cervix image and receive a screening verdict (**suspicious / not suspicious**), a VIA
result, lesion-level findings, a risk index, WHO treatment-eligibility checks and a management
recommendation. Every result is stored and must be confirmed by a clinician.

> **Decision support only.** VIScan does not diagnose. A trained clinician must confirm every
> result before any treatment decision.

- Base URL: `http://<host>:5050/api/v1`
- Request bodies: `multipart/form-data` for image upload, `application/json` elsewhere
- Responses: JSON (except the overlay PNG, the HTML report and the JSONL export)
- Dates: ISO 8601 (`YYYY-MM-DD`); timestamps are UTC ISO 8601

## Contents

1. [Authentication](#authentication)
2. [Errors](#errors)
3. [Enumerations](#enumerations)
4. [Endpoints](#endpoints)
   - [Health](#get-health)
   - [Interpret an image](#post-interpret)
   - [Get an interpretation](#get-interpretationsid)
   - [Annotated overlay image](#get-interpretationsidoverlaypng)
   - [Printable report](#get-interpretationsidreport)
   - [Original image](#get-imagesidfile)
   - [Clinician review](#post-interpretationsidannotations)
   - [Review worklist](#get-worklist)
   - [Diagnosis records](#post-patientsiddiagnoses)
   - [Outcomes](#post-patientsidoutcomes)
   - [Patient record](#get-patientsid)
   - [Metrics](#get-metrics)
   - [Dataset export](#get-datasetexport)
   - [Care summary](#get-interpretationsidcare)
   - [Nearby pharmacies](#get-placespharmacies)
   - [Partner hospitals](#get-partner-hospitals)
   - [Refer to a partner hospital](#post-interpretationsidreferrals)
   - [Send results by SMS / WhatsApp](#post-interpretationsidnotifications)
5. [How a result is produced](#how-a-result-is-produced)
6. [Data model](#data-model)
7. [Configuration](#configuration)

---

## Authentication

Authentication is optional and controlled by the `VISCAN_API_KEY` environment variable.

- If `VISCAN_API_KEY` is **unset**, all endpoints are open (development only).
- If it is **set**, every request except `GET /health` must include:

```
X-API-Key: <VISCAN_API_KEY>
```

Missing or wrong key → `401 {"error": "Invalid or missing X-API-Key header."}`

## Errors

Errors return a JSON body `{"error": "<message>"}`.

| Status | Meaning |
|---|---|
| 400 | Validation error (bad enum value, missing field, unreadable image, unsupported format) |
| 401 | Missing/invalid `X-API-Key` |
| 404 | Resource not found |
| 413 | Image larger than 10 MB |
| 502 | The AI provider call failed (e.g. OpenAI unavailable, model access denied) |

## Enumerations

| Name | Values |
|---|---|
| `screening_verdict` | `SUSPICIOUS`, `NOT_SUSPICIOUS`, `INDETERMINATE` |
| `via_result` | `VIA_NEGATIVE`, `VIA_POSITIVE`, `SUSPICIOUS_FOR_CANCER`, `INADEQUATE` |
| `suspicion_level` | `low` (<15), `moderate` (15-44), `high` (45-74), `very_high` (75+), `unknown` |
| `urgency` | `routine`, `soon`, `urgent` |
| `image_modality` | `acetic_acid`, `green_filter`, `lugol_iodine`, `native_saline`, `cytology_microscopy`, `not_cervix`, `unclear` |
| `transformation_zone_type` | `type_1`, `type_2`, `type_3`, `undetermined` |
| `scj_visibility` | `fully_visible`, `partially_visible`, `not_visible` |
| `hiv_status` / `hpv_status` | `positive`, `negative`, `unknown` |
| `symptoms` | `postcoital_bleeding`, `intermenstrual_bleeding`, `postmenopausal_bleeding`, `abnormal_discharge`, `pelvic_pain`, `dyspareunia`, `none` |
| `review_status` | `pending`, `reviewed` (clinician agreed), `disputed` (clinician disagreed) |
| `lesion.density` | `faint`, `moderate`, `dense` |
| `lesion.margins` | `diffuse`, `sharp`, `raised_irregular` |
| `lesion.surface` | `smooth`, `irregular`, `raised`, `ulcerated` |
| `lesion.vessel_pattern` | `none_visible`, `fine_punctation`, `coarse_punctation`, `fine_mosaic`, `coarse_mosaic`, `atypical_vessels` |
| diagnosis `method` | `colposcopy`, `histology`, `hpv_test`, `cytology` |
| diagnosis `result` | `normal`, `CIN1`, `CIN2`, `CIN3`, `AIS`, `invasive_cancer`, `hpv_positive`, `hpv_negative`, `inconclusive` |
| outcome `treatment` | `none`, `thermal_ablation`, `cryotherapy`, `LEEP`, `cone_biopsy`, `referred_oncology`, `other` |
| outcome `status` | `open`, `completed`, `lost_to_follow_up` |

**Verdict mapping:** `VIA_POSITIVE` and `SUSPICIOUS_FOR_CANCER` → `SUSPICIOUS`;
`VIA_NEGATIVE` → `NOT_SUSPICIOUS`; `INADEQUATE` → `INDETERMINATE`.

---

## Endpoints

### `GET /health`

Liveness check; never requires an API key.

```json
{ "status": "ok", "engine": "openai", "model": "gpt-5" }
```

`engine` is `openai` when an OpenAI key is configured, otherwise `heuristic` (offline baseline).

---

### `POST /interpret`

Upload one VIA image and receive the full interpretation. The image, visit, AI output, lesions and
assessment are stored. Typical latency with `gpt-5` is 30-60 s.

**Request** — `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---|---|
| `image` | file | **yes** | JPEG, PNG or WEBP, ≤ 10 MB. White-light photo ~1 min after 3-5% acetic acid |
| `patient_external_id` | string | no | Pseudonymised ID. Links screens over time (history/trend). Omit for anonymous |
| `age` | int 10-100 | no | |
| `hiv_status` | enum | no | |
| `hpv_status` | enum | no | |
| `hpv_genotypes` | string | no | e.g. `16, 18` |
| `symptoms` | enum list | no | Repeat the field or comma-separate: `postcoital_bleeding,abnormal_discharge` |
| `pregnant` | bool | no | `true/false/yes/no/1/0` |
| `parity` | int 0-25 | no | |
| `smoker` | bool | no | |
| `contraception` | string | no | |
| `previously_treated` | bool | no | Prior treatment for cervical precancer |
| `previous_screening_result` | `via_result` | no | If omitted, the last stored result for the patient is used |
| `visit_date` | date | no | Defaults to today |
| `clinician_id` | string | no | Who performed the screening |
| `site` / `device` | string | no | Screening site and camera/device |
| `notes` | string | no | |

**Example**

```bash
curl -X POST http://localhost:5050/api/v1/interpret \
  -H "X-API-Key: $VISCAN_API_KEY" \
  -F image=@cervix.jpg \
  -F patient_external_id=SITE01-000123 \
  -F age=38 -F hiv_status=positive -F hpv_status=positive \
  -F symptoms=postcoital_bleeding -F pregnant=false -F parity=3 \
  -F site="Kibera clinic" -F clinician_id=nurse-01
```

**Response** — `201 Created` (abridged real response)

```json
{
  "interpretation_id": 1,
  "image_id": 1,
  "patient_id": 1,
  "visit_id": 1,
  "created_at": "2026-09-30T13:20:51+00:00",

  "verdict": {
    "screening_verdict": "SUSPICIOUS",
    "is_suspicious": true,
    "label": "Suspicious - abnormal area seen, needs treatment or referral",
    "suspicion_level": "very_high",
    "risk_score": 86,
    "via_result": "VIA_POSITIVE",
    "confidence": 0.7
  },

  "diagnosis": {
    "via_result": "VIA_POSITIVE",
    "confidence": 0.7,
    "summary": "VIA positive and eligible for ablation: offer same-visit thermal ablation or cryotherapy (screen-and-treat), with follow-up at 12 months.",
    "urgency": "soon"
  },

  "clinical_summary": {
    "key_observations": [
      "Distinct, opaque acetowhite area at 12-4 o'clock touching the SCJ",
      "Additional smaller acetowhite focus near the os with fine punctation",
      "SCJ fully visible; transformation zone type 1"
    ],
    "rationale": "Dense acetowhite epithelium abutting the SCJ ...",
    "patient_explanation": "The vinegar test showed a white area on your cervix ...",
    "counselling_points": ["Explain that an area of the cervix changed colour ...", "..."],
    "clinician_checklist": [
      "Confirm the AI result by direct visual inspection before acting.",
      "Check the whole transformation zone, including the canal ...",
      "Gently clear mucus/blood and reassess margins and any canal extension.",
      "Record your own VIA result in VIScan (agree/disagree) to improve the model."
    ]
  },

  "image_assessment": {
    "image_modality": "acetic_acid",
    "adequacy": { "adequate": true, "issues": [] },
    "model_quality_read": {
      "cervix_fully_visible": true, "focus": "good", "lighting": "good",
      "glare": "mild", "obscured_by": ["none"]
    },
    "local_quality_metrics": {
      "acceptable": true, "blocking_issues": [], "warnings": [],
      "metrics": { "width": 768, "height": 568, "brightness": 118.2, "sharpness": 41.5,
                   "glare_fraction": 0.004, "red_dominance": 0.91 }
    },
    "scj_visibility": "fully_visible",
    "transformation_zone_type": "type_1"
  },

  "findings": {
    "acetowhite_present": true,
    "acetowhite_density": "dense",
    "lesion_margins": "sharp",
    "lesion_clock_positions": [12, 1, 2, 3, 4],
    "cervix_area_involved_percent": 35,
    "extends_into_canal": false,
    "other_findings": []
  },

  "lesions": [
    {
      "id": 1, "clock_start": 12, "clock_end": 4, "area_percent": 30,
      "density": "dense", "margins": "sharp", "surface": "smooth",
      "vessel_pattern": "fine_punctation", "touches_scj": true, "extends_into_canal": false,
      "bbox": { "x": 0.48, "y": 0.1, "width": 0.45, "height": 0.55 },
      "description": "Opaque acetowhite plaque abutting the SCJ ..."
    }
  ],

  "cancer_red_flags": {
    "mass_or_exophytic_growth": false, "ulceration": false, "contact_bleeding": true,
    "atypical_vessels": false, "necrosis": false, "irregular_contour": false
  },
  "benign_findings": ["ectropion", "cervicitis"],

  "swede": {
    "components": { "acetowhiteness": 2, "margins_surface": 1, "vessels": 0, "lesion_size": 1 },
    "total": 4, "max": 8,
    "interpretation": "intermediate - low-grade lesion likely; high grade not excluded",
    "note": "Modified Swede score without the iodine component (VIA only); bands are indicative."
  },

  "histology_likelihood": { "normal_or_benign": 0.2, "cin1": 0.35, "cin2_plus": 0.38, "invasive_cancer": 0.07 },
  "differential": [
    { "diagnosis": "CIN1 (low-grade)", "likelihood": "high" },
    { "diagnosis": "CIN2+ (high-grade)", "likelihood": "moderate" }
  ],

  "risk_index": {
    "score": 86, "level": "very_high",
    "breakdown": [
      { "factor": "AI result VIA_POSITIVE", "points": 45 },
      { "factor": "Swede features (4/8)", "points": 8 },
      { "factor": "Cancer red flags: contact bleeding", "points": 5 },
      { "factor": "AI-estimated CIN2+ probability 45%", "points": 4 },
      { "factor": "Living with HIV", "points": 8 },
      { "factor": "HPV positive", "points": 10 },
      { "factor": "Abnormal bleeding: postcoital bleeding", "points": 6 }
    ]
  },

  "treatment_eligibility": {
    "ablation_eligible": true,
    "checklist": [
      { "criterion": "No suspicion of invasive cancer", "met": true, "detail": "" },
      { "criterion": "Squamocolumnar junction fully visible (TZ type 1 or 2)", "met": true, "detail": "TZ type_1" },
      { "criterion": "Lesion covers < 75% of the ectocervix", "met": true, "detail": "~35%" },
      { "criterion": "Lesion does not extend into the endocervical canal", "met": true, "detail": "" },
      { "criterion": "Not pregnant (otherwise defer treatment unless cancer suspected)", "met": true, "detail": "" }
    ]
  },

  "recommendation": {
    "category": "VIA_POSITIVE",
    "action": "VIA positive and eligible for ablation: offer same-visit thermal ablation or cryotherapy ...",
    "urgency": "soon",
    "ablation_eligible": true,
    "follow_up_months": 12,
    "reasons": [],
    "flags": [
      "Low AI confidence (70%); prioritise clinician review.",
      "Woman living with HIV: higher risk of progression and recurrence.",
      "HPV positive: VIA is being used for triage; a negative VIA does not exclude disease.",
      "Contact bleeding noted: confirm it is from ectropion/cervicitis and not the lesion before ablating."
    ],
    "requires_clinician_confirmation": true
  },

  "follow_up_due": "2027-09-30",
  "history": { "previous_screens": [], "trend": "first_screen_on_record", "days_since_last_screen": null },
  "visit": { "id": 1, "age_at_visit": 38, "hiv_status": "positive", "hpv_status": "positive",
             "symptoms": ["postcoital_bleeding"], "pregnant": false, "parity": 3, "...": "..." },
  "review_status": "pending",
  "engine": { "name": "openai", "model": "gpt-5", "latency_ms": 56000, "reference_examples": [] },
  "links": {
    "self": "/api/v1/interpretations/1",
    "image": "/api/v1/images/1/file",
    "overlay": "/api/v1/interpretations/1/overlay.png",
    "report": "/api/v1/interpretations/1/report",
    "annotate": "/api/v1/interpretations/1/annotations"
  },
  "disclaimer": "Decision support only. A trained clinician must confirm every result before any treatment."
}
```

**Key response fields**

| Field | Description |
|---|---|
| `verdict.screening_verdict` | The headline answer: is this suspicious or not |
| `verdict.risk_score` | 0-100 additive risk index (null when `INDETERMINATE`); see `risk_index.breakdown` |
| `diagnosis.summary` | What to do next, in one sentence |
| `lesions[].bbox` | Approximate lesion box, normalised 0-1, origin top-left |
| `swede` | Modified Swede score (0-8; iodine component not assessed in VIA) |
| `histology_likelihood` | AI-estimated probability of the most severe histology if biopsied (sums to 1) |
| `treatment_eligibility.checklist[].met` | `true`, `false`, or `null` (cannot be determined from the image) |
| `history.trend` | `first_screen_on_record`, `new_positive`, `persistent_positive`, `resolved_since_last_screen`, `stable_negative`, `not_comparable` |
| `follow_up_due` | Date of the next visit (retake today for `INDETERMINATE`) |

**Non-VIA images.** Green-filter, Lugol's iodine, native/saline, microscopy, or non-cervix images
are returned as `INADEQUATE` / `INDETERMINATE` with the reason in `image_assessment.adequacy.issues`.
Images that fail the local quality gate (too small, too dark, severely blurred) are rejected
without calling the AI (`engine.name = "quality_gate"`).

---

### `GET /interpretations/{id}`

Returns the same body as `POST /interpret` for a stored interpretation, plus
`annotations` (clinician reviews).

---

### `GET /interpretations/{id}/overlay.png`

PNG of the image with numbered lesion boxes, clock positions and a verdict banner
(red = suspicious, green = not suspicious, grey = indeterminate).

---

### `GET /interpretations/{id}/report`

Printable HTML clinical report: verdict, action, annotated image, patient/visit context,
lesion table, Swede score, histology likelihood, WHO eligibility checklist, risk breakdown,
clinician checklist, counselling text and a clinician sign-off section. Use the browser's
*Print → Save as PDF* for a PDF.

---

### `GET /images/{id}/file`

The original uploaded image.

---

### `POST /interpretations/{id}/annotations`

Record the clinician's own VIA read. This is the ground truth used for metrics and for
calibrating the model (clinician-verified cases are used as reference examples for future
interpretations). Sets `review_status` to `reviewed` (agrees) or `disputed` (disagrees).

**Request** — JSON

| Field | Type | Required |
|---|---|---|
| `clinician_id` | string | **yes** |
| `via_result` | `via_result` | **yes** |
| `lesion_clock_positions` | int[] (1-12) | no |
| `transformation_zone_type` | `type_1`/`type_2`/`type_3` | no |
| `notes` | string | no |

```bash
curl -X POST http://localhost:5050/api/v1/interpretations/1/annotations \
  -H "Content-Type: application/json" \
  -d '{"clinician_id":"nurse-01","via_result":"VIA_POSITIVE","lesion_clock_positions":[12,1,2,3],"notes":"Agree"}'
```

**Response** — `201`

```json
{ "id": 1, "image_id": 1, "interpretation_id": 1, "clinician_id": "nurse-01",
  "via_result": "VIA_POSITIVE", "agrees_with_ai": true, "lesion_clock_positions": [12, 1, 2, 3],
  "transformation_zone_type": null, "notes": "Agree", "created_at": "...", "review_status": "reviewed" }
```

---

### `GET /worklist`

Clinician triage queue, ordered: suspicious for cancer → suspicious → indeterminate → not
suspicious, then by risk score (highest first), then oldest first.

| Query | Default | Values |
|---|---|---|
| `status` | `pending` | `pending`, `reviewed`, `disputed`, `all` |
| `verdict` | all | `SUSPICIOUS`, `NOT_SUSPICIOUS`, `INDETERMINATE` |
| `limit` | 50 | 1-500 |

```json
[
  { "interpretation_id": 1, "patient_external_id": "SITE01-000123", "created_at": "...",
    "screening_verdict": "SUSPICIOUS", "via_result": "VIA_POSITIVE", "risk_score": 86,
    "suspicion_level": "very_high", "confidence": 0.7, "urgency": "soon",
    "action": "VIA positive and eligible for ablation ...", "follow_up_due": "2027-09-30",
    "review_status": "pending",
    "links": { "self": "/api/v1/interpretations/1", "report": "/api/v1/interpretations/1/report" } }
]
```

---

### `POST /patients/{id}/diagnoses`

Add a confirmatory diagnosis (colposcopy, histology, HPV test, cytology). Histology/colposcopy
results are used as the reference standard in `/metrics`.

```json
{ "method": "histology", "result": "CIN3", "image_id": 1, "diagnosed_on": "2026-10-14", "notes": "Punch biopsy 2 o'clock" }
```

`method` and `result` are required. `image_id` (optional) must belong to the patient. → `201`

---

### `POST /patients/{id}/outcomes`

Record treatment and follow-up.

```json
{ "treatment": "thermal_ablation", "treated_on": "2026-09-30", "follow_up_on": "2027-09-30",
  "follow_up_result": "VIA_NEGATIVE", "status": "completed", "notes": "" }
```

All fields optional; `treatment` defaults to `none`, `status` to `open`. → `201`

---

### `GET /patients/{id}`

Full longitudinal record: patient, all images with their interpretations (and annotations and
lesions), visits, diagnoses and outcomes.

---

### `GET /metrics`

Programme and model performance.

```json
{
  "total_interpretations": 42,
  "by_engine": { "openai": 40, "heuristic": 2 },
  "by_verdict": { "SUSPICIOUS": 9, "NOT_SUSPICIOUS": 28, "INDETERMINATE": 5 },
  "by_via_result": { "VIA_NEGATIVE": 28, "VIA_POSITIVE": 8, "SUSPICIOUS_FOR_CANCER": 1, "INADEQUATE": 5 },
  "by_review_status": { "pending": 12, "reviewed": 27, "disputed": 3 },
  "average_risk_score": 21.4,
  "clinician_agreement": {
    "reviewed": 30, "agreement_rate": 0.9, "cohens_kappa": 0.78,
    "confusion_matrix_ai_vs_clinician": { "VIA_POSITIVE": { "VIA_POSITIVE": 7, "VIA_NEGATIVE": 1 } }
  },
  "vs_histology_cin2_plus": {
    "cases_with_reference": 10, "true_positive": 5, "false_positive": 3,
    "true_negative": 2, "false_negative": 0,
    "sensitivity": 1.0, "specificity": 0.4, "ppv": 0.625, "npv": 1.0
  }
}
```

Quality-gate rejections are excluded from agreement/accuracy figures.

---

### `GET /dataset/export`

Downloads `viscan_dataset.jsonl`: one line per image with quality metrics, patient, AI results,
clinician annotations, diagnoses and outcomes. Use for audits, external evaluation or future
model fine-tuning.

---

### `GET /interpretations/{id}/care`

What happens after the screen. The latest clinician annotation overrides the AI result.

```json
{
  "interpretation_id": 2,
  "patient_external_id": "E2E-042",
  "final_via_result": "VIA_POSITIVE",
  "result_source": "clinician",
  "screening_verdict": "SUSPICIOUS",
  "is_suspicious": true,
  "needs_referral": false,
  "urgency": "soon",
  "action": "VIA positive and eligible for ablation: offer same-visit thermal ablation ...",
  "suggested_supplies": [
    {"item": "Sanitary pads", "why": "Watery discharge or light bleeding for up to 4 weeks after treatment", "prescription": false}
  ],
  "referrals": [],
  "notifications": [],
  "message_preview": {"sms": "Hello, this is your clinic (VIScan). ...", "whatsapp": "Hello, ... Reply or call the clinic with any questions."}
}
```

`needs_referral` is true when cancer is suspected or the lesion is not eligible for ablation.
`suggested_supplies` is empty unless the result is VIA positive or suspicious for cancer.

---

### `GET /places/pharmacies`

Pharmacies near a location, from OpenStreetMap (Overpass API; no key needed, results cached for
10 minutes, mirrors tried in order).

| Query | Default | Notes |
|---|---|---|
| `lat`, `lng` | `DEFAULT_LATITUDE`, `DEFAULT_LONGITUDE` | Search centre |
| `radius` | `3000` | Metres, 200 to 20000 |

```json
{
  "source": "openstreetmap",
  "center": {"lat": -1.9441, "lng": 30.0619},
  "radius_m": 2000,
  "results": [
    {"id": "node/123", "name": "Miracle Pharmacy", "latitude": -1.945, "longitude": 30.061,
     "distance_km": 0.14, "address": null, "phone": "+250 788 890 078", "opening_hours": null,
     "osm_url": "https://www.openstreetmap.org/node/123"}
  ]
}
```

Returns `503` with `results: []` when every Overpass mirror is unavailable.

---

### `GET /partner-hospitals`

Partner hospitals that accept referrals, nearest first. Optional `lat`, `lng` (distance origin)
and `service` (for example `colposcopy`). Four demo partners (`is_demo: true`) are seeded around
the default location on first start when `SEED_DEMO_PARTNERS` is on; replace them with real
partners.

### `POST /partner-hospitals`

```json
{"name": "Kigali Women's Clinic", "latitude": -1.95, "longitude": 30.06,
 "address": "KN 3 Rd", "city": "Kigali", "phone": "+250 700 000 000", "whatsapp": "+250 700 000 000",
 "services": ["colposcopy", "LEEP"], "opening_hours": "Mon-Fri 08:00-17:00"}
```

`name`, `latitude` and `longitude` are required. Returns `201` with the hospital.

---

### `POST /interpretations/{id}/referrals`

```json
{"hospital_id": 1, "referred_by": "nurse-07", "urgency": "soon", "reason": "optional"}
```

`urgency` (`routine`/`soon`/`urgent`) and `reason` default to the recommendation. Returns `201`
with the referral (`status: "sent"`). Later patient messages mention the referral hospital.

---

### `POST /interpretations/{id}/notifications`

Send the patient their result. **Currently a dummy provider:** the message is stored with
`status: "simulated"` and `provider: "dummy"`; nothing is sent.

```json
{"channel": "whatsapp", "phone": "+250788000111", "message": "optional, defaults to the preview", "sent_by": "nurse-07"}
```

`channel` is `sms` or `whatsapp`; `phone` needs at least 7 digits. Returns `201`.

---

## How a result is produced

1. **Validation & storage** — image type/size checked, SHA-256 computed, file stored.
2. **Local quality gate** — resolution, brightness, blur (Laplacian variance), glare and colour
   profile. Blocking failures return `INADEQUATE` without an AI call.
3. **Vision model** — OpenAI (`OPENAI_MODEL`, default `gpt-5`) with a strict JSON schema and a
   WHO/IARC VIA prompt. The model first identifies the image modality; only white-light
   acetic-acid photos receive a VIA read (enforced in code). Up to `FEWSHOT_EXAMPLES`
   clinician-verified cases are included as reference images.
4. **Clinical rules engine** (deterministic, `app/services/rules.py`)
   - verdict mapping and risk index (itemised points)
   - modified Swede score interpretation
   - WHO ablation eligibility: no cancer suspicion (mass, ulcer, necrosis, atypical vessels,
     irregular contour), TZ type 1/2, lesion < 75%, no canal extension, not pregnant
   - symptomatic women with a negative VIA are referred for diagnostic evaluation
   - follow-up intervals: negative 36 months, treated 12 months, cancer suspicion 1 month
   - longitudinal comparison with previous screens
5. **Persistence** — visit, image, interpretation, lesions and assessment are stored; the case
   enters the worklist as `pending`.

Without an OpenAI key the app falls back to an offline colour-heuristic baseline with capped
confidence (demo/testing only).

## Data model

| Table | Purpose |
|---|---|
| `patient` | Pseudonymised patient (`external_id`, age, HIV status) |
| `screening_visit` | Clinical context per visit (symptoms, HPV, pregnancy, parity, smoking, prior treatment ...) |
| `via_image` | Uploaded image metadata, SHA-256, local quality metrics |
| `ai_interpretation` | AI output + assessment; indexed `screening_verdict`, `risk_score`, `review_status`, `follow_up_due` |
| `lesion` | One row per lesion (clock span, area, density, margins, surface, vessels, bbox) |
| `clinician_annotation` | Clinician VIA read (ground truth) |
| `diagnosis_record` | Colposcopy / histology / HPV / cytology results |
| `outcome` | Treatment and follow-up |
| `partner_hospital` | Referral destinations with location and services |
| `referral` | Referral of a screen to a partner hospital |
| `notification` | Result messages sent to patients (SMS / WhatsApp; currently simulated) |

Tables are created automatically on startup.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | – | Enables the OpenAI vision engine |
| `OPENAI_MODEL` | `gpt-5` | Vision model |
| `OPENAI_REASONING_EFFORT` | – | `minimal`/`low`/`medium`/`high` for reasoning models (lower = faster) |
| `INTERPRETER_MODE` | `auto` | `auto`, `openai`, `heuristic` |
| `FEWSHOT_EXAMPLES` | `2` | Clinician-verified reference images sent per request |
| `REVIEW_CONFIDENCE_THRESHOLD` | `0.75` | Below this, results are flagged for priority review |
| `VISCAN_API_KEY` | – | Require `X-API-Key` on all API calls |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSLMODE` | – | PostgreSQL connection (used when `DB_HOST` is set) |
| `DATABASE_URL` | – | Full SQLAlchemy URL (overrides `DB_*`) |
| `SQLITE_PATH` | `instance/viscan.db` | SQLite file used when no Postgres is configured |
| `UPLOAD_DIR` | `instance/uploads` | Image storage directory |
| `PORT` | `5050` | HTTP port |
| `DEFAULT_LATITUDE`, `DEFAULT_LONGITUDE` | `-1.9441`, `30.0619` | Default map centre (clinic location) |
| `OVERPASS_URLS` | public mirrors | Comma-separated Overpass endpoints for the pharmacy search |
| `SEED_DEMO_PARTNERS` | on | Seed demo partner hospitals when the table is empty |
