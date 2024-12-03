from aiogram import Bot, Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from dependency_injector.wiring import Provide, inject
from database_service.models.test_service import Test, Question, Answer, UserResponse  # Модель тестов
from ..container import BotContainer
from aiogram.types import InputMediaPhoto
from sqlalchemy.exc import IntegrityError
from ..config import BotConfig
from user_service import UserService
from openai_service import OpenaiService

from collections import defaultdict
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram.utils.keyboard import InlineKeyboardBuilder

class TestStates(StatesGroup):
    waiting_for_answer = State()
    next_question = State()


router = Router()

# Сообщение, если пользователь превысил лимит
async def kira_plus_error(message: types.Message) -> None:
    text = "К сожалению, достигнут лимит сообщений. Общаться безлимитно можно, купив подписку на <a href='https://ya.ru/'> Кира+ </a>"
    await message.answer(text)


# Сообщение, если превышен общий лимит
async def tech_error(message: types.Message, bot: Bot, config: BotConfig) -> None:
    error_text = (
        "Простите, сейчас у меня некоторые технические неполадки. "
        "Разработчики уже работают над их устранением. "
        "Попробуйте написать чуть позже"
    )
    await bot.send_message(text=error_text, chat_id=message.chat.id)

    limit_text = """⚠️ Превышены общие лимиты на использование сервиса OpenAI."""
    await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=limit_text)


async def save_user_response(session: AsyncSession,
                             user_id: int,
                             test_id: str,
                             question_id: int,
                             answer_text: str | None,
                             answer_id: int | None) -> None:
    try:
        # Проверяем, существует ли уже ответ на данный вопрос
        query = select(UserResponse).where(
            UserResponse.user_id == user_id,
            UserResponse.test_id == test_id,
            UserResponse.question_id == question_id
        )
        result = await session.execute(query)
        existing_response = result.scalar_one_or_none()
        if existing_response:
            existing_response.answer_text = answer_text
            existing_response.answer_id = answer_id
        else:
            new_response = UserResponse(
                user_id=user_id,
                test_id=test_id,
                question_id=question_id,
                answer_text=answer_text,
                answer_id=answer_id
            )
            session.add(new_response)
        await session.commit()

    except IntegrityError:
        await session.rollback()
        raise



async def get_tests_by_folder(session: AsyncSession) -> dict:
    """Группирует тесты по директориям."""
    result = await session.execute(select(Test))
    tests = result.scalars().all()

    # Группируем тесты по папкам
    folder_dict = defaultdict(list)
    for test in tests:
        folder_dict[test.folder].append(test)
    return folder_dict

async def get_tests_keyboard(session: AsyncSession) -> InlineKeyboardMarkup:
    result = await session.execute(select(Test))
    tests = result.scalars().all()
    keyboard = InlineKeyboardBuilder()
    for test in tests:
        keyboard.button(
            text=test.title,
            callback_data=f"test:{test.test_id}"
        )
    keyboard.adjust(1)
    return keyboard.as_markup()




@router.callback_query(F.data == "gaming_tests")
@inject
async def test_menu(call: types.CallbackQuery,
                    session: AsyncSession = Provide[BotContainer.postgres.session]) -> None:
    keyboard = await get_tests_keyboard(session)

    if call.message and call.message.text:
        await call.message.edit_text("Выберите тест из списка:", reply_markup=keyboard)
    else:
        await call.message.delete()
        await call.message.answer("Выберите тест из списка:", reply_markup=keyboard)


@router.callback_query(F.data[:5] == 'test:')
@inject
async def show_test_description(
        call: types.CallbackQuery,
        session: AsyncSession = Provide[BotContainer.postgres.session]) -> None:
    test_id = call.data.split(":")[1]

    result = await session.execute(
        select(Test).filter_by(test_id=test_id)
    )
    test = result.scalar_one_or_none()

    if not test:
        await call.answer("Тест не найден.", show_alert=True)
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Начать тест", callback_data=f"start_test:{test_id}")
    keyboard.button(text="Назад", callback_data="gaming_tests")
    keyboard.adjust(1)

    text = f"<b>{test.title}</b>\n\n{test.description or 'Описание отсутствует.'}"

    media = InputMediaPhoto(media=test.welcome_image, caption=text)

    if test.welcome_image:
        await call.message.edit_media(
            media=media,
            reply_markup=keyboard.as_markup()
        )
    else:
        await call.message.edit_text(
            text=text,
            reply_markup=keyboard.as_markup()
        )


@router.callback_query(F.data[:11] == 'start_test:')
@inject
async def start_test(
        call: types.CallbackQuery,
        state: FSMContext,
        bot: Bot,
        session: AsyncSession = Provide[BotContainer.postgres.session]) -> None:
    test_id = call.data.split(":")[1]

    result = await session.execute(
        select(Question)
        .filter_by(test_id=test_id)
        .options(selectinload(Question.answers))
        .order_by(Question.position)
    )
    questions = result.scalars().all()

    if not questions:
        await call.answer("Нет доступных вопросов для этого теста.")
        return

    await state.update_data(questions=questions, question_index=0, test_id=test_id, answers=[])

    await send_next_question(call.message, state, bot)


async def send_next_question(message: types.Message,
                             state: FSMContext,
                             bot: Bot,
                             session: AsyncSession = Provide[BotContainer.postgres.session]) -> None:
    data = await state.get_data()
    questions = data["questions"]
    question_index = data["question_index"]

    if question_index >= len(questions):
        await test_end(message, state, bot, session)
        return

    current_question = questions[question_index]

    question_text = f"""<b>Вопрос {question_index + 1}:</b>

{current_question.question}"""

    media = None
    if current_question.image:
        media = InputMediaPhoto(media=current_question.image, caption=question_text)

    keyboard = InlineKeyboardBuilder()

    if current_question.question_type.lower() == "открытый":
        question_text += '\n\n Напишите ваш ответ текстом'

    elif current_question.question_type.lower() == "закрытый":
        question_text += '\n\n Выберите ответ из предложенных вариантов'

        for answer in current_question.answers:
            keyboard.button(text=answer.answer_text, callback_data=f"answer:{answer.id}")

    if question_index > 0:
        keyboard.button(text="Назад", callback_data="back_question")

    keyboard.adjust(1)
    keyboard = keyboard.as_markup()

    bot_message_id = data.get("bot_message_id")
    if media:
        if bot_message_id:
            await bot.edit_message_media(
                chat_id=message.chat.id,
                message_id=bot_message_id,
                media=media,
                reply_markup=keyboard
            )
        else:
            sent_message = await bot.send_photo(
                chat_id=message.chat.id,
                photo=current_question.image,
                caption=question_text,
                reply_markup=keyboard
            )
            bot_message_id = sent_message.message_id
    else:
        if bot_message_id:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_message_id,
                text=question_text,
                reply_markup=keyboard
            )
        else:
            sent_message = await bot.send_message(
                chat_id=message.chat.id,
                text=question_text,
                reply_markup=keyboard
            )
            bot_message_id = sent_message.message_id

    # Сохраняем ID сообщения бота в состояние
    await state.update_data(bot_message_id=bot_message_id)

    await state.set_state(TestStates.waiting_for_answer)



@router.message(TestStates.waiting_for_answer)
@inject
async def handle_open_answer(message: types.Message, state: FSMContext, bot: Bot,
                             session: AsyncSession = Provide[BotContainer.postgres.session]):
    data = await state.get_data()
    question_index = data["question_index"]
    questions = data["questions"]
    answers = data["answers"]
    current_question = questions[question_index]
    user_answer = message.text
    answers.append({"question_id": current_question.id, "answer": user_answer})

    if current_question.question_type.lower() == "закрытый":
        await message.answer('Выберите ответ из предложенных вариантов')
        return

    await message.delete()

    await save_user_response(
        session=session,
        user_id=message.from_user.id,
        test_id=data["test_id"],
        question_id=current_question.id,
        answer_text=user_answer,
        answer_id=None
    )

    await state.update_data(question_index=question_index + 1, answers=answers)
    await send_next_question(message, state, bot)


@router.callback_query(F.data[:7] == "answer:")
@inject
async def handle_closed_answer(call: types.CallbackQuery, state: FSMContext, bot: Bot,
                               session: AsyncSession = Provide[BotContainer.postgres.session]):
    data = await state.get_data()
    question_index = data["question_index"]
    questions = data["questions"]
    answers = data["answers"]
    answer_id = int(call.data.split(":")[1])
    current_question = questions[question_index]

    # Ищем текст ответа по ID
    selected_answer = next((ans for ans in current_question.answers if ans.id == answer_id), None)
    if selected_answer:
        answer_text = selected_answer.answer_text
        answers.append({"question_id": current_question.id, "answer": answer_text})

    await save_user_response(
        session=session,
        user_id=call.from_user.id,
        test_id=data["test_id"],
        question_id=current_question.id,
        answer_text=selected_answer.answer_text,
        answer_id=answer_id
    )

    await state.update_data(question_index=question_index + 1, answers=answers)
    await send_next_question(call.message, state, bot)


async def get_discuss_prompt(user_id: int, test_id: str, session: AsyncSession) -> tuple:
    result = await session.execute(
        select(Test.prompt).filter(Test.test_id == test_id)
    )
    base_prompt = result.scalar()

    user_responses = await get_user_responses(user_id=user_id, test_id=test_id, session=session)

    prompt_text = base_prompt + '\n\n'

    for user_response, question in user_responses:
        prompt_text += f"Вопрос: {question.question}\nОтвет: {user_response.answer_text}\n"

    return prompt_text


# Вспомогательная функция для получения ответов пользователя
async def get_user_responses(user_id: int, test_id: str, session: AsyncSession):
    result = await session.execute(
        select(UserResponse, Question)
        .join(Question, UserResponse.question_id == Question.id)
        .filter(
            UserResponse.user_id == user_id,
            UserResponse.test_id == test_id,
            Question.test_id == test_id
        )
        .order_by(UserResponse.question_id)
    )
    return result.all()


# Основная функция завершения теста
async def test_end(message: types.Message, state: FSMContext, bot: Bot, session: AsyncSession):
    await message.delete()

    data = await state.get_data()
    test_id = data.get("test_id")

    # Создаем inline-клавиатуру с кнопкой "Обсудить результаты"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text="Обсудить результаты",
        callback_data="discuss_results=" + test_id
    )
    keyboard_markup = keyboard.as_markup()

    # Отправляем итоговое сообщение пользователю
    await message.answer(
        f"Тест пройден. Хочешь обсудить его результаты со мной?",
        reply_markup=keyboard_markup
    )

    await state.clear()


@router.callback_query(F.data[:16] == 'discuss_results=')
@inject
async def discuss_results(call: types.CallbackQuery, bot: Bot,
                          session: AsyncSession = Provide[BotContainer.postgres.session],
                          openai: OpenaiService = Provide[BotContainer.openai.service],
                          config: BotConfig = Provide[BotContainer.config],
                          user: UserService = Provide[BotContainer.user_microservice.user_service], ):
    test_id = call.data.replace('discuss_results=', '')
    prompt_text = await get_discuss_prompt(user_id=call.from_user.id, test_id=test_id, session=session)

    # Проверка персональных лимитов
    user_limit_allowed = await user.check_usage(user=call.from_user, session=session, openai_config=openai.config)
    if not user_limit_allowed:
        await kira_plus_error(message=call.message)
        return

    # Преобразуем сообщения в формат, который понимает openai
    message_completion = map(lambda msg: openai.msg_to_completion_param(msg, bot.id), [])

    model = await openai.get_model(session)

    # Получаем ответ от openai в формате stream и выводим его пользователю
    tokens_stream = openai.get_tokens_stream(conversation=message_completion, prompt=prompt_text, model=model)

    try:
        result, tokens_stream = await openai.accumulate_string_stream_result(tokens_stream)
        tokens_usage = await openai.send_stream_with_animation(call.message, bot, tokens_stream,
                                                               is_allowed=user_limit_allowed, )
        if not tokens_usage:
            raise NotImplementedError('Токены не определены')

        await user.update_usage(user=call.from_user, messages_count=1, tokens_count=tokens_usage, session=session)
        await openai.update_total_limit(messages_count=1, tokens_count=tokens_usage, session=session)

        # Сохранение ответа в историю переписки
        final_text = result.result
        final_text = final_text.split('/#u')[0]
        await openai.save_message(session=session, chat_id=call.message.chat.id, author_id=bot.id, text=final_text)
        await session.commit()

    except Exception as exc:
        await tech_error(message=call.message, bot=bot, config=config)
        error = exc
        assert call.from_user is not None
        if error is not None:
            raise error


@router.callback_query(F.data == "back_question")
@inject
async def go_back_to_previous_question(call: types.CallbackQuery,
                                       state: FSMContext,
                                       bot: Bot) -> None:
    data = await state.get_data()
    question_index = data["question_index"]

    # Убираем последний ответ из списка при возвращении назад
    answers = data["answers"]
    if answers:
        answers = answers[:-1]  # Убираем последний ответ

    # Если индекс больше 0, то уменьшаем его, иначе не меняем
    if question_index > 0:
        new_question_index = question_index - 1
    else:
        new_question_index = 0  # Чтобы не получить отрицательный индекс

    await state.update_data(question_index=new_question_index, answers=answers)

    await send_next_question(call.message, state, bot)


