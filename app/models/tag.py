
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Index,
    func,
    text
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.post_tag import PostTag


class Tag(Base):
    __tablename__ = "tags"

    # 태그 이름의 대소문자 무시 UNIQUE 인덱스
    __table_args__ = (
        Index(
            "uq_tags_name_lower",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Tag : PostTag = 1:N
    post_tags: Mapped[list["PostTag"]] = relationship(
        "PostTag",
        back_populates="tag",
    )
