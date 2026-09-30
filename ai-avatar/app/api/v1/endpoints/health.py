from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_connection
from app.services.anam_service import anam_service
from app.schemas.avatar_report import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Check the operational status of the service, remote PostgreSQL connection, and Anam AI configuration.
    """
    db_ok = await check_db_connection()
    anam_ok = anam_service.is_configured

    status_str = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=status_str,
        service=settings.APP_NAME,
        port=settings.APP_PORT,
        environment=settings.ENVIRONMENT,
        database_connected=db_ok,
        anam_configured=anam_ok,
        timestamp=datetime.now(timezone.utc),
    )
