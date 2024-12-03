from aiogram import BaseMiddleware
from aiogram.types import Update
import logging


class ErrorHandlerMiddleware(BaseMiddleware):
    def __init__(self, bot, admin_chat_id: int):
        """
        Инициализация middleware для обработки ошибок.
        :param bot: Экземпляр бота.
        :param admin_chat_id: ID чата администратора.
        """
        super().__init__()
        self.bot = bot
        self.admin_chat_id = admin_chat_id
        self.logger = logging.getLogger(__name__)

    async def __call__(self, handler, event: Update, data: dict):
        try:
            return await handler(event, data)
        except Exception as e:
            # Логирование ошибки
            self.logger.exception(f"Ошибка во время обработки обновления: {event}")

            # Формирование сообщения об ошибке
            error_message = (
                f"⚠️ **Ошибка**:\n\n"
                f"**Исключение:** {e}\n\n"
                f"**Update:** {event.dict()}"
            )

            # Отправка сообщения администратору
            #await self.bot.send_message(chat_id=self.admin_chat_id, text=error_message)

            # Повторно поднимаем исключение, если нужно, или подавляем его
            raise
