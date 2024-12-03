import enum
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel
from datetime import datetime

class UserUsage(BaseModel):
    # Таблица для проверки использования лимитов каждым пользователем
    __tablename__ = "user_usage"

    # Идентификатор пользователя
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    # Дата
    date: Mapped[datetime] = mapped_column(sa.Date, unique=True, primary_key=True)
    # Использовано сообщений
    message_usage: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Использовано токенов
    tokens_usage: Mapped[int] = mapped_column(sa.Integer, nullable=False)