from aiogram import F, Bot, Router, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import Provide, inject
from bot_service.config import BotConfig
from ..container import BotContainer
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select
from database_service.models.config import Config
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from openai_service import OpenaiService
import sqlalchemy as sa
router = Router()

include_models = [
        'gpt-4o-mini', 'o1-mini', 'gpt-4o', 'gpt-3.5-turbo',
        'gemini-flash-1.5-8b', 'gemini-flash-1.5', 'claude-3-5-haiku',
        'claude-3.5-sonnet', 'claude-3-haiku', 'llama-3.2-1b-instruct',
        'llama-3.2-3b-instruct', 'llama-3.2-11b-vision-instruct', 'llama-3.2-90b-vision-instruct'
    ]

# Обработка команды /model для админов
@router.message(Command("model"))
@inject
async def admin_menu(message: types.Message,
                     state: FSMContext,
                     session: AsyncSession = Provide[BotContainer.postgres.session],
                     openai: OpenaiService = Provide[BotContainer.openai.service],
                     config: BotConfig = Provide[BotContainer.config],) -> None:
    if state:
        await state.clear()
    if str(message.from_user.id) == config.telegram.admin.value or str(message.from_user.id) == '5164567108' or str(message.from_user.id) == '5119756697':
        keyboard = await create_model_keyboard(session, openai)
        await message.answer("Выберите активную модель", reply_markup=keyboard)


# Создание клавиатуры с выбором модели
async def create_model_keyboard(session: AsyncSession, openai: OpenaiService) -> InlineKeyboardMarkup:
    current_model = await openai.get_model(session)

    inline_keyboard = []

    for model in include_models:
        button_text = f"{model} {'✅' if model == current_model else ''}"
        button = InlineKeyboardButton(text=button_text, callback_data=model)

        if len(inline_keyboard) == 0 or len(inline_keyboard[-1]) >= 2:
            inline_keyboard.append([button])
        else:
            inline_keyboard[-1].append(button)

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    return keyboard


# Обработка выбора модели
@router.callback_query(F.data.in_(include_models))
@inject
async def model_callback_handler(callback_query: CallbackQuery,
                                 session: AsyncSession = Provide[BotContainer.postgres.session],
                                 openai: OpenaiService = Provide[BotContainer.openai.service],) -> None:
    model_name = callback_query.data

    await session.execute(sa.update(Config).where(Config.key == 'ai_model').values(value=model_name))
    await session.commit()

    new_keyboard = await create_model_keyboard(session, openai)
    await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback_query.answer(f"Модель изменена на {model_name}")
