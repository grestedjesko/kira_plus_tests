import sys
from aiogram import Bot, Dispatcher
from .handlers import get_routers, onboarding, ai_talking, admin, test
from .container import BotContainer
from .config import BotConfig
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
import logging
from .middlewares.logger import ErrorHandlerMiddleware

class BotMicroService:
    def __init__(self, environment: dict) -> None:
        """
        Инициализация микросервиса.
        :param environment: Словарь переменных окружения.
        """
        self.context = environment
        self.config = BotConfig(self.context)  # Загружаем конфигурацию из окружения
        self.container = None
        self.bot = None
        self.dispatcher = None

    async def setup(self) -> None:
        """
        Метод для настройки зависимостей.
        """
        # Инициализация контейнера зависимостей (в будущем можно добавить больше сервисов)
        self.container = BotContainer(config=self.config)
        self.container.wire(modules=[onboarding, ai_talking, admin, test])

    async def main(self) -> None:
        """
        Основной метод для запуска бота.
        """

        # Настройка логгера
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        self.bot = Bot(token=self.config.telegram.token.value,
                       default=DefaultBotProperties(parse_mode=ParseMode.HTML))  # Токен бота из конфигурации
        self.dispatcher = Dispatcher()

        # Подключаем роутеры для обработки команд
        self.dispatcher.include_routers(*get_routers(self.config))

        self.dispatcher.message.middleware(ErrorHandlerMiddleware(self.bot, self.config.telegram.logs_chat_id.value))


        # Стартуем polling
        await self.dispatcher.start_polling(self.bot)

    async def shutdown(self) -> None:
        """
        Метод для корректного завершения работы бота.
        """
        if hasattr(self, 'bot') and self.bot:
            await self.bot.session.close()  # Закрытие сессии бота

