from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.auth.app.core.database import Base, engine
from services.auth.app.features.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for local development / testing if not using Alembic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Money Judgement - Auth Service",
    version="1.0.0",
    description="Microservice quản lý định danh người dùng, xác thực JWT và hồ sơ ngân hàng",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Support both prefixed /api/v1 and root paths for flexibility with Gateway and direct tests
app.include_router(users_router, prefix="/api/v1")
app.include_router(users_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "auth-service"}
