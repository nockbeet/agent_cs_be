
from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

from app.database import Base, DATABASE_URL, engine
import app.models


# Alembic Config 객체
config = context.config


# Alembic 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ORM 모델의 메타데이터
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """오프라인 모드 마이그레이션"""

    context.configure(
        url=DATABASE_URL.render_as_string(
            hide_password=False
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드 마이그레이션"""

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
