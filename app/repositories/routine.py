from sqlmodel import Session, select
from app.models import Routine, RoutineExercise, Exercise
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RoutineRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, description: Optional[str], owner_id: int) -> Routine:
        routine = Routine(name=name, description=description, owner_id=owner_id)
        self.db.add(routine)
        self.db.commit()
        self.db.refresh(routine)
        return routine

    def get_by_id(self, routine_id: int) -> Optional[Routine]:
        return self.db.get(Routine, routine_id)

    def get_by_owner(self, owner_id: int) -> list[Routine]:
        return self.db.exec(
            select(Routine).where(Routine.owner_id == owner_id)
            .order_by(Routine.created_at.desc())
        ).all()

    def get_public(self, exclude_user_id: Optional[int] = None) -> list[Routine]:
        query = select(Routine).where(Routine.is_public == True)
        if exclude_user_id:
            query = query.where(Routine.owner_id != exclude_user_id)
        return self.db.exec(query.order_by(Routine.created_at.desc())).all()

    def update(self, routine: Routine, name: str, description: Optional[str], is_public: bool) -> Routine:
        routine.name = name
        routine.description = description
        routine.is_public = is_public
        try:
            self.db.add(routine)
            self.db.commit()
            self.db.refresh(routine)
            return routine
        except Exception as e:
            self.db.rollback()
            raise

    def delete(self, routine: Routine):
        try:
            for re in routine.exercises:
                self.db.delete(re)
            
            for like in routine.likes:
                self.db.delete(like)
            for invite in routine.invites:
                self.db.delete(invite)

            for session in routine.sessions:
                for se in session.exercises:
                    self.db.delete(se)
                self.db.delete(session)

            self.db.delete(routine)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error deleting routine: {e}")
            self.db.rollback()
            raise

    def add_exercise(self, routine_id: int, exercise_id: int, sets: Optional[int],
                     reps: Optional[int], duration_seconds: Optional[int],
                     rest_seconds: Optional[int], notes: Optional[str]) -> RoutineExercise:
        existing = self.db.exec(
            select(RoutineExercise).where(RoutineExercise.routine_id == routine_id)
        ).all()
        position = len(existing)
        re = RoutineExercise(
            routine_id=routine_id,
            exercise_id=exercise_id,
            position=position,
            sets=sets,
            reps=reps,
            duration_seconds=duration_seconds,
            rest_seconds=rest_seconds or 60,
            notes=notes,
        )
        self.db.add(re)
        self.db.commit()
        self.db.refresh(re)
        return re

    def get_routine_exercise(self, routine_exercise_id: int) -> Optional[RoutineExercise]:
        return self.db.get(RoutineExercise, routine_exercise_id)

    def remove_exercise(self, routine_exercise: RoutineExercise):
        try:
            self.db.delete(routine_exercise)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise

    def get_exercises_for_routine(self, routine_id: int) -> list[RoutineExercise]:
        return self.db.exec(
            select(RoutineExercise)
            .where(RoutineExercise.routine_id == routine_id)
            .order_by(RoutineExercise.position)
        ).all()

    def upsert_exercise_ref(self, exercise_data: dict) -> Exercise:
        existing = self.db.exec(
            select(Exercise).where(Exercise.exercise_id == exercise_data["exerciseId"])
        ).one_or_none()
        if not existing:
            existing = Exercise(
                exercise_id=exercise_data["exerciseId"],
                name=exercise_data["name"],
                body_part=exercise_data["bodyParts"][0] if exercise_data.get("bodyParts") else "",
                equipment=exercise_data["equipments"][0] if exercise_data.get("equipments") else "",
                target=exercise_data["targetMuscles"][0] if exercise_data.get("targetMuscles") else "",
                gif_url=exercise_data.get("gifUrl"),
            )
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
        return existing