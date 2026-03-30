from sqlmodel import Session, select
from app.models import WorkoutSession, SessionExercise
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: int, routine_id: int) -> WorkoutSession:
        session = WorkoutSession(
            user_id=user_id,
            routine_id=routine_id,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_id(self, session_id: int) -> Optional[WorkoutSession]:
        return self.db.get(WorkoutSession, session_id)

    def get_by_user(self, user_id: int) -> list[WorkoutSession]:
        return self.db.exec(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
            .order_by(WorkoutSession.started_at.desc())
        ).all()

    def get_by_user_and_routine(self, user_id: int, routine_id: int) -> list[WorkoutSession]:
        return self.db.exec(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
            .where(WorkoutSession.routine_id == routine_id)
            .order_by(WorkoutSession.started_at.desc())
        ).all()

    def complete_session(self, session: WorkoutSession, notes: Optional[str]) -> WorkoutSession:
        session.completed_at = datetime.now(timezone.utc)
        delta = session.completed_at - session.started_at.replace(tzinfo=timezone.utc) \
            if session.started_at.tzinfo is None \
            else session.completed_at - session.started_at
        session.duration_minutes = max(1, int(delta.total_seconds() / 60))
        session.notes = notes
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def log_exercise(self, session_id: int, exercise_id: int,
                     sets_completed: Optional[int], reps_completed: Optional[int],
                     weight_kg: Optional[float], duration_seconds: Optional[int],
                     notes: Optional[str]) -> SessionExercise:
        se = SessionExercise(
            session_id=session_id,
            exercise_id=exercise_id,
            sets_completed=sets_completed,
            reps_completed=reps_completed,
            weight_kg=weight_kg,
            duration_seconds=duration_seconds,
            notes=notes,
        )
        self.db.add(se)
        self.db.commit()
        self.db.refresh(se)
        return se

    def get_session_exercises(self, session_id: int) -> list[SessionExercise]:
        return self.db.exec(
            select(SessionExercise).where(SessionExercise.session_id == session_id)
        ).all()

    def get_sessions_for_exercise(self, user_id: int, exercise_id: int) -> list[SessionExercise]:
        """All logged sets for a specific exercise by this user, across all sessions."""
        return self.db.exec(
            select(SessionExercise)
            .join(WorkoutSession, WorkoutSession.id == SessionExercise.session_id)
            .where(WorkoutSession.user_id == user_id)
            .where(SessionExercise.exercise_id == exercise_id)
            .order_by(WorkoutSession.started_at.desc())
        ).all()