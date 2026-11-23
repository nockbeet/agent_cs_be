
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.post import Post

class PostLike(Base):
    __tablename__ = "post_likes"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "post_id",
            name="uq_post_likes_user_id_post_id",
        ),
    )

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

    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("posts.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


    # PostLike : User = N:1
    user: Mapped["User"] = relationship(
        "User",
        back_populates="post_likes",
    )

    # PostLike : Post = N:1
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="post_likes",
    )
