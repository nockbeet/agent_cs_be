
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.post import Post

class PostImage(Base):
    __tablename__ = "post_images"

    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "image_url",
            name="uq_post_images_post_id_image_url",
        ),
    )

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

    image_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


    # PostImage : Post = N:1
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="images",
    )
