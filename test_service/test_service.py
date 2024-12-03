from sqlalchemy.exc import IntegrityError

from database_service.models.test_service import Test, Question, UserResponse, Folder

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from collections import defaultdict


class TestService:
    @staticmethod
    async def get_tests_keyboard(session: AsyncSession) -> InlineKeyboardMarkup:
        result = await session.execute(select(Test))
        tests = result.scalars().all()
        keyboard = InlineKeyboardBuilder()
        for test in tests:
            keyboard.button(
                text=test.title,
                callback_data=f"test:{test.test_id}"
            )
        keyboard.button(text='Назад', callback_data='main_menu')
        keyboard.adjust(1)
        return keyboard.as_markup()

    @staticmethod
    async def get_directory_keyboard(session: AsyncSession, current_folder: str = "/") -> InlineKeyboardMarkup:
        result = await session.execute(select(Folder))
        folders = result.scalars().all()
        folders_name = {folder.folder: folder.title for folder in folders}

        result = await session.execute(select(Test))
        tests = result.scalars().all()

        # Фильтруем тесты и папки в текущей директории
        folder_structure = defaultdict(list)
        for test in tests:
            folder_path = test.folder.strip("/")
            if folder_path.startswith(current_folder.strip("/")):
                relative_path = folder_path[len(current_folder.strip("/")):].strip("/")
                if "/" not in relative_path and relative_path:  # Текущая директория
                    folder_structure["folders"].append(relative_path)
                elif not relative_path:  # Тесты в текущей папке
                    folder_structure["tests"].append(test)

        # Генерация клавиатуры
        keyboard = InlineKeyboardBuilder()

        # Добавляем папки
        unique_folders = set(folder_structure["folders"])

        for folder in unique_folders:
            folder = f"{current_folder}/{folder}"
            keyboard.button(
                text=f'📂 {folders_name[folder]}',
                callback_data=f"folder:{folder}"
            )

        # Добавляем тесты
        for test in folder_structure["tests"]:
            keyboard.button(
                text=test.title,
                callback_data=f"test:{test.test_id}"
            )

        # Добавляем кнопку "Назад", если это не корень
        if current_folder != "/":
            parent_folder = "/".join(current_folder.strip("/").split("/")[:-1])
            parent_folder = f"/{parent_folder}" if parent_folder else "/"
            print(current_folder)
            if current_folder == '/main_menu_tests_text':
                keyboard.button(text='🔙 Назад', callback_data='main_menu')
            else:
                keyboard.button(text='🔙 Назад', callback_data=f"folder:{parent_folder}")

        keyboard.adjust(1)  # Одна кнопка на строку
        return keyboard.as_markup()


    @staticmethod
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

    @staticmethod
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

class TestAfterMessageService:
    pass