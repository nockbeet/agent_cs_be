
from sqlalchemy import (
    Integer,
    ForeignKey,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.tag import Tag

class PostTag(Base):
    __tablename__ = "post_tags"

    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "tag_id",
            name="uq_post_tags_post_id_tag_id",
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

    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tags.id"),
        nullable=False,
    )



    # PostTag : Post = N:1
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="post_tags",
    )

    # PostTag : Tag = N:1
    tag: Mapped["Tag"] = relationship(
        "Tag",
        back_populates="post_tags",
    )
