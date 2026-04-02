from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import select
from typing import List, Optional
from app.models.models import CustomExercise
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.utilities.flash import flash

router = APIRouter(prefix="/api/custom_exercises", tags=["Custom Exercises"])

@router.post("/")
async def create_custom_exercise(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    name: str = Form(...),
    description: str = Form(default=""),
    body_part: str = Form(...),
    equipment: str = Form(...),
    media_url: str = Form(default="")
):
    custom_ex = CustomExercise(
        user_id=user.id,
        name=name,
        description=description,
        body_part=body_part,
        equipment=equipment,
        media_url=media_url
    )
    db.add(custom_ex)
    db.commit()
    flash(request, "Custom exercise created successfully!")
    
    referer = request.headers.get("referer") or "/routines"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)

@router.get("/", response_model=List[CustomExercise])
def get_my_custom_exercises(
    db: SessionDep, 
    current_user: AuthDep
):
    statement = select(CustomExercise).where(CustomExercise.user_id == current_user.id)
    return db.exec(statement).all()

@router.delete("/{exercise_id}")
def delete_custom_exercise(
    request: Request,
    exercise_id: int, 
    db: SessionDep, 
    current_user: AuthDep
):
    statement = select(CustomExercise).where(
        CustomExercise.id == exercise_id,
        CustomExercise.user_id == current_user.id
    )
    exercise = db.exec(statement).first()
    
    if not exercise:
        raise HTTPException(status_code=404, detail="Custom exercise not found")
    
    db.delete(exercise)
    db.commit()
    
    flash(request, "Custom exercise deleted successfully!")
    referer = request.headers.get("referer") or "/routines"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)