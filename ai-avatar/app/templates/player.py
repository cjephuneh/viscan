def render_player_html(report, video_url: str, video_status: str, findings: dict) -> str:
    """Renders the HTML for the clinician video player page."""
    video_markup = (
        f'<video id="player" controls autoplay playsinline src="{video_url}"></video>'
        if video_url
        else """
          <div class="spinner-box">
            <div class="spinner"></div>
            <div style="font-size: 15px; font-weight: 600; color: #38bdf8;">Rendering Avatar Video with Anam AI</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 6px;">Generating photorealistic speech and clinical gestures. Page updates automatically...</div>
          </div>
        """
    )

    badge_class = "ready" if video_url else "pending"
    badge_text = "Video Ready" if video_url else "Rendering Video..."
    conf_str = f"{int(report.confidence_score * 100)}%" if report.confidence_score else "N/A"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ViScan - Clinical Avatar Report ({report.scan_id})</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      padding: 24px;
      min-height: 100vh;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #1e293b;
    }}
    .header h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #38bdf8;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      background: #0284c7;
      color: #ffffff;
    }}
    .badge.ready {{ background: #059669; }}
    .badge.pending {{ background: #d97706; }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 24px;
    }}
    @media (min-width: 900px) {{
      .grid {{ grid-template-columns: 1.2fr 1fr; }}
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    .card h2 {{
      font-size: 16px;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 16px;
    }}
    .video-box {{
      width: 100%;
      aspect-ratio: 16/9;
      background: #000;
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }}
    video {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .spinner-box {{
      text-align: center;
      padding: 20px;
    }}
    .spinner {{
      width: 48px;
      height: 48px;
      border: 4px solid #334155;
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 16px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .btn-row {{
      display: flex;
      gap: 12px;
      margin-top: 16px;
    }}
    button {{
      background: #0284c7;
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s;
    }}
    button:hover {{ background: #0369a1; }}
    .info-row {{
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid #334155;
      font-size: 14px;
    }}
    .info-label {{ color: #94a3b8; }}
    .info-val {{ font-weight: 500; text-align: right; max-width: 60%; }}
    .script-box {{
      margin-top: 16px;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 14px;
      font-size: 13px;
      line-height: 1.6;
      color: #cbd5e1;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>ViScan Clinician Avatar Video</h1>
      <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">
        Scan: <strong>{report.scan_id}</strong> • Patient: <strong>{report.patient_id}</strong>
      </div>
    </div>
    <span class="badge {badge_class}">
      {badge_text}
    </span>
  </div>

  <div class="grid">
    <!-- Video Player Column -->
    <div class="card">
      <h2>Digital Clinician Avatar</h2>
      <div class="video-box" id="videoBox">
        {video_markup}
      </div>
      <div class="btn-row">
        <button onclick="copyVideoUrl()">Copy Direct MP4 URL</button>
        <button onclick="copyEmbedCode()">Copy Iframe Embed Code</button>
      </div>
      <div id="copyAlert" style="font-size: 12px; color: #34d399; margin-top: 8px; display: none;">Copied to clipboard!</div>
    </div>

    <!-- Clinical Details Column -->
    <div class="card">
      <h2>Cervical Assessment Details</h2>
      <div class="info-row">
        <span class="info-label">Screening Assessment</span>
        <span class="info-val" style="color: #f87171;">{report.screening_result}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Confidence Score</span>
        <span class="info-val">{conf_str}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Transformation Zone</span>
        <span class="info-val">{findings.get("transformation_zone", "N/A")}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Acetowhite Lesion</span>
        <span class="info-val">{findings.get("aceto_white_changes", "None")} ({findings.get("lesion_quadrant", "General")})</span>
      </div>
      <div class="info-row">
        <span class="info-label">Vascular Morphology</span>
        <span class="info-val">{findings.get("vascular_patterns", "Normal")}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Lugol Iodine Uptake</span>
        <span class="info-val">{findings.get("lugol_iodine_reaction", "N/A")}</span>
      </div>

      <div style="margin-top: 18px;">
        <span class="info-label" style="font-size: 13px; font-weight: 600;">Clinical Recommendation</span>
        <div style="font-size: 13px; color: #e2e8f0; margin-top: 4px; padding: 10px; background: #0f172a; border-radius: 6px; border-left: 3px solid #38bdf8;">
          {report.recommendations}
        </div>
      </div>

      <div style="margin-top: 18px;">
        <span class="info-label" style="font-size: 13px; font-weight: 600;">Spoken Narration Script</span>
        <div class="script-box">
          {report.generated_script}
        </div>
      </div>
    </div>
  </div>

  <script>
    const videoUrl = "{video_url}";
    const reportId = "{report.id}";

    function copyVideoUrl() {{
      if (!videoUrl) {{
        alert("Video is still generating. Please wait a moment.");
        return;
      }}
      navigator.clipboard.writeText(videoUrl);
      showAlert();
    }}

    function copyEmbedCode() {{
      const embed = `<iframe src="${{window.location.origin}}/player/${{reportId}}" width="100%" height="600" frameborder="0" allow="autoplay"></iframe>`;
      navigator.clipboard.writeText(embed);
      showAlert();
    }}

    function showAlert() {{
      const a = document.getElementById("copyAlert");
      a.style.display = "block";
      setTimeout(() => a.style.display = "none", 2500);
    }}

    // Auto-poll if video is still rendering
    if (!videoUrl) {{
      const interval = setInterval(async () => {{
        try {{
          const res = await fetch(`/api/v1/reports/${{reportId}}/video`);
          const data = await res.json();
          if (data.video_url && data.status === "completed") {{
            clearInterval(interval);
            window.location.reload();
          }}
        }} catch (e) {{
          console.error("Polling error", e);
        }}
      }}, 3000);
    }}
  </script>
</body>
</html>"""
