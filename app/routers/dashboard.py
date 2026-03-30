from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlmodel import select, func
from datetime import datetime, timezone, timedelta
from app.dependencies import SessionDep, AuthDep
from app.models import WorkoutSession, SessionExercise, Exercise, Routine
from . import router, templates, api_router


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request, user: AuthDep, db: SessionDep):
    sessions = db.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.completed_at != None)
        .order_by(WorkoutSession.completed_at.desc())
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user, "sessions": sessions},
    )


@api_router.get("/dashboard/stats")
async def dashboard_stats(user: AuthDep, db: SessionDep, period: str = "all"):
    """Returns aggregated stats for the progress dashboard charts."""
    now = datetime.now(timezone.utc)
    cutoff = None
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "6months":
        cutoff = now - timedelta(days=180)

    query = select(WorkoutSession).where(
        WorkoutSession.user_id == user.id,
        WorkoutSession.completed_at != None,
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)

    sessions = db.exec(query.order_by(WorkoutSession.completed_at)).all()

    # Sessions over time (for line chart)
    sessions_over_time = [
        {
            "date": s.completed_at.strftime("%Y-%m-%d"),
            "duration": s.duration_minutes or 0,
        }
        for s in sessions
    ]

    # Total volume per muscle group (for bar chart)
    muscle_volume: dict[str, int] = {}
    total_sets = 0
    for s in sessions:
        logged = db.exec(
            select(SessionExercise).where(SessionExercise.session_id == s.id)
        ).all()
        for se in logged:
            sets = se.sets_completed or 0
            total_sets += sets
            ex = db.get(Exercise, se.exercise_id)
            if ex and ex.target:
                muscle_volume[ex.target] = muscle_volume.get(ex.target, 0) + sets

    muscle_chart = sorted(
        [{"muscle": k, "sets": v} for k, v in muscle_volume.items()],
        key=lambda x: x["sets"], reverse=True
    )[:10]

    return {
        "total_sessions": len(sessions),
        "total_sets": total_sets,
        "total_duration": sum(s.duration_minutes or 0 for s in sessions),
        "sessions_over_time": sessions_over_time,
        "muscle_volume": muscle_chart,
    }


@api_router.get("/exercises/{exercise_id}/history")
async def exercise_history(exercise_id: str, user: AuthDep, db: SessionDep, period: str = "all"):
    """Returns session history for a specific exercise."""
    now = datetime.now(timezone.utc)
    cutoff = None
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "6months":
        cutoff = now - timedelta(days=180)

    # Get local exercise record
    ex = db.exec(select(Exercise).where(Exercise.exercise_id == exercise_id)).one_or_none()
    if not ex:
        return {"sets": [], "best": None}

    query = (
        select(SessionExercise, WorkoutSession)
        .join(WorkoutSession, WorkoutSession.id == SessionExercise.session_id)
        .where(WorkoutSession.user_id == user.id)
        .where(SessionExercise.exercise_id == ex.id)
        .where(WorkoutSession.completed_at != None)
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)

    rows = db.exec(query.order_by(WorkoutSession.completed_at)).all()

    sets = [
        {
            "date": session.completed_at.strftime("%Y-%m-%d"),
            "sets": se.sets_completed,
            "reps": se.reps_completed,
            "weight_kg": se.weight_kg,
            "duration_seconds": se.duration_seconds,
            "notes": se.notes,
        }
        for se, session in rows
    ]

    best = None
    weight_entries = [s for s in sets if s["weight_kg"]]
    if weight_entries:
        best = max(weight_entries, key=lambda x: x["weight_kg"])

    return {"sets": sets, "best": best, "total_sets": len(sets)}