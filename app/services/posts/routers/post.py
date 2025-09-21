from typing import List
from fastapi import APIRouter, Depends, Request, UploadFile, Form, File
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

from ..schemas import PostData
from ..services import (
    create_post,
    delete_post,
    dislike_post,
    edit_post,
    get_posts,
    like_post,
    reacted_post,
)

router = APIRouter()


@router.get("/get_posts", response_model=List[PostData])
async def get_user_posts(request: Request, db: AsyncSession = Depends(get_db)):
    return await get_posts(request.state.user_email, db)


@router.post("/create_post", response_model=PostData)
async def create_user_post(
    request: Request,
    post_text: str = Form(...),
    post_image: UploadFile | None = File(...),
    db: AsyncSession = Depends(get_db),
):
    return await create_post(request.state.user_email, post_text, db, post_image)


@router.delete("/delete_post")
async def delete_user_post(
    request: Request, post_id: int, db: AsyncSession = Depends(get_db)
):
    return await delete_post(request.state.user_email, post_id, db)


@router.patch("/edit_post")
async def edit_user_post(
    request: Request,
    post_text: str | None = Form(None),
    post_id: str = Form(...),
    post_image: UploadFile | None = File(None),
    remove_image: str = Form("false"),
    db: AsyncSession = Depends(get_db),
):
    return await edit_post(
        request.state.user_email, post_text, post_id, remove_image, db, post_image
    )


@router.post("/like_post")
async def like_user_post(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await like_post(request.state.user_email, post_id, db)


@router.post("/dislike_post")
async def dislike_user_post(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await dislike_post(request.state.user_email, post_id, db)


@router.get("/get_reacted_posts")
async def get_user_reacted_posts(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await reacted_post(request.state.user_email, db)
