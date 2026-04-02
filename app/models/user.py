from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password: str
    role: str = ""
    privacy_level: str = Field(default="public")

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    routines: list['Routine'] = Relationship(back_populates="owner")
    sessions: list['WorkoutSession'] = Relationship(back_populates="user")
    likes: list['RoutineLike'] = Relationship(back_populates="user")
    custom_exercises: list['CustomExercise'] = Relationship(back_populates="owner")
    posts: list['Post'] = Relationship(back_populates="author")
