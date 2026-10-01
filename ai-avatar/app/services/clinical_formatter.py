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

        # Keep the spoken script short so live Present and MP4 rendering stay pitch-friendly.
        greeting = f"Hello. This is your ViScan report for patient {data.patient_id}."

        confidence_str = (
            f", AI confidence {int(data.confidence_score * 100)} percent"
            if data.confidence_score is not None
            else ""
        )
        assessment = f"The confirmed screening result is: {data.screening_result}{confidence_str}."

        findings_bits = []
        if data.findings:
            f: ClinicalFindings = data.findings
            if f.aceto_white_changes:
                loc = f" at {f.lesion_quadrant}" if f.lesion_quadrant else ""
                findings_bits.append(f"Acetowhite findings: {f.aceto_white_changes}{loc}.")
            elif f.additional_observations:
                findings_bits.append(f"Key findings: {f.additional_observations}.")

        findings_narrative = (" " + " ".join(findings_bits)) if findings_bits else ""
        rec = f" Next step: {data.recommendations}"
        notes = f" Clinician note: {data.clinical_notes}." if data.clinical_notes else ""
        conclusion = " Please review the images and confirm the care plan."

        return f"{greeting} {assessment}{findings_narrative}{rec}{notes}{conclusion}"

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
