from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UiSampleProfile


DEFAULT_UI_SAMPLE_PROFILES = {
    "A": {
        "company_name": "에이원옵틱",
        "display_name": "이준호",
        "phone_number": "010-3139-3872",
        "password": "a1b2c3d4e5",
    },
    "B": {
        "company_name": "메디테크",
        "display_name": "김영희",
        "phone_number": "010-4242-5252",
        "password": "b1c2d3e4f5",
    },
}


def ensure_default_ui_sample_profiles(database_session: Session) -> None:
    for profile_key, profile_value in DEFAULT_UI_SAMPLE_PROFILES.items():
        existing_row = database_session.get(UiSampleProfile, profile_key)
        if existing_row is None:
            database_session.add(
                UiSampleProfile(
                    profile_key=profile_key,
                    company_name=profile_value["company_name"],
                    display_name=profile_value["display_name"],
                    phone_number=profile_value["phone_number"],
                    password=profile_value["password"],
                )
            )
            continue
        existing_row.company_name = profile_value["company_name"]
        existing_row.display_name = profile_value["display_name"]
        existing_row.phone_number = profile_value["phone_number"]
        existing_row.password = profile_value["password"]
    database_session.commit()


def list_ui_sample_profiles_map(database_session: Session) -> dict[str, dict[str, str]]:
    rows = database_session.scalars(
        select(UiSampleProfile).order_by(UiSampleProfile.profile_key.asc())
    )
    sample_profiles_map: dict[str, dict[str, str]] = {}
    for row in rows:
        sample_profiles_map[row.profile_key] = {
            "company_name": row.company_name,
            "display_name": row.display_name,
            "phone_number": row.phone_number,
            "password": row.password,
        }
    return sample_profiles_map
