from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
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


class ProductTestRelease(Base):
    __tablename__ = "product_test_release"

    product_test_release_id: Mapped[str] = mapped_column(Text, primary_key=True)
    upstream_release_id: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_release_system: Mapped[str] = mapped_column(Text, nullable=False)
    release_stage: Mapped[str] = mapped_column(Text, nullable=False)
    release_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    product_test_release_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestTargetDefinition(Base):
    __tablename__ = "product_test_target_definition"

    product_test_target_definition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_code: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    hardware_revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_software_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_firmware_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_test_target_definition_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestTarget(Base):
    __tablename__ = "product_test_target"
    __table_args__ = (
        Index("ix_product_test_target_definition_id", "product_test_target_definition_id"),
    )

    product_test_target_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_target_definition_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_target_definition.product_test_target_definition_id"),
        nullable=False,
    )
    serial_number: Mapped[str] = mapped_column(Text, nullable=False)
    software_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacture_lot: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_test_target_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestEnvironmentDefinition(Base):
    __tablename__ = "product_test_environment_definition"

    product_test_environment_definition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_environment_definition_name: Mapped[str] = mapped_column(Text, nullable=False)
    test_country: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_company: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_building: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_floor: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_room: Mapped[str | None] = mapped_column(Text, nullable=True)
    network_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_computer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    operating_system_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_tool_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_tool_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_voltage: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_connector_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_test_environment_definition_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestEnvironment(Base):
    __tablename__ = "product_test_environment"
    __table_args__ = (
        Index("ix_product_test_environment_definition_id", "product_test_environment_definition_id"),
    )

    product_test_environment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_environment_definition_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            "product_test_environment_definition.product_test_environment_definition_id"
        ),
        nullable=False,
    )
    product_test_environment_name: Mapped[str] = mapped_column(Text, nullable=False)
    test_computer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    operating_system_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_tool_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    network_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_voltage: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_connector_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_test_environment_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestCase(Base):
    __tablename__ = "product_test_case"

    product_test_case_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_case_title: Mapped[str] = mapped_column(Text, nullable=False)
    test_category: Mapped[str] = mapped_column(Text, nullable=False)
    test_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    precondition: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_test_case_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestProcedure(Base):
    __tablename__ = "product_test_procedure"
    __table_args__ = (
        Index("ix_product_test_procedure_case_id", "product_test_case_id"),
    )

    product_test_procedure_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_case_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_case.product_test_case_id"),
        nullable=False,
    )
    procedure_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    procedure_action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    required_evidence_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_test_procedure_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestRun(Base):
    __tablename__ = "product_test_run"
    __table_args__ = (
        Index("ix_product_test_run_product_test_release_id", "product_test_release_id"),
        Index("ix_product_test_run_product_test_target_id", "product_test_target_id"),
        Index("ix_product_test_run_product_test_environment_id", "product_test_environment_id"),
    )

    product_test_run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_release_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_release.product_test_release_id"),
        nullable=False,
    )
    product_test_target_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_target.product_test_target_id"),
        nullable=False,
    )
    product_test_environment_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_environment.product_test_environment_id"),
        nullable=False,
    )
    product_test_run_status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_by: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestResult(Base):
    __tablename__ = "product_test_result"
    __table_args__ = (
        Index("ix_product_test_result_product_test_run_id", "product_test_run_id"),
        Index("ix_product_test_result_product_test_case_id", "product_test_case_id"),
    )

    product_test_result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_run.product_test_run_id"),
        nullable=False,
    )
    product_test_case_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_case.product_test_case_id"),
        nullable=False,
    )
    product_test_result_status: Mapped[str] = mapped_column(Text, nullable=False)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    judgement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_judged_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_judged_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestProcedureResult(Base):
    __tablename__ = "product_test_procedure_result"
    __table_args__ = (
        Index(
            "ix_product_test_procedure_result_product_test_result_id",
            "product_test_result_id",
        ),
        Index(
            "ix_product_test_procedure_result_product_test_procedure_id",
            "product_test_procedure_id",
        ),
    )

    product_test_procedure_result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_result_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_result.product_test_result_id"),
        nullable=False,
    )
    product_test_procedure_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_procedure.product_test_procedure_id"),
        nullable=False,
    )
    product_test_procedure_result_status: Mapped[str] = mapped_column(Text, nullable=False)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    judgement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    judged_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    judged_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestDefect(Base):
    __tablename__ = "product_test_defect"
    __table_args__ = (
        Index("ix_product_test_defect_product_test_result_id", "product_test_result_id"),
    )

    product_test_defect_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_result_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_result.product_test_result_id"),
        nullable=False,
    )
    product_test_procedure_result_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("product_test_procedure_result.product_test_procedure_result_id"),
        nullable=True,
    )
    defect_title: Mapped[str] = mapped_column(Text, nullable=False)
    defect_description: Mapped[str] = mapped_column(Text, nullable=False)
    defect_severity: Mapped[str] = mapped_column(Text, nullable=False)
    defect_priority: Mapped[str] = mapped_column(Text, nullable=False)
    product_test_defect_status: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    retest_product_test_result_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("product_test_result.product_test_result_id"),
        nullable=True,
    )
    retested_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    retested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestEvidence(Base):
    __tablename__ = "product_test_evidence"
    __table_args__ = (
        Index("ix_product_test_evidence_product_test_result_id", "product_test_result_id"),
        Index(
            "ix_product_test_evidence_product_test_procedure_result_id",
            "product_test_procedure_result_id",
        ),
    )

    product_test_evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_result_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_result.product_test_result_id"),
        nullable=False,
    )
    product_test_procedure_result_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("product_test_procedure_result.product_test_procedure_result_id"),
        nullable=True,
    )
    product_test_defect_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("product_test_defect.product_test_defect_id"),
        nullable=True,
    )
    product_test_evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestReport(Base):
    __tablename__ = "product_test_report"
    __table_args__ = (
        Index("ix_product_test_report_product_test_release_id", "product_test_release_id"),
    )

    product_test_report_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_test_release_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_release.product_test_release_id"),
        nullable=False,
    )
    product_test_report_type: Mapped[str] = mapped_column(Text, nullable=False)
    product_test_report_status: Mapped[str] = mapped_column(Text, nullable=False)
    product_test_report_title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestStatusTransition(Base):
    __tablename__ = "product_test_status_transition"
    __table_args__ = (
        Index(
            "ix_product_test_status_transition_entity_type_entity_id",
            "entity_type",
            "entity_id",
        ),
    )

    product_test_status_transition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    transition_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    transitioned_at: Mapped[str] = mapped_column(Text, nullable=False)
    transitioned_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
