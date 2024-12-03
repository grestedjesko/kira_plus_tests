import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database_service.models.openai_context import OpenaiContext

from database_service.models.config import Config

from .data_classes import Result, MessageDTO

from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionUserMessageParam,
)

from aiogram import Bot,  types

from database_service.models.test_service import Test, UserResponse, Question

from sqlalchemy.ext.asyncio import AsyncSession

from user_service import UserService

from sqlalchemy import select

from test_service.test_service import TestService

class PromptManager:
    # Класс, который отвечает за работу с prompt и историей сообщений
    def __init__(self, config):
        self.config = config

    def msg_to_completion_param(self, msg: MessageDTO, bot_id: int) -> \
            (ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam):

        if msg.author_id != bot_id:
            return ChatCompletionUserMessageParam(role="user", content=msg.text)
        return ChatCompletionAssistantMessageParam(
            role="assistant", content=msg.text
        )

    async def load_history(self, session: AsyncSession, chat_id: int, limit: int) -> list[MessageDTO]:
        cursor = await session.execute(
            sa.select(
                OpenaiContext.text,
                OpenaiContext.author_id,
            )
            .where(
                OpenaiContext.chat_id == chat_id,
            )
            .order_by(OpenaiContext.created_at.desc())
            .limit(limit)
        )
        return [
            MessageDTO(
                author_id=author_id,
                text=text
            )
            for text, author_id in map(
                lambda r: r.tuple(), cursor.all()
            )
        ]

    async def save_message(self, session: AsyncSession, chat_id: int, author_id: int, text: str,) -> None:
        await session.execute(
            sa.insert(OpenaiContext).values(
                chat_id=chat_id,
                author_id=author_id,
                text=text,
            )
        )
        await session.commit()

    async def get_talking_default_prompt(self, session: AsyncSession) -> str:
        result = await session.execute(
            sa.select(Config.value).where(Config.key == 'openai_default_prompt')
        )
        prompt = result.scalar_one_or_none()
        return prompt

    async def get_talking_custom_prompt(self, message: types.Message, bot: Bot, session: AsyncSession, user: UserService):
        # Получаем факты о пользователи
        facts = await user.get_facts(message.from_user, session)

        # Получаем базовый prompt
        prompt = await self.get_talking_default_prompt(session)
        facts_text = "\n".join(f"{key}: {value}" for key, value in facts.items())
        prompt = prompt + "\n" + facts_text

        return prompt

    async def get_history(self, message: types.Message, bot: Bot, session: AsyncSession):
        await self.save_message(session=session, chat_id=message.chat.id,
                                author_id=message.from_user.id, text=message.text)

        # Получаем контекст (историю сообщений из базы)
        messages = await self.load_history(session, chat_id=message.chat.id, limit=10)

        # Переворачиваем историю сообщений, чтобы они были в правильном порядке
        real_messages_history = reversed(messages)

        message_completion = map(lambda msg: self.msg_to_completion_param(msg, bot.id),
                                 real_messages_history)

        return message_completion

    @staticmethod
    async def get_test_discuss_prompt(test_id: str, user_responses: list[tuple[UserResponse, Question]], session: AsyncSession) -> tuple:
        result = await session.execute(
            select(Test.prompt).filter(Test.test_id == test_id)
        )
        base_prompt = result.scalar()
        print(base_prompt)
        prompt_text = base_prompt + '\n\n'

        for user_response, question in user_responses:
            prompt_text += f"Вопрос: {question.question}\nОтвет: {user_response.answer_text}\n"

        return prompt_text
