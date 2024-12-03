from aiogram import F, Bot, Router, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from sqlalchemy.ext.asyncio import AsyncSession

from dependency_injector.wiring import Closing, Provide, inject

from bot_service.config import BotConfig
from user_service.user_service import UserService

from ..container import BotContainer
from database_service.models.users import UserModel

from sqlalchemy.dialects.postgresql import insert as pg_insert
import text_config

from aiogram.filters import Command

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from aiogram import html

from datetime import datetime

from .test import show_test

router = Router()

def menu_logs_message(user_id: int, username: str) -> str:
    return f"@{username}[{user_id}]:\n Вызвал главное меню"

def auth_logs_message(user_id: int, username: str) -> str:
    return f"@{username}[{user_id}]:\n Зарегестрирован"

def onboarding_logs_message(user_id: int, username: str) -> str:
    return f"@{username}[{user_id}]:\n Онбординг пройден"


class OnboardingStates(StatesGroup):
    waiting_for_age = State()

class TalkingStates(StatesGroup):
    waiting_for_answer = State()

#Генерация главного меню
def main_menu_keyboard():
    keyboard = InlineKeyboardBuilder()
    #keyboard.row(types.InlineKeyboardButton(text=text_config.main_menu_talk_text, callback_data="want_talk"))
    keyboard.row(types.InlineKeyboardButton(text=text_config.main_menu_tests_text, callback_data="gaming_tests"))
    keyboard.row(types.InlineKeyboardButton(text=text_config.main_menu_kiraplus_text, callback_data="kira_plus"))
    keyboard.row(types.InlineKeyboardButton(text=text_config.main_menu_profile_text, callback_data="profile"))
    return keyboard

def backmenu():
    backmenu = InlineKeyboardBuilder()
    backmenu.row(types.InlineKeyboardButton(text="Назад", callback_data="main_menu"))
    return backmenu


@router.message(Command("start", "menu"))
@inject
async def start_message(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession = Provide[BotContainer.postgres.session],
    user_service: UserService = Provide[BotContainer.user_microservice.user_service],
    config: BotConfig = Provide[BotContainer.config],
) -> None:
    if state:
        await state.clear()

    if "test=" in message.text:
        test_id = message.text.split("test=")[1]

        if not await user_service.getuser(message.from_user, session):
            await user_service.auth(message.from_user, session)
            logs_text = auth_logs_message(user_id=message.from_user.id, username=message.from_user.username)
            await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=logs_text)

        await bot.send_message(
            chat_id=config.telegram.logs_chat_id.value,
            text=f"{message.from_user.id} вызвал тест {test_id}"
        )

        await show_test(test_id=test_id, message=message, bot=bot, session=session)

        return

    if await user_service.getuser(message.from_user, session):
        await message.answer(
            text_config.main_menu_text,
            reply_markup=main_menu_keyboard().as_markup()
        )

        logs_text = menu_logs_message(user_id=message.from_user.id, username=message.from_user.username)
        await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=logs_text)
        return

    await user_service.auth(message.from_user, session)

    logs_text = auth_logs_message(user_id=message.from_user.id, username=message.from_user.username)
    await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=logs_text)

    keyboard = InlineKeyboardBuilder().row(
        types.InlineKeyboardButton(text=text_config.onboarding_0_answer, callback_data="hello")
    )
    await message.answer(text_config.onboarding_0_text, reply_markup=keyboard.as_markup())




@router.callback_query(F.data == "hello")
async def agreement_accept(call: types.CallbackQuery):
    keyboard = InlineKeyboardBuilder().row(
        types.InlineKeyboardButton(text=text_config.onboarding_1_answer, callback_data="accept_agreement"))
    await call.message.edit_text(text_config.onboarding_1_text, reply_markup=keyboard.as_markup())


@router.callback_query(F.data == 'accept_agreement')
async def pin_in_chats(call: types.CallbackQuery, bot: Bot):
    keyboard = InlineKeyboardBuilder().row(
        types.InlineKeyboardButton(text=text_config.onboarding_2_answer, callback_data="start_continue"))

    await call.message.delete()
    await bot.send_photo(chat_id=call.message.chat.id,
                         photo=text_config.onboarding_2_image,
                         caption=text_config.onboarding_2_text,
                         reply_markup=keyboard.as_markup())


@router.callback_query(F.data == "start_continue")
async def ask_age(call: types.CallbackQuery, bot:Bot, state: FSMContext):
    await call.message.delete()

    await bot.send_message(chat_id=call.message.chat.id, text=text_config.onboarding_3_text)
    await state.set_state(OnboardingStates.waiting_for_age)

# Клавиатура при первом выборе пола
def onboarding_gender_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=text_config.onboarding_5_variants[0], callback_data="male"),
    types.InlineKeyboardButton(text=text_config.onboarding_5_variants[1], callback_data="female"))
    keyboard.row(types.InlineKeyboardButton(text=text_config.onboarding_5_variants[2], callback_data="none"))
    return keyboard

# Клавиатура при изменении информации о поле
def edit_gender_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=text_config.onboarding_5_variants[0], callback_data="edit_male"),
    types.InlineKeyboardButton(text=text_config.onboarding_5_variants[1], callback_data="edit_female"))

    keyboard.row(types.InlineKeyboardButton(text='В главное меню', callback_data='main_menu'))
    return keyboard


@router.message(OnboardingStates.waiting_for_age)
@inject
async def onboarding_age(message: types.Message,
                       state: FSMContext,
                       user_service: UserService = Provide[BotContainer.user_microservice.user_service],
                       session: AsyncSession = Provide[BotContainer.postgres.session]):
    await state.clear()

    # Проверка на валидность возраста (если не валидный - указываем 18 лет)
    if message.text.isdigit():
        user_age = int(message.text)
        if user_age < 18 or user_age > 70:
            birth_year = 2006
        else:
            current_year = datetime.now().year
            birth_year = current_year - int(user_age)
    else:
        birth_year = 2006

    await user_service.save_age(message.from_user, birth_year, session)

    if await user_service.get_gender(message.from_user, session):
        keyboard = edit_gender_keyboard()
    else:
        keyboard = onboarding_gender_keyboard()

    await message.answer(text_config.onboarding_4_text, reply_markup=keyboard.as_markup())




@router.callback_query(F.data.in_(['male', 'female', 'none', 'edit_male', 'edit_female']))
@inject
async def onboarding_gender(call: types.CallbackQuery,
                     user_service: UserService = Provide[BotContainer.user_microservice.user_service],
                     session: AsyncSession = Provide[BotContainer.postgres.session]):

    # Редактирование  информации о поле
    if call.data in ["edit_male", "edit_female"]:
        await user_service.save_gender(call.from_user, call.data.replace('edit_', ''), session)
        await call.message.edit_text('Данные успешно сохранены', reply_markup=backmenu().as_markup())

    # Первый выбор пола
    elif call.data in ["male", "female"]:
        await user_service.save_gender(call.from_user, call.data, session)

        keyboard = InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text=text_config.onboarding_6_answer, callback_data="get_channel"))

        await call.message.edit_text(text_config.onboarding_6_text, reply_markup=keyboard.as_markup())



@router.callback_query(F.data == "get_channel")
@inject
async def get_channel(call: types.CallbackQuery, bot: Bot,
                      config: BotConfig = Provide[BotContainer.config]):
    await call.message.edit_text(text_config.onboarding_7_text, reply_markup=None)

    logs_text = onboarding_logs_message(call.from_user.username, call.from_user.id)

    await bot.send_message(chat_id=config.telegram.logs_chat_id.value, text=logs_text)

    await call.message.answer(text_config.onboarding_7_2_text, reply_markup=main_menu_keyboard().as_markup())


@router.callback_query(F.data == "want_talk")
async def want_talk(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(text_config.want_talk_text, reply_markup=backmenu().as_markup())
    await state.set_state(TalkingStates.waiting_for_answer)


@router.callback_query(F.data == "profile")
@inject
async def profile(call: types.CallbackQuery,
                  state: FSMContext,
                  user_service: UserService = Provide[BotContainer.user_microservice.user_service],
                  session: AsyncSession = Provide[BotContainer.postgres.session]):
    backmenu = InlineKeyboardBuilder()
    backmenu.row(types.InlineKeyboardButton(text="Изменить информацию", callback_data="edit_profile"))
    backmenu.row(types.InlineKeyboardButton(text="Назад", callback_data="main_menu"))

    gender, age = await user_service.get_user_gender_age(call.from_user, session)
    profile_text = text_config.profile_text % (call.from_user.first_name, gender, age)

    await call.message.edit_text(profile_text, reply_markup=backmenu.as_markup(), parse_mode='html')

@router.callback_query(F.data == "main_menu")
async def main_menu(call: types.CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    await call.message.edit_text(text_config.main_menu_text, reply_markup=main_menu_keyboard().as_markup())


@router.callback_query(F.data == "edit_profile")
async def edit_profile(call: types.CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    await call.message.edit_text('Введите ваш возраст', reply_markup=backmenu().as_markup())
    await state.set_state(OnboardingStates.waiting_for_age)

