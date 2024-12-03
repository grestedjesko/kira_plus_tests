from aiogram import Bot, Router, types

from dependency_injector.wiring import Closing, Provide, inject

from ..config import BotConfig
from ..container import BotContainer
from sqlalchemy.ext.asyncio import AsyncSession

from openai_service import OpenaiService

from user_service import UserService

router = Router()


def build_logs_message(user_id: int, username: str, message: str, answer: str) -> str:
    return f"@{username}[{user_id}]:\n{message}\n\nОтвет: \n{answer}"


@router.message()
@inject
async def ai_talk(message: types.Message,
                           bot: Bot,
                           session: AsyncSession = Provide[BotContainer.postgres.session],
                           config: BotConfig = Provide[BotContainer.config],
                           openai: OpenaiService = Provide[BotContainer.openai.service],
                           user: UserService = Provide[BotContainer.user_microservice.user_service],) -> None:
    # Проверяем валидность запроса пользователя
    if message.text[0] == '/':
        return
    assert message.from_user is not None
    user_query = message.text
    if user_query is None:
        await message.answer("Вы забыли ввести текст!")
        return

    # Получение prompt для разговора
    prompt = await openai.prompt_manager.get_talking_custom_prompt(message=message, bot=bot, session=session, user=user)

    await send_ai_answer(prompt=prompt,
                         user_query=user_query,
                         message=message,
                         bot=bot,
                         session=session,
                         config=config,
                         openai=openai)


async def send_ai_answer(prompt: str,
                         user_query: str,
                         message: types.Message,
                         bot: Bot,
                         session: AsyncSession = Provide[BotContainer.postgres.session],
                         config: BotConfig = Provide[BotContainer.config],
                         openai: OpenaiService = Provide[BotContainer.openai.service],) -> None:

    should_save_message = True

    user_limit_allowed = await openai.limit_manager.check_limits(session=session,
                                                                 message=message,
                                                                 bot=bot,
                                                                 config=config)

    # Получение истории диалога
    message_completion = await openai.prompt_manager.get_history(message=message, bot=bot, session=session)

    await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=prompt)

    # Получаем выбранную модель для запроса
    model = await openai.interaction_manager.get_model(session)

    # Получаем ответ от openai в формате stream и выводим его пользователю
    tokens_stream = openai.interaction_manager.get_tokens_stream(conversation=message_completion,
                                                                 prompt=prompt,
                                                                 model=model)
    try:
        result, tokens_stream = await openai.interaction_manager.accumulate_string_stream_result(tokens_stream)

        tokens_usage = await openai.interaction_manager.send_stream_with_animation(message, bot, tokens_stream,
                                                                                   is_allowed=user_limit_allowed, )
        if not tokens_usage:
            raise NotImplementedError('Токены не определены')

        await openai.limit_manager.update_limits(user=message.from_user,
                                                 tokens_usage=tokens_usage,
                                                 session=session)
        # Сохранение ответа в историю переписки
        final_text = result.result
        final_text = final_text.split('/#u')[0]

        await openai.prompt_manager.save_message(session=session,
                                                 chat_id=message.chat.id,
                                                 author_id=bot.id,
                                                 text=final_text)
        await session.commit()

    except Exception as exc:
        await openai.limit_manager.tech_error(message=message, bot=bot, config=config)
        error = exc
        assert message.from_user is not None
        if error is not None:
            raise error

    logs_text = build_logs_message(user_id=message.from_user.id,
                                   username=message.from_user.username,
                                   message=user_query,
                                   answer=final_text)

    await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=logs_text)