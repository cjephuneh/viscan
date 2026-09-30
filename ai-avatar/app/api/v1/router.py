from fastapi import APIRouter
from app.api.v1.endpoints import reports, personas, health

api_router = APIRouter()

api_router.include_router(health.router, prefix="", tags=["Health"])
api_router.include_router(reports.router, prefix="/reports", tags=["Cervical Reports"])
api_router.include_router(personas.router, prefix="/personas", tags=["Personas"])
