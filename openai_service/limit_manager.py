from database_service.models.total_daily_usage import TotalDailyUsage

from database_service.models.user_usage import UserUsage

from aiogram import types

from sqlalchemy.ext.asyncio import AsyncSession

from openai_service.config import OpenaiConfig

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime

from bot_service.config import BotConfig
from aiogram import Bot, Router, types

class LimitManager:
    def __init__(self, config):
        self.config = config

    # Сообщение, если превышен общий лимит
    async def tech_error(self, message: types.Message, bot: Bot, config: BotConfig) -> None:
        error_text = (
            "Простите, сейчас у меня некоторые технические неполадки. "
            "Разработчики уже работают над их устранением. "
            "Попробуйте написать чуть позже"
        )
        await bot.send_message(text=error_text, chat_id=message.chat.id)

        limit_text = """⚠️ Превышены общие лимиты на использование сервиса OpenAI."""
        await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=limit_text)

    # Сообщение, если пользователь превысил лимит
    async def kira_plus_error(self, message: types.Message) -> None:
        text = "К сожалению, достигнут лимит сообщений. Общаться безлимитно можно, купив подписку на <a href='https://ya.ru/'> Кира+ </a>"
        await message.answer(text)


    async def check_user_limit(self, user: types.User, session: AsyncSession, openai_config: OpenaiConfig) -> bool:
        current_date = datetime.today().date()
        cursor = await session.execute(
            sa.select(UserUsage.tokens_usage, UserUsage.message_usage)
            .where(UserUsage.user_id == user.id, UserUsage.date == current_date)
        )
        result = cursor.fetchone()

        if result is None:
            await session.execute(
                pg_insert(UserUsage)
                .values(user_id=user.id, date=current_date, tokens_usage=0, message_usage=0)
                .on_conflict_do_nothing()
            )
            await session.commit()
            return True

        tokens_usage, message_usage = result

        return (tokens_usage < int(openai_config.tokens_user_limit.value)
                and message_usage < int(openai_config.messages_user_limit.value))

    async def update_user_limit(self, user: types.User, messages_count: int, tokens_count: int, session: AsyncSession) -> None:
        current_date = datetime.today().date()
        await session.execute(
            sa.update(UserUsage)
            .where(UserUsage.user_id == user.id, UserUsage.date == current_date)
            .values(
                tokens_usage=UserUsage.tokens_usage + tokens_count,
                message_usage=UserUsage.message_usage + messages_count
            )
        )
        await session.commit()


    async def check_total_limit(self, session: AsyncSession) -> bool:
        current_date = datetime.today().date()

        result = await session.execute(
            sa.select(TotalDailyUsage.tokens_usage, TotalDailyUsage.message_usage,)
            .where(TotalDailyUsage.date == current_date,)
        )
        limit = result.fetchone()
        if limit:
            if (limit.tokens_usage < int(self.config.tokens_limit.value)
                    and limit.message_usage < int(self.config.messages_limit.value)):
                return True  # Возвращаем, если лимиты не превышены
            else:
                return False  # Возвращаем, если лимиты превышены
        else:
            await session.execute(
                sa.insert(TotalDailyUsage).values(
                    date=current_date,
                    tokens_usage=0,
                    message_usage=0,
                )
            )
            await session.commit()
            return True


    async def update_total_limit(self, messages_count, tokens_count, session: AsyncSession) -> None:
        current_date = datetime.today().date()
        await session.execute(
            sa.update(TotalDailyUsage)
            .where(TotalDailyUsage.date == current_date)
            .values(
                tokens_usage=TotalDailyUsage.tokens_usage + tokens_count,
                message_usage=TotalDailyUsage.message_usage + messages_count
            )
        )
        await session.commit()


    async def check_limits(self, session: AsyncSession, message: types.Message, bot: Bot, config: BotConfig):
        # Проверка общих лимитов
        limit_allowed = await self.check_total_limit(session=session)
        if not limit_allowed:
            await self.tech_error(message=message, bot=bot, config=config)
            return False

        # Проверка персональных лимитов
        user_limit_allowed = await self.check_user_limit(user=message.from_user, session=session, openai_config=self.config)
        if not user_limit_allowed:
            await self.kira_plus_error(message=message)
            return False

        return True


    async def update_limits(self, user: types.User, tokens_usage: int, session: AsyncSession):
        await self.update_user_limit(user=user,
                                messages_count=1,
                                tokens_count=tokens_usage,
                                session=session)

        await self.update_total_limit(messages_count=1,
                                      tokens_count=tokens_usage,
                                      session=session)
