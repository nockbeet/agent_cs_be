
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.post_like import PostLike
from app.models.post_tag import PostTag
from app.models.tag import Tag
from app.schemas.user import UserDetailResponse, UserUpdateRequest
from app.schemas.post import PostListResponse
from app.services.s3 import (
    ImageValidationError,
    ImageStorageError,
    upload_image,
    generate_image_url,
    delete_image,
)


router = APIRouter(
    prefix="/users",
    tags=["User"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# -------------------------
# 공통 함수
# -------------------------

def get_active_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    return user


def to_user_response(user: User) -> dict:
    data = UserDetailResponse.model_validate(user).model_dump()

    if user.profile_image_url:
        try:
            data["profile_image_url"] = generate_image_url(
                user.profile_image_url
            )
        except ImageStorageError as exc:
            raise HTTPException(
                status_code=502,
                detail="프로필 이미지 URL 생성에 실패했습니다.",
            ) from exc

    return data


def to_post_response(db: Session, post: Post) -> dict:
    author = db.get(User, post.user_id)

    tags = db.scalars(
        select(Tag)
        .join(PostTag, PostTag.tag_id == Tag.id)
        .where(PostTag.post_id == post.id)
        .order_by(Tag.id)
    ).all()

    try:
        author_image_url = (
            generate_image_url(author.profile_image_url)
            if author and author.profile_image_url
            else None
        )
    except ImageStorageError as exc:
        raise HTTPException(
            status_code=502,
            detail="작성자 프로필 이미지 URL 생성에 실패했습니다.",
        ) from exc

    return {
        "id": post.id,
        "title": post.title,
        "author_id": author.id,
        "author_account_id": author.account_id,
        "author_username": author.username,
        "author_image_url": author_image_url,
        "hashtags": [
            {"id": tag.id, "name": tag.name}
            for tag in tags
        ],
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "view_count": post.view_count,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


# -------------------------
# 내 프로필 조회
# -------------------------

@router.get(
    "/me",
    response_model=UserDetailResponse,
)
def get_my_profile(current_user: CurrentUser):
    return to_user_response(current_user)


# -------------------------
# 내 프로필 수정
# -------------------------

@router.patch(
    "/me",
    response_model=UserDetailResponse,
)
def update_my_profile(
    current_user: CurrentUser,
    db: DbSession,
    username: Annotated[str | None, Form()] = None,
    email: Annotated[str | None, Form()] = None,
    bio: Annotated[str | None, Form()] = None,
    profile_image: Annotated[UploadFile | None, File()] = None,
):
    new_image_key = None
    old_image_key = current_user.profile_image_url

    # -------------------------
    # 1. 프로필 입력값 검증
    # -------------------------

    update_data = {}

    if username is not None:
        if username.lower() == "null":
            raise HTTPException(
                status_code=422,
                detail="닉네임은 null로 변경할 수 없습니다.",
            )

        update_data["username"] = username

    if email is not None:
        if email.lower() == "null":
            raise HTTPException(
                status_code=422,
                detail="이메일은 null로 변경할 수 없습니다.",
            )

        update_data["email"] = email

    if bio is not None:
        # form-data에서 "null" 문자열을 전달하면
        # 자기소개를 삭제하도록 처리
        update_data["bio"] = (
            None if bio == "null" else bio
        )

    try:
        validated_data = UserUpdateRequest.model_validate(
            update_data
        )

    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(
                include_context=False,
                include_input=False,
            ),
        ) from exc

    # -------------------------
    # 2. 이메일 중복 검사
    # -------------------------

    if "email" in update_data:
        existing_user = db.scalar(
            select(User).where(
                User.email == validated_data.email,
                User.id != current_user.id,
            )
        )

        if existing_user is not None:
            raise HTTPException(
                status_code=409,
                detail="이미 사용 중인 이메일입니다.",
            )

    # -------------------------
    # 3. 검증된 프로필 정보 적용
    # -------------------------

    for field_name in validated_data.model_fields_set:
        setattr(
            current_user,
            field_name,
            getattr(validated_data, field_name),
        )

    # -------------------------
    # 4. 프로필 이미지 업로드
    # -------------------------

    if profile_image is not None:
        try:
            new_image_key = upload_image(
                file=profile_image,
                folder="profiles",
                owner_id=current_user.id,
            )

        except ImageValidationError as exc:
            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        except ImageStorageError as exc:
            db.rollback()

            raise HTTPException(
                status_code=502,
                detail="프로필 이미지 업로드에 실패했습니다.",
            ) from exc

        current_user.profile_image_url = new_image_key

    # -------------------------
    # 5. DB 변경 사항 저장
    # -------------------------

    try:
        db.commit()
        db.refresh(current_user)

    except SQLAlchemyError as exc:
        db.rollback()

        # DB 저장에 실패한 경우
        # 새로 업로드한 S3 이미지 삭제
        if new_image_key is not None:
            try:
                delete_image(new_image_key)
            except ImageStorageError:
                pass

        if isinstance(exc, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="중복된 사용자 정보가 존재합니다.",
            ) from exc

        raise HTTPException(
            status_code=500,
            detail="프로필 수정에 실패했습니다.",
        ) from exc

    # -------------------------
    # 6. 이전 프로필 이미지 삭제
    # -------------------------

    if new_image_key is not None and old_image_key:
        try:
            delete_image(old_image_key)

        except ImageStorageError:
            # DB 수정은 이미 완료되었으므로
            # 이전 이미지 삭제 실패로 요청을 실패 처리하지 않음
            # 추후 로깅 및 재시도 처리 필요
            pass

    # -------------------------
    # 7. 수정된 사용자 프로필 반환
    # -------------------------

    return to_user_response(current_user)


# -------------------------
# 특정 사용자 프로필 조회
# -------------------------

@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
)
def get_user_profile(
    user_id: int,
    db: DbSession,
):
    user = get_active_user(db, user_id)
    return to_user_response(user)


# -------------------------
# 특정 사용자 게시글 목록
# -------------------------

@router.get(
    "/{user_id}/posts",
    response_model=list[PostListResponse],
)
def get_user_posts(
    user_id: int,
    db: DbSession,
):
    get_active_user(db, user_id)

    posts = db.scalars(
        select(Post)
        .where(
            Post.user_id == user_id,
            Post.is_deleted.is_(False),
        )
        .order_by(
            Post.created_at.desc(),
            Post.id.desc(),
        )
    ).all()

    return [
        to_post_response(db, post)
        for post in posts
    ]


# -------------------------
# 특정 사용자가 좋아요한 게시글 목록
# -------------------------

@router.get(
    "/{user_id}/likes/posts",
    response_model=list[PostListResponse],
)
def get_user_liked_posts(
    user_id: int,
    db: DbSession,
):
    get_active_user(db, user_id)

    posts = db.scalars(
        select(Post)
        .join(PostLike, PostLike.post_id == Post.id)
        .where(
            PostLike.user_id == user_id,
            Post.is_deleted.is_(False),
        )
        .order_by(
            Post.created_at.desc(),
            Post.id.desc(),
        )
    ).all()

    return [
        to_post_response(db, post)
        for post in posts
    ]
