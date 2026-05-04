from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginFormInput(BaseModel):
    user_name: str
    password: str


class TestResultPartialInput(BaseModel):
    key_1: str
    key_2: str
    key_3: str
    key_4: str
    form_submission_id: str | None = None
    data_writer_name: str | None = None
    is_reviewed: bool | None = None

    field_01: str | None = None
    field_02: str | None = None
    field_03: str | None = None
    field_04: str | None = None
    field_05: str | None = None
    field_06: str | None = None
    field_07: str | None = None
    field_08: str | None = None
    field_09: str | None = None
    field_10: str | None = None
    field_11: str | None = None
    field_12: str | None = None
    field_13: str | None = None
    field_14: str | None = None
    field_15: str | None = None
    field_16: str | None = None
    field_17: str | None = None
    field_18: str | None = None
    field_19: str | None = None
    field_20: str | None = None
    field_21: str | None = None

    low_test_started_at: datetime | None = None
    low_test_ended_at: datetime | None = None
    low_test_delta: str | None = None
    high_test_started_at: datetime | None = None
    high_test_ended_at: datetime | None = None
    high_test_delta: str | None = None


class TestResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    form_submission_id: str | None = None
    data_writer_name: str | None
    is_reviewed: bool
    key_1: str
    key_2: str
    key_3: str
    key_4: str
    field_01: str | None
    field_02: str | None
    field_03: str | None
    field_04: str | None
    field_05: str | None
    field_06: str | None
    field_07: str | None
    field_08: str | None
    field_09: str | None
    field_10: str | None
    field_11: str | None
    field_12: str | None
    field_13: str | None
    field_14: str | None
    field_15: str | None
    field_16: str | None
    field_17: str | None
    field_18: str | None
    field_19: str | None
    field_20: str | None
    field_21: str | None
    low_test_started_at: datetime | None
    low_test_ended_at: datetime | None
    low_test_delta: str | None
    high_test_started_at: datetime | None
    high_test_ended_at: datetime | None
    high_test_delta: str | None
    created_at: datetime
    updated_at: datetime


class TestResultDeleteInput(BaseModel):
    row_ids: list[int]


class TestResultSaveAllInput(BaseModel):
    rows: list[TestResultPartialInput]
    delete_row_ids: list[int] = []


class TestResultReviewCompleteInput(BaseModel):
    row_ids: list[int]
