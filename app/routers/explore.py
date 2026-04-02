from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from .. import models
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/explore", tags=["Explore"])

@router.get("/feed")
def get_timeline_feed(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    mute_statement = select(models.UserMute.muted_id).where(models.UserMute.muter_id == current_user.id)
    muted_user_ids = db.exec(mute_statement).all()

    post_statement = (
        select(models.Post, models.User)
        .join(models.User)
        .where(models.User.privacy_level == "public")
        .where(models.Post.user_id.notin_(muted_user_ids))
        .order_by(desc(models.Post.created_at))
        .limit(50)
    )
    
    results = db.exec(post_statement).all()

    feed = []
    for post, author in results:
        likes = sum(1 for r in post.reactions if r.is_like)
        dislikes = sum(1 for r in post.reactions if not r.is_like)
        feed.append({
            "post": post,
            "likes": likes,
            "dislikes": dislikes,
            "author_username": author.username
        })
    return feed

@router.post("/post")
def create_post(
    content: str, 
    routine_id: int = None, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    if routine_id:
        routine_statement = select(models.Routine).where(
            models.Routine.id == routine_id, 
            models.Routine.owner_id == current_user.id
        )
        routine = db.exec(routine_statement).first()
        if not routine or not routine.is_public:
            raise HTTPException(status_code=400, detail="Invalid or private routine")

    new_post = models.Post(content=content, routine_id=routine_id, user_id=current_user.id)
    db.add(new_post)
    db.commit()
    return {"message": "Posted to timeline!"}

@router.post("/{post_id}/react")
def react_to_post(
    post_id: int, 
    is_like: bool, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    statement = select(models.PostReaction).where(
        models.PostReaction.post_id == post_id,
        models.PostReaction.user_id == current_user.id
    )
    reaction = db.exec(statement).first()

    if reaction:
        reaction.is_like = is_like
        db.add(reaction)
    else:
        new_reaction = models.PostReaction(post_id=post_id, user_id=current_user.id, is_like=is_like)
        db.add(new_reaction)
    
    db.commit()
    return {"message": "Reaction updated"}

@router.post("/mute/{user_id}")
def mute_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot mute yourself")
        
    statement = select(models.UserMute).where(
        models.UserMute.muter_id == current_user.id, 
        models.UserMute.muted_id == user_id
    )
    mute = db.exec(statement).first()
    
    if not mute:
        new_mute = models.UserMute(muter_id=current_user.id, muted_id=user_id)
        db.add(new_mute)
        db.commit()
        return {"message": "User muted"}
    return {"message": "User is already muted"}