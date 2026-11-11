"""Engine, session factory and migrations."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from intentlock.db.models import DEFAULT_TENANT_ID, Base, Tenant

ALEMBIC_DIR = Path(__file__).resolve().parent / "alembic"


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        memory = url in ("sqlite://", "sqlite:///:memory:")
        kwargs = {"connect_args": {"check_same_thread": False}}
        if memory:
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # SQLite ignores foreign keys unless asked
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def run_migrations(url: str) -> None:
    """Apply Alembic migrations up to head. Called once at start-up."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def create_schema_for_tests(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def seed_default_tenant(factory: sessionmaker[Session]) -> None:
    with factory() as s:
        if s.scalar(select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID)) is None:
            s.add(Tenant(id=DEFAULT_TENANT_ID, name="Netrava demo merchant"))
            s.commit()
