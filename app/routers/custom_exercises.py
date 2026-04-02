from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
from .. import models
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/custom-exercises", tags=["Custom Exercises"])

@router.post("/", response_model=models.CustomExercise)
def create_custom_exercise(
    exercise: models.CustomExerciseBase, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    new_exercise = models.CustomExercise.model_validate(exercise, update={"user_id": current_user.id})
    db.add(new_exercise)
    db.commit()
    db.refresh(new_exercise)
    return new_exercise

@router.get("/", response_model=List[models.CustomExercise])
def get_my_custom_exercises(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    statement = select(models.CustomExercise).where(models.CustomExercise.user_id == current_user.id)
    return db.exec(statement).all()

@router.put("/{exercise_id}", response_model=models.CustomExercise)
def update_custom_exercise(
    exercise_id: int, 
    updated_exercise: models.CustomExerciseBase, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    statement = select(models.CustomExercise).where(
        models.CustomExercise.id == exercise_id,
        models.CustomExercise.user_id == current_user.id
    )
    exercise = db.exec(statement).first()
    
    if not exercise:
        raise HTTPException(status_code=404, detail="Custom exercise not found")
    
    exercise_data = updated_exercise.model_dump(exclude_unset=True)
    for key, value in exercise_data.items():
        setattr(exercise, key, value)
        
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise

@router.delete("/{exercise_id}")
def delete_custom_exercise(
    exercise_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    statement = select(models.CustomExercise).where(
        models.CustomExercise.id == exercise_id,
        models.CustomExercise.user_id == current_user.id
    )
    exercise = db.exec(statement).first()
    
    if not exercise:
        raise HTTPException(status_code=404, detail="Custom exercise not found")
    
    db.delete(exercise)
    db.commit()
    return {"message": "Custom exercise deleted successfully"}