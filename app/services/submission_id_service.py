import datetime as _dt
import re


def normalize_company_name(company_name: str) -> str:
    raw = (company_name or "").strip()
    if not raw:
        return "no_company"
    # 기존 form_* 관례에 맞게 공백 제거 + 안전 문자만 유지
    compact = re.sub(r"\s+", "", raw)
    safe = re.sub(r"[^0-9A-Za-z가-힣-]+", "", compact)
    normalized = safe or "no_company"
    # form_submission_id now uses "_" as segment delimiter.
    # Ensure a segment can never contain "_" itself.
    return normalized.replace("_", "-")


def normalize_id_segment(value: str, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    compact = re.sub(r"\s+", "", raw)
    safe = re.sub(r"[^0-9A-Za-z가-힣-]+", "", compact)
    normalized = safe or fallback
    return normalized.replace("_", "-")


def today_yyyymmdd() -> str:
    now = _dt.datetime.now(_dt.timezone.utc).astimezone()
    return now.strftime("%Y%m%d")
