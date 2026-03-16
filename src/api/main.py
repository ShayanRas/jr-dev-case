"""FastAPI application -- the API gateway.

In AskCipher's production architecture:
- Server (:8000) is the public-facing API gateway (this role)
- Hinge (:9000) is the agent orchestration service (react_agent package)
- Pointer (:9001) handles external integrations (tools make these calls)

This simplified version runs everything in one process but maintains
the architectural separation in code structure.
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import close_pool, init_pool
from api.routes import router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown resources."""
    logger.info("Starting up -- initializing database pool...")
    await init_pool()
    logger.info("Database pool ready.")
    yield
    logger.info("Shutting down -- closing database pool...")
    await close_pool()


app = FastAPI(
    title="AskCipher Interview Case API",
    description="Simplified API gateway demonstrating the Server/Hinge/Pointer architecture pattern.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
