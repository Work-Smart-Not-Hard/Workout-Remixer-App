from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlmodel import select, or_
from datetime import datetime, timezone, timedelta
from app.dependencies import SessionDep, AuthDep
from app.models import WorkoutSession, SessionExercise, Exercise
from . import router, templates, api_router


def _get_cutoff(period: str):
    now = datetime.now(timezone.utc)
    return {
        "day":     now - timedelta(days=1),
        "week":    now - timedelta(days=7),
        "month":   now - timedelta(days=30),
        "6months": now - timedelta(days=180),
        "year":    now - timedelta(days=365),
    }.get(period)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request, user: AuthDep, db: SessionDep):
    sessions = db.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.completed_at != None)
        .order_by(WorkoutSession.completed_at.desc())
    ).all()
    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={"user": user, "sessions": sessions},
    )


@router.get("/dashboard/muscle/{muscle_name}", response_class=HTMLResponse)
async def muscle_history_view(request: Request, muscle_name: str, user: AuthDep,
                               db: SessionDep, period: str = "week"):
    return templates.TemplateResponse(
        request=request, name="muscle_history.html",
        context={"user": user, "muscle_name": muscle_name, "period": period},
    )

@api_router.get("/dashboard/heatmap")
async def heatmap_data(user: AuthDep, db: SessionDep, period: str = "week"):
    cutoff = _get_cutoff(period)
    query = select(WorkoutSession).where(
        WorkoutSession.user_id == user.id,
        WorkoutSession.completed_at != None,
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)
    sessions = db.exec(query).all()

    muscle_sets: dict[str, int] = {}
    for s in sessions:
        logged = db.exec(select(SessionExercise).where(SessionExercise.session_id == s.id)).all()
        for se in logged:
            ex = db.get(Exercise, se.exercise_id)
            if ex and ex.target:
                key = ex.target.lower()
                muscle_sets[key] = muscle_sets.get(key, 0) + (se.sets_completed or 1)

    if not muscle_sets:
        return {}
    max_sets = max(muscle_sets.values())
    return {m: round(v / max_sets, 2) for m, v in muscle_sets.items()}


@api_router.get("/dashboard/stats")
async def dashboard_stats(user: AuthDep, db: SessionDep, period: str = "all"):
    cutoff = _get_cutoff(period)
    query = select(WorkoutSession).where(
        WorkoutSession.user_id == user.id,
        WorkoutSession.completed_at != None,
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)
    sessions = db.exec(query.order_by(WorkoutSession.completed_at)).all()

    sessions_over_time = [
        {"date": s.completed_at.strftime("%Y-%m-%d"), "duration": s.duration_minutes or 0}
        for s in sessions
    ]
    muscle_volume: dict[str, int] = {}
    total_sets = 0
    for s in sessions:
        logged = db.exec(select(SessionExercise).where(SessionExercise.session_id == s.id)).all()
        for se in logged:
            sets = se.sets_completed or 0
            total_sets += sets
            ex = db.get(Exercise, se.exercise_id)
            if ex and ex.target:
                muscle_volume[ex.target] = muscle_volume.get(ex.target, 0) + sets

    return {
        "total_sessions": len(sessions),
        "total_sets": total_sets,
        "total_duration": sum(s.duration_minutes or 0 for s in sessions),
        "sessions_over_time": sessions_over_time,
        "muscle_volume": sorted(
            [{"muscle": k, "sets": v} for k, v in muscle_volume.items()],
            key=lambda x: x["sets"], reverse=True
        )[:10],
    }


@api_router.get("/dashboard/muscle/{muscle_name}/history")
async def muscle_history_api(muscle_name: str, user: AuthDep, db: SessionDep, period: str = "all"):
    cutoff = _get_cutoff(period)

    exercises = db.exec(
        select(Exercise).where(
            or_(
                Exercise.target.ilike(f"%{muscle_name}%"),
                Exercise.body_part.ilike(f"%{muscle_name}%"),
            )
        )
    ).all()

    if not exercises:
        return {"entries": [], "total_sets": 0, "exercises": []}

    exercise_ids = {ex.id for ex in exercises}
    exercise_map = {ex.id: ex for ex in exercises}

    query = (
        select(SessionExercise, WorkoutSession)
        .join(WorkoutSession, WorkoutSession.id == SessionExercise.session_id)
        .where(WorkoutSession.user_id == user.id)
        .where(SessionExercise.exercise_id.in_(exercise_ids))
        .where(WorkoutSession.completed_at != None)
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)

    rows = db.exec(query.order_by(WorkoutSession.completed_at.desc())).all()
    entries = [
        {
            "date": session.completed_at.strftime("%Y-%m-%d"),
            "exercise_name": exercise_map[se.exercise_id].name,
            "exercise_db_id": exercise_map[se.exercise_id].exercise_id,
            "sets": se.sets_completed,
            "reps": se.reps_completed,
            "weight_kg": se.weight_kg,
            "duration_seconds": se.duration_seconds,
            "notes": se.notes,
        }
        for se, session in rows
        if se.exercise_id in exercise_map
    ]

    return {
        "entries": entries,
        "total_sets": sum(e["sets"] or 0 for e in entries),
        "exercises": [{"name": e.name, "exercise_id": e.exercise_id} for e in exercises[:10]],
    }


@api_router.get("/exercises/{exercise_id}/history")
async def exercise_history(exercise_id: str, user: AuthDep, db: SessionDep, period: str = "all"):
    cutoff = _get_cutoff(period)
    ex = db.exec(select(Exercise).where(Exercise.exercise_id == exercise_id)).one_or_none()
    if not ex:
        return {"sets": [], "best": None, "total_sets": 0}

    query = (
        select(SessionExercise, WorkoutSession)
        .join(WorkoutSession, WorkoutSession.id == SessionExercise.session_id)
        .where(WorkoutSession.user_id == user.id)
        .where(SessionExercise.exercise_id == ex.id)
        .where(WorkoutSession.completed_at != None)
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)

    rows = db.exec(
        query.order_by(WorkoutSession.completed_at, SessionExercise.id)
    ).all()

    sets = [
        {
            "session_id": session.id,
            "date": session.completed_at.strftime("%Y-%m-%d"),
            "sets": se.sets_completed,
            "reps": se.reps_completed,
            "weight_kg": se.weight_kg,
            "duration_seconds": se.duration_seconds,
            "notes": se.notes,
        }
        for se, session in rows
    ]
    weight_entries = [s for s in sets if s["weight_kg"]]
    best = max(weight_entries, key=lambda x: x["weight_kg"]) if weight_entries else None
    return {"sets": sets, "best": best, "total_sets": len(sets)}