from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    project_name: str
    project_version: str
    base_directory_path: Path
    data_directory_path: Path
    sqlite_database_file_path: Path
    sqlite_database_url: str


def build_app_settings() -> AppSettings:
    base_directory_path = Path(__file__).resolve().parent
    data_directory_path = base_directory_path.parent / "data"
    sqlite_database_file_path = data_directory_path / "product_test_tracking_system.db"
    sqlite_database_url = f"sqlite:///{sqlite_database_file_path.as_posix()}"
    return AppSettings(
        project_name="product_test_tracking_system",
        project_version="0.1.0",
        base_directory_path=base_directory_path,
        data_directory_path=data_directory_path,
        sqlite_database_file_path=sqlite_database_file_path,
        sqlite_database_url=sqlite_database_url,
    )


app_settings = build_app_settings()
