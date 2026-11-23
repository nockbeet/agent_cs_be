
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
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
    from app.models.post import Post

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("posts.id"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    parent_comment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("comments.id"),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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


    # Comment : Post = N:1
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="comments",
    )

    # Comment : User = N:1
    user: Mapped["User"] = relationship(
        "User",
        back_populates="comments",
    )

    # Comment : Comment = 자기 참조 N:1
    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        remote_side="Comment.id",
        back_populates="replies",
    )

    # Comment : Comment = 자기 참조 1:N
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
    )
