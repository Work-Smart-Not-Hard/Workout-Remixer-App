from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from app.models.user import (User, UserBase)

# ---------------------------------------------------------------------------
# Exercise  (local cache of ExerciseDB API data)
# ---------------------------------------------------------------------------

class Exercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exercise_id: str = Field(index=True, unique=True)
    name: str
    body_part: str
    equipment: str
    target: str
    gif_url: Optional[str] = None

    routine_exercises: list['RoutineExercise'] = Relationship(back_populates="exercise")
    session_exercises: list['SessionExercise'] = Relationship(back_populates="exercise")


class Routine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    is_public: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    owner_id: int = Field(foreign_key="user.id")
    remixed_from_id: Optional[int] = Field(default=None, foreign_key="routine.id")

    owner: Optional['User'] = Relationship(back_populates="routines")
    exercises: list['RoutineExercise'] = Relationship(back_populates="routine")
    sessions: list['WorkoutSession'] = Relationship(back_populates="routine")
    likes: list['RoutineLike'] = Relationship(back_populates="routine")
    invites: list['WorkoutInvite'] = Relationship(back_populates="routine")


class RoutineExercise(SQLModel, table=True):
    __tablename__ = "routineexercise"

    id: Optional[int] = Field(default=None, primary_key=True)
    routine_id: int = Field(foreign_key="routine.id")
    exercise_id: int = Field(foreign_key="exercise.id")
    position: int = Field(default=0)
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    rest_seconds: Optional[int] = Field(default=60)
    notes: Optional[str] = None

    routine: Optional['Routine'] = Relationship(back_populates="exercises")
    exercise: Optional['Exercise'] = Relationship(back_populates="routine_exercises")


class WorkoutSession(SQLModel, table=True):
    __tablename__ = "workoutsession"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    routine_id: int = Field(foreign_key="routine.id")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    paired_session_id: Optional[int] = Field(default=None, foreign_key="workoutsession.id")

    user: Optional['User'] = Relationship(back_populates="sessions")
    routine: Optional['Routine'] = Relationship(back_populates="sessions")
    exercises: list['SessionExercise'] = Relationship(back_populates="session")


class SessionExercise(SQLModel, table=True):
    __tablename__ = "sessionexercise"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="workoutsession.id")
    exercise_id: int = Field(foreign_key="exercise.id")
    sets_completed: Optional[int] = None
    reps_completed: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None

    session: Optional['WorkoutSession'] = Relationship(back_populates="exercises")
    exercise: Optional['Exercise'] = Relationship(back_populates="session_exercises")


class RoutineLike(SQLModel, table=True):
    __tablename__ = "routinelike"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    routine_id: int = Field(foreign_key="routine.id")
    liked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: Optional['User'] = Relationship(back_populates="likes")
    routine: Optional['Routine'] = Relationship(back_populates="likes")


class WorkoutInvite(SQLModel, table=True):
    __tablename__ = "workoutinvite"

    id: Optional[int] = Field(default=None, primary_key=True)
    routine_id: int = Field(foreign_key="routine.id")
    inviter_id: int = Field(foreign_key="user.id")
    invitee_id: int = Field(foreign_key="user.id")
    status: str = Field(default="pending")  # pending | accepted | declined
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: Optional[datetime] = None

    routine: Optional['Routine'] = Relationship(back_populates="invites")


class ExerciseFavourite(SQLModel, table=True):
    __tablename__ = "exercisefavourite"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    exercise_id: str = Field(index=True)  # ExerciseDB string ID
    name: str
    gif_url: Optional[str] = None
    body_part: Optional[str] = None
    target: Optional[str] = None
    equipment: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))