
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


# -------------------------
# 사용자 프로필 수정
# -------------------------

class UserUpdateRequest(BaseModel):
    username: str | None = Field(
        default=None,
        min_length=1,
        max_length=30
    )
    email: EmailStr | None = None
    bio: str | None = Field(
        default=None,
        max_length=500
    )

    @model_validator(mode="after")
    def validate_username(self):
        if (
            "username" in self.model_fields_set
            and self.username is None
        ):
            raise ValueError("username은 null로 변경할 수 없습니다.")

        return self


# -------------------------
# 사용자 프로필 조회
# -------------------------

class UserDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: str
    username: str | None
    email: EmailStr | None
    bio: str | None
    profile_image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
