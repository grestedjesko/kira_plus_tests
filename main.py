from sys import argv

from bot_service import BotMicroService
from table_service.table_service import TableService

import uvloop

from dotenv import load_dotenv
import os

load_dotenv()  # Это загрузит переменные окружения из файла .env


class BaseLauncher:
    def __init__(self, microservice):
        self.microservice = microservice

    def run(self, loop):
        # Пример получения конфигурации
        environment = os.environ
        instance = self.microservice(environment)
        loop.run_until_complete(instance.setup())  # Инициализация микросервиса
        loop.run_until_complete(instance.main())   # Запуск микросервиса


if __name__ == "__main__":
    if len(argv) < 2:
        raise Exception("Microservice name is not specified")
    name = argv[1]

    microservice = None
    if name == 'bot':
        microservice = BotMicroService
    elif name == 'table':
        microservice = TableService

    BaseLauncher(microservice).run(uvloop.new_event_loop())
