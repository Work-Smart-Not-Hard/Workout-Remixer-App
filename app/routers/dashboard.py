from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlmodel import select, desc
from datetime import datetime, timezone, timedelta
from app.dependencies import SessionDep, AuthDep
from app.models import WorkoutSession, SessionExercise, Exercise
from . import router, templates, api_router

SECONDARY_MUSCLE_WEIGHT = 0.5


def _iso_utc(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_cutoff(period: str):
    now = datetime.now(timezone.utc)
    return {
        "day":     now - timedelta(days=1),
        "week":    now - timedelta(days=7),
        "month":   now - timedelta(days=30),
        "6months": now - timedelta(days=180),
        "year":    now - timedelta(days=365),
    }.get(period)


def _get_day_start():
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _muscle_buckets(exercise: Exercise) -> tuple[set[str], set[str]]:
    primary = set()
    if exercise.target:
        primary.add(exercise.target.strip().lower())
    if exercise.body_part:
        primary.add(exercise.body_part.strip().lower())

    secondary = set()
    for m in str(exercise.secondary_muscles or "").split(","):
        key = m.strip().lower()
        if key:
            secondary.add(key)

    secondary -= primary
    return primary, secondary


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request, user: AuthDep, db: SessionDep):
    sessions = db.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.completed_at != None)
        .order_by(desc(WorkoutSession.completed_at))
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
        query = query.where(WorkoutSession.completed_at >= cutoff)  # type: ignore[operator]
    sessions = db.exec(query).all()

    muscle_sets: dict[str, float] = {}
    for s in sessions:
        logged = db.exec(select(SessionExercise).where(SessionExercise.session_id == s.id)).all()
        for se in logged:
            ex = db.get(Exercise, se.exercise_id)
            if ex:
                sets = se.sets_completed or 1
                primary, secondary = _muscle_buckets(ex)
                for muscle in primary:
                    muscle_sets[muscle] = muscle_sets.get(muscle, 0) + sets
                for muscle in secondary:
                    muscle_sets[muscle] = muscle_sets.get(muscle, 0) + (sets * SECONDARY_MUSCLE_WEIGHT)

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
        query = query.where(WorkoutSession.completed_at >= cutoff)  # type: ignore[operator]
    sessions = db.exec(query.order_by(desc(WorkoutSession.completed_at))).all()

    today_cutoff = _get_day_start()
    today_query = select(WorkoutSession).where(
        WorkoutSession.user_id == user.id,
        WorkoutSession.completed_at != None,
        WorkoutSession.completed_at >= today_cutoff,  # type: ignore[operator]
    )
    today_sessions = db.exec(today_query.order_by(desc(WorkoutSession.completed_at))).all()

    sessions_over_time = [
        {"date": _iso_utc(s.completed_at), "duration": s.duration_minutes or 0}
        for s in sessions
    ]
    muscle_volume: dict[str, float] = {}
    total_sets = 0
    for s in sessions:
        logged = db.exec(select(SessionExercise).where(SessionExercise.session_id == s.id)).all()
        for se in logged:
            sets = se.sets_completed or 0
            total_sets += sets
            ex = db.get(Exercise, se.exercise_id)
            if ex:
                primary, secondary = _muscle_buckets(ex)
                for muscle in primary:
                    muscle_volume[muscle] = muscle_volume.get(muscle, 0) + sets
                for muscle in secondary:
                    muscle_volume[muscle] = muscle_volume.get(muscle, 0) + (sets * SECONDARY_MUSCLE_WEIGHT)

    return {
        "total_sessions": len(sessions),
        "total_sets": total_sets,
        "total_duration": sum(s.duration_minutes or 0 for s in sessions),
        "today_sessions": len(today_sessions),
        "today_sets": sum(
            (se.sets_completed or 0)
            for s in today_sessions
            for se in db.exec(select(SessionExercise).where(SessionExercise.session_id == s.id)).all()
        ),
        "today_duration": sum(s.duration_minutes or 0 for s in today_sessions),
        "sessions_over_time": sessions_over_time,
        "muscle_volume": sorted(
            [{"muscle": k, "sets": round(v, 2)} for k, v in muscle_volume.items()],
            key=lambda x: x["sets"], reverse=True
        )[:10],
    }


@api_router.get("/dashboard/muscle/{muscle_name}/history")
async def muscle_history_api(muscle_name: str, user: AuthDep, db: SessionDep, period: str = "all"):
    cutoff = _get_cutoff(period)

    muscle_key = muscle_name.strip().lower()
    query = (
        select(SessionExercise, WorkoutSession)
        .join(WorkoutSession, WorkoutSession.id == SessionExercise.session_id)  # type: ignore[arg-type]
        .where(WorkoutSession.user_id == user.id)
        .where(SessionExercise.exercise_id != None)
        .where(WorkoutSession.completed_at != None)
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)  # type: ignore[operator]

    rows = db.exec(query.order_by(desc(WorkoutSession.completed_at))).all()
    exercise_map: dict[int, Exercise] = {}
    matched_exercises: dict[int, Exercise] = {}
    entries = []

    for se, session in rows:
        if se.exercise_id is None:
            continue
        ex = exercise_map.get(se.exercise_id)
        if ex is None:
            ex = db.get(Exercise, se.exercise_id)
            if not ex:
                continue
            exercise_map[se.exercise_id] = ex

        primary, secondary = _muscle_buckets(ex)
        muscles = primary.union(secondary)
        if not any(muscle_key in m or m in muscle_key for m in muscles):
            continue

        if ex.id is None:
            continue
        matched_exercises[ex.id] = ex
        entries.append(
            {
                "date": _iso_utc(session.completed_at),
                "exercise_name": ex.name,
                "exercise_db_id": ex.exercise_id,
                "sets": se.sets_completed,
                "reps": se.reps_completed,
                "weight_kg": se.weight_kg,
                "duration_seconds": se.duration_seconds,
                "notes": se.notes,
            }
        )

    return {
        "entries": entries,
        "total_sets": sum(e["sets"] or 0 for e in entries),
        "exercises": [
            {"name": e.name, "exercise_id": e.exercise_id}
            for e in list(matched_exercises.values())[:10]
        ],
    }


@api_router.get("/exercises/{exercise_id}/history")
async def exercise_history(exercise_id: str, user: AuthDep, db: SessionDep, period: str = "all"):
    cutoff = _get_cutoff(period)
    ex = db.exec(select(Exercise).where(Exercise.exercise_id == exercise_id)).one_or_none()
    if not ex:
        return {"sets": [], "best": None, "total_sets": 0}

    query = (
        select(SessionExercise, WorkoutSession)
        .join(WorkoutSession, WorkoutSession.id == SessionExercise.session_id)  # type: ignore[arg-type]
        .where(WorkoutSession.user_id == user.id)
        .where(SessionExercise.exercise_id == ex.id)
        .where(WorkoutSession.completed_at != None)
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)  # type: ignore[operator]

    rows = db.exec(query.order_by(desc(WorkoutSession.completed_at), desc(SessionExercise.id))).all()

    sets = [
        {
            "session_id": session.id,
            "date": _iso_utc(session.completed_at),
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