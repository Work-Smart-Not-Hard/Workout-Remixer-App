from fastapi import Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select
from typing import Optional
from app.models.models import CustomExercise, RoutineExercise, Exercise
from app.dependencies import SessionDep, AuthDep
from app.utilities.flash import flash
from . import router, templates, api_router


def _get_or_create_exercise_ref(db, ce: CustomExercise) -> Exercise:
    """Ensure an Exercise row exists for a custom exercise (exercise_id = custom_<id>)."""
    ex_id = f"custom_{ce.id}"
    existing = db.exec(select(Exercise).where(Exercise.exercise_id == ex_id)).one_or_none()
    if existing:
        existing.name = ce.name
        existing.gif_url = ce.media_url
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    ex = Exercise(
        exercise_id=ex_id,
        name=ce.name,
        body_part=ce.body_part or "",
        equipment=ce.equipment or "",
        target=ce.body_part or "",
        gif_url=ce.media_url,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@router.get("/custom-exercises", response_class=HTMLResponse)
async def custom_exercises_view(request: Request, user: AuthDep, db: SessionDep):
    exercises = db.exec(
        select(CustomExercise)
        .where(CustomExercise.user_id == user.id)
        .order_by(CustomExercise.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="custom_exercises.html",
        context={"user": user, "exercises": exercises},
    )



@api_router.post("/custom-exercises", status_code=status.HTTP_201_CREATED)
async def create_custom_exercise(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    name: str = Form(),
    description: str = Form(default=""),
    body_part: str = Form(default=""),
    equipment: str = Form(default=""),
    media_url: str = Form(default=""),
):
    ce = CustomExercise(
        user_id=user.id,
        name=name,
        description=description or None,
        body_part=body_part,
        equipment=equipment,
        media_url=media_url or None,
    )
    db.add(ce)
    db.commit()
    db.refresh(ce)
    # Create the backing Exercise row immediately so it shows up in routine search
    _get_or_create_exercise_ref(db, ce)
    flash(request, f'Custom exercise "{name}" created!')
    return RedirectResponse(
        url=request.url_for("custom_exercises_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/custom-exercises/{ce_id}/edit")
async def edit_custom_exercise(
    request: Request,
    ce_id: int,
    user: AuthDep,
    db: SessionDep,
    name: str = Form(),
    description: str = Form(default=""),
    body_part: str = Form(default=""),
    equipment: str = Form(default=""),
    media_url: str = Form(default=""),
):
    ce = db.get(CustomExercise, ce_id)
    if not ce or ce.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    ce.name = name
    ce.description = description or None
    ce.body_part = body_part
    ce.equipment = equipment
    ce.media_url = media_url or None
    db.add(ce)
    db.commit()
    db.refresh(ce)
    # Keep the backing Exercise row in sync
    _get_or_create_exercise_ref(db, ce)
    flash(request, f'Custom exercise "{name}" updated!')
    return RedirectResponse(
        url=request.url_for("custom_exercises_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/custom-exercises/{ce_id}/delete")
async def delete_custom_exercise(
    request: Request,
    ce_id: int,
    user: AuthDep,
    db: SessionDep,
):
    ce = db.get(CustomExercise, ce_id)
    if not ce or ce.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    name = ce.name
    ex_ref = db.exec(
        select(Exercise).where(Exercise.exercise_id == f"custom_{ce_id}")
    ).one_or_none()
    if ex_ref:
        linked = db.exec(
            select(RoutineExercise).where(RoutineExercise.exercise_id == ex_ref.id)
        ).all()
        for re in linked:
            db.delete(re)
        db.delete(ex_ref)
    db.delete(ce)
    db.commit()
    flash(request, f'Custom exercise "{name}" deleted.')
    return RedirectResponse(
        url=request.url_for("custom_exercises_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.get("/custom-exercises")
async def list_custom_exercises(user: AuthDep, db: SessionDep):
    exercises = db.exec(
        select(CustomExercise).where(CustomExercise.user_id == user.id)
    ).all()
    return [
        {
            "id": ex.id,
            "exerciseId": f"custom_{ex.id}",
            "name": ex.name,
            "description": ex.description,
            "body_part": ex.body_part,
            "equipment": ex.equipment,
            "media_url": ex.media_url,
            "bodyParts": [ex.body_part] if ex.body_part else [],
            "equipments": [ex.equipment] if ex.equipment else [],
            "targetMuscles": [ex.body_part] if ex.body_part else [],
            "secondaryMuscles": [],
            "gifUrl": ex.media_url or "",
            "isCustom": True,
        }
        for ex in exercises
    ]


#API: Copy custom exercise into a remixed routine
def copy_custom_exercise_for_user(db, source_ce: CustomExercise, target_user_id: int) -> CustomExercise:
    """Duplicate a CustomExercise into the target user's library."""
    new_ce = CustomExercise(
        user_id=target_user_id,
        name=source_ce.name,
        description=source_ce.description,
        body_part=source_ce.body_part,
        equipment=source_ce.equipment,
        media_url=source_ce.media_url,
    )
    db.add(new_ce)
    db.commit()
    db.refresh(new_ce)
    _get_or_create_exercise_ref(db, new_ce)
    return new_ce