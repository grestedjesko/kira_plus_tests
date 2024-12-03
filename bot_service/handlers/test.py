from aiogram import Bot, Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import selectinload
from dependency_injector.wiring import Provide, inject
from database_service.models.test_service import Test, Question, Folder, UserTimers
from ..container import BotContainer
from aiogram.types import InputMediaPhoto
from ..config import BotConfig

from openai_service import OpenaiService

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from test_service.test_service import TestService

# функция для отправки ответа от нейросети, можно вынести из хендлера ai talking далее
from .ai_talking import send_ai_answer

from user_service import UserService

from datetime import datetime, timedelta

import asyncio

class TestStates(StatesGroup):
    waiting_for_answer = State()
    next_question = State()
    discussing_results = State()


router = Router()


@router.callback_query(F.data == "gaming_tests")
@inject
async def test_menu(call: types.CallbackQuery,
                    session: AsyncSession = Provide[BotContainer.postgres.session],
                    test: TestService = Provide[BotContainer.test.service],) -> None:

    #keyboard = await test.get_tests_keyboard(session)
    keyboard = await test.get_directory_keyboard(session=session, current_folder='/main_menu_tests_text')

    if call.message and call.message.text:
        await call.message.edit_text("Выберите тест из списка:", reply_markup=keyboard)
    else:
        await call.message.delete()
        await call.message.answer("Выберите тест из списка:", reply_markup=keyboard)


# Обработчик переходов по папкам
@router.callback_query(F.data[:7] == "folder:")
@inject
async def show_directory(callback: types.CallbackQuery,
                         session: AsyncSession = Provide[BotContainer.postgres.session],
                         test: TestService = Provide[BotContainer.test.service]) -> None:
    result = await session.execute(select(Folder))
    folders = result.scalars().all()
    folders_name = {folder.folder: folder.title for folder in folders}

    folder = callback.data.split(":", 1)[1]
    keyboard = await test.get_directory_keyboard(session, folder)
    await callback.message.edit_text(f"Вы в папке: {folders_name[folder]}", reply_markup=keyboard)



@router.callback_query(F.data[:5] == 'test:')
@inject
async def show_test_description(
        call: types.CallbackQuery,
        state: FSMContext,
        session: AsyncSession = Provide[BotContainer.postgres.session],) -> None:
    if state:
        await state.clear()
    test_id = call.data.split(":")[1]
    await show_test(test_id=test_id,
                    message=call.message,
                    bot=call.bot,
                    session=session)


async def show_test(test_id: str, message: types.Message, bot: Bot, session: AsyncSession):
    result = await session.execute(
        select(Test).filter_by(test_id=test_id)
    )
    test = result.scalar_one_or_none()

    if not test:
        await message.answer("Тест не найден.", show_alert=True)
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Начать тест", callback_data=f"start_test:{test_id}")
    keyboard.button(text="Назад", callback_data="gaming_tests")
    keyboard.adjust(1)

    text = f"<b>{test.title}</b>\n\n{test.description or 'Описание отсутствует.'}"

    if message.from_user.id == bot.id:
        media = InputMediaPhoto(media=test.welcome_image, caption=text)
        if test.welcome_image:
            await message.edit_media(
                media=media,
                reply_markup=keyboard.as_markup()
            )
        else:
            await message.edit_text(
                text=text,
                reply_markup=keyboard.as_markup()
            )
    else:
        if test.welcome_image:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=test.welcome_image,
                caption=text,
                reply_markup=keyboard.as_markup()
            )
        else:
            await message.answer(
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


@router.message(TestStates.waiting_for_answer)
@inject
async def handle_open_answer(message: types.Message, state: FSMContext, bot: Bot,
                             session: AsyncSession = Provide[BotContainer.postgres.session],
                             test: TestService = Provide[BotContainer.test.service],):
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

    await test.save_user_response(
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
                               session: AsyncSession = Provide[BotContainer.postgres.session],
                               test: TestService = Provide[BotContainer.test.service],):
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

    await test.save_user_response(
        session=session,
        user_id=call.from_user.id,
        test_id=data["test_id"],
        question_id=current_question.id,
        answer_text=selected_answer.answer_text,
        answer_id=answer_id
    )

    await state.update_data(question_index=question_index + 1, answers=answers)
    await send_next_question(call.message, state, bot)


@router.callback_query(F.data[:16] == 'discuss_results=')
@inject
async def discuss_results(call: types.CallbackQuery, bot: Bot,
                          state: FSMContext,
                          session: AsyncSession = Provide[BotContainer.postgres.session],
                          test: TestService = Provide[BotContainer.test.service],
                          openai: OpenaiService = Provide[BotContainer.openai.service],
                          config: BotConfig = Provide[BotContainer.config],):

    await call.message.delete()

    test_id = call.data.replace('discuss_results=', '')

    user_responses = await test.get_user_responses(user_id=call.from_user.id,
                                             test_id=test_id,
                                             session=session)

    prompt_text = await openai.prompt_manager.get_test_discuss_prompt(test_id=test_id,
                                                                      user_responses=user_responses,
                                                                      session=session)
    print(prompt_text)

    await send_ai_answer(prompt=prompt_text,
                         user_query="Узнать интерпретацию результатов",
                         message=call.message,
                         bot=bot,
                         session=session,
                         config=config,
                         openai=openai)

    # Устанавливаем состояние для обсуждения
    await state.set_state(TestStates.discussing_results)

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


@router.message(TestStates.discussing_results)
@inject
async def continue_discussion(message: types.Message,
                              state: FSMContext,
                              bot: Bot,
                              session: AsyncSession = Provide[BotContainer.postgres.session],
                              openai: OpenaiService = Provide[BotContainer.openai.service],
                              config: BotConfig = Provide[BotContainer.config],
                              user: UserService = Provide[BotContainer.user_microservice.user_service],):
    user_query = message.text
    if not user_query:
        await message.answer("Пожалуйста, введите текст для продолжения обсуждения.")
        return

    # Получаем ответ от нейросети
    prompt = await openai.prompt_manager.get_test_discuss_prompt(message=message, bot=bot, session=session, user=user)

    await send_ai_answer(prompt=prompt,
                         user_query=user_query,
                         message=message,
                         bot=bot,
                         session=session,
                         config=config,
                         openai=openai)


async def send_next_question(message: types.Message,
                             state: FSMContext,
                             bot: Bot,) -> None:
    data = await state.get_data()
    questions = data["questions"]
    question_index = data["question_index"]

    if question_index >= len(questions):
        await test_end(message, state)
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
    elif question_index == 0:
        test_id = data["test_id"]
        keyboard.button(text="Назад", callback_data="test:"+test_id)

    keyboard.adjust(1)
    keyboard = keyboard.as_markup()

    bot_message_id = data.get("bot_message_id")
    if message.from_user.id == bot.id and not bot_message_id:
        bot_message_id = message.message_id

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


# Основная функция завершения теста
async def test_end(message: types.Message, state: FSMContext):
    await message.delete()

    data = await state.get_data()
    test_id = data.get("test_id")

    # Создаем inline-клавиатуру с кнопкой "Обсудить результаты"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text="Узнать результаты",
        callback_data="discuss_results=" + test_id
    )
    keyboard_markup = keyboard.as_markup()

    # Отправляем итоговое сообщение пользователю
    await message.answer(
        f"Тест пройден. Хочешь обсудить его результаты со мной?",
        reply_markup=keyboard_markup
    )
    await state.clear()

