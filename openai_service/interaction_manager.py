import asyncio
from datetime import datetime

import httpx
from openai import AsyncOpenAI


import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Any, AsyncIterable, Iterable
import aiostream

from openai.types.chat import (
    ChatCompletionMessageParam
)

from database_service.models.total_daily_usage import TotalDailyUsage

from database_service.models.config import Config

from aiogram import types, Bot

from datetime import timedelta

from .data_classes import Result, MessageDTO



class InteractionManager:
    def __init__(self, config):
        #self.http_client = httpx.AsyncClient(proxies=config.proxy.value)
        self.openai_client = AsyncOpenAI(api_key=config.token.value, base_url='https://api.aitunnel.ru/v1/') #, http_client=self.http_client)
        self.config = config

    async def test_proxy(self):
        try:
            response = await self.http_client.get('https://api.ipify.org?format=json')
            response.raise_for_status()
            print("Proxy is working. IP:", response.json())
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"An error occurred: {e}")

    async def get_model(self, session: AsyncSession) -> str:
        result = await session.execute(sa.select(Config).where(Config.key == 'ai_model'))
        config = result.scalar_one_or_none()
        return config.value if config else None

    async def get_tokens_stream(self,
        conversation: Iterable[ChatCompletionMessageParam],
        prompt: str, model) -> AsyncIterable[str]:

        messages: Iterable[ChatCompletionMessageParam] = [
            {"role": "system", "content": prompt},
            *conversation,
        ]

        response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
        )

        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content is not None and len(content) > 0:
                yield content
            elif chunk.usage: # Возвращаем количество использованных токенов
                yield f'/#u{chunk.usage.total_tokens}'


    async def accumulate_string_stream_result(self,
        stream: AsyncIterable[str])-> tuple[Result, AsyncIterable[str]]:

        result = Result(result="")

        def mapper(chunk: str, *_: Any) -> str:
            nonlocal result
            result.result += chunk
            return chunk

        mapped_stream = aiostream.stream.map(
            stream,
            mapper,
        )
        return result, mapped_stream


    async def send_stream_with_animation(self,
                                         message: types.Message,
                                         bot: Bot,
                                         stream: AsyncIterable[str],
                                         is_allowed: bool,) -> int | None:

        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        sended_message = await message.answer("▌")
        current_text: str = ""
        usage = 0
        last_sended_timestamp: datetime = datetime.now()
        async for chunk in stream:
            if chunk:
                if '/#u' in chunk:
                    usage = int(chunk.replace('/#u', ''))
                    chunk=''

                current_text += chunk

                if not is_allowed and len(current_text) >= 100:
                    await sended_message.edit_text(current_text + "...")
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=(
                            "Кажется, у тебя закончился лимит бесплатных сообщений на сегодня. "
                            "Возвращайся завтра или оплати ежемесячный тариф, чтобы общаться "
                            "со мной без ограничений."
                        ),
                        reply_markup=types.InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    types.InlineKeyboardButton(
                                        text="Оплатить", callback_data="pay-for-tariff"
                                    ),
                                ]
                            ]
                        ),
                    )
                    return

                if datetime.now() - last_sended_timestamp < timedelta(seconds=float(self.config.interval_s.value)):
                    continue

                if chunk:
                    await sended_message.edit_text(current_text + "▌")

                last_sended_timestamp = datetime.now()
                await asyncio.sleep(0.1)
        if current_text:
            await sended_message.edit_text(current_text)
        return usage if usage else None

