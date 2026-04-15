import uvicorn
import logging
import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, status
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import select
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
        await _seed_bob_sample_data()

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


async def _seed_bob_sample_data():
    from app.database import get_cli_session
    from app.models import Routine, WorkoutSession, SessionExercise, User
    from app.repositories.routine import RoutineRepository
    from app.services.exercisedb_service import ExerciseDBService

    # BEGIN BOB SAMPLE DATA SEED
    seed_tag = "[BOB_SAMPLE_DATA]"
    schedule = [
        ("Bob Week Builder", 4),
        ("Bob Monthly Grind", 21),
        ("Bob 6 Month Split", 170),
        ("Bob Yearly Strength", 385),
        ("Bob 2 Year Reset", 760),
    ]

    try:
        with get_cli_session() as db:
            bob = db.exec(select(User).where(User.username == "bob")).one_or_none()
            if not bob:
                return

            already_seeded = next(
                (
                    routine for routine in db.exec(
                        select(Routine).where(Routine.owner_id == bob.id)
                    ).all()
                    if seed_tag in (routine.description or "")
                ),
                None,
            )
            if already_seeded:
                return

            bob_id = bob.id
            if bob_id is None:
                return

            service = ExerciseDBService()
            page = await service.get_exercises_page(limit=500)
            api_exercises = page.get("data", []) if isinstance(page, dict) else []
            gif_exercises = [
                ex for ex in api_exercises
                if ex.get("exerciseId") and ex.get("name") and ex.get("gifUrl")
            ]
            if len(gif_exercises) < 12:
                logger.warning("Bob sample seed skipped: not enough ExerciseDB entries with GIFs.")
                return

            routine_repo = RoutineRepository(db)
            now = datetime.now(timezone.utc)

            for idx, (routine_name, days_ago) in enumerate(schedule):
                routine = Routine(
                    owner_id=bob_id,
                    name=routine_name,
                    description=f"{seed_tag} Demo routine for {routine_name}.",
                    is_public=True,
                    created_at=now - timedelta(days=days_ago),
                    updated_at=now - timedelta(days=days_ago),
                )
                db.add(routine)
                db.commit()
                db.refresh(routine)

                routine_id = routine.id
                if routine_id is None:
                    continue

                exercise_payloads = [
                    gif_exercises[(idx * 3 + offset) % len(gif_exercises)]
                    for offset in range(4)
                ]

                added_rows = []
                for position, payload in enumerate(exercise_payloads):
                    exercise_ref = routine_repo.upsert_exercise_ref(payload)
                    exercise_id = exercise_ref.id
                    if exercise_id is None:
                        continue
                    row = routine_repo.add_exercise(
                        routine_id=routine_id,
                        exercise_id=exercise_id,
                        sets=3 + (position % 2),
                        reps=8 + position,
                        duration_seconds=None,
                        rest_seconds=75,
                        notes=f"{seed_tag} routine exercise",
                    )
                    added_rows.append(row)

                started_at = now - timedelta(days=days_ago, hours=1 + idx)
                duration_minutes = 35 + idx * 9
                completed_at = started_at + timedelta(minutes=duration_minutes)

                session = WorkoutSession(
                    user_id=bob_id,
                    routine_id=routine_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_minutes=duration_minutes,
                    notes=f"{seed_tag} {routine_name}",
                )
                db.add(session)
                db.commit()
                db.refresh(session)

                session_id = session.id
                if session_id is None:
                    continue

                for position, row in enumerate(added_rows):
                    db.add(
                        SessionExercise(
                            session_id=session_id,
                            exercise_id=row.exercise_id,
                            sets_completed=row.sets or 3,
                            reps_completed=(row.reps or 8) + 1,
                            weight_kg=round(25 + idx * 5 + position * 4, 1),
                            duration_seconds=None,
                            notes=f"{seed_tag} logged set",
                        )
                    )
                db.commit()

            logger.info("Seeded Bob demo data with ExerciseDB GIF exercises.")
    except Exception as e:
        logger.warning(f"Bob sample seed skipped: {e}")
    # END BOB SAMPLE DATA SEED


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