import uvicorn
import app.models
from fastapi import FastAPI, Request, status
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from app.routers import templates, static_files, router, api_router
from app.config import get_settings
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import create_db_and_tables
    create_db_and_tables()

    # Auto-seed required users on startup in non-production environments
    if get_settings().env.lower() in ["dev", "development"]:
        _seed_default_users()

    yield


def _seed_default_users():
    """Ensure the project-required credentials exist on every dev startup."""
    from app.database import get_cli_session
    from app.repositories.user import UserRepository
    from app.services.auth_service import AuthService
    from app.models.user import User
    from app.schemas.user import AdminCreate
    from app.utilities.security import encrypt_password
    from sqlmodel import Session
    import logging

    logger = logging.getLogger(__name__)

    try:
        with get_cli_session() as db:
            repo = UserRepository(db)
            auth = AuthService(repo)

            if not repo.get_by_username("bob"):
                auth.register_user("bob", "bob@example.com", "bobpass")
                logger.info("Seeded user: bob")

            if not repo.get_by_username("admin"):
                admin = AdminCreate(
                    username="admin",
                    email="admin@example.com",
                    password=encrypt_password("adminpass"),
                    role="admin",
                )
                repo.create(admin)
                logger.info("Seeded admin: admin")
    except Exception as e:
        logger.warning(f"Seed skipped (likely first run before tables exist): {e}")


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
    return templates.TemplateResponse(
        request=request,
        name="401.html",
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=get_settings().app_host,
        port=get_settings().app_port,
        reload=get_settings().env.lower() != "production",
    )