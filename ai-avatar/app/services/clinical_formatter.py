from typing import Optional
from app.schemas.avatar_report import ReportCreateRequest, ClinicalFindings


class ClinicalFormatter:
    """
    Formats cervical screening data and AI diagnostic assessments
    into authoritative, clear clinical reporting scripts and system prompts for Anam AI avatars.
    """

    @staticmethod
    def generate_narration_script(data: ReportCreateRequest) -> str:
        """
        Creates a clear, professional spoken narration script for the clinician avatar.
        """
        if data.custom_script and data.custom_script.strip():
            return data.custom_script.strip()

        # Build script segments
        greeting = (
            f"Hello. This is the automated ViScan clinical assessment report for Patient ID {data.patient_id}, "
            f"corresponding to Cervical Scan reference {data.scan_id}."
        )

        # Result & Confidence
        confidence_str = (
            f" with an AI model confidence score of {int(data.confidence_score * 100)} percent"
            if data.confidence_score is not None
            else ""
        )
        assessment = (
            f"Primary visual evaluation indicates: {data.screening_result}{confidence_str}."
        )

        # Visual Findings summary
        findings_bullets = []
        if data.findings:
            f: ClinicalFindings = data.findings
            if f.transformation_zone:
                findings_bullets.append(f"Transformation zone is classified as {f.transformation_zone}.")
            if f.aceto_white_changes:
                loc = f" in the {f.lesion_quadrant} quadrant" if f.lesion_quadrant else ""
                findings_bullets.append(f"Acetowhite changes: {f.aceto_white_changes}{loc}.")
            if f.vascular_patterns:
                findings_bullets.append(f"Vascular morphology demonstrates {f.vascular_patterns}.")
            if f.lugol_iodine_reaction:
                findings_bullets.append(f"Lugol's iodine testing resulted in: {f.lugol_iodine_reaction}.")
            if f.additional_observations:
                findings_bullets.append(f"Additional visual findings: {f.additional_observations}.")

        findings_narrative = (
            " " + " ".join(findings_bullets) if findings_bullets else ""
        )

        # Clinical Recommendation
        rec = f"Clinical Recommendation: {data.recommendations}"

        # Physician notes if present
        notes = f" Reviewer notes note: {data.clinical_notes}" if data.clinical_notes else ""

        conclusion = (
            "This concludes the primary visual summary. "
            "Please review the attached scan images and confirm the management plan."
        )

        full_script = f"{greeting} {assessment}{findings_narrative} {rec}{notes} {conclusion}"
        return full_script

    @staticmethod
    def build_anam_system_prompt(data: ReportCreateRequest, script: str) -> str:
        """
        Constructs the system prompt for Anam AI Persona, instructing the avatar
        to act as an expert colposcopy & cervical screening clinical reporter.
        """
        prompt = (
            "You are Dr. ViScan, an empathetic, highly knowledgeable clinical AI specialist in "
            "cervical cancer screening, visual inspection with acetic acid (VIA), and digital colposcopy.\n\n"
            "Your role is to present clinical screening findings to healthcare providers and clinicians clearly, "
            "precisely, and professionally.\n\n"
            f"CURRENT CASE CONTEXT:\n"
            f"- Patient ID: {data.patient_id}\n"
            f"- Scan Reference ID: {data.scan_id}\n"
            f"- Diagnostic Assessment: {data.screening_result}\n"
            f"- Model Confidence: {f'{data.confidence_score:.2f}' if data.confidence_score is not None else 'N/A'}\n"
            f"- Spoken Report Summary: {script}\n"
            f"- Management Recommendation: {data.recommendations}\n"
        )

        if data.findings:
            f = data.findings
            prompt += (
                f"- Findings Details: TZ={f.transformation_zone or 'N/A'}, "
                f"Acetowhite={f.aceto_white_changes or 'N/A'} at {f.lesion_quadrant or 'unspecified'}, "
                f"Vascular={f.vascular_patterns or 'N/A'}, Iodine={f.lugol_iodine_reaction or 'N/A'}\n"
            )

        if data.clinical_notes:
            prompt += f"- Clinical Notes: {data.clinical_notes}\n"

        prompt += (
            "\nBEHAVIOR & GUIDELINES:\n"
            "1. Deliver the clinical report with composure, empathy, and professional clarity.\n"
            "2. Answer clinician queries regarding the diagnostic criteria, classification guidelines (e.g. 2011 IFCPC Colposcopic Terminology), and next steps.\n"
            "3. Always emphasize that clinical decisions rest with the attending medical professional.\n"
            "4. In a live session the Spoken Report Summary is delivered to you verbatim through the talk command "
            "as soon as the video starts. Do not greet, introduce yourself or improvise before that. Afterwards, "
            "only speak when asked a question, and keep answers short.\n"
        )
        return prompt
