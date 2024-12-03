from dependency_injector import containers, providers
from oauth2client.service_account import ServiceAccountCredentials
from .config import TableConfig


from database_service import DatabaseContainer
from database_service.config import PostgresConfig


class TableContainer(containers.DeclarativeContainer):
    config: providers.Singleton[TableConfig] = providers.Singleton(TableConfig)

    credentials: providers.Factory[ServiceAccountCredentials] = providers.Factory(
        lambda config: ServiceAccountCredentials.from_json_keyfile_name(
            config.credentials.value,
            ['https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive']
        ),
        config.provided  # Ensures the `config` is resolved properly
    )

    postgres_config: providers.Singleton[PostgresConfig] = providers.Singleton(
        lambda config: PostgresConfig(environment=config.environment),
        config=config
    )
    postgres: DatabaseContainer = providers.Container(
        DatabaseContainer, config=postgres_config
    )