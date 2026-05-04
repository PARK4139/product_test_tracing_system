from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FormSubmission, TestResult, get_utc_now_datetime


def _dt(base: datetime, hours: int) -> datetime:
    return base + timedelta(hours=hours)


def _parse_datetime_maybe(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    s_norm = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s_norm)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc)
        # assume KST when tz is missing
        return dt.replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _load_raw_sample_lists() -> dict[str, list] | None:
    p = Path(__file__).parent / "raw_sample.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    # treat empty template as "not provided"
    any_values = False
    for v in data.values():
        if isinstance(v, list) and len(v) > 0:
            any_values = True
            break
    return data if any_values else None


def seed_sample_data(database_session: Session) -> None:
    """
    Idempotent sample seed.
    - Exactly 3 sample groups.
    - Each group: 3 rows sharing same form_submission_id.
    """

    samples = [
        ("form_sample_draft_001", "draft"),
        ("form_sample_submitted_001", "submitted"),
        ("form_sample_approved_001", "approved"),
    ]
    sample_ids = [sid for sid, _ in samples]

    # purge existing sample rows/submissions
    database_session.execute(delete(TestResult).where(TestResult.form_submission_id.in_(sample_ids)))
    database_session.execute(delete(FormSubmission).where(FormSubmission.submission_id.in_(sample_ids)))
    database_session.commit()

    now = get_utc_now_datetime()
    base = datetime.now(timezone.utc) - timedelta(days=3)

    raw_lists = _load_raw_sample_lists()

    raw_company_names = [
        "컨포커스",
        "윌템스_검안기",
        "윌템스_덴탈",
        "사이언스테라",
        "JHT",
        "윌템스",
        "컨포커스-호롭터",
    ]

    def add_submission(sid: str, status: str) -> None:
        fs = FormSubmission(submission_id=sid, status=status, created_by_phone=None)
        fs.created_at = now
        if status == "submitted":
            fs.submitted_at = now
        if status == "approved":
            fs.submitted_at = now - timedelta(hours=2)
            fs.decided_at = now
        database_session.add(fs)

        # NOTE: test_result has a UNIQUE constraint on (key_1,key_2,key_3,key_4) across the whole table.
        # Keep seed idempotent by ensuring unique quartet per row.
        draft_writers = ["홍길동", "김이서", "박재광"]
        submitted_writers = ["최민준", "정서윤", "한지우"]
        approved_writers = ["이도윤", "박서연", "김지훈"]
        rows = []
        offset = 0 if "draft" in sid else (3 if "submitted" in sid else 6)

        # If user-provided raw lists exist, seed one group with aligned rows from them (no randomization).
        if raw_lists:
            companies = raw_lists.get("업체명") or []
            models = raw_lists.get("모델명") or []
            procs = raw_lists.get("공정번호") or []
            units_list = raw_lists.get("검사대수") or []
            low_s_list = raw_lists.get("저온 투입일") or []
            low_e_list = raw_lists.get("저온 완료일") or []
            low_delta_list = raw_lists.get("저온 시간") or []
            pf1_list = raw_lists.get("PASS / FAIL1") or []
            high_s_list = raw_lists.get("고온 투입일") or []
            high_e_list = raw_lists.get("고온 완료일") or []
            high_delta_list = raw_lists.get("고온 시간") or []
            pf2_list = raw_lists.get("PASS / FAIL2") or []
            defect_list = raw_lists.get("불량내용") or []
            confirm_list = raw_lists.get("확인사항") or []
            action_list = raw_lists.get("조치사항") or []
            qty3_list = raw_lists.get("검사수량3") or []
            bad3_list = raw_lists.get("불량수량3") or []
            st_list = raw_lists.get("ST") or []
            rr_list = raw_lists.get("rr") or []
            yield_list = raw_lists.get("임율") or []
            cost_list = raw_lists.get("비용") or []

            lengths = [
                len(companies),
                len(models),
                len(procs),
                len(units_list),
                len(low_s_list),
                len(low_e_list),
                len(low_delta_list),
                len(pf1_list),
                len(high_s_list),
                len(high_e_list),
                len(high_delta_list),
                len(pf2_list),
                len(defect_list),
                len(confirm_list),
                len(action_list),
                len(qty3_list),
                len(bad3_list),
                len(st_list),
                len(rr_list),
                len(yield_list),
                len(cost_list),
            ]
            n = min([x for x in lengths if x > 0], default=0)
            if status == "draft" and n > 0:
                month = str(datetime.now().month)
                for i in range(n):
                    writer = draft_writers[i % len(draft_writers)]
                    company = str(companies[i]).strip()
                    model = str(models[i]).strip()
                    proc = str(procs[i]).strip()
                    units = str(units_list[i]).strip()
                    low_s = _parse_datetime_maybe(low_s_list[i])
                    low_e = _parse_datetime_maybe(low_e_list[i])
                    high_s = _parse_datetime_maybe(high_s_list[i])
                    high_e = _parse_datetime_maybe(high_e_list[i])
                    low_delta = str(low_delta_list[i]).rstrip("\n")
                    high_delta = str(high_delta_list[i]).rstrip("\n")

                    field_10 = "\n".join(
                        [
                            f"ST: {str(st_list[i]).rstrip()}",
                            f"rr: {str(rr_list[i]).rstrip()}",
                            f"임율: {str(yield_list[i]).rstrip()}",
                            f"비용: {str(cost_list[i]).rstrip()}",
                        ]
                    )

                    rows.append(
                        TestResult(
                            key_1=company,
                            key_2=writer,
                            key_3=model,
                            key_4=proc,
                            form_submission_id=sid,
                            data_writer_name=writer,
                            is_reviewed=False,
                            field_01=month,  # 월
                            field_02=units,  # 검사대수
                            field_03=str(pf1_list[i]).rstrip(),  # PASS/FAIL1
                            field_04=str(pf2_list[i]).rstrip(),  # PASS/FAIL2
                            field_05=str(defect_list[i]),  # 불량내용 (multiline preserved)
                            field_06=str(confirm_list[i]),  # 확인사항 (multiline preserved)
                            field_07=str(action_list[i]),  # 조치사항 (multiline preserved)
                            field_08=str(qty3_list[i]).rstrip(),  # 검사수량3
                            field_09=str(bad3_list[i]).rstrip(),  # 불량수량3
                            field_10=field_10,  # ST/rr/임율/비용 packed
                            low_test_started_at=low_s,
                            low_test_ended_at=low_e,
                            low_test_delta=low_delta,
                            high_test_started_at=high_s,
                            high_test_ended_at=high_e,
                            high_test_delta=high_delta,
                        )
                    )
                database_session.add_all(rows)
                return

        # fallback: 3 rows per submission, sample-ish fields
        for i in range(3):
            if "draft" in sid:
                writer = draft_writers[i % len(draft_writers)]
            elif "submitted" in sid:
                writer = submitted_writers[i % len(submitted_writers)]
            else:
                writer = approved_writers[i % len(approved_writers)]
            company = raw_company_names[(offset + i) % len(raw_company_names)]
            # first row matches user raw sample timestamps (KST-ish; stored as tz-aware UTC here)
            if i == 0 and "draft" in sid:
                low_s = datetime(2025, 2, 10, 11, 0, tzinfo=timezone.utc)
                low_e = datetime(2025, 2, 11, 10, 0, tzinfo=timezone.utc)
                high_s = datetime(2025, 2, 11, 10, 10, tzinfo=timezone.utc)
                high_e = datetime(2025, 2, 11, 18, 30, tzinfo=timezone.utc)
                low_delta = "23:00"
                high_delta = "8:20"
                model = "HBM-1"
                proc = "2502-H009"
                month = "2"
                units = "1"
            else:
                low_s = _dt(base, i * 2)
                low_e = _dt(base, i * 2 + 1)
                high_s = _dt(base, i * 2 + 2)
                high_e = _dt(base, i * 2 + 3)
                low_delta = "01:00:00"
                high_delta = "01:00:00"
                model = f"{sid}_MODEL-{i+1}"
                proc = f"{sid}_PROC-{i+1}"
                month = "2"
                units = "1"
            rows.append(
                TestResult(
                    key_1=company,
                    key_2=writer,
                    key_3=model,
                    key_4=proc,
                    form_submission_id=sid,
                    data_writer_name=writer,
                    is_reviewed=(status == "approved"),
                    field_01=month,
                    field_02=units,
                    low_test_started_at=low_s,
                    low_test_ended_at=low_e,
                    low_test_delta=low_delta,
                    high_test_started_at=high_s,
                    high_test_ended_at=high_e,
                    high_test_delta=high_delta,
                )
            )
        database_session.add_all(rows)

    for sid, status in samples:
        add_submission(sid, status)

    database_session.commit()

