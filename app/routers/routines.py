from fastapi import HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from app.dependencies import SessionDep, AuthDep
from app.repositories.routine import RoutineRepository
from app.services.routine_service import RoutineService
from app.utilities.flash import flash
from . import router, templates, api_router


def get_service(db) -> RoutineService:
    return RoutineService(RoutineRepository(db))


# ── Views ─────────────────────────────────────────────────────────────────────

@router.get("/routines", response_class=HTMLResponse)
async def routines_view(request: Request, user: AuthDep, db: SessionDep):
    service = get_service(db)
    routines = service.get_user_routines(user.id)
    return templates.TemplateResponse(
        request=request,
        name="routines.html",
        context={"user": user, "routines": routines},
    )


@router.get("/explore", response_class=HTMLResponse)
async def explore_view(request: Request, user: AuthDep, db: SessionDep):
    service = get_service(db)
    public_routines = service.get_public_routines(user.id)
    return templates.TemplateResponse(
        request=request,
        name="explore.html",
        context={"user": user, "routines": public_routines},
    )


@router.get("/routines/{routine_id}", response_class=HTMLResponse)
async def routine_detail_view(request: Request, routine_id: int, user: AuthDep, db: SessionDep):
    service = get_service(db)
    routine, exercises = service.get_routine_with_exercises(routine_id, user.id)
    return templates.TemplateResponse(
        request=request,
        name="routine_detail.html",
        context={"user": user, "routine": routine, "exercises": exercises},
    )


# ── API ───────────────────────────────────────────────────────────────────────

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
    service = get_service(db)
    routine = service.create_routine(name=name, description=description or None, owner_id=user.id)
    flash(request, f'Routine "{routine.name}" created!')
    return RedirectResponse(url=request.url_for("routine_detail_view", routine_id=routine.id),
                            status_code=status.HTTP_303_SEE_OTHER)


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
    service = get_service(db)
    service.update_routine(
        routine_id=routine_id,
        user_id=user.id,
        name=name,
        description=description or None,
        is_public=is_public,
    )
    flash(request, "Routine updated!")
    return RedirectResponse(url=request.url_for("routine_detail_view", routine_id=routine_id),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/routines/{routine_id}/delete")
async def delete_routine(
    request: Request,
    routine_id: int,
    user: AuthDep,
    db: SessionDep,
):
    service = get_service(db)
    service.delete_routine(routine_id=routine_id, user_id=user.id)
    flash(request, "Routine deleted.")
    return RedirectResponse(url=request.url_for("routines_view"),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/routines/{routine_id}/remix")
async def remix_routine(
    request: Request,
    routine_id: int,
    user: AuthDep,
    db: SessionDep,
):
    service = get_service(db)
    new_routine = service.remix_routine(routine_id=routine_id, user_id=user.id)
    flash(request, f'Remixed "{new_routine.name}" — it\'s now in your routines!')
    return RedirectResponse(url=request.url_for("routine_detail_view", routine_id=new_routine.id),
                            status_code=status.HTTP_303_SEE_OTHER)


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
    service = get_service(db)
    exercise_data = {
        "exerciseId": exercise_id,
        "name": exercise_name,
        "bodyParts": exercise_body_parts.split(",") if exercise_body_parts else [],
        "equipments": exercise_equipments.split(",") if exercise_equipments else [],
        "targetMuscles": exercise_target_muscles.split(",") if exercise_target_muscles else [],
        "gifUrl": exercise_gif_url,
    }
    service.add_exercise_to_routine(
        routine_id=routine_id,
        user_id=user.id,
        exercise_data=exercise_data,
        sets=sets,
        reps=reps,
        duration_seconds=duration_seconds,
        rest_seconds=rest_seconds,
        notes=notes or None,
    )
    flash(request, f'"{exercise_name}" added to routine!')
    return RedirectResponse(url=request.url_for("routine_detail_view", routine_id=routine_id),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/routines/exercises/{routine_exercise_id}/remove")
async def remove_exercise(
    request: Request,
    routine_exercise_id: int,
    user: AuthDep,
    db: SessionDep,
):
    repo = RoutineRepository(db)
    re = repo.get_routine_exercise(routine_exercise_id)
    if not re:
        raise HTTPException(status_code=404, detail="Not found")
    routine_id = re.routine_id
    service = get_service(db)
    service.remove_exercise_from_routine(routine_exercise_id, user.id)
    flash(request, "Exercise removed.")
    return RedirectResponse(url=request.url_for("routine_detail_view", routine_id=routine_id),
                            status_code=status.HTTP_303_SEE_OTHER)