from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, BigInteger, Integer, UniqueConstraint, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_sensitivity: Mapped[str] = mapped_column(String, default="medium")
    is_dnd: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    keywords: Mapped[List["KeywordModel"]] = relationship(
        "KeywordModel", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

class KeywordModel(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word: Mapped[str] = mapped_column(String)
    is_stop_word: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="keywords")

class ProcessedEmailModel(Base):
    __tablename__ = "processed_emails"
    __table_args__ = (UniqueConstraint("user_id", "email_uid"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    email_uid: Mapped[str] = mapped_column(String)
    sender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    email_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    body_full: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="")
    triggered_word: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    links: Mapped[Optional[str]] = mapped_column(Text, nullable=True)         # JSON array
    attachments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON array

class DeviceTokenModel(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("user_id", "token"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String, index=True)
    platform: Mapped[str] = mapped_column(String, default="android")  # android / ios / web
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VerificationTokenModel(Base):
    __tablename__ = "verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    token_type: Mapped[str] = mapped_column(String)  # email_verify | password_reset | email_change
    payload: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EmailCacheModel(Base):
    __tablename__ = "email_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text_hash: Mapped[str] = mapped_column(String, unique=True)
    is_important: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String)

class PendingNotificationModel(Base):
    __tablename__ = "pending_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    email_uid: Mapped[str] = mapped_column(String)
    sender: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body_snippet: Mapped[str] = mapped_column(String)
    body_full: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    links: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # JSON array
    attachments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    ai_reason: Mapped[str] = mapped_column(String, default="")
    triggered_word: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
