from dependency_injector import containers, providers
from .config import BotConfig
from user_service import UserServiceContainer  # Импортируем контейнер UserMicroService

from database_service import DatabaseContainer
from database_service.config import PostgresConfig

from openai_service import OpenaiServiceContainer
from openai_service.config import OpenaiConfig

from test_service import TestContainer


class BotContainer(containers.DeclarativeContainer):
    config = providers.Singleton(BotConfig)

    postgres_config: providers.Singleton[PostgresConfig] = providers.Singleton(
        lambda config: PostgresConfig(environment=config.environment),
        config=config
    )
    postgres: DatabaseContainer = providers.Container(
        DatabaseContainer, config=postgres_config
    )

    user_microservice = providers.Container(UserServiceContainer)

    openai_config: providers.Singleton[OpenaiConfig] = providers.Singleton(
        lambda config: OpenaiConfig(environment=config.environment),
        config=config
    )

    openai: OpenaiServiceContainer = providers.Container(
        OpenaiServiceContainer, config=openai_config
    )

    test: TestContainer = providers.Container(TestContainer)
