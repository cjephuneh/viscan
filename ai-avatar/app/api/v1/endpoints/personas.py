from fastapi import APIRouter
from app.services.anam_service import anam_service
from app.core.config import settings

router = APIRouter()


@router.get("", tags=["Personas"])
async def list_personas():
    """
    List configured Anam AI personas or available presets.
    """
    anam_data = await anam_service.list_personas()
    return {
        "default_persona_id": settings.ANAM_DEFAULT_PERSONA_ID or None,
        "default_avatar_id": settings.ANAM_DEFAULT_AVATAR_ID or None,
        "default_voice_id": settings.ANAM_DEFAULT_VOICE_ID or None,
        "anam_api_configured": anam_service.is_configured,
        "anam_response": anam_data,
    }
