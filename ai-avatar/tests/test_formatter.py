import pytest
from app.services.clinical_formatter import ClinicalFormatter
from app.schemas.avatar_report import ReportCreateRequest, ClinicalFindings


def test_generate_narration_script_with_detailed_findings(sample_hsil_payload):
    """Verify spoken script stays short but covers patient, result, key finding and next step."""
    req = ReportCreateRequest(**sample_hsil_payload)
    script = ClinicalFormatter.generate_narration_script(req)

    assert "PT-TEST-1001" in script
    assert "High-grade Squamous Intraepithelial Lesion (HSIL)" in script
    assert "94 percent" in script
    assert "Dense, opaque aceto-white lesion with sharp margins" in script
    assert "12 to 3" in script
    assert "Colposcopy-directed punch biopsy" in script
    assert "Urgent triage follow-up" in script
    # Pitch-friendly length: avoid the old long multi-paragraph narration.
    assert len(script) < 900


def test_custom_script_override():
    """Verify custom script overrides automatic narration generation."""
    custom_text = "This is a custom clinician summary provided by an external AI model."
    req = ReportCreateRequest(
        scan_id="SCAN-CUSTOM",
        patient_id="PT-CUSTOM",
        screening_result="Normal",
        recommendations="None",
        custom_script=custom_text,
    )
    script = ClinicalFormatter.generate_narration_script(req)
    assert script == custom_text


def test_build_anam_system_prompt(sample_hsil_payload):
    """Verify Anam AI Persona system prompt contains all clinical context and role directives."""
    req = ReportCreateRequest(**sample_hsil_payload)
    script = ClinicalFormatter.generate_narration_script(req)
    prompt = ClinicalFormatter.build_anam_system_prompt(req, script)

    assert "Dr. ViScan" in prompt
    assert "cervical cancer screening" in prompt
    assert "PT-TEST-1001" in prompt
    assert "SCAN-TEST-HSIL-001" in prompt
    assert "HSIL" in prompt
    assert "0.94" in prompt
    assert "BEHAVIOR & GUIDELINES" in prompt
    assert "attending medical professional" in prompt
