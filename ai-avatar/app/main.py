import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

from app.core.config import settings
from app.core.database import init_db, engine, check_db_connection, get_db
from app.api.v1.router import api_router
from app.schemas.avatar_report import HealthResponse
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("viscan_avatar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for FastAPI application."""
    logger.info(f"Starting {settings.APP_NAME} on port {settings.APP_PORT}...")
    # Initialize remote PostgreSQL tables
    await init_db()
    yield
    # Cleanup database connections
    logger.info("Closing database engine connections...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Microservice for generating interactive AI clinical reporting avatars "
        "(powered by Anam.ai) for cervical cancer screening and colposcopy examinations."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "status": "online",
        "port": settings.APP_PORT,
        "docs_url": "/docs",
        "api_v1": f"{settings.API_V1_PREFIX}",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def root_health():
    """Service health check endpoint."""
    from app.services.anam_service import anam_service
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


@app.get("/player/{report_id}", response_class=HTMLResponse, tags=["Player"])
async def player_page(report_id: str, db: AsyncSession = Depends(get_db)):
    """
    Dedicated clinician video player & report view.
    Can be loaded directly in browsers or embedded into frontend dashboards via <iframe>.
    """
    from sqlalchemy import select, or_
    from app.models.avatar_report import CervicalAvatarReport
    from app.services.anam_service import anam_service
    from app.templates.player import render_player_html

    res = await db.execute(
        select(CervicalAvatarReport).where(
            or_(
                CervicalAvatarReport.id == report_id,
                CervicalAvatarReport.scan_id == report_id,
            )
        )
    )
    report = res.scalar_one_or_none()
    if not report:
        return HTMLResponse(
            content="<h2 style='font-family:sans-serif;text-align:center;margin-top:50px;'>Report not found.</h2>",
            status_code=404,
        )

    # Always re-fetch the video URL: Anam returns presigned links that expire
    # after ~1 hour, and the player is embedded in the frontend long after
    # rendering (care page, screening history). Falls back to the stored URL.
    if report.anam_video_id:
        try:
            info = await anam_service.get_avatar_video(report.anam_video_id)
            content = info.get("content", {})
            if content.get("available") and content.get("url"):
                report.anam_video_url = content.get("url")
                report.video_status = "completed"
                await db.commit()
        except Exception:
            pass

    video_url = report.anam_video_url or ""
    video_status = report.video_status or "pending"
    findings = report.findings_data or {}

    html_content = render_player_html(report, video_url, video_status, findings)
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
