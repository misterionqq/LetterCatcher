from typing import List
from sqlalchemy import String, Boolean, ForeignKey, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserModel(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    ai_sensitivity: Mapped[str] = mapped_column(String, default="medium")

    keywords: Mapped[List["KeywordModel"]] = relationship(
        "KeywordModel", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

class KeywordModel(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    word: Mapped[str] = mapped_column(String)
    is_stop_word: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="keywords")