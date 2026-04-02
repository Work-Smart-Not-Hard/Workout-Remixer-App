import uvicorn
import httpx
import asyncio
import logging
from fastapi import FastAPI, Request, status
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from app.routers import templates, static_files, router, api_router
from app.config import get_settings
from contextlib import asynccontextmanager
from app.services.exercisedb_service import ExerciseDBService

logger = logging.getLogger(__name__)

EXERCISEDB_BASE = "https://exercisedb-api-oe62.onrender.com/api/v1"


async def warmup_exercisedb():
    """Wake up the ExerciseDB server and proactively cache all 1,500 exercises in the background."""
    try:
        service = ExerciseDBService()
        # This will securely fetch all pages and store them in the class-level cache
        await service._fetch_all_exercises()
        logger.info("Successfully warmed up and cached all exercises on startup.")
    except Exception as e:
        logger.error(f"Background warmup of ExerciseDB failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import create_db_and_tables
    create_db_and_tables()

    if get_settings().env.lower() in ["dev", "development"]:
        _seed_default_users()

    # Fire warmup in background — don't block startup
    asyncio.create_task(warmup_exercisedb())

    yield


def _seed_default_users():
    from app.database import get_cli_session
    from app.repositories.user import UserRepository
    from app.services.auth_service import AuthService
    from app.schemas.user import AdminCreate
    from app.utilities.security import encrypt_password

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
    uvicorn.run(
        "app.main:app",
        host=get_settings().app_host,
        port=get_settings().app_port,
        reload=get_settings().env.lower() != "production",
    )