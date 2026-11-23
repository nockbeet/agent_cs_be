
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.tag import TagResponse


# -------------------------
# 게시글 작성 요청
# -------------------------

class PostCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)

    image_ids: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)


# -------------------------
# 게시글 수정 요청
# -------------------------

class PostUpdateRequest(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200
    )
    content: str | None = Field(
        default=None,
        min_length=1
    )

    # 기존 이미지 유지 대상
    keep_image_ids: list[int] | None = None

    # 새로 업로드하는 이미지의 참조 ID
    image_ids: list[str] = Field(default_factory=list)

    # 미전달: 기존 태그 유지
    # []: 모든 태그 삭제
    # 값 전달: 해당 태그 목록으로 교체
    hashtags: list[str] | None = None

    @model_validator(mode="after")
    def validate_required_fields(self):
        for field_name in ("title", "content"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(
                    f"{field_name}은 null로 변경할 수 없습니다."
                )

        return self


# -------------------------
# 게시글 이미지 응답
# -------------------------

class PostImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str


# -------------------------
# 게시글 목록 응답
# -------------------------

class PostListResponse(BaseModel):
    id: int
    title: str

    author_id: int
    author_account_id: str
    author_username: str | None
    author_image_url: str | None

    hashtags: list[TagResponse] = Field(default_factory=list)

    like_count: int
    comment_count: int
    view_count: int

    created_at: datetime
    updated_at: datetime


# -------------------------
# 게시글 상세 응답
# -------------------------

class PostDetailResponse(PostListResponse):
    content: str
    images: list[PostImageResponse] = Field(default_factory=list)
    is_deleted: bool


# -------------------------
# 게시글 좋아요 응답
# -------------------------

class PostLikeResponse(BaseModel):
    post_id: int
    like_count: int
    is_liked: bool
