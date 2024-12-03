import enum
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel


class OpenaiContext(BaseModel):
    __tablename__ = "openai_context"

    # Идентификатор сообщения
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    # Идентификатор чата (message.chat.id)
    chat_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    # Идентификатор пользователя для определения чье сообщение (message.from_user.id)
    author_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    # Текст сообщения
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)