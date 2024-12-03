import enum
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel
from datetime import datetime

class UserFacts(BaseModel):
    # Таблица с фактами о пользователях
    __tablename__ = "user_facts"

    # Идентификатор факта
    fact_id: Mapped[int] = mapped_column(sa.Integer, nullable=False, primary_key=True)
    # Идентификатор пользователя (message.from_user.id)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, primary_key=True)
    # Название факта/теста (например: Тест на абьюзивные отношения)
    fact_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    # Значение факта/результата теста (например: Склонен к абьюзивным отношениям)
    fact_value: Mapped[str] = mapped_column(sa.Text, nullable=False)

