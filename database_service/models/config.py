import enum
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel


class Config(BaseModel):
    __tablename__ = "config"

    # Ключ, для поиска какого-то значения конфигурации бота
    key: Mapped[str] = mapped_column(sa.String, primary_key=True, autoincrement=True)
    # Значение конфигурации
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)