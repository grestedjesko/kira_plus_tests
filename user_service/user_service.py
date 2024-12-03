from database_service.models.users import UserModel
from database_service.models.user_facts import UserFacts
from database_service.models.user_usage import UserUsage

from aiogram import types

from sqlalchemy.ext.asyncio import AsyncSession

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime
class UserService():
    async def getuser(self, user: types.User, session: AsyncSession) -> bool:
        cursor = await session.execute(
            sa.select(UserModel.user_id).where(UserModel.user_id == user.id)
        )
        result = cursor.scalar_one_or_none()
        return result is not None

    async def auth(self, user: types.User, session: AsyncSession) -> None:
        values: dict[str, str | None, str | None, str, int] = {
            "first_name": user.first_name,
            "username": user.username,
            "birth_year": None,
            "language_code": user.language_code,
            "spended_token": 0,
        }

        await session.execute(
            pg_insert(UserModel)
            .values(user_id=user.id, **values)
            .on_conflict_do_nothing()
        )
        await session.commit()

    async def save_age(self, user: types.User, birth_year: int, session: AsyncSession) -> None:
        await session.execute(
            sa.update(UserModel)
            .where(UserModel.user_id == user.id)
            .values(birth_year=birth_year)
        )
        await session.commit()

    async def save_gender(self, user: types.User, gender: str, session: AsyncSession) -> None:
        await session.execute(
            sa.update(UserModel)
            .where(UserModel.user_id == user.id)
            .values(gender=gender)
        )
        await session.commit()

    async def get_gender(self, user: types.User, session: AsyncSession) -> str:
        cursor = await session.execute(
            sa.select(UserModel.gender)
            .where(UserModel.user_id == user.id)
        )
        result = cursor.fetchone()[0]
        return result

    async def calculate_age(self, birth_year: int) -> int:
        current_year = datetime.now().year
        user_age = current_year - birth_year

        return user_age


    async def get_user_gender_age(self, user: types.User, session: AsyncSession) -> tuple[str, int]:
        cursor = await session.execute(
            sa.select(UserModel.gender, UserModel.birth_year).where(
                UserModel.user_id == user.id)
        )
        user_info = cursor.fetchone()

        gender, birth_year = user_info
        if not birth_year:
            birth_year=2006

        if gender == 'male':
            gender = 'Мужской'
        elif gender == 'female':
            gender = 'Женский'
        else:
            gender = 'Не указан'

        age = await self.calculate_age(birth_year)

        return (gender, age)

    async def get_facts(self, user: types.User, session: AsyncSession) -> dict[str, str, int]:
        name = user.first_name
        gender, age = await self.get_user_gender_age(user, session)
        cursor = await session.execute(
            sa.select(UserFacts.fact_id, UserFacts.fact_key, UserFacts.fact_value).where(
                UserFacts.user_id == user.id)
        )
        facts = cursor.fetchall()

        result = {'Имя': name,'Пол': gender, 'Возраст': age}

        for fact in facts:
            result[fact[1]] = fact[2]
        return result





