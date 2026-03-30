from app.repositories.routine import RoutineRepository
from app.models import Routine, RoutineExercise
from typing import Optional
from fastapi import HTTPException, status


class RoutineService:
    def __init__(self, repo: RoutineRepository):
        self.repo = repo

    def create_routine(self, name: str, description: Optional[str], owner_id: int) -> Routine:
        return self.repo.create(name=name, description=description, owner_id=owner_id)

    def get_user_routines(self, owner_id: int) -> list[Routine]:
        return self.repo.get_by_owner(owner_id)

    def get_public_routines(self, exclude_user_id: Optional[int] = None) -> list[Routine]:
        return self.repo.get_public(exclude_user_id=exclude_user_id)

    def get_routine_or_404(self, routine_id: int) -> Routine:
        routine = self.repo.get_by_id(routine_id)
        if not routine:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
        return routine

    def assert_owner(self, routine: Routine, user_id: int):
        if routine.owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your routine")

    def update_routine(self, routine_id: int, user_id: int, name: str,
                       description: Optional[str], is_public: bool) -> Routine:
        routine = self.get_routine_or_404(routine_id)
        self.assert_owner(routine, user_id)
        return self.repo.update(routine, name=name, description=description, is_public=is_public)

    def delete_routine(self, routine_id: int, user_id: int):
        routine = self.get_routine_or_404(routine_id)
        self.assert_owner(routine, user_id)
        self.repo.delete(routine)

    def remix_routine(self, routine_id: int, user_id: int) -> Routine:
        """Copy a public routine and all its exercises into a new routine owned by user_id."""
        source = self.get_routine_or_404(routine_id)
        if not source.is_public and source.owner_id != user_id:
            raise HTTPException(status_code=403, detail="This routine is private")

        # Create new routine referencing the source
        new_routine = self.repo.create(
            name=f"{source.name} (remix)",
            description=source.description,
            owner_id=user_id,
        )
        # Set remixed_from_id
        new_routine.remixed_from_id = source.id
        self.repo.db.add(new_routine)
        self.repo.db.commit()
        self.repo.db.refresh(new_routine)

        # Copy all exercises
        source_exercises = self.repo.get_exercises_for_routine(routine_id)
        for re in source_exercises:
            self.repo.add_exercise(
                routine_id=new_routine.id,
                exercise_id=re.exercise_id,
                sets=re.sets,
                reps=re.reps,
                duration_seconds=re.duration_seconds,
                rest_seconds=re.rest_seconds,
                notes=re.notes,
            )

        return new_routine

    def add_exercise_to_routine(self, routine_id: int, user_id: int, exercise_data: dict,
                                sets: Optional[int], reps: Optional[int],
                                duration_seconds: Optional[int], rest_seconds: Optional[int],
                                notes: Optional[str]) -> RoutineExercise:
        routine = self.get_routine_or_404(routine_id)
        self.assert_owner(routine, user_id)
        exercise = self.repo.upsert_exercise_ref(exercise_data)
        return self.repo.add_exercise(
            routine_id=routine_id,
            exercise_id=exercise.id,
            sets=sets,
            reps=reps,
            duration_seconds=duration_seconds,
            rest_seconds=rest_seconds,
            notes=notes,
        )

    def remove_exercise_from_routine(self, routine_exercise_id: int, user_id: int):
        re = self.repo.get_routine_exercise(routine_exercise_id)
        if not re:
            raise HTTPException(status_code=404, detail="Exercise not found in routine")
        routine = self.get_routine_or_404(re.routine_id)
        self.assert_owner(routine, user_id)
        self.repo.remove_exercise(re)

    def get_routine_with_exercises(self, routine_id: int, user_id: int) -> tuple[Routine, list]:
        routine = self.get_routine_or_404(routine_id)
        if routine.owner_id != user_id and not routine.is_public:
            raise HTTPException(status_code=403, detail="This routine is private")
        exercises = self.repo.get_exercises_for_routine(routine_id)
        return routine, exercises