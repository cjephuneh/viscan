# ViScan AI Avatar Service — Frontend Integration Guide

This guide details all API request contracts, payload definitions, JSON response schemas, and integration code snippets for connecting frontend applications (React, Next.js, Vue, Angular, or Vanilla JS) to the **ViScan AI Avatar Service** (Port `9090`).

---

## 🌐 Base URL & Endpoints Summary

- **Base URL**: `http://<API_HOST>:9090` (Local testing: `http://localhost:9090`)
- **Interactive Swagger Documentation**: `http://localhost:9090/docs`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/reports` | Ingests scan findings, generates narrative script, and triggers avatar video render |
| `GET` | `/api/v1/reports/{id_or_scan_id}/video` | **Primary Frontend Endpoint**: Retrieves the direct playable `.mp4` video URL & render status |
| `POST` | `/api/v1/reports/{id_or_scan_id}/video` | Manually (re)triggers video rendering |
| `GET` | `/player/{id_or_scan_id}` | Hosted HTML5 video player page (ready to embed in `<iframe>`) |
| `GET` | `/api/v1/reports/{id_or_scan_id}` | Fetches full report data, visual findings, and generated script |
| `GET` | `/api/v1/reports` | Lists reports with pagination and optional `patient_id` filter |
| `POST` | `/api/v1/reports/{id_or_scan_id}/session` | Issues short-lived WebRTC session token for real-time live avatar dialogue |
| `GET` | `/health` | Health check endpoint |

---

## 1. Create / Ingest Clinical Report

**Endpoint:** `POST /api/v1/reports`  
**Content-Type:** `application/json`

### Request Body

```json
{
  "scan_id": "SCAN-2026-001",
  "patient_id": "PT-4421",
  "clinician_id": "DR-MWIMULE-01",
  "screening_result": "High-grade Squamous Intraepithelial Lesion (HSIL)",
  "confidence_score": 0.94,
  "findings": {
    "transformation_zone": "Type 1 - Fully visible",
    "aceto_white_changes": "Dense, opaque aceto-white lesion with distinct margins",
    "lesion_quadrant": "12 to 3 o clock",
    "vascular_patterns": "Coarse punctation and mosaicism",
    "lugol_iodine_reaction": "Schiller positive (mustard yellow uptake void)",
    "additional_observations": "No suspected invasion beyond squamocolumnar junction."
  },
  "recommendations": "Urgent colposcopic-directed punch biopsy and high-risk HPV genotyping.",
  "clinical_notes": "Patient presents for routine follow-up triage."
}
```

#### Field Specifications:
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `scan_id` | String | **Yes** | Unique cervical scan or colposcopy examination identifier |
| `patient_id` | String | **Yes** | Anonymized patient ID or Medical Record Number |
| `screening_result` | String | **Yes** | Clinical diagnosis / triage classification (e.g. HSIL, LSIL, NILM, ASC-US) |
| `recommendations` | String | **Yes** | Clinical management plan |
| `confidence_score` | Float | No | AI model confidence score between `0.0` and `1.0` |
| `findings` | Object | No | Visual colposcopy inspection findings |
| `findings.transformation_zone` | String | No | Transformation Zone classification (Type 1, 2, or 3) |
| `findings.aceto_white_changes` | String | No | Description of acetowhite changes |
| `findings.lesion_quadrant` | String | No | Clock-face position (e.g. "12 to 3 o clock") |
| `findings.vascular_patterns` | String | No | Vascular morphology (e.g. "Fine punctation", "Coarse mosaic") |
| `findings.lugol_iodine_reaction` | String | No | Lugol iodine uptake status |
| `clinical_notes` | String | No | Physician or triage supplemental notes |
| `custom_script` | String | No | Custom spoken narration override (if omitted, generated automatically) |

### Response (`201 Created`)

```json
{
  "id": "64bc0b3c-fa58-4509-9e8c-859a84a6fe0b",
  "scan_id": "SCAN-2026-001",
  "patient_id": "PT-4421",
  "clinician_id": "DR-MWIMULE-01",
  "screening_result": "High-grade Squamous Intraepithelial Lesion (HSIL)",
  "confidence_score": 0.94,
  "findings_data": {
    "transformation_zone": "Type 1 - Fully visible",
    "aceto_white_changes": "Dense, opaque aceto-white lesion with distinct margins",
    "lesion_quadrant": "12 to 3 o clock",
    "vascular_patterns": "Coarse punctation and mosaicism",
    "lugol_iodine_reaction": "Schiller positive (mustard yellow uptake void)",
    "additional_observations": "No suspected invasion beyond squamocolumnar junction."
  },
  "recommendations": "Urgent colposcopic-directed punch biopsy and high-risk HPV genotyping.",
  "clinical_notes": "Patient presents for routine follow-up triage.",
  "generated_script": "Hello. This is the automated ViScan clinical assessment report for Patient ID PT-4421, corresponding to Cervical Scan reference SCAN-2026-001. Primary visual evaluation indicates: High-grade Squamous Intraepithelial Lesion (HSIL) with an AI model confidence score of 94 percent. Transformation zone is classified as Type 1 - Fully visible. Acetowhite changes: Dense, opaque aceto-white lesion with distinct margins in the 12 to 3 o clock quadrant. Vascular morphology demonstrates Coarse punctation and mosaicism. Lugol's iodine testing resulted in: Schiller positive (mustard yellow uptake void). Additional visual findings: No suspected invasion beyond squamocolumnar junction. Clinical Recommendation: Urgent colposcopic-directed punch biopsy and high-risk HPV genotyping. Reviewer notes note: Patient presents for routine follow-up triage. This concludes the primary visual summary. Please review the attached scan images and confirm the management plan.",
  "anam_persona_id": null,
  "anam_session_token": "eyJhbGciOiJIUzI1NiIs...",
  "anam_video_id": "avv_60a4977d-dddb-49b7-8fb6-7491841a53ba",
  "anam_video_url": null,
  "video_status": "running",
  "player_url": "/player/64bc0b3c-fa58-4509-9e8c-859a84a6fe0b",
  "status": "READY",
  "created_at": "2026-09-30T12:27:43.217000Z",
  "updated_at": "2026-09-30T12:27:43.217000Z"
}
```

---

## 2. Get Avatar Video URL (For Direct Playback)

**Endpoint:** `GET /api/v1/reports/{id_or_scan_id}/video`

Call this endpoint to check the render status. Video rendering takes approximately **8 to 12 seconds**. Once ready, `video_url` contains the downloadable and streamable `.mp4` file.

### Response (`200 OK`)

```json
{
  "report_id": "64bc0b3c-fa58-4509-9e8c-859a84a6fe0b",
  "scan_id": "SCAN-2026-001",
  "video_id": "avv_60a4977d-dddb-49b7-8fb6-7491841a53ba",
  "status": "completed",
  "video_url": "https://anam-session-recordings-prod.3b4e2c62766b488dfadbba0f05120797.r2.cloudflarestorage.com/1MrJeDq9NC3RZpzma9t0cCrEJhX3lU3S/b0988f1e-2429-4005-9420-f6e73e83e72c/recording.mp4",
  "player_url": "/player/64bc0b3c-fa58-4509-9e8c-859a84a6fe0b",
  "duration_seconds": 18.4,
  "expires_at": "2026-09-30T15:23:44.371Z",
  "instructions": "Use video_url directly in HTML5 <video src=...> or player_url in an <iframe>."
}
```

#### Status Values:
- `"pending"` / `"running"`: The avatar video is currently rendering. Poll again in 2–3 seconds.
- `"completed"`: Rendering is finished. `video_url` contains the playable `.mp4`.
- `"failed"`: Video rendering encountered an error.

---

## 3. Hosted Player Page (`<iframe>` Embed)

**Endpoint:** `GET /player/{id_or_scan_id}`

Returns a responsive, styled clinical viewer page with:
- The avatar video player (auto-playing when ready).
- Automatic status polling with spinner while rendering.
- Complete clinical findings table & recommendations.
- Spoken narration script transcript.

### How to Embed:

```html
<iframe
  src="http://localhost:9090/player/SCAN-2026-001"
  width="100%"
  height="650"
  frameborder="0"
  allow="autoplay; fullscreen"
  style="border-radius: 12px; border: 1px solid #334155;">
</iframe>
```

---

## 4. Real-Time WebRTC Streaming Token (Optional Interactive Mode)

**Endpoint:** `POST /api/v1/reports/{id_or_scan_id}/session`

If your frontend wants the clinician to have a **two-way live conversational dialogue** with the avatar rather than playing an MP4 video, call this endpoint to obtain a 1-hour session token.

### Response (`200 OK`)

```json
{
  "report_id": "64bc0b3c-fa58-4509-9e8c-859a84a6fe0b",
  "session_token": "eyJhbGciOiJIUzI1NiIsImtpZCI6Imp3dC1zZXNzaW9uLXNpZ25pbmcta2V5Iiw...",
  "persona_id": null,
  "system_prompt": "You are Dr. ViScan, an empathetic, highly knowledgeable clinical AI specialist...",
  "generated_script": "Hello. This is the automated ViScan clinical assessment report...",
  "expires_in_seconds": 3600,
  "instructions": "Pass this session_token to the Anam client SDK to initiate WebRTC streaming."
}
```

---

## 5. Frontend Code Examples

### A. React / Next.js Component (Native Video Player with Polling)

```tsx
import React, { useEffect, useState } from "react";

interface VideoStatus {
  status: "pending" | "running" | "completed" | "failed";
  video_url: string | null;
  player_url: string;
}

export function CervicalAvatarVideo({ scanId }: { scanId: string }) {
  const [videoData, setVideoData] = useState<VideoStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const checkVideoStatus = async () => {
      try {
        const res = await fetch(`http://localhost:9090/api/v1/reports/${scanId}/video`);
        const data: VideoStatus = await res.json();
        setVideoData(data);

        if (data.status === "completed" && data.video_url) {
          setLoading(false);
          clearInterval(intervalId);
        }
      } catch (err) {
        console.error("Failed to load avatar video", err);
      }
    };

    // Initial check
    checkVideoStatus();

    // Poll every 3 seconds until completed
    intervalId = setInterval(checkVideoStatus, 3000);

    return () => clearInterval(intervalId);
  }, [scanId]);

  if (loading || !videoData?.video_url) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-900 rounded-lg text-slate-100">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-sky-400 mb-4" />
        <p className="font-medium text-sky-400">Rendering Clinician Avatar Video...</p>
        <p className="text-xs text-slate-400 mt-1">Status: {videoData?.status || "initializing"}</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 p-4 rounded-lg shadow-lg">
      <video
        controls
        autoPlay
        playsInline
        className="w-full rounded-md shadow"
        src={videoData.video_url}
      />
    </div>
  );
}
```

---

### B. Vanilla JavaScript / HTML Integration

```html
<!DOCTYPE html>
<html>
<head>
  <title>Cervical Scan Avatar Video</title>
</head>
<body>
  <div id="videoContainer">
    <p id="statusMsg">Loading avatar video...</p>
    <video id="avatarVideo" controls autoplay playsinline style="display:none; width: 640px; border-radius: 8px;"></video>
  </div>

  <script>
    const API_BASE = "http://localhost:9090";
    const SCAN_ID = "SCAN-2026-001";

    async function loadVideo() {
      const statusMsg = document.getElementById("statusMsg");
      const videoEl = document.getElementById("avatarVideo");

      const poll = async () => {
        const res = await fetch(`${API_BASE}/api/v1/reports/${SCAN_ID}/video`);
        const data = await res.json();

        if (data.status === "completed" && data.video_url) {
          statusMsg.style.display = "none";
          videoEl.src = data.video_url;
          videoEl.style.display = "block";
          clearInterval(interval);
        } else {
          statusMsg.innerText = `Generating avatar video... (${data.status})`;
        }
      };

      poll();
      const interval = setInterval(poll, 3000);
    }

    loadVideo();
  </script>
</body>
</html>
```

---

### C. Live WebRTC Streaming Dialogue (Using `@anam-ai/js-sdk`)

```javascript
import { createClient } from "@anam-ai/js-sdk";

async function startInteractiveAvatar(scanId, videoElementId) {
  // 1. Fetch ephemeral session token from your backend
  const response = await fetch(`http://localhost:9090/api/v1/reports/${scanId}/session`, {
    method: "POST"
  });
  const { session_token } = await response.json();

  // 2. Initialize Anam client with session token (Zero API key exposure)
  const client = createClient({ sessionToken: session_token });

  // 3. Connect real-time WebRTC stream to DOM <video> element
  const videoElement = document.getElementById(videoElementId);
  await client.streamToVideoElement(videoElement);
}
```
