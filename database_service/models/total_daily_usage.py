import enum
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel
from datetime import datetime


class TotalDailyUsage(BaseModel):
    # Таблица с общим количеством использованных токенов и сообщений за день

    __tablename__ = "total_daily_usage"

    # Дата
    date: Mapped[datetime] = mapped_column(sa.Date, unique=True, primary_key=True)
    # Использовано токенов
    tokens_usage: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Использовано сообщений
    message_usage: Mapped[int] = mapped_column(sa.Integer, nullable=False)