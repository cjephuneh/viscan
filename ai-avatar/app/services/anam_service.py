import logging
from typing import Optional, Dict, Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AnamService:
    """
    Client service for interacting with the Anam AI API (https://anam.ai).
    Handles persona management, session token generation for WebRTC avatar streaming.
    """

    def __init__(self):
        self.base_url = settings.ANAM_BASE_URL.rstrip("/")
        self.api_key = settings.ANAM_API_KEY

    @property
    def is_configured(self) -> bool:
        """Returns True if Anam API Key is configured."""
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"))

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_session_token(
        self,
        system_prompt: str,
        persona_id: Optional[str] = None,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Requests a short-lived session token from Anam AI (POST /v1/auth/session-token).
        The client SDK uses this token to initiate low-latency WebRTC avatar streaming.
        """
        if not self.is_configured:
            logger.warning(
                "ANAM_API_KEY is not configured or is a placeholder. "
                "Returning simulated session token for development/testing."
            )
            return {
                "sessionToken": f"simulated_anam_session_token_{persona_id or 'default'}",
                "simulated": True,
            }

        url = f"{self.base_url}/auth/session-token"

        target_persona_id = persona_id or settings.ANAM_DEFAULT_PERSONA_ID or None

        payload: Dict[str, Any] = {}
        if target_persona_id:
            payload["personaId"] = target_persona_id

        # Attach custom configuration / system prompt for this clinical report case
        persona_config: Dict[str, Any] = {
            "name": "Dr. ViScan Cervical Specialist",
            "systemPrompt": system_prompt,
        }

        # If specific avatar/voice IDs configured
        eff_avatar_id = avatar_id or settings.ANAM_DEFAULT_AVATAR_ID
        if eff_avatar_id:
            persona_config["avatarId"] = eff_avatar_id

        eff_voice_id = voice_id or settings.ANAM_DEFAULT_VOICE_ID
        if eff_voice_id:
            persona_config["voiceId"] = eff_voice_id

        payload["personaConfig"] = persona_config

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                logger.info("Successfully acquired Anam AI session token.")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Anam API HTTP error ({e.response.status_code}): {e.response.text}"
                )
                raise RuntimeError(
                    f"Failed to obtain Anam session token: {e.response.text}"
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Network error connecting to Anam API: {e}")
                raise RuntimeError(f"Network failure connecting to Anam AI: {e}") from e

    async def list_personas(self) -> Dict[str, Any]:
        """Fetches personas configured in the Anam account."""
        if not self.is_configured:
            return {
                "personas": [],
                "message": "ANAM_API_KEY is not configured. Personas cannot be fetched remotely.",
            }

        url = f"{self.base_url}/personas"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error fetching personas from Anam: {e}")
                return {"personas": [], "error": str(e)}

    async def create_avatar_video(
        self,
        script: str,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
        persona_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Triggers asynchronous MP4 avatar video rendering from a script (POST /v1/avatar-videos).
        Requires Idempotency-Key header.
        """
        import uuid

        if not self.is_configured:
            return {
                "id": f"simulated_video_{uuid.uuid4().hex[:8]}",
                "status": "completed",
                "content": {
                    "available": True,
                    "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                },
                "simulated": True,
            }

        url = f"{self.base_url}/avatar-videos"
        headers = self._get_headers()
        headers["Idempotency-Key"] = str(uuid.uuid4())

        eff_avatar_id = avatar_id or settings.ANAM_DEFAULT_AVATAR_ID or "54f78dd3-bd52-4077-899d-322fcb56d4cd"
        eff_voice_id = voice_id or settings.ANAM_DEFAULT_VOICE_ID or "91b4ce0f-4fc0-11f1-84b0-52bacf74fa75"

        payload: Dict[str, Any] = {
            "script": script,
            "avatarId": eff_avatar_id,
            "voiceId": eff_voice_id,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Initiated Anam avatar video render job: {data.get('id')}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"Anam avatar-video generation error ({e.response.status_code}): {e.response.text}")
                raise RuntimeError(f"Anam video render error: {e.response.text}") from e
            except Exception as e:
                logger.error(f"Failed to call Anam avatar-video API: {e}")
                raise RuntimeError(f"Anam video render connection failure: {e}") from e

    async def get_avatar_video(self, video_id: str) -> Dict[str, Any]:
        """
        Retrieves current status and downloadable/playable MP4 URL of an avatar video job.
        """
        if not self.is_configured or video_id.startswith("simulated_"):
            return {
                "id": video_id,
                "status": "completed",
                "content": {
                    "available": True,
                    "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                },
            }

        url = f"{self.base_url}/avatar-videos/{video_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to query avatar video {video_id}: {e.response.text}")
                raise RuntimeError(f"Failed to query video status: {e.response.text}") from e
            except Exception as e:
                logger.error(f"Error querying video status: {e}")
                raise RuntimeError(f"Failed to check video status: {e}") from e


# Singleton instance
anam_service = AnamService()
