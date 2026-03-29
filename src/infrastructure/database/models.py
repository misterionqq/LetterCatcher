from typing import List
from sqlalchemy import String, Boolean, ForeignKey, BigInteger, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserModel(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    ai_sensitivity: Mapped[str] = mapped_column(String, default="medium")
    is_dnd: Mapped[bool] = mapped_column(Boolean, default=False)

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

class ProcessedEmailModel(Base):
    __tablename__ = "processed_emails"
    __table_args__ = (UniqueConstraint("user_id", "email_uid"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    email_uid: Mapped[str] = mapped_column(String)

class EmailCacheModel(Base):
    __tablename__ = "email_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text_hash: Mapped[str] = mapped_column(String, unique=True)
    is_important: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String)