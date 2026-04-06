from fastapi import HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select
from typing import Optional
from app.dependencies import SessionDep, AuthDep
from app.repositories.routine import RoutineRepository
from app.services.routine_service import RoutineService
from app.utilities.flash import flash
from app.models.models import CustomExercise, Exercise, RoutineExercise, Routine
from . import router, templates, api_router


def get_service(db) -> RoutineService:
    return RoutineService(RoutineRepository(db))


#Views

@router.get("/routines", response_class=HTMLResponse)
async def routines_view(request: Request, user: AuthDep, db: SessionDep):
    routines = get_service(db).get_user_routines(user.id)
    return templates.TemplateResponse(
        request=request,
        name="routines.html",
        context={"user": user, "routines": routines},
    )


@router.get("/routines/{routine_id}", response_class=HTMLResponse)
async def routine_detail_view(request: Request, routine_id: int, user: AuthDep, db: SessionDep):
    service = get_service(db)
    routine, exercises = service.get_routine_with_exercises(routine_id, user.id)
    custom_exercises = db.exec(
        select(CustomExercise).where(CustomExercise.user_id == user.id)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="routine_detail.html",
        context={
            "user": user,
            "routine": routine,
            "exercises": exercises,
            "custom_exercises": custom_exercises,
        },
    )


#Routines

@api_router.get("/routines")
async def list_routines(user: AuthDep, db: SessionDep):
    return get_service(db).get_user_routines(user.id)


@api_router.post("/routines", status_code=status.HTTP_201_CREATED)
async def create_routine(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    name: str = Form(),
    description: str = Form(default=""),
):
    routine = get_service(db).create_routine(
        name=name, description=description or None, owner_id=user.id
    )
    flash(request, f'Routine "{routine.name}" created!')
    return RedirectResponse(
        url=request.url_for("routine_detail_view", routine_id=routine.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/routines/{routine_id}/edit")
async def edit_routine(
    request: Request,
    routine_id: int,
    user: AuthDep,
    db: SessionDep,
    name: str = Form(),
    description: str = Form(default=""),
    is_public: bool = Form(default=False),
):
    get_service(db).update_routine(
        routine_id=routine_id, user_id=user.id,
        name=name, description=description or None, is_public=is_public,
    )
    flash(request, "Routine updated!")
    return RedirectResponse(
        url=request.url_for("routine_detail_view", routine_id=routine_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/routines/{routine_id}/delete")
async def delete_routine(request: Request, routine_id: int, user: AuthDep, db: SessionDep):
    get_service(db).delete_routine(routine_id=routine_id, user_id=user.id)
    flash(request, "Routine deleted.")
    return RedirectResponse(
        url=request.url_for("routines_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/routines/{routine_id}/remix")
async def remix_routine(request: Request, routine_id: int, user: AuthDep, db: SessionDep):
    """Copy a public routine into the current user's library.
    Custom exercises from the source are duplicated into the user's library."""
    source = get_service(db).get_routine_or_404(routine_id)
    if not source.is_public and source.owner_id != user.id:
        raise HTTPException(status_code=403, detail="This routine is private")

    new_r = Routine(
        name=f"{source.name} (remix)",
        description=source.description,
        owner_id=user.id,
        remixed_from_id=source.id,
    )
    db.add(new_r)
    db.commit()
    db.refresh(new_r)

    repo = RoutineRepository(db)
    for re in repo.get_exercises_for_routine(routine_id):
        exercise = re.exercise
        target_exercise_id = re.exercise_id

        if exercise and exercise.exercise_id.startswith("custom_"):
            try:
                source_ce_id = int(exercise.exercise_id.split("_", 1)[1])
            except (ValueError, IndexError):
                source_ce_id = None

            if source_ce_id:
                source_ce = db.get(CustomExercise, source_ce_id)
                if source_ce and source_ce.user_id != user.id:
                    new_ce = CustomExercise(
                        user_id=user.id,
                        name=source_ce.name,
                        description=source_ce.description,
                        body_part=source_ce.body_part,
                        equipment=source_ce.equipment,
                        media_url=source_ce.media_url,
                    )
                    db.add(new_ce)
                    db.commit()
                    db.refresh(new_ce)
                    new_ex = Exercise(
                        exercise_id=f"custom_{new_ce.id}",
                        name=new_ce.name,
                        body_part=new_ce.body_part or "",
                        equipment=new_ce.equipment or "",
                        target=new_ce.body_part or "",
                        gif_url=new_ce.media_url,
                    )
                    db.add(new_ex)
                    db.commit()
                    db.refresh(new_ex)
                    target_exercise_id = new_ex.id

        db.add(RoutineExercise(
            routine_id=new_r.id,
            exercise_id=target_exercise_id,
            position=re.position,
            sets=re.sets,
            reps=re.reps,
            duration_seconds=re.duration_seconds,
            rest_seconds=re.rest_seconds or 60,
            notes=re.notes,
            is_custom=re.is_custom,
            custom_exercise_id=re.custom_exercise_id,
        ))

    db.commit()
    flash(request, f'Remixed "{source.name}" — it\'s now in your routines!')
    return RedirectResponse(
        url=request.url_for("routine_detail_view", routine_id=new_r.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/routines/{routine_id}/exercises")
async def add_exercise(
    request: Request,
    routine_id: int,
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
    get_service(db).add_exercise_to_routine(
        routine_id=routine_id,
        user_id=user.id,
        exercise_data={
            "exerciseId": exercise_id,
            "name": exercise_name,
            "bodyParts": exercise_body_parts.split(",") if exercise_body_parts else [],
            "equipments": exercise_equipments.split(",") if exercise_equipments else [],
            "targetMuscles": exercise_target_muscles.split(",") if exercise_target_muscles else [],
            "gifUrl": exercise_gif_url,
        },
        sets=sets,
        reps=reps,
        duration_seconds=duration_seconds,
        rest_seconds=rest_seconds,
        notes=notes or None,
    )
    flash(request, f'"{exercise_name}" added to routine!')
    return RedirectResponse(
        url=request.url_for("routine_detail_view", routine_id=routine_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@api_router.post("/routines/exercises/{routine_exercise_id}/remove")
async def remove_exercise(
    request: Request, routine_exercise_id: int, user: AuthDep, db: SessionDep,
):
    repo = RoutineRepository(db)
    re = repo.get_routine_exercise(routine_exercise_id)
    if not re:
        raise HTTPException(status_code=404, detail="Not found")
    routine_id = re.routine_id
    get_service(db).remove_exercise_from_routine(routine_exercise_id, user.id)
    flash(request, "Exercise removed.")
    return RedirectResponse(
        url=request.url_for("routine_detail_view", routine_id=routine_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )