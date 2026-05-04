from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DropdownOption


DROPDOWN_FIELD_NAMES = [
    "key_1",
    "key_2",
    "key_3",
    "key_4",
    "field_01",
    "field_02",
    "field_03",
]

DEFAULT_DROPDOWN_OPTIONS: dict[str, list[str]] = {
    "key_1": [
        "HUVITZ",
        "메디테크",
        "에이원옵틱",
    ],
    "key_3": [
        "HRT-7000",
        "HRT-8000",
        "HLM-9000",
    ],
    "key_4": [
        "P-100",
        "P-200",
        "P-300",
    ],
}


def list_dropdown_options_map(database_session: Session) -> dict[str, list[str]]:
    rows = database_session.scalars(
        select(DropdownOption).order_by(
            DropdownOption.field_name.asc(),
            DropdownOption.option_value.asc(),
        )
    )
    options_map: dict[str, list[str]] = {field_name: [] for field_name in DROPDOWN_FIELD_NAMES}
    for row in rows:
        if row.field_name not in options_map:
            continue
        options_map[row.field_name].append(row.option_value)
    return options_map


def add_dropdown_option_if_missing(
    database_session: Session,
    field_name: str,
    option_value: str,
) -> bool:
    normalized_field_name = field_name.strip()
    normalized_option_value = option_value.strip()
    if normalized_field_name not in DROPDOWN_FIELD_NAMES:
        raise ValueError("지원하지 않는 필드입니다.")
    if not normalized_option_value:
        raise ValueError("옵션 값을 입력해 주세요.")

    existing_row = database_session.scalar(
        select(DropdownOption).where(
            DropdownOption.field_name == normalized_field_name,
            DropdownOption.option_value == normalized_option_value,
        )
    )
    if existing_row is not None:
        return False

    database_session.add(
        DropdownOption(
            field_name=normalized_field_name,
            option_value=normalized_option_value,
        )
    )
    database_session.commit()
    return True


def delete_dropdown_option_if_exists(
    database_session: Session,
    field_name: str,
    option_value: str,
) -> bool:
    normalized_field_name = field_name.strip()
    normalized_option_value = option_value.strip()
    if normalized_field_name not in DROPDOWN_FIELD_NAMES:
        raise ValueError("지원하지 않는 필드입니다.")
    if not normalized_option_value:
        raise ValueError("옵션 값을 입력해 주세요.")

    result = database_session.execute(
        delete(DropdownOption).where(
            DropdownOption.field_name == normalized_field_name,
            DropdownOption.option_value == normalized_option_value,
        )
    )
    database_session.commit()
    return bool(result.rowcount)


def list_dropdown_options_for_field(database_session: Session, field_name: str) -> list[str]:
    normalized_field_name = field_name.strip()
    if normalized_field_name not in DROPDOWN_FIELD_NAMES:
        raise ValueError("지원하지 않는 필드입니다.")
    rows = database_session.scalars(
        select(DropdownOption.option_value)
        .where(DropdownOption.field_name == normalized_field_name)
        .order_by(DropdownOption.option_value.asc())
    )
    return list(rows)


def ensure_default_dropdown_options(database_session: Session) -> None:
    changed = False
    for field_name, option_values in DEFAULT_DROPDOWN_OPTIONS.items():
        if field_name not in DROPDOWN_FIELD_NAMES:
            continue
        for option_value in option_values:
            normalized_option_value = str(option_value or "").strip()
            if not normalized_option_value:
                continue
            existing_row = database_session.scalar(
                select(DropdownOption).where(
                    DropdownOption.field_name == field_name,
                    DropdownOption.option_value == normalized_option_value,
                )
            )
            if existing_row is not None:
                continue
            database_session.add(
                DropdownOption(
                    field_name=field_name,
                    option_value=normalized_option_value,
                )
            )
            changed = True
    if changed:
        database_session.commit()
