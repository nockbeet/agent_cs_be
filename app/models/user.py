from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    func,
    text,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.post import Post
    from app.models.post_like import PostLike
    from app.models.comment import Comment

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    account_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    username: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )

    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    profile_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
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
    
    
    # User : Session = 1:N
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
    )

    # User : Post = 1:N
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="user",
    )

    # User : PostLike = 1:N
    post_likes: Mapped[list["PostLike"]] = relationship(
        "PostLike",
        back_populates="user",
    )

    # User : Comment = 1:N
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="user",
    )
