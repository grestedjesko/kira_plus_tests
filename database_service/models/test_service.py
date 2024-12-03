import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .base import BaseModel

class Test(BaseModel):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    folder: Mapped[str | None] = mapped_column(sa.Text)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    welcome_image: Mapped[str | None] = mapped_column(sa.Text)
    questions_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    available_in_kira: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    test_available: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    message_after_test: Mapped[str | None] = mapped_column(sa.Text)
    prompt: Mapped[str | None] = mapped_column(sa.Text)

    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="test", cascade="all, delete-orphan"
    )

class Question(BaseModel):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(
        sa.String(255), sa.ForeignKey("tests.test_id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(sa.Text, nullable=False)
    image: Mapped[str | None] = mapped_column(sa.Text)
    question_type: Mapped[str | None] = mapped_column(sa.String(50))
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    test: Mapped["Test"] = relationship("Test", back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(
        "Answer", back_populates="question", cascade="all, delete-orphan"
    )

class Answer(BaseModel):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    answer_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    question: Mapped["Question"] = relationship("Question", back_populates="answers")

class UserResponse(BaseModel):
    __tablename__ = "user_responses"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    test_id: Mapped[str] = mapped_column(
        sa.String(255), sa.ForeignKey("tests.test_id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    answer_text: Mapped[str | None] = mapped_column(sa.Text)  # Для открытых вопросов
    answer_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("answers.id", ondelete="SET NULL")
    )  # Для закрытых вопросов

    test: Mapped["Test"] = relationship("Test")
    question: Mapped["Question"] = relationship("Question")
    answer: Mapped["Answer"] = relationship("Answer")


class Folder(BaseModel):
    __tablename__ = "folders"

    folder: Mapped[str] = mapped_column(sa.String, primary_key=True)
    title: Mapped[str] = mapped_column(sa.String, nullable=True)


class UserTimers(BaseModel):
    __tablename__ = "user_timers"

    user_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    end_time: Mapped[datetime] = mapped_column(sa.TIMESTAMP, nullable=False)