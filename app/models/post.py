
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    func,
    text,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.post_image import PostImage
    from app.models.post_like import PostLike
    from app.models.comment import Comment
    from app.models.post_tag import PostTag

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    like_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    comment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


    # Post : User = N:1
    user: Mapped["User"] = relationship(
        "User",
        back_populates="posts",
    )

    # Post : PostImage = 1:N
    images: Mapped[list["PostImage"]] = relationship(
        "PostImage",
        back_populates="post",
    )

    # Post : PostLike = 1:N
    post_likes: Mapped[list["PostLike"]] = relationship(
        "PostLike",
        back_populates="post",
    )

    # Post : Comment = 1:N
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="post",
    )

    # Post : PostTag = 1:N
    post_tags: Mapped[list["PostTag"]] = relationship(
        "PostTag",
        back_populates="post",
    )
