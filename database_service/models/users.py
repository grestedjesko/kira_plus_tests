import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel  # Импортируем базовый класс

class UserModel(BaseModel):
    __tablename__ = "users"

    # Поля таблицы, специфичные для модели User
    user_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)  # Уникальный идентификатор пользователя
    first_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)  # Имя пользователя
    username: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)  # Username пользователя (необязательное)
    birth_year: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)  # Год рождения пользователя (тип DATE)
    language_code: Mapped[str | None] = mapped_column(sa.String(5), nullable=True)  # Код языка пользователя (макс. 5 символов)
    gender: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    spended_token: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)  # Количество использованных токенов


    # Уникальные ограничения и другие параметры (при необходимости)
    __table_args__ = (
        sa.UniqueConstraint("user_id", name="unique_user_id"),  # Уникальный user_id
    )
