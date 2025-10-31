from typing import List, Optional
from fastapi import APIRouter, Depends, Request, UploadFile, Form, File, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

from ..schemas import (
    PostData,
    PostCommentData,
    LikePostRequest,
    DislikePostRequest,
    AddCommentRequest,
    LikeCommentRequest,
    DislikeCommentRequest,
    DeleteCommentRequest,
)
from ..services import (
    create_post,
    delete_post,
    dislike_post,
    edit_post,
    get_posts,
    get_friends_posts,
    get_feed_posts,
    get_comments,
    add_comment,
    delete_comment,
    like_post,
    get_reacted_posts,
    like_comment,
    dislike_comment,
)

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status":"ok"}

@router.get("/my_posts", response_model=List[PostData])
async def get_user_posts(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get user's posts with pagination."""
    return await get_posts(request.state.user_email, db, limit, offset)

@router.get("/friend_posts", response_model=List[PostData])
async def friends_posts(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get user's friends posts with pagination"""
    return await get_friends_posts(request.state.user_email, db, limit, offset)

@router.get("/feed", response_model=List[PostData])
async def feed(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """User's posts + friends' posts, sorted by created_at desc."""
    return await get_feed_posts(request.state.user_email, db, limit, offset)


@router.post("/create_post", response_model=PostData, status_code=201)
async def create_user_post(
    request: Request,
    post_text: str = Form(...),
    post_image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    return await create_post(request.state.user_email, post_text, db, post_image)


@router.delete("/delete_post")
async def delete_user_post(
    request: Request,
    post_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    return await delete_post(request.state.user_email, post_id, db)


@router.patch("/edit_post", response_model=PostData)
async def edit_user_post(
    request: Request,
    post_text: Optional[str] = Form(None),
    post_id: int = Form(...),
    remove_image: bool = Form(False),
    post_image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    return await edit_post(
        request.state.user_email, post_text, post_id, remove_image, db, post_image
    )


@router.post("/like_post")
async def like_user_post(
    request: Request,
    post_request: LikePostRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Like a post."""
    return await like_post(request.state.user_email, post_request.post_id, db)


@router.post("/dislike_post")
async def dislike_user_post(
    request: Request,
    post_request: DislikePostRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Dislike a post."""
    return await dislike_post(request.state.user_email, post_request.post_id, db)


@router.get("/get_reacted_posts", response_model=List[PostData])
async def get_user_reacted_posts(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get posts the user has reacted to."""
    return await get_reacted_posts(request.state.user_email, db)


@router.get("/comments", response_model=List[PostCommentData])
async def get_post_comments(
    request: Request,
    post_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get comments for a post with pagination."""
    return await get_comments(request.state.user_email, post_id, db, limit, offset)


@router.post("/add_comment", response_model=PostCommentData, status_code=201)
async def add_post_comment(
    request: Request,
    comment_request: AddCommentRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to a post."""
    return await add_comment(
        comment_request.post_id,
        comment_request.comment_text,
        request.state.user_email,
        db,
    )


@router.delete("/delete_comment")
async def delete_comment_endpoint(
    request: Request,
    comment_request: DeleteCommentRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment."""
    return await delete_comment(
        request.state.user_email, comment_request.comment_id, db
    )


@router.post("/like_comment")
async def like_comment_endpoint(
    request: Request,
    comment_request: LikeCommentRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Like a comment."""
    return await like_comment(request.state.user_email, comment_request.comment_id, db)


@router.post("/dislike_comment")
async def dislike_comment_endpoint(
    request: Request,
    comment_request: DislikeCommentRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Dislike a comment."""
    return await dislike_comment(
        request.state.user_email, comment_request.comment_id, db
    )
