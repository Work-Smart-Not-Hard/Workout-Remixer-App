from fastapi import Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select, desc, func
from typing import Optional
from collections import defaultdict
from app.dependencies import SessionDep, AuthDep
from app.models import WorkoutSession, SessionExercise, Exercise
from app.models.models import User 
from app.utilities.flash import flash
from . import router, templates, api_router

SECONDARY_MUSCLE_WEIGHT = 0.5


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


async def _build_session_entry(
    db,
    session: WorkoutSession,
) -> dict:
    logged = db.exec(
        select(SessionExercise)
        .where(SessionExercise.session_id == session.id)
        .order_by(SessionExercise.id)      # preserve set order
    ).all()

    exercise_groups: dict[int, list] = defaultdict(list)
    for se in logged:
        if se.exercise_id is not None:
            exercise_groups[se.exercise_id].append(se)

    exercises = []
    muscle_sets: dict[str, float] = {}
    total_sets = 0
    total_volume = 0.0

    for exercise_id, ses in exercise_groups.items():
        ex = db.get(Exercise, exercise_id)
        if not ex:
            continue

        agg_sets      = len(ses)
        agg_reps      = sum(se.reps_completed or 0 for se in ses) or None
        weights       = [se.weight_kg for se in ses if se.weight_kg]
        agg_weight    = max(weights) if weights else None 
        agg_duration  = sum(se.duration_seconds or 0 for se in ses) or None
        agg_notes     = "; ".join(se.notes for se in ses if se.notes) or None

        exercises.append({
            "name": ex.name,
            "target": ex.target,
            "body_part": ex.body_part,
            "gif_url": ex.gif_url,
            "exercise_id": ex.exercise_id,
            "sets": agg_sets,
            "reps": agg_reps,
            "weight_kg": agg_weight,
            "duration_seconds": agg_duration,
            "notes": agg_notes,
        })

        primary, secondary = _muscle_buckets(ex)
        for muscle in primary:
            muscle_sets[muscle] = muscle_sets.get(muscle, 0) + agg_sets
        for muscle in secondary:
            muscle_sets[muscle] = muscle_sets.get(muscle, 0) + (agg_sets * SECONDARY_MUSCLE_WEIGHT)

        total_sets += agg_sets
        if agg_weight and agg_sets and agg_reps:
            total_volume += agg_weight * agg_reps 

    # Normalise muscle data to 0-1
    muscle_data: dict[str, float] = {}
    if muscle_sets:
        max_v = max(muscle_sets.values())
        muscle_data = {m: round(v / max_v, 2) for m, v in muscle_sets.items()}

    routine = session.routine
    return {
        "id": session.id,
        "started_at": session.started_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "duration_minutes": session.duration_minutes,
        "notes": session.notes,
        "routine": {"id": routine.id, "name": routine.name} if routine else None,
        "exercises": exercises,
        "muscle_data": muscle_data,
        "total_sets": total_sets,
        "total_volume": round(total_volume, 1),
        "exercise_count": len(exercises),
    }


@router.get("/activity", response_class=HTMLResponse)
async def activity_view(request: Request, user: AuthDep, db: SessionDep):
    return templates.TemplateResponse(
        request=request,
        name="activity.html",
        context={"user": user},
    )

@api_router.get("/activity/feed")
async def get_my_activity(
    user: AuthDep,
    db: SessionDep,
    offset: int = 0,
    limit: int = 10,
):
    sessions = db.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .where(WorkoutSession.completed_at != None)
        .order_by(desc(WorkoutSession.completed_at))
        .offset(offset)
        .limit(limit)
    ).all()
    entries = []
    for s in sessions:
        entries.append(await _build_session_entry(db, s))
    return entries


@api_router.get("/activity/stats")
async def get_my_activity_stats(user: AuthDep, db: SessionDep):
    total_sessions = db.exec(
        select(func.count()).select_from(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id)
            .where(WorkoutSession.completed_at != None)
            .subquery()
        )
    ).one()
    return {"total_sessions": total_sessions}


@api_router.get("/users/{profile_user_id}/activity")
async def get_user_activity(
    profile_user_id: int,
    user: AuthDep,
    db: SessionDep,
    offset: int = 0,
    limit: int = 10,
):
    profile_user = db.get(User, profile_user_id)
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    if profile_user.privacy_level != "public" and profile_user_id != user.id:
        raise HTTPException(status_code=403, detail="This profile is private")

    sessions = db.exec(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == profile_user_id)
        .where(WorkoutSession.completed_at != None)
        .order_by(desc(WorkoutSession.completed_at))
        .offset(offset)
        .limit(limit)
    ).all()
    entries = []
    for s in sessions:
        entries.append(await _build_session_entry(db, s))
    return entries


@api_router.get("/users/{profile_user_id}/activity/stats")
async def get_user_activity_stats(
    profile_user_id: int,
    user: AuthDep,
    db: SessionDep,
    period: str = "all",
):
    from datetime import datetime, timezone, timedelta

    profile_user = db.get(User, profile_user_id)
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")
    if profile_user.privacy_level != "public" and profile_user_id != user.id:
        raise HTTPException(status_code=403, detail="Private profile")

    now = datetime.now(timezone.utc)
    cutoff_map = {
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "year": now - timedelta(days=365),
    }
    cutoff = cutoff_map.get(period)

    query = (
        select(WorkoutSession)
        .where(WorkoutSession.user_id == profile_user_id)
        .where(WorkoutSession.completed_at != None)
    )
    if cutoff:
        query = query.where(WorkoutSession.completed_at >= cutoff)

    sessions = db.exec(query.order_by(WorkoutSession.completed_at)).all()

    muscle_sets: dict[str, float] = {}
    total_sets = 0
    for s in sessions:
        logged = db.exec(
            select(SessionExercise).where(SessionExercise.session_id == s.id)
        ).all()
        for se in logged:
            ex = db.get(Exercise, se.exercise_id) if se.exercise_id else None
            if ex:
                sets = se.sets_completed or 0
                total_sets += sets
                primary, secondary = _muscle_buckets(ex)
                for muscle in primary:
                    muscle_sets[muscle] = muscle_sets.get(muscle, 0) + sets
                for muscle in secondary:
                    muscle_sets[muscle] = muscle_sets.get(muscle, 0) + (sets * SECONDARY_MUSCLE_WEIGHT)

    heatmap = {}
    if muscle_sets:
        max_v = max(muscle_sets.values())
        heatmap = {m: round(v / max_v, 2) for m, v in muscle_sets.items()}

    return {
        "total_sessions": len(sessions),
        "total_sets": total_sets,
        "total_duration": sum(s.duration_minutes or 0 for s in sessions),
        "heatmap": heatmap,
    }


@api_router.post("/sessions/{session_id}/edit-notes")
async def edit_session_notes(
    request: Request,
    session_id: int,
    user: AuthDep,
    db: SessionDep,
    notes: str = Form(default=""),
):
    session = db.get(WorkoutSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.notes = notes.strip() or None
    db.add(session)
    db.commit()
    return {"ok": True, "notes": session.notes}


@api_router.post("/sessions/{session_id}/delete-activity")
async def delete_session_activity(
    request: Request,
    session_id: int,
    user: AuthDep,
    db: SessionDep,
):
    session = db.get(WorkoutSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    for se in db.exec(
        select(SessionExercise).where(SessionExercise.session_id == session_id)
    ).all():
        db.delete(se)

    db.delete(session)
    db.commit()
    return {"ok": True}