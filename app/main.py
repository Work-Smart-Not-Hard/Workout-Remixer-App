import uvicorn
import logging
import os
from fastapi import FastAPI, Request, status
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from app.routers import templates, static_files, router, api_router
from app.config import get_settings
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import create_db_and_tables
    create_db_and_tables()

    if get_settings().env.lower() in ["dev", "development"]:
        _seed_default_users()

    yield


def _seed_default_users():
    from app.database import get_cli_session
    from app.repositories.user import UserRepository
    from app.services.auth_service import AuthService

    try:
        with get_cli_session() as db:
            repo = UserRepository(db)
            auth = AuthService(repo)
            if not repo.get_by_username("bob"):
                auth.register_user("bob", "bob@example.com", "bobpass")
                logger.info("Seeded user: bob")
    except Exception as e:
        logger.warning(f"Seed skipped: {e}")

app = FastAPI(
    middleware=[
        Middleware(SessionMiddleware, secret_key=get_settings().secret_key)
    ],
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(api_router)
app.mount("/static", static_files, name="static")


@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_redirect_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(request=request, name="401.html")


if __name__ == "__main__":
    runtime_port = int(os.getenv("PORT", str(get_settings().app_port)))
    uvicorn.run(
        "app.main:app",
        host=get_settings().app_host,
        port=runtime_port,
        reload=get_settings().env.lower() != "production",
    )