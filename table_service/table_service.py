from .config import TableConfig
import asyncio

from .container import TableContainer
from table_service import main

from .main import update_test_database


class TableService:
    def __init__(self, environment):
        self.context = environment
        self.config = TableConfig(self.context)
        self.container = None

    async def setup(self) -> None:
        """
        Метод для настройки зависимостей.
        """
        # Инициализация контейнера зависимостей (в будущем можно добавить больше сервисов)
        self.container = TableContainer(config=self.config)
        self.container.wire(modules=[main])

    async def main(self) -> None:
        await self.start_polling()

    async def start_polling(self) -> None:
        print('polling started')
        while True:
            await update_test_database()
            print('обновлено')
            await asyncio.sleep(900)


