from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logger import logger

from app.database.database import Base, engine
from app.database import models  # noqa: F401

from app.services.llm.router import LLMRouter

from app.api.chat import router as chat_router
from app.api.download import router as download_router
from app.api.projects import router as projects_router
from app.api.ws import router as ws_router
from app.api.runs import router as runs_router

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("=" * 60)
    logger.info(
        f"Starting {settings.PROJECT_NAME}"
    )
    logger.info("=" * 60)

    # Database
    try:

        Base.metadata.create_all(
            bind=engine
        )

        logger.info(
            "Database initialized successfully."
        )

    except Exception:

        logger.exception(
            "Database initialization failed."
        )

    # LLM
    try:

        LLMRouter.get_llm()

        logger.info(
            "LLM initialized successfully."
        )

    except Exception:

        logger.exception(
            "LLM initialization failed."
        )

    yield

    logger.info("=" * 60)
    logger.info(
        f"Shutting down {settings.PROJECT_NAME}"
    )
    logger.info("=" * 60)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "Autonomous AI Software Engineer API"
    ),
    debug=settings.DEBUG,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    chat_router
)

app.include_router(
    download_router
)

app.include_router(
    projects_router
)

app.include_router(
    ws_router
)
app.include_router(
    runs_router
)

@app.get("/")
async def root():

    return {
        "message": (
            f"Welcome to "
            f"{settings.PROJECT_NAME} 🚀"
        ),
        "version": settings.PROJECT_VERSION,
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "debug": settings.DEBUG,
    }


@app.get("/llm")
async def current_llm():

    llm = LLMRouter.get_llm()

    return {
        "provider": (
            llm.__class__.__name__
        ),
        "priority": getattr(
            settings,
            "LLM_PRIORITY",
            "",
        ),
        "model": getattr(
            llm,
            "model",
            "Unknown",
        ),
    }