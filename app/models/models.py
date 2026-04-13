from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password: str
    role: str = ""
    privacy_level: str = Field(default="public")
    weight_kg: Optional[float] = None  # used for calorie calculations

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    routines: list['Routine'] = Relationship(back_populates="owner")
    sessions: list['WorkoutSession'] = Relationship(back_populates="user")
    likes: list['RoutineLike'] = Relationship(back_populates="user")
    custom_exercises: list['CustomExercise'] = Relationship(back_populates="owner")
    posts: list['Post'] = Relationship(back_populates="author")

class Exercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exercise_id: str = Field(index=True, unique=True)
    name: str
    body_part: str
    equipment: str
    target: str
    secondary_muscles: Optional[str] = None  # comma-separated, lowercased
    gif_url: Optional[str] = None

    routine_exercises: list['RoutineExercise'] = Relationship(back_populates="exercise")
    session_exercises: list['SessionExercise'] = Relationship(back_populates="exercise")

class CustomExercise(SQLModel, table=True):
    __tablename__ = "custom_exercise"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    name: str = Field(index=True)
    description: Optional[str] = None
    body_part: str
    equipment: str
    media_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    owner: Optional['User'] = Relationship(back_populates="custom_exercises")
    routine_exercises: list['RoutineExercise'] = Relationship(back_populates="custom_exercise")

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
    posts: list['Post'] = Relationship(back_populates="routine")


class RoutineExercise(SQLModel, table=True):
    __tablename__ = "routineexercise"

    id: Optional[int] = Field(default=None, primary_key=True)
    routine_id: int = Field(foreign_key="routine.id")
    
    is_custom: bool = Field(default=False)
    exercise_id: Optional[int] = Field(default=None, foreign_key="exercise.id")
    custom_exercise_id: Optional[int] = Field(default=None, foreign_key="custom_exercise.id")
    
    position: int = Field(default=0)
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    rest_seconds: Optional[int] = Field(default=60)
    notes: Optional[str] = None

    routine: Optional['Routine'] = Relationship(back_populates="exercises")
    exercise: Optional['Exercise'] = Relationship(back_populates="routine_exercises")
    custom_exercise: Optional['CustomExercise'] = Relationship(back_populates="routine_exercises")


class WorkoutSession(SQLModel, table=True):
    __tablename__ = "workoutsession"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    routine_id: int = Field(foreign_key="routine.id")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    calories_burned: Optional[float] = None  # calculated on session completion
    paired_session_id: Optional[int] = Field(default=None, foreign_key="workoutsession.id")

    user: Optional['User'] = Relationship(back_populates="sessions")
    routine: Optional['Routine'] = Relationship(back_populates="sessions")
    exercises: list['SessionExercise'] = Relationship(back_populates="session")


class SessionExercise(SQLModel, table=True):
    __tablename__ = "sessionexercise"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="workoutsession.id")
    
    is_custom: bool = Field(default=False)
    exercise_id: Optional[int] = Field(default=None, foreign_key="exercise.id")
    custom_exercise_id: Optional[int] = Field(default=None, foreign_key="custom_exercise.id")
    
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

class Post(SQLModel, table=True):
    """Timeline posts for the Explore page"""
    __tablename__ = "post"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    routine_id: Optional[int] = Field(default=None, foreign_key="routine.id", ondelete="SET NULL")
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    author: Optional['User'] = Relationship(back_populates="posts")
    routine: Optional['Routine'] = Relationship(back_populates="posts")
    reactions: list['PostReaction'] = Relationship(back_populates="post", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class PostReaction(SQLModel, table=True):
    """Likes and Dislikes for timeline posts"""
    __tablename__ = "post_reaction"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="post.id", ondelete="CASCADE")
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    is_like: bool  # True = Like, False = Dislike
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    post: Optional['Post'] = Relationship(back_populates="reactions")


class UserMute(SQLModel, table=True):
    """Tracks which users have muted other users"""
    __tablename__ = "user_mute"
    
    muter_id: int = Field(foreign_key="user.id", ondelete="CASCADE", primary_key=True)
    muted_id: int = Field(foreign_key="user.id", ondelete="CASCADE", primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
