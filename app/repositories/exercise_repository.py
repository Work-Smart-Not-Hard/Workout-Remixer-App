from sqlmodel import Session, select
from app.models import Exercise
from typing import Optional


class ExerciseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_exercise_id(self, exercise_id: str) -> Optional[Exercise]:
        return self.db.exec(select(Exercise).where(Exercise.exercise_id == exercise_id)).one_or_none()

    def upsert(self, exercise_data: dict) -> Exercise:
        """Insert or update a local Exercise record from ExerciseDB API data."""
        secondary = ",".join(
            sorted({
                str(m).strip().lower()
                for m in (exercise_data.get("secondaryMuscles") or [])
                if str(m).strip()
            })
        ) or None

        exercise = self.get_by_exercise_id(exercise_data["exerciseId"])
        if not exercise:
            exercise = Exercise(
                exercise_id=exercise_data["exerciseId"],
                name=exercise_data["name"],
                body_part=exercise_data["bodyParts"][0] if exercise_data.get("bodyParts") else "",
                equipment=exercise_data["equipments"][0] if exercise_data.get("equipments") else "",
                target=exercise_data["targetMuscles"][0] if exercise_data.get("targetMuscles") else "",
                secondary_muscles=secondary,
                gif_url=exercise_data.get("gifUrl"),
            )
            self.db.add(exercise)
            self.db.commit()
            self.db.refresh(exercise)
        else:
            changed = False
            if secondary and exercise.secondary_muscles != secondary:
                exercise.secondary_muscles = secondary
                changed = True
            if changed:
                self.db.add(exercise)
                self.db.commit()
                self.db.refresh(exercise)
        return exercise

    def get_by_id(self, id: int) -> Optional[Exercise]:
        return self.db.get(Exercise, id)