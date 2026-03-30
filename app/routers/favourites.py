from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlmodel import select
from app.dependencies import SessionDep, AuthDep
from app.models import ExerciseFavourite
from . import router, templates, api_router


# ── View ──────────────────────────────────────────────────────────────────────

@router.get("/favourites", response_class=HTMLResponse)
async def favourites_view(request: Request, user: AuthDep, db: SessionDep):
    favs = db.exec(
        select(ExerciseFavourite)
        .where(ExerciseFavourite.user_id == user.id)
        .order_by(ExerciseFavourite.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="favourites.html",
        context={"user": user, "favourites": favs},
    )


# ── API ───────────────────────────────────────────────────────────────────────

@api_router.get("/favourites")
async def list_favourites(user: AuthDep, db: SessionDep):
    """Returns list of favourited exercise_ids for the current user."""
    favs = db.exec(
        select(ExerciseFavourite).where(ExerciseFavourite.user_id == user.id)
    ).all()
    return [{"exercise_id": f.exercise_id, "name": f.name, "gif_url": f.gif_url,
             "body_part": f.body_part, "target": f.target, "equipment": f.equipment} for f in favs]


@api_router.post("/favourites/toggle")
async def toggle_favourite(request: Request, user: AuthDep, db: SessionDep):
    """Toggle favourite on/off. Accepts JSON body with exercise data."""
    body = await request.json()
    exercise_id = body.get("exerciseId")

    existing = db.exec(
        select(ExerciseFavourite)
        .where(ExerciseFavourite.user_id == user.id)
        .where(ExerciseFavourite.exercise_id == exercise_id)
    ).one_or_none()

    if existing:
        db.delete(existing)
        db.commit()
        return {"favourited": False}
    else:
        fav = ExerciseFavourite(
            user_id=user.id,
            exercise_id=exercise_id,
            name=body.get("name", ""),
            gif_url=body.get("gifUrl"),
            body_part=body.get("bodyParts", [""])[0] if body.get("bodyParts") else None,
            target=body.get("targetMuscles", [""])[0] if body.get("targetMuscles") else None,
            equipment=body.get("equipments", [""])[0] if body.get("equipments") else None,
        )
        db.add(fav)
        db.commit()
        return {"favourited": True}