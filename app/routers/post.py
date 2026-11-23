
import json
import re
from typing import Annotated
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.post_like import PostLike
from app.models.tag import Tag
from app.models.post_tag import PostTag
from app.schemas.post import (
    PostCreateRequest,
    PostUpdateRequest,
    PostListResponse,
    PostDetailResponse,
    PostLikeResponse,
)
from app.services.s3 import (
    ImageValidationError,
    ImageStorageError,
    upload_image,
    generate_image_url,
    delete_image,
)


router = APIRouter(prefix="/posts", tags=["Post"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]

UPLOAD_PATTERN = re.compile(r"upload://([^\s)]+)")
IMAGE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
INTERNAL_IMAGE_PATTERN = re.compile(r"s3://posts/[^\s)]+")
HTTP_IMAGE_PATTERN = re.compile(r"https?://[^\s)]+")
MAX_IMAGES = 10


# -------------------------
# 공통 검증 및 변환
# -------------------------

def validate_schema(schema_class, data):
    try:
        return schema_class.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(
                include_context=False,
                include_input=False,
            ),
        ) from exc


def parse_form_list(values, field_name, integer=False):
    """
    반복 form-data 키 또는 JSON 배열 문자열 지원.
    None: 미전달
    ["[]"]: 명시적인 빈 목록
    """
    if values is None:
        return None

    if len(values) == 1 and values[0].strip().startswith("["):
        try:
            parsed = json.loads(values[0])
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"{field_name}의 JSON 형식이 올바르지 않습니다.",
            ) from exc
    else:
        parsed = values

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}은 배열이어야 합니다.",
        )

    if integer:
        try:
            if any(isinstance(v, bool) for v in parsed):
                raise ValueError()
            return [int(v) for v in parsed]
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"{field_name}에는 정수 ID만 사용할 수 있습니다.",
            ) from exc

    if any(not isinstance(v, str) for v in parsed):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}에는 문자열만 사용할 수 있습니다.",
        )

    return parsed


def normalize_hashtags(hashtags):
    result = []
    seen = set()

    for hashtag in hashtags:
        name = hashtag.strip().lower()

        if not name or len(name) > 50:
            raise HTTPException(
                status_code=422,
                detail="해시태그는 공백이 아닌 1~50자여야 합니다.",
            )

        if name not in seen:
            seen.add(name)
            result.append(name)

    return result


def validate_images(content, images, image_ids):
    if len(images) > MAX_IMAGES:
        raise HTTPException(
            status_code=422,
            detail=f"이미지는 최대 {MAX_IMAGES}장까지 첨부할 수 있습니다.",
        )

    if len(images) != len(image_ids):
        raise HTTPException(
            status_code=422,
            detail="images와 image_ids의 개수가 일치해야 합니다.",
        )

    if len(image_ids) != len(set(image_ids)):
        raise HTTPException(
            status_code=422,
            detail="image_ids는 중복될 수 없습니다.",
        )

    if any(not IMAGE_ID_PATTERN.fullmatch(v) for v in image_ids):
        raise HTTPException(
            status_code=422,
            detail="올바르지 않은 image_id 형식입니다.",
        )

    references = set(UPLOAD_PATTERN.findall(content))

    if references != set(image_ids):
        raise HTTPException(
            status_code=422,
            detail="본문의 upload:// 참조와 image_ids가 일치하지 않습니다.",
        )

    remaining = UPLOAD_PATTERN.sub("", content)
    if "upload://" in remaining:
        raise HTTPException(
            status_code=422,
            detail="올바르지 않은 임시 이미지 참조입니다.",
        )


def cleanup_images(keys):
    for key in keys:
        try:
            delete_image(key)
        except (ImageStorageError, ImageValidationError):
            # 추후 로깅 및 재시도 처리
            pass


def get_active_post(
    db: Session,
    post_id: int,
    *,
    for_update: bool = False,
) -> Post:
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


def check_post_owner(post, user):
    if post.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="본인의 게시글만 수정하거나 삭제할 수 있습니다.",
        )


def get_post_tags(db, post_id):
    return db.scalars(
        select(Tag)
        .join(PostTag, PostTag.tag_id == Tag.id)
        .where(PostTag.post_id == post_id)
        .order_by(Tag.id)
    ).all()


def get_post_images(db, post_id):
    return db.scalars(
        select(PostImage)
        .where(PostImage.post_id == post_id)
        .order_by(PostImage.id)
    ).all()


def replace_uploaded_references(content, key_map):
    return UPLOAD_PATTERN.sub(
        lambda match: f"s3://{key_map[match.group(1)]}",
        content,
    )


def normalize_existing_references(content, allowed_keys):
    """
    기존 이미지의 Presigned URL을 영구 내부 참조로 복원.
    다른 S3 객체나 외부 URL은 변경하지 않음.
    """
    def replace_url(match):
        url = match.group(0)
        parsed = urlsplit(url)
        key = unquote(parsed.path.lstrip("/"))

        if key in allowed_keys:
            return f"s3://{key}"

        return url

    return HTTP_IMAGE_PATTERN.sub(replace_url, content)


def validate_existing_references(content, allowed_keys):
    for reference in INTERNAL_IMAGE_PATTERN.findall(content):
        key = reference.removeprefix("s3://")
        if key not in allowed_keys:
            raise HTTPException(
                status_code=422,
                detail="게시글에 속하지 않는 S3 이미지 참조입니다.",
            )

    if "s3://" in INTERNAL_IMAGE_PATTERN.sub("", content):
        raise HTTPException(
            status_code=422,
            detail="허용되지 않은 내부 이미지 참조입니다.",
        )


def replace_tags(db, post_id, tag_names):
    db.execute(
        delete(PostTag).where(PostTag.post_id == post_id)
    )

    for name in tag_names:
        tag = db.scalar(
            select(Tag).where(func.lower(Tag.name) == name)
        )

        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()

        db.add(PostTag(post_id=post_id, tag_id=tag.id))


def to_post_response(db, post, detail=False):
    author = db.get(User, post.user_id)
    tags = get_post_tags(db, post.id)

    if author is None:
        raise HTTPException(
            status_code=500,
            detail="게시글 작성자 정보를 찾을 수 없습니다.",
        )

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

    result = {
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

    if not detail:
        return result

    images = get_post_images(db, post.id)

    try:
        url_map = {
            image.image_url: generate_image_url(image.image_url)
            for image in images
        }
    except (ImageStorageError, ImageValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="게시글 이미지 URL 생성에 실패했습니다.",
        ) from exc

    content = post.content
    for key, url in url_map.items():
        content = content.replace(f"s3://{key}", url)

    result.update({
        "content": content,
        "images": [
            {
                "id": image.id,
                "image_url": url_map[image.image_url],
            }
            for image in images
        ],
        "is_deleted": post.is_deleted,
    })

    return result


# -------------------------
# GET /posts
# 게시글 목록
# -------------------------

@router.get("", response_model=list[PostListResponse])
def get_posts(
    db: DbSession,
    title: str | None = None,
    tag: str | None = None,
    sort: str = Query(default="created_at", pattern="^(created_at|view_count)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Post).where(Post.is_deleted.is_(False))

    if title:
        stmt = stmt.where(Post.title.ilike(f"%{title}%"))

    if tag:
        normalized_tag = tag.strip().lower()
        stmt = stmt.where(
            Post.id.in_(
                select(PostTag.post_id)
                .join(Tag, Tag.id == PostTag.tag_id)
                .where(func.lower(Tag.name) == normalized_tag)
            )
        )

    if sort == "view_count":
        stmt = stmt.order_by(
            Post.view_count.desc(),
            Post.created_at.desc(),
            Post.id.desc(),
        )
    else:
        stmt = stmt.order_by(
            Post.created_at.desc(),
            Post.id.desc(),
        )

    posts = db.scalars(
        stmt.limit(limit).offset(offset)
    ).all()

    return [to_post_response(db, post) for post in posts]


# -------------------------
# POST /posts
# 게시글 작성
# -------------------------

@router.post(
    "",
    response_model=PostDetailResponse,
    status_code=201,
)
def create_post(
    current_user: CurrentUser,
    db: DbSession,
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    images: Annotated[list[UploadFile] | None, File()] = None,
    image_ids: Annotated[list[str] | None, Form()] = None,
    hashtags: Annotated[list[str] | None, Form()] = None,
):
    images = images or []
    image_ids = parse_form_list(image_ids, "image_ids") or []
    hashtags = parse_form_list(hashtags, "hashtags") or []

    data = validate_schema(
        PostCreateRequest,
        {
            "title": title,
            "content": content,
            "image_ids": image_ids,
            "hashtags": hashtags,
        },
    )

    if not data.title.strip() or not data.content.strip():
        raise HTTPException(
            status_code=422,
            detail="제목과 본문은 공백만 입력할 수 없습니다.",
        )

    validate_images(data.content, images, image_ids)

    if "s3://" in data.content:
        raise HTTPException(
            status_code=422,
            detail="새 게시글에서 내부 S3 참조를 사용할 수 없습니다.",
        )

    tag_names = normalize_hashtags(data.hashtags)
    uploaded_keys = []

    try:
        post = Post(
            user_id=current_user.id,
            title=data.title,
            content=data.content,
        )
        db.add(post)
        db.flush()

        key_map = {}

        for image_id, image_file in zip(image_ids, images):
            key = upload_image(
                file=image_file,
                folder="posts",
                owner_id=post.id,
            )
            uploaded_keys.append(key)
            key_map[image_id] = key

            db.add(PostImage(post_id=post.id, image_url=key))

        post.content = replace_uploaded_references(
            data.content, key_map
        )

        replace_tags(db, post.id, tag_names)

        db.commit()
        db.refresh(post)

    except ImageValidationError as exc:
        db.rollback()
        cleanup_images(uploaded_keys)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except ImageStorageError as exc:
        db.rollback()
        cleanup_images(uploaded_keys)
        raise HTTPException(
            status_code=502,
            detail="이미지 업로드에 실패했습니다.",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        cleanup_images(uploaded_keys)
        if isinstance(exc, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="데이터 저장 중 충돌이 발생했습니다.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="게시글 저장에 실패했습니다.",
        ) from exc

    return to_post_response(db, post, detail=True)


# -------------------------
# GET /posts/{post_id}
# 게시글 상세 조회
# -------------------------

@router.get("/{post_id}", response_model=PostDetailResponse)
def get_post(post_id: int, db: DbSession):
    get_active_post(db, post_id)

    try:
        db.execute(
            update(Post)
            .where(Post.id == post_id, Post.is_deleted.is_(False))
            .values(view_count=Post.view_count + 1)
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="게시글 조회수 갱신에 실패했습니다.",
        ) from exc

    post = get_active_post(db, post_id)
    return to_post_response(db, post, detail=True)


# -------------------------
# PATCH /posts/{post_id}
# 게시글 수정
# -------------------------

@router.patch("/{post_id}", response_model=PostDetailResponse)
def update_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
    title: Annotated[str | None, Form()] = None,
    content: Annotated[str | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    image_ids: Annotated[list[str] | None, Form()] = None,
    keep_image_ids: Annotated[list[str] | None, Form()] = None,
    hashtags: Annotated[list[str] | None, Form()] = None,
):
    post = get_active_post(db, post_id, for_update=True)
    check_post_owner(post, current_user)

    images = images or []
    image_ids = parse_form_list(image_ids, "image_ids") or []
    keep_ids = parse_form_list(
        keep_image_ids, "keep_image_ids", integer=True
    )
    tag_values = parse_form_list(hashtags, "hashtags")

    update_data = {
        "image_ids": image_ids,
    }

    if title is not None:
        update_data["title"] = title
    if content is not None:
        update_data["content"] = content
    if keep_ids is not None:
        update_data["keep_image_ids"] = keep_ids
    if tag_values is not None:
        update_data["hashtags"] = tag_values

    data = validate_schema(PostUpdateRequest, update_data)

    if title is not None and not title.strip():
        raise HTTPException(
            status_code=422,
            detail="제목은 공백만 입력할 수 없습니다.",
        )

    if content is not None and not content.strip():
        raise HTTPException(
            status_code=422,
            detail="본문은 공백만 입력할 수 없습니다.",
        )

    if images and content is None:
        raise HTTPException(
            status_code=422,
            detail="새 이미지를 추가하려면 content도 전달해야 합니다.",
        )

    effective_content = content if content is not None else post.content
    validate_images(effective_content, images, image_ids)

    existing_images = get_post_images(db, post_id)
    existing_by_id = {image.id: image for image in existing_images}

    if keep_ids is None:
        keep_ids = list(existing_by_id)

    if len(keep_ids) != len(set(keep_ids)):
        raise HTTPException(
            status_code=422,
            detail="keep_image_ids는 중복될 수 없습니다.",
        )

    if any(image_id not in existing_by_id for image_id in keep_ids):
        raise HTTPException(
            status_code=422,
            detail="게시글에 속하지 않는 이미지 ID입니다.",
        )

    allowed_keys = {
        existing_by_id[image_id].image_url
        for image_id in keep_ids
    }

    if content is not None:
        effective_content = normalize_existing_references(
            effective_content, allowed_keys
        )

    validate_existing_references(effective_content, allowed_keys)

    # 본문이 유지되는데 기존 참조 이미지를 제거할 수는 없음
    referenced_keys = {
        ref.removeprefix("s3://")
        for ref in INTERNAL_IMAGE_PATTERN.findall(effective_content)
    }

    if not referenced_keys.issubset(allowed_keys):
        raise HTTPException(
            status_code=422,
            detail="본문에서 참조하는 기존 이미지는 유지해야 합니다.",
        )

    tag_names = (
        normalize_hashtags(data.hashtags)
        if tag_values is not None
        else None
    )

    uploaded_keys = []

    try:
        if title is not None:
            post.title = data.title

        key_map = {}
        for image_id, image_file in zip(image_ids, images):
            key = upload_image(
                file=image_file,
                folder="posts",
                owner_id=post.id,
            )
            uploaded_keys.append(key)
            key_map[image_id] = key
            db.add(PostImage(post_id=post.id, image_url=key))

        if content is not None:
            post.content = replace_uploaded_references(
                effective_content, key_map
            )

        for image in existing_images:
            if image.id not in keep_ids:
                db.delete(image)

        if tag_names is not None:
            replace_tags(db, post.id, tag_names)

        db.commit()
        db.refresh(post)

    except ImageValidationError as exc:
        db.rollback()
        cleanup_images(uploaded_keys)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except ImageStorageError as exc:
        db.rollback()
        cleanup_images(uploaded_keys)
        raise HTTPException(
            status_code=502,
            detail="이미지 업로드에 실패했습니다.",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        cleanup_images(uploaded_keys)
        if isinstance(exc, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="게시글 수정 중 데이터 충돌이 발생했습니다.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="게시글 수정에 실패했습니다.",
        ) from exc

    # 제거된 이미지의 S3 객체는 즉시 삭제하지 않음
    return to_post_response(db, post, detail=True)


# -------------------------
# DELETE /posts/{post_id}
# 게시글 삭제 (Soft Delete)
# -------------------------

@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    try:
        post = get_active_post(
            db=db,
            post_id=post_id,
            for_update=True,
        )

        check_post_owner(post, current_user)

        post.is_deleted = True

        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="게시글 삭제에 실패했습니다.",
        ) from exc

    return {"detail": "게시글이 삭제되었습니다."}


# -------------------------
# POST /posts/{post_id}/likes
# 좋아요 등록
# -------------------------

@router.post(
    "/{post_id}/likes",
    response_model=PostLikeResponse,
)
def like_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    # 게시글 행 잠금
    get_active_post(db, post_id, for_update=True)

    existing_like = db.scalar(
        select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == current_user.id,
        )
    )

    if existing_like is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 좋아요한 게시글입니다.",
        )

    try:
        db.add(
            PostLike(
                post_id=post_id,
                user_id=current_user.id,
            )
        )
        db.flush()

        result = db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1)
            .returning(Post.like_count)
        )
        
        like_count = result.scalar_one()
        
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="이미 좋아요한 게시글입니다.",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="좋아요 등록에 실패했습니다.",
        ) from exc

    return {
        "post_id": post_id,
        "like_count": like_count,
        "is_liked": True,
    }


# -------------------------
# DELETE /posts/{post_id}/likes
# 좋아요 취소
# -------------------------

@router.delete(
    "/{post_id}/likes",
    response_model=PostLikeResponse,
)
def unlike_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    # 게시글 행 잠금
    get_active_post(db, post_id, for_update=True)

    try:
        result = db.execute(
            delete(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.user_id == current_user.id,
            )
        )

        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail="좋아요 기록이 존재하지 않습니다.",
            )

        result = db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count - 1)
            .returning(Post.like_count)
        )
        
        like_count = result.scalar_one()
        
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="좋아요 취소에 실패했습니다.",
        ) from exc

    return {
        "post_id": post_id,
        "like_count": like_count,
        "is_liked": False,
    }
