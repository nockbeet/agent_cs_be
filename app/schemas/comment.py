
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


# -------------------------
# 댓글 및 대댓글 작성 요청
# -------------------------

class CommentCreateRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=5000
    )


# -------------------------
# 댓글 및 대댓글 수정 요청
# -------------------------

class CommentUpdateRequest(BaseModel):
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000
    )

    @model_validator(mode="after")
    def validate_content(self):
        if (
            "content" in self.model_fields_set
            and self.content is None
        ):
            raise ValueError(
                "content는 null로 변경할 수 없습니다."
            )

        return self


# -------------------------
# 댓글 및 대댓글 응답
# -------------------------

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    content: str | None

    author_id: int
    author_account_id: str
    author_username: str | None
    author_image_url: str | None

    parent_comment_id: int | None
    replies: list["CommentResponse"] = Field(
        default_factory=list
    )

    created_at: datetime
    updated_at: datetime
    is_deleted: bool


# -------------------------
# 댓글 삭제 응답
# -------------------------

class CommentDeleteResponse(BaseModel):
    message: str
