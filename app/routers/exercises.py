from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi import Request
from app.dependencies import AuthDep
from app.services.exercisedb_service import ExerciseDBService
from . import router, templates, api_router


@router.get("/exercises", response_class=HTMLResponse)
async def exercises_view(request: Request, user: AuthDep):
    return templates.TemplateResponse(
        request=request,
        name="exercises.html",
        context={"user": user},
    )


@api_router.get("/exercises/muscles")
async def list_muscles(user: AuthDep):
    return ExerciseDBService().get_muscles()


@api_router.get("/exercises/equipments")
async def list_equipments(user: AuthDep):
    return ExerciseDBService().get_equipments()


@api_router.get("/exercises")
async def list_exercises(
    user: AuthDep,
    search: str = "",
):
    """Returns all exercises (with optional fuzzy search). Filtering is done client-side."""
    service = ExerciseDBService()
    exercises = await service.get_all_exercises(search=search)
    return {"data": exercises, "total": len(exercises)}


@api_router.get("/exercises/{exercise_id}")
async def get_exercise(exercise_id: str, user: AuthDep):
    service = ExerciseDBService()
    exercise = await service.get_exercise_by_id(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise