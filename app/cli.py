"""
CLI management commands for the Workout Remixer app.

Usage:
    python -m app.cli seed-users
    python -m app.cli create-admin --username admin --email admin@example.com --password secret
"""
import typer
import asyncio
from sqlmodel import select
from app.database import get_cli_session
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService
from app.schemas.user import AdminCreate
from app.utilities.security import encrypt_password
from app.models import User, Exercise
from app.services.exercisedb_service import ExerciseDBService

app = typer.Typer()


@app.command()
def seed_users():
    """Seed the required assessment user (bob) and a default admin."""
    with get_cli_session() as db:
        user_repo = UserRepository(db)
        auth_service = AuthService(user_repo)

        # Required by the project spec: username=bob, password=bobpass
        if not user_repo.get_by_username("bob"):
            auth_service.register_user("bob", "bob@example.com", "bobpass")
            typer.echo("✅  Created user: bob / bobpass")
        else:
            typer.echo("ℹ️   User 'bob' already exists, skipping.")

        # Default admin account
        if not user_repo.get_by_username("admin"):
            admin_data = AdminCreate(
                username="admin",
                email="admin@example.com",
                password=encrypt_password("adminpass"),
                role="admin",
            )
            user_repo.create(admin_data)
            typer.echo("✅  Created admin: admin / adminpass")
        else:
            typer.echo("ℹ️   Admin 'admin' already exists, skipping.")


@app.command()
def create_admin(
    username: str = typer.Option(..., prompt=True),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """Create a new admin user interactively."""
    with get_cli_session() as db:
        user_repo = UserRepository(db)
        if user_repo.get_by_username(username):
            typer.echo(f"❌  Username '{username}' already taken.", err=True)
            raise typer.Exit(1)
        admin_data = AdminCreate(
            username=username,
            email=email,
            password=encrypt_password(password),
            role="admin",
        )
        user_repo.create(admin_data)
        typer.echo(f"✅  Admin '{username}' created successfully.")


@app.command()
def list_users():
    """List all registered users."""
    from tabulate import tabulate
    with get_cli_session() as db:
        user_repo = UserRepository(db)
        users = user_repo.get_all_users()
        if not users:
            typer.echo("No users found.")
            return
        rows = [[u.id, u.username, u.email, u.role] for u in users]
        typer.echo(tabulate(rows, headers=["ID", "Username", "Email", "Role"]))


@app.command("backfill-secondary-muscles")
def backfill_secondary_muscles():
    """Backfill Exercise.secondary_muscles from ExerciseDB in one offline pass."""

    async def _fetch_lookup() -> dict[str, str]:
        service = ExerciseDBService()
        items = await service._fetch_all_exercises()
        lookup: dict[str, str] = {}
        for item in items:
            ex_id = str(item.get("exerciseId") or item.get("id") or "").strip()
            if not ex_id:
                continue
            secondary = ",".join(
                sorted({
                    str(m).strip().lower()
                    for m in (item.get("secondaryMuscles") or [])
                    if str(m).strip()
                })
            )
            lookup[ex_id] = secondary
        return lookup

    typer.echo("Fetching ExerciseDB cache for secondary muscles...")
    lookup = asyncio.run(_fetch_lookup())
    typer.echo(f"Loaded {len(lookup)} ExerciseDB records.")

    with get_cli_session() as db:
        exercises = db.exec(select(Exercise)).all()
        updated = 0
        for ex in exercises:
            secondary = lookup.get(ex.exercise_id, "")
            secondary_value = secondary or None
            if ex.secondary_muscles != secondary_value:
                ex.secondary_muscles = secondary_value
                db.add(ex)
                updated += 1
        db.commit()

    typer.echo(f"Backfill complete. Updated {updated} local exercises.")


if __name__ == "__main__":
    app()