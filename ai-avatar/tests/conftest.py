import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.core.database import Base, get_db
import app.models  # Ensure models register with Base.metadata

# Use an isolated in-memory SQLite database for deterministic test execution
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables in the test database once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session for each test."""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an ASGI test client with the database dependency overridden."""
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def sample_hsil_payload():
    return {
        "scan_id": "SCAN-TEST-HSIL-001",
        "patient_id": "PT-TEST-1001",
        "clinician_id": "DR-MWIMULE-TEST",
        "screening_result": "High-grade Squamous Intraepithelial Lesion (HSIL)",
        "confidence_score": 0.94,
        "findings": {
            "transformation_zone": "Type 1 - Fully visible",
            "aceto_white_changes": "Dense, opaque aceto-white lesion with sharp margins",
            "lesion_quadrant": "12 to 3 o clock",
            "vascular_patterns": "Coarse punctation and mosaicism",
            "lugol_iodine_reaction": "Schiller positive (mustard yellow uptake void)",
            "additional_observations": "No suspected invasive micro-carcinoma."
        },
        "recommendations": "Colposcopy-directed punch biopsy and HPV high-risk genotyping.",
        "clinical_notes": "Urgent triage follow-up."
    }


@pytest.fixture
def sample_normal_payload():
    return {
        "scan_id": "SCAN-TEST-NORMAL-001",
        "patient_id": "PT-TEST-1002",
        "clinician_id": "DR-MWIMULE-TEST",
        "screening_result": "Negative for Intraepithelial Lesion or Malignancy (NILM)",
        "confidence_score": 0.98,
        "findings": {
            "transformation_zone": "Type 1 - Fully visible",
            "aceto_white_changes": "None observed",
            "lesion_quadrant": "N/A",
            "vascular_patterns": "Normal fine capillary network",
            "lugol_iodine_reaction": "Schiller negative (uniform mahogany brown)",
            "additional_observations": "Cervix appears healthy and smooth."
        },
        "recommendations": "Routine repeat screening in 3 years.",
        "clinical_notes": "Normal visual screening."
    }
