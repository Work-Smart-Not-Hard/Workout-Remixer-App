from fastapi import Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from app.dependencies import SessionDep, AuthDep
from app.repositories.session import SessionRepository
from app.repositories.routine import RoutineRepository
from app.utilities.flash import flash
from . import router, templates, api_router


def get_repo(db) -> SessionRepository:
    return SessionRepository(db)


# ── Views ─────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_view(request: Request, session_id: int, user: AuthDep, db: SessionDep):
    repo = get_repo(db)
    session = repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        flash(request, "Session not found.", "danger")
        return RedirectResponse(url=request.url_for("routines_view"),
                                status_code=status.HTTP_303_SEE_OTHER)

    routine_repo = RoutineRepository(db)
    routine, exercises = RoutineRepository(db).get_by_id(session.routine_id), \
                         routine_repo.get_exercises_for_routine(session.routine_id)
    logged = repo.get_session_exercises(session_id)
    logged_ids = {se.exercise_id for se in logged}

    return templates.TemplateResponse(
        request=request,
        name="session.html",
        context={
            "user": user,
            "session": session,
            "routine": routine,
            "exercises": exercises,
            "logged": logged,
            "logged_ids": logged_ids,
        },
    )


# ── API ───────────────────────────────────────────────────────────────────────

@api_router.post("/sessions/start")
async def start_session(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    routine_id: int = Form(),
):
    repo = get_repo(db)
    session = repo.create_session(user_id=user.id, routine_id=routine_id)
    return RedirectResponse(url=request.url_for("session_view", session_id=session.id),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/sessions/{session_id}/log")
async def log_exercise(
    request: Request,
    session_id: int,
    user: AuthDep,
    db: SessionDep,
    exercise_id: int = Form(),
    sets_completed: Optional[int] = Form(default=None),
    reps_completed: Optional[int] = Form(default=None),
    weight_kg: Optional[float] = Form(default=None),
    duration_seconds: Optional[int] = Form(default=None),
    notes: str = Form(default=""),
):
    repo = get_repo(db)
    session = repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        flash(request, "Not your session.", "danger")
        return RedirectResponse(url=request.url_for("routines_view"),
                                status_code=status.HTTP_303_SEE_OTHER)

    repo.log_exercise(
        session_id=session_id,
        exercise_id=exercise_id,
        sets_completed=sets_completed,
        reps_completed=reps_completed,
        weight_kg=weight_kg,
        duration_seconds=duration_seconds,
        notes=notes or None,
    )
    return RedirectResponse(url=request.url_for("session_view", session_id=session_id),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/sessions/{session_id}/complete")
async def complete_session(
    request: Request,
    session_id: int,
    user: AuthDep,
    db: SessionDep,
    notes: str = Form(default=""),
):
    repo = get_repo(db)
    session = repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        flash(request, "Not your session.", "danger")
        return RedirectResponse(url=request.url_for("routines_view"),
                                status_code=status.HTTP_303_SEE_OTHER)

    repo.complete_session(session, notes=notes or None)
    flash(request, "Workout complete! Great work 💪")
    return RedirectResponse(url=request.url_for("routines_view"),
                            status_code=status.HTTP_303_SEE_OTHER)