import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.core.database import init_db, engine, check_db_connection
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


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
