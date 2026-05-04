from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def get_utc_now_datetime() -> datetime:
    return datetime.now(timezone.utc)


class FormSubmission(Base):
    __tablename__ = "form_submission"

    submission_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_by_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        onupdate=get_utc_now_datetime,
        nullable=False,
    )


class UserAccount(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        onupdate=get_utc_now_datetime,
        nullable=False,
    )


class TestResult(Base):
    __tablename__ = "test_result"
    __table_args__ = (
        UniqueConstraint(
            "form_submission_id",
            "key_1",
            "key_2",
            "key_3",
            "key_4",
            name="uq_test_result_submission_key_quintet",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Natural key: 업체명, 양식제출자, 모델명, 공정번호 (MVP: key_1~key_3 + data_writer/역할 재배치됨)
    key_1: Mapped[str] = mapped_column(Text, nullable=False)
    key_2: Mapped[str] = mapped_column(Text, nullable=False)
    key_3: Mapped[str] = mapped_column(Text, nullable=False)
    key_4: Mapped[str] = mapped_column(Text, nullable=False)
    submission_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_submission_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_writer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_reviewed: Mapped[bool] = mapped_column(nullable=False, default=False)

    field_01: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_02: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_03: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_04: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_05: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_06: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_07: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_08: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_09: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_10: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_11: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_12: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_13: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_14: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_15: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_16: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_17: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_18: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_19: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_20: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_21: Mapped[str | None] = mapped_column(Text, nullable=True)

    low_test_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    low_test_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    low_test_delta: Mapped[str | None] = mapped_column(Text, nullable=True)
    high_test_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    high_test_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    high_test_delta: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        onupdate=get_utc_now_datetime,
        nullable=False,
    )


class DropdownOption(Base):
    __tablename__ = "dropdown_option"
    __table_args__ = (
        UniqueConstraint("field_name", "option_value", name="uq_dropdown_option_field_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    option_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        nullable=False,
    )


class UiSampleProfile(Base):
    __tablename__ = "ui_sample_profile"

    profile_key: Mapped[str] = mapped_column(Text, primary_key=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(Text, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now_datetime,
        onupdate=get_utc_now_datetime,
        nullable=False,
    )
