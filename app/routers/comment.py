
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.schemas.comment import (
    CommentCreateRequest,
    CommentUpdateRequest,
    CommentResponse,
    CommentDeleteResponse,
)
from app.services.s3 import (
    generate_image_url,
    ImageStorageError,
    ImageValidationError,
)


router = APIRouter(
    prefix="/posts/{post_id}/comments",
    tags=["Comment"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# -------------------------
# 공통 검증 및 변환
# -------------------------

def get_active_post(
    db: Session,
    post_id: int,
    *,
    for_update: bool = False,
) -> Post:
    """
    활성 게시글 조회.

    for_update=True:
    게시글 행을 잠가 댓글 작성/수정/삭제와
    다른 트랜잭션의 변경을 조정한다.
    """
    stmt = select(Post).where(
        Post.id == post_id,
        Post.is_deleted.is_(False),
    )

    if for_update:
        stmt = stmt.with_for_update()

    post = db.scalar(stmt)

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="게시글을 찾을 수 없습니다.",
        )

    return post


def get_active_comment(
    db: Session,
    post_id: int,
    comment_id: int,
    *,
    for_update: bool = False,
) -> Comment:
    """
    활성 댓글 조회.

    for_update=True:
    댓글 수정/삭제 또는 대댓글 작성 시
    동일 댓글에 대한 충돌을 방지한다.
    """
    stmt = select(Comment).where(
        Comment.id == comment_id,
        Comment.post_id == post_id,
        Comment.is_deleted.is_(False),
    )

    if for_update:
        stmt = stmt.with_for_update()

    comment = db.scalar(stmt)

    if comment is None:
        raise HTTPException(
            status_code=404,
            detail="댓글을 찾을 수 없습니다.",
        )

    return comment


def check_comment_owner(
    comment: Comment,
    user: User,
) -> None:
    if comment.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="본인의 댓글만 수정하거나 삭제할 수 있습니다.",
        )


def validate_comment_content(content: str) -> None:
    if not content.strip():
        raise HTTPException(
            status_code=422,
            detail="댓글 내용은 공백만 입력할 수 없습니다.",
        )


def to_comment_response(
    comment: Comment,
    author: User,
    replies: list[dict] | None = None,
) -> dict:
    try:
        author_image_url = (
            generate_image_url(author.profile_image_url)
            if author.profile_image_url
            else None
        )
    except (ImageStorageError, ImageValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="작성자 이미지 URL 생성에 실패했습니다.",
        ) from exc

    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "content": (
            None if comment.is_deleted else comment.content
        ),
        "author_id": author.id,
        "author_account_id": author.account_id,
        "author_username": author.username,
        "author_image_url": author_image_url,
        "parent_comment_id": comment.parent_comment_id,
        "replies": replies if replies is not None else [],
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "is_deleted": comment.is_deleted,
    }


def build_comment_tree(comments: list[Comment]) -> list[dict]:
    """
    댓글 목록을 최대 2단계 트리로 변환.
    삭제된 부모 댓글의 기존 대댓글도 유지.
    """
    response_map = {}
    root_comments = []

    for comment in comments:
        response_map[comment.id] = to_comment_response(
            comment=comment,
            author=comment.user,
        )

    for comment in comments:
        response = response_map[comment.id]

        if comment.parent_comment_id is None:
            root_comments.append(response)
        else:
            parent_response = response_map.get(
                comment.parent_comment_id
            )

            if parent_response is not None:
                parent_response["replies"].append(response)

    return root_comments


def change_comment_count(
    db: Session,
    post_id: int,
    amount: int,
) -> None:
    """
    댓글 수를 DB에서 원자적으로 변경한다.

    게시글 행은 호출 측에서 먼저 잠근 상태여야 한다.
    """
    result = db.execute(
        update(Post)
        .where(
            Post.id == post_id,
            Post.is_deleted.is_(False),
        )
        .values(
            comment_count=Post.comment_count + amount
        )
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        raise HTTPException(
            status_code=404,
            detail="게시글을 찾을 수 없습니다.",
        )


# -------------------------
# GET /posts/{post_id}/comments
# 댓글 목록 조회
# -------------------------

@router.get(
    "",
    response_model=list[CommentResponse],
)
def get_comments(
    post_id: int,
    db: DbSession,
):
    # 단순 조회에는 잠금이 필요하지 않음
    get_active_post(db, post_id)

    comments = db.scalars(
        select(Comment)
        .options(joinedload(Comment.user))
        .where(Comment.post_id == post_id)
        .order_by(
            Comment.created_at.asc(),
            Comment.id.asc(),
        )
    ).all()

    return build_comment_tree(comments)


# -------------------------
# POST /posts/{post_id}/comments
# 댓글 작성
# -------------------------

@router.post(
    "",
    response_model=CommentResponse,
    status_code=201,
)
def create_comment(
    post_id: int,
    data: CommentCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    validate_comment_content(data.content)

    try:
        # 게시글 행 잠금
        get_active_post(
            db,
            post_id,
            for_update=True,
        )

        comment = Comment(
            post_id=post_id,
            user_id=current_user.id,
            parent_comment_id=None,
            content=data.content,
        )

        db.add(comment)
        db.flush()

        change_comment_count(
            db=db,
            post_id=post_id,
            amount=1,
        )

        db.commit()
        db.refresh(comment)

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="댓글 작성에 실패했습니다.",
        ) from exc

    return to_comment_response(
        comment=comment,
        author=current_user,
    )


# -------------------------
# PATCH /posts/{post_id}/comments/{comment_id}
# 댓글 수정
# -------------------------

@router.patch(
    "/{comment_id}",
    response_model=CommentResponse,
)
def update_comment(
    post_id: int,
    comment_id: int,
    data: CommentUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    if data.content is None:
        raise HTTPException(
            status_code=422,
            detail="수정할 댓글 내용을 입력해야 합니다.",
        )

    validate_comment_content(data.content)

    try:
        # 1. 게시글 행 잠금
        get_active_post(
            db,
            post_id,
            for_update=True,
        )

        # 2. 댓글 행 잠금
        comment = get_active_comment(
            db=db,
            post_id=post_id,
            comment_id=comment_id,
            for_update=True,
        )

        check_comment_owner(comment, current_user)

        # 3. 수정 후 커밋
        comment.content = data.content

        db.commit()
        db.refresh(comment)

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="댓글 수정에 실패했습니다.",
        ) from exc

    return to_comment_response(
        comment=comment,
        author=current_user,
    )


# -------------------------
# DELETE /posts/{post_id}/comments/{comment_id}
# 댓글 삭제 (Soft Delete)
# -------------------------

@router.delete(
    "/{comment_id}",
    response_model=CommentDeleteResponse,
)
def delete_comment(
    post_id: int,
    comment_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    try:
        # 1. 게시글 행 잠금
        get_active_post(
            db,
            post_id,
            for_update=True,
        )

        # 2. 댓글 행 잠금
        comment = get_active_comment(
            db=db,
            post_id=post_id,
            comment_id=comment_id,
            for_update=True,
        )

        check_comment_owner(comment, current_user)

        # 3. 삭제되지 않은 댓글만 변경
        result = db.execute(
            update(Comment)
            .where(
                Comment.id == comment_id,
                Comment.post_id == post_id,
                Comment.is_deleted.is_(False),
            )
            .values(is_deleted=True)
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail="댓글을 찾을 수 없습니다.",
            )

        # 4. 실제 삭제에 성공한 경우만 댓글 수 감소
        change_comment_count(
            db=db,
            post_id=post_id,
            amount=-1,
        )

        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="댓글 삭제에 실패했습니다.",
        ) from exc

    return {
        "message": "댓글이 삭제되었습니다.",
    }


# -------------------------
# POST /posts/{post_id}/comments/{comment_id}/replies
# 대댓글 작성
# -------------------------

@router.post(
    "/{comment_id}/replies",
    response_model=CommentResponse,
    status_code=201,
)
def create_reply(
    post_id: int,
    comment_id: int,
    data: CommentCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    validate_comment_content(data.content)

    try:
        # 1. 게시글 행 잠금
        get_active_post(
            db,
            post_id,
            for_update=True,
        )

        # 2. 부모 댓글 행 잠금
        parent_comment = get_active_comment(
            db=db,
            post_id=post_id,
            comment_id=comment_id,
            for_update=True,
        )

        # 최대 2단계까지만 허용
        if parent_comment.parent_comment_id is not None:
            raise HTTPException(
                status_code=400,
                detail="대댓글에는 답글을 작성할 수 없습니다.",
            )

        # 삭제된 부모 댓글은 get_active_comment에서 차단됨
        reply = Comment(
            post_id=post_id,
            user_id=current_user.id,
            parent_comment_id=parent_comment.id,
            content=data.content,
        )

        db.add(reply)
        db.flush()

        change_comment_count(
            db=db,
            post_id=post_id,
            amount=1,
        )

        db.commit()
        db.refresh(reply)

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="대댓글 작성에 실패했습니다.",
        ) from exc

    return to_comment_response(
        comment=reply,
        author=current_user,
    )
