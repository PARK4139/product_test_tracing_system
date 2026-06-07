from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def get_utc_now_datetime() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "project"

    project_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    project_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_status: Mapped[str] = mapped_column(Text, nullable=False, default="ACTIVE")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectMembership(Base):
    __tablename__ = "project_membership"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
        Index("ix_project_membership_project_id", "project_id"),
        Index("ix_project_membership_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_account.id"),
        nullable=False,
    )
    membership_role: Mapped[str] = mapped_column(Text, nullable=False, default="tester")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


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


class ProductTestRelease(Base):
    __tablename__ = "product_test_release"
    __table_args__ = (
        Index("ix_product_test_release_project_id", "project_id"),
    )

    product_test_release_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
    __table_args__ = (
        Index("ix_product_test_target_definition_project_id", "project_id"),
    )

    product_test_target_definition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_target_project_id", "project_id"),
        Index("ix_product_test_target_definition_id", "product_test_target_definition_id"),
    )

    product_test_target_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
    __table_args__ = (
        Index("ix_product_test_environment_definition_project_id", "project_id"),
    )

    product_test_environment_definition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_environment_project_id", "project_id"),
        Index("ix_product_test_environment_definition_id", "product_test_environment_definition_id"),
    )

    product_test_environment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
    __table_args__ = (
        Index("ix_product_test_case_project_id", "project_id"),
    )

    product_test_case_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_procedure_project_id", "project_id"),
        Index("ix_product_test_procedure_case_id", "product_test_case_id"),
    )

    product_test_procedure_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_run_project_id", "project_id"),
        Index("ix_product_test_run_product_test_release_id", "product_test_release_id"),
        Index("ix_product_test_run_product_test_target_id", "product_test_target_id"),
        Index("ix_product_test_run_product_test_environment_id", "product_test_environment_id"),
    )

    product_test_run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_result_project_id", "project_id"),
        Index("ix_product_test_result_product_test_run_id", "product_test_run_id"),
        Index("ix_product_test_result_product_test_case_id", "product_test_case_id"),
    )

    product_test_result_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_procedure_result_project_id", "project_id"),
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
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_defect_project_id", "project_id"),
        Index("ix_product_test_defect_product_test_result_id", "product_test_result_id"),
    )

    product_test_defect_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
    expected_resolution_date: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        Index("ix_product_test_evidence_project_id", "project_id"),
        Index("ix_product_test_evidence_product_test_result_id", "product_test_result_id"),
        Index(
            "ix_product_test_evidence_product_test_procedure_result_id",
            "product_test_procedure_result_id",
        ),
    )

    product_test_evidence_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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
        Index("ix_product_test_report_project_id", "project_id"),
        Index("ix_product_test_report_product_test_release_id", "product_test_release_id"),
    )

    product_test_report_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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


class ProductTestReportSnapshot(Base):
    __tablename__ = "product_test_report_snapshot"
    __table_args__ = (
        Index("ix_product_test_report_snapshot_project_id", "project_id"),
        Index("ix_product_test_report_snapshot_product_test_report_id", "product_test_report_id"),
        Index("ix_product_test_report_snapshot_product_test_release_id", "product_test_release_id"),
        Index("ix_product_test_report_snapshot_snapshot_type", "snapshot_type"),
    )

    product_test_report_snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
    product_test_report_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_report.product_test_report_id"),
        nullable=False,
    )
    product_test_release_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("product_test_release.product_test_release_id"),
        nullable=False,
    )
    snapshot_type: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_format: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_payload: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_data_locked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductTestStatusTransition(Base):
    __tablename__ = "product_test_status_transition"
    __table_args__ = (
        Index("ix_product_test_status_transition_project_id", "project_id"),
        Index(
            "ix_product_test_status_transition_entity_type_entity_id",
            "entity_type",
            "entity_id",
        ),
    )

    product_test_status_transition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("project.project_id"),
        nullable=True,
    )
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


class WorkCalendar(Base):
    """근무일/휴무일 캘린더 — 테스트 기간 산정 기준."""
    __tablename__ = "work_calendar"
    __table_args__ = (
        Index("ix_work_calendar_date", "calendar_date"),
    )

    work_calendar_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_date: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # YYYY-MM-DD
    is_workday: Mapped[int] = mapped_column(Integer, nullable=False, default=1)    # 1=근무, 0=휴무
    day_type: Mapped[str] = mapped_column(Text, nullable=False, default="WORKDAY") # WORKDAY / HOLIDAY / WEEKEND
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class CustomSheetTab(Base):
    """탭뷰 '+' 버튼으로 사용자가 직접 만드는 스프레드시트형 커스텀 탭.

    한 행 = 탭 1개. 컬럼/행 데이터는 JSON 문자열로 저장(범용 스키마).
    columns_json: [{"key": "col_1", "label": "이름", "type": "text"}, ...]
    rows_json:    [{"col_1": "값1", "col_2": 123}, ...]
    SQLite의 json_extract / json_each 로 통계·집계 쿼리 가능.
    """
    __tablename__ = "custom_sheet_tab"
    __table_args__ = (
        Index("ix_custom_sheet_tab_region_key", "region_key"),
        UniqueConstraint("region_key", "sort_order", name="uq_custom_sheet_tab_region_sort"),
    )

    custom_sheet_tab_id: Mapped[str] = mapped_column(Text, primary_key=True)
    region_key: Mapped[str] = mapped_column(Text, nullable=False)  # configs/primary/secondary/quaternary
    tab_label: Mapped[str] = mapped_column(Text, nullable=False)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    rows_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class UiStatePref(Base):
    """브라우저 localStorage 대신 서버 DB에 저장할 수 있는 화면 UI 상태(키-값) 저장소.

    탭 순서/접기 상태/활성 탭/라벨/뷰모드 등 사용자 화면 설정을 DB에 저장해두면,
    다른 PC에서 동일 DB를 clone 했을 때도 화면 상태가 그대로 유지된다.
    pref_key 예: "sheet_tab_layout_v2", "admin_master_primary_tab" 등
    (프런트의 localStorage 키 이름을 그대로 사용).
    value_json: 저장값을 JSON 문자열로 직렬화해서 저장(문자열/객체/배열 모두 호환).
    """
    __tablename__ = "ui_state_pref"

    pref_key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, default="null")
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
