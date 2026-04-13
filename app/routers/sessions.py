from fastapi import Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from app.dependencies import SessionDep, AuthDep
from app.repositories.session import SessionRepository
from app.repositories.routine import RoutineRepository
from app.models import Exercise
from app.utilities.flash import flash
from . import router, templates, api_router


def get_repo(db) -> SessionRepository:
    return SessionRepository(db)


#Views

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


@router.get("/sessions/{session_id}/edit", response_class=HTMLResponse)
async def session_edit_view(request: Request, session_id: int, user: AuthDep, db: SessionDep):
    repo = get_repo(db)
    session = repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        flash(request, "Session not found.", "danger")
        return RedirectResponse(url=request.url_for("activity_view"),
                                status_code=status.HTTP_303_SEE_OTHER)

    if not session.completed_at:
        flash(request, "Only completed sessions can be edited from activity.", "warning")
        return RedirectResponse(url=request.url_for("session_view", session_id=session_id),
                                status_code=status.HTTP_303_SEE_OTHER)

    routine_repo = RoutineRepository(db)
    routine = routine_repo.get_by_id(session.routine_id)
    logged = sorted(repo.get_session_exercises(session_id), key=lambda se: se.id or 0)

    groups_map: dict[int, dict] = {}
    groups: list[dict] = []
    for se in logged:
        if se.exercise_id is None:
            continue
        if se.exercise_id not in groups_map:
            ex = db.get(Exercise, se.exercise_id)
            group = {
                "exercise_id": se.exercise_id,
                "exercise_name": ex.name if ex else "Exercise",
                "exercise_target": ex.target if ex else None,
                "exercise_gif": ex.gif_url if ex else None,
                "sets": [],
            }
            groups_map[se.exercise_id] = group
            groups.append(group)
        groups_map[se.exercise_id]["sets"].append(se)

    return templates.TemplateResponse(
        request=request,
        name="session_edit.html",
        context={
            "user": user,
            "session": session,
            "routine": routine,
            "edit_groups": groups,
        },
    )


#API

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


@api_router.post("/sessions/{session_id}/add-exercise")
async def add_exercise_to_active_session(
    request: Request,
    session_id: int,
    user: AuthDep,
    db: SessionDep,
    exercise_id: str = Form(),
    exercise_name: str = Form(),
    exercise_body_parts: str = Form(default=""),
    exercise_equipments: str = Form(default=""),
    exercise_target_muscles: str = Form(default=""),
    exercise_gif_url: str = Form(default=""),
    sets: Optional[int] = Form(default=None),
    reps: Optional[int] = Form(default=None),
    duration_seconds: Optional[int] = Form(default=None),
    rest_seconds: Optional[int] = Form(default=60),
    notes: str = Form(default=""),
):
    repo = get_repo(db)
    session = repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        flash(request, "Not your session.", "danger")
        return RedirectResponse(url=request.url_for("routines_view"),
                                status_code=status.HTTP_303_SEE_OTHER)

    routine_repo = RoutineRepository(db)
    exercise = routine_repo.upsert_exercise_ref({
        "exerciseId": exercise_id,
        "name": exercise_name,
        "bodyParts": exercise_body_parts.split(",") if exercise_body_parts else [],
        "equipments": exercise_equipments.split(",") if exercise_equipments else [],
        "targetMuscles": exercise_target_muscles.split(",") if exercise_target_muscles else [],
        "gifUrl": exercise_gif_url,
    })

    routine_repo.add_exercise(
        routine_id=session.routine_id,
        exercise_id=exercise.id,
        sets=sets,
        reps=reps,
        duration_seconds=duration_seconds,
        rest_seconds=rest_seconds,
        notes=(notes or "").strip() or None,
    )

    flash(request, f'"{exercise_name}" added to this workout.', "success")
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


@api_router.post("/sessions/{session_id}/edit-records")
async def edit_session_records(
    request: Request,
    session_id: int,
    user: AuthDep,
    db: SessionDep,
):
    repo = get_repo(db)
    session = repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        flash(request, "Session not found.", "danger")
        return RedirectResponse(url=request.url_for("activity_view"),
                                status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    logged = repo.get_session_exercises(session_id)

    def _as_int(value):
        try:
            if value is None:
                return None
            s = str(value).strip()
            return int(s) if s else None
        except (TypeError, ValueError):
            return None

    def _as_float(value):
        try:
            if value is None:
                return None
            s = str(value).strip()
            return float(s) if s else None
        except (TypeError, ValueError):
            return None

    for se in logged:
        se.reps_completed = _as_int(form.get(f"reps_completed_{se.id}"))
        se.weight_kg = _as_float(form.get(f"weight_kg_{se.id}"))
        se.duration_seconds = _as_int(form.get(f"duration_seconds_{se.id}"))
        note_raw = form.get(f"set_notes_{se.id}")
        se.notes = str(note_raw).strip() if note_raw is not None else None
        if se.notes == "":
            se.notes = None
        db.add(se)

    session_note_raw = form.get("session_notes")
    session.notes = str(session_note_raw).strip() if session_note_raw is not None else None
    if session.notes == "":
        session.notes = None
    db.add(session)
    db.commit()

    flash(request, "Workout record updated.", "success")
    return RedirectResponse(url=request.url_for("activity_view"),
                            status_code=status.HTTP_303_SEE_OTHER)