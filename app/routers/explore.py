from fastapi import Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select, desc, func
from typing import Optional
from app.dependencies import SessionDep, AuthDep
from app.models.models import Post, PostReaction, UserMute, Routine
from app.models.user import User
from app.utilities.flash import flash
from . import router, templates, api_router


@router.get("/explore", response_class=HTMLResponse)
async def explore_view(request: Request, user: AuthDep, db: SessionDep):
    routines = db.exec(
        select(Routine)
        .where(Routine.owner_id == user.id)
        .order_by(Routine.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="explore.html",
        context={"user": user, "my_routines": routines},
    )


@router.get("/users/{profile_user_id}/profile", response_class=HTMLResponse)
async def profile_view(request: Request, profile_user_id: int, user: AuthDep, db: SessionDep):
    profile_user = db.get(User, profile_user_id)
    if not profile_user:
        flash(request, "User not found.", "danger")
        return RedirectResponse(url=request.url_for("explore_view"),
                                status_code=status.HTTP_303_SEE_OTHER)
    is_muted = db.exec(
        select(UserMute).where(
            UserMute.muter_id == user.id,
            UserMute.muted_id == profile_user_id,
        )
    ).one_or_none() is not None
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user": user,
            "profile_user": profile_user,
            "is_own": profile_user_id == user.id,
            "is_muted": is_muted,
        },
    )


@api_router.get("/explore/feed")
async def get_feed(user: AuthDep, db: SessionDep, offset: int = 0, limit: int = 20):
    # Get muted user ids
    muted_ids = [
        row for row in db.exec(
            select(UserMute.muted_id).where(UserMute.muter_id == user.id)
        ).all()
    ]

    query = (
        select(Post)
        .join(User, User.id == Post.user_id)
        .where(Post.user_id.notin_(muted_ids))
        .where(
            (User.privacy_level == "public") | (Post.user_id == user.id)
        )
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(limit)
    )
    posts = db.exec(query).all()

    post_ids = [p.id for p in posts]
    reaction_rows = db.exec(
        select(PostReaction.post_id, PostReaction.is_like, func.count())
        .where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id, PostReaction.is_like)
    ).all() if post_ids else []

    counts: dict[int, dict] = {pid: {"likes": 0, "dislikes": 0} for pid in post_ids}
    for pid, is_like, cnt in reaction_rows:
        key = "likes" if is_like else "dislikes"
        counts[pid][key] = cnt

    my_reactions_rows = db.exec(
        select(PostReaction.post_id, PostReaction.is_like)
        .where(PostReaction.user_id == user.id)
        .where(PostReaction.post_id.in_(post_ids))
    ).all() if post_ids else []
    my_reactions: dict[int, bool] = {pid: is_like for pid, is_like in my_reactions_rows}

    result = []
    for p in posts:
        routine_data = None
        if p.routine_id and p.routine:
            routine_data = {
                "id": p.routine.id,
                "name": p.routine.name,
                "description": p.routine.description,
                "is_public": p.routine.is_public,
                "owner_id": p.routine.owner_id,
                "exercise_count": len(p.routine.exercises),
            }
        result.append({
            "id": p.id,
            "content": p.content,
            "created_at": p.created_at.isoformat(),
            "author": {
                "id": p.author.id if p.author else None,
                "username": p.author.username if p.author else "Unknown",
                "privacy_level": p.author.privacy_level if p.author else "public",
            },
            "routine": routine_data,
            "likes": counts.get(p.id, {}).get("likes", 0),
            "dislikes": counts.get(p.id, {}).get("dislikes", 0),
            "my_reaction": my_reactions.get(p.id),   # True=like, False=dislike, None=none
            "is_own": p.user_id == user.id,
        })
    return result


@api_router.post("/explore/post")
async def create_post(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    content: str = Form(),
    routine_id: Optional[int] = Form(default=None),
):
    if not content.strip():
        flash(request, "Post cannot be empty.", "danger")
        return RedirectResponse(url=request.url_for("explore_view"),
                                status_code=status.HTTP_303_SEE_OTHER)
    if routine_id:
        r = db.get(Routine, routine_id)
        if not r or r.owner_id != user.id:
            routine_id = None

    post = Post(user_id=user.id, content=content.strip(), routine_id=routine_id)
    db.add(post)
    db.commit()
    flash(request, "Posted!")
    return RedirectResponse(url=request.url_for("explore_view"),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/explore/post/{post_id}/delete")
async def delete_post(request: Request, post_id: int, user: AuthDep, db: SessionDep):
    post = db.get(Post, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    # cascade handles reactions via sa_relationship_kwargs
    db.delete(post)
    db.commit()
    flash(request, "Post deleted.")
    return RedirectResponse(url=request.url_for("explore_view"),
                            status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/explore/post/{post_id}/react")
async def react_post(
    request: Request,
    post_id: int,
    user: AuthDep,
    db: SessionDep,
):
    body = await request.json()
    is_like: bool = body.get("is_like", True)

    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = db.exec(
        select(PostReaction).where(
            PostReaction.post_id == post_id,
            PostReaction.user_id == user.id,
        )
    ).one_or_none()

    if existing:
        if existing.is_like == is_like:
            db.delete(existing)
            db.commit()
            my_reaction = None
        else:
            existing.is_like = is_like
            db.add(existing)
            db.commit()
            my_reaction = is_like
    else:
        r = PostReaction(post_id=post_id, user_id=user.id, is_like=is_like)
        db.add(r)
        db.commit()
        my_reaction = is_like

    likes = db.exec(
        select(func.count()).select_from(
            select(PostReaction)
            .where(PostReaction.post_id == post_id, PostReaction.is_like == True)
            .subquery()
        )
    ).one()
    dislikes = db.exec(
        select(func.count()).select_from(
            select(PostReaction)
            .where(PostReaction.post_id == post_id, PostReaction.is_like == False)
            .subquery()
        )
    ).one()
    return {"likes": likes, "dislikes": dislikes, "my_reaction": my_reaction}


#Mute
@api_router.post("/explore/mute/{target_id}")
async def toggle_mute(target_id: int, user: AuthDep, db: SessionDep):
    if target_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot mute yourself")
    existing = db.exec(
        select(UserMute).where(
            UserMute.muter_id == user.id, UserMute.muted_id == target_id
        )
    ).one_or_none()
    if existing:
        db.delete(existing)
        db.commit()
        return {"muted": False}
    db.add(UserMute(muter_id=user.id, muted_id=target_id))
    db.commit()
    return {"muted": True}


#Profile data
@api_router.get("/users/{profile_user_id}/profile/data")
async def get_profile_data(profile_user_id: int, user: AuthDep, db: SessionDep):
    profile_user = db.get(User, profile_user_id)
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    is_private = profile_user.privacy_level != "public"
    if is_private and profile_user_id != user.id:
        return {
            "user": {"id": profile_user.id, "username": profile_user.username,
                     "privacy_level": profile_user.privacy_level},
            "private": True,
        }

    is_muted = db.exec(
        select(UserMute).where(
            UserMute.muter_id == user.id, UserMute.muted_id == profile_user_id
        )
    ).one_or_none() is not None

    public_routines = db.exec(
        select(Routine)
        .where(Routine.owner_id == profile_user_id, Routine.is_public == True)
        .order_by(Routine.created_at.desc())
    ).all()

    posts = db.exec(
        select(Post)
        .where(Post.user_id == profile_user_id)
        .order_by(desc(Post.created_at))
        .limit(20)
    ).all()

    post_ids = [p.id for p in posts]
    reaction_rows = db.exec(
        select(PostReaction.post_id, PostReaction.is_like, func.count())
        .where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id, PostReaction.is_like)
    ).all() if post_ids else []
    counts: dict[int, dict] = {pid: {"likes": 0, "dislikes": 0} for pid in post_ids}
    for pid, is_like, cnt in reaction_rows:
        counts[pid]["likes" if is_like else "dislikes"] = cnt

    return {
        "user": {
            "id": profile_user.id,
            "username": profile_user.username,
            "privacy_level": profile_user.privacy_level,
        },
        "private": False,
        "is_muted": is_muted,
        "stats": {
            "public_routines": len(public_routines),
            "total_posts": len(posts),
        },
        "routines": [
            {"id": r.id, "name": r.name, "description": r.description,
             "exercise_count": len(r.exercises)}
            for r in public_routines[:10]
        ],
        "posts": [
            {
                "id": p.id,
                "content": p.content,
                "created_at": p.created_at.isoformat(),
                "likes": counts.get(p.id, {}).get("likes", 0),
                "dislikes": counts.get(p.id, {}).get("dislikes", 0),
                "routine": {"id": p.routine.id, "name": p.routine.name} if p.routine else None,
            }
            for p in posts
        ],
    }


#API: Privacy settings
@api_router.post("/users/privacy")
async def update_privacy(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    privacy_level: str = Form(default="public"),
):
    if privacy_level not in ("public", "private"):
        privacy_level = "public"
    user.privacy_level = privacy_level
    db.add(user)
    db.commit()
    flash(request, "Privacy setting updated!")
    return RedirectResponse(
        url=request.url_for("profile_view", profile_user_id=user.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )