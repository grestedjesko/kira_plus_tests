import urllib.parse
from datetime import datetime, timezone
from typing import Any, AsyncContextManager, AsyncGenerator, Callable

import asyncpg

from dependency_injector import containers, providers

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    sessionmaker as sqlalchemy_sessionmaker,
)

from .config import PostgresConfig

Sessionmaker = Callable[..., AsyncContextManager[AsyncSession]]


def create_db_url(config: PostgresConfig) -> str:
    return "postgresql+asyncpg://{user}{password}@{host}:{port}/{db}".format(
        user=config.username.value,
        password=f":{urllib.parse.quote_plus(config.password.value)}",
        host=config.host.value,
        port=config.port.value,
        db=config.db.value,
    )


def encoder(d: datetime) -> str:
    return d.isoformat()


def decoder(value: str) -> datetime:
    return datetime.fromisoformat(value.replace(" ", "T")).replace(tzinfo=timezone.utc)


class CustomConnection(asyncpg.Connection):  # type: ignore [misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.is_datetime_set = False

    async def set_type_codec(self, *args: Any, **kwargs: Any) -> None:
        if not self.is_datetime_set:
            self.is_datetime_set = True
            await self.set_type_codec(
                "timestamp",
                encoder=encoder,
                decoder=decoder,
                schema="pg_catalog",
            )
        await super().set_type_codec(*args, **kwargs)


async def use_session(
    sessionmaker: Sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        yield session


class DatabaseContainer(containers.DeclarativeContainer):
    wiring_db_config = containers.WiringConfiguration(packages=["database"])
    config: providers.Singleton[PostgresConfig] = providers.Singleton(PostgresConfig)
    connection_url = providers.Singleton(create_db_url, config=config)
    engine: providers.Singleton[AsyncEngine] = providers.Singleton(
        create_async_engine,
        url=connection_url,
        future=True,
        connect_args={"connection_class": CustomConnection},
    )
    sessionmaker: providers.Factory[Sessionmaker] = providers.Factory(
        sqlalchemy_sessionmaker,
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    session = providers.Resource(use_session, sessionmaker)


class Base(DeclarativeBase):
    pass
