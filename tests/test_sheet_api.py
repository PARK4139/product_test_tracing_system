from __future__ import annotations

from sqlalchemy import text


def _get_db_counts() -> dict[str, int]:
    from app.db import session_local
    from app.services.sheet_service import (
        _extract_case_topology,
        _extract_combo,
        _is_comparable_case_topology,
    )
    from app.services.topology_normalize import normalize_combo

    with session_local() as database_session:
        result_rows = database_session.execute(
            text(
                """
                SELECT
                    r.product_test_result_id,
                    r.product_test_case_id,
                    r.remark,
                    COUNT(DISTINCT e.product_test_evidence_id) AS evidence_count
                FROM product_test_result r
                LEFT JOIN product_test_evidence e
                  ON e.product_test_result_id = r.product_test_result_id
                GROUP BY
                    r.product_test_result_id,
                    r.product_test_case_id,
                    r.remark
                """
            )
        ).mappings().all()
        release_counts = database_session.execute(
            text(
                """
                SELECT
                    SUM(CASE WHEN test_round_id IS NULL THEN 1 ELSE 0 END) AS releases_without_round_count,
                    (
                        SELECT COUNT(*)
                        FROM product_test_round round
                        LEFT JOIN product_test_release rel
                          ON rel.test_round_id = round.test_round_id
                        WHERE rel.product_test_release_id IS NULL
                    ) AS rounds_without_release_count
                FROM product_test_release
                """
            )
        ).mappings().one()
        topology_mismatch_count = 0
        evidence_missing_count = 0
        parsed_combo_count = 0
        for row in result_rows:
            combo = normalize_combo(_extract_combo(row["remark"]))
            case_topology = _extract_case_topology(row["product_test_case_id"])
            if combo:
                parsed_combo_count += 1
            if int(row["evidence_count"] or 0) == 0:
                evidence_missing_count += 1
            if combo and _is_comparable_case_topology(row["product_test_case_id"], case_topology) and case_topology != combo:
                topology_mismatch_count += 1
        return {
            "topology_mismatch_count": topology_mismatch_count,
            "evidence_missing_count": evidence_missing_count,
            "parsed_combo_count": parsed_combo_count,
            "releases_without_round_count": int(release_counts["releases_without_round_count"] or 0),
            "rounds_without_release_count": int(release_counts["rounds_without_release_count"] or 0),
        }


def _get_first_opened_defect() -> tuple[str, str, str]:
    from app.db import session_local

    with session_local() as database_session:
        row = database_session.execute(
            text(
                """
                SELECT product_test_defect_id, product_test_defect_status, product_test_result_id
                FROM product_test_defect
                ORDER BY product_test_defect_id
                LIMIT 1
                """
            )
        ).one()
        return str(row[0]), str(row[1]), str(row[2])


def _count_status_transitions(entity_type: str, entity_id: str) -> int:
    from app.db import session_local

    with session_local() as database_session:
        return int(
            database_session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM product_test_status_transition
                    WHERE entity_type = :entity_type
                      AND entity_id = :entity_id
                    """
                ),
                {"entity_type": entity_type, "entity_id": entity_id},
            ).scalar_one()
            or 0
        )


def test_sheet_result_and_release_summaries_match_db(seeded_wifi_ap_db):
    counts = _get_db_counts()

    result_response = seeded_wifi_ap_db.get("/admin/api/sheet/result", headers={"x-user-role": "tester"})
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["table"] == "result"
    assert result_payload["summary"]["flag_counts"].get("topology_mismatch", 0) == counts["topology_mismatch_count"]
    assert result_payload["summary"]["flag_counts"].get("evidence_missing", 0) == counts["evidence_missing_count"]
    assert result_payload["summary"]["parsed_combo_count"] == counts["parsed_combo_count"]

    release_response = seeded_wifi_ap_db.get("/admin/api/sheet/release", headers={"x-user-role": "tester"})
    assert release_response.status_code == 200
    release_payload = release_response.json()
    assert release_payload["table"] == "release"
    assert release_payload["summary"]["flag_counts"].get("round_missing", 0) == counts["releases_without_round_count"]
    assert release_payload["summary"]["rounds_without_release_count"] == counts["rounds_without_release_count"]


def test_sheet_case_and_evidence_endpoints_return_expected_shape(seeded_wifi_ap_db):
    case_response = seeded_wifi_ap_db.get("/admin/api/sheet/case", headers={"x-user-role": "tester"})
    assert case_response.status_code == 200
    case_payload = case_response.json()
    assert case_payload["table"] == "case"
    assert case_payload["summary"]["row_count"] == len(case_payload["rows"])
    assert {"id", "title", "status", "flags"} <= set(case_payload["rows"][0])

    evidence_response = seeded_wifi_ap_db.get("/admin/api/sheet/evidence", headers={"x-user-role": "tester"})
    assert evidence_response.status_code == 200
    evidence_payload = evidence_response.json()
    assert evidence_payload["table"] == "evidence"
    assert evidence_payload["summary"]["missing_evidence_result_count"] >= 0


def test_sheet_endpoint_rejects_unknown_table(client):
    response = client.get("/admin/api/sheet/unknown", headers={"x-user-role": "tester"})
    assert response.status_code == 404
    assert "Unsupported sheet table" in response.json()["detail"]


def test_sheet_defect_preview_and_apply_creates_transition(seeded_wifi_ap_db):
    defect_id, defect_status, result_id = _get_first_opened_defect()
    assert defect_status == "opened"
    before_transition_count = _count_status_transitions("product_test_defect", defect_id)

    evidence_payload = {
        "result_id": result_id,
        "defect_id": defect_id,
        "evidence_type": "log",
        "file_path": f"/evidence/2026/06/08/{defect_id.lower()}_guard_log.txt",
        "file_name": f"{defect_id.lower()}_guard_log.txt",
        "file_hash": f"guard-{defect_id.lower()}",
        "captured_at": "2026-06-08 21:05",
        "remark": "[원본] defect guard evidence",
    }
    evidence_preview_response = seeded_wifi_ap_db.post(
        "/admin/api/sheet/evidence",
        headers={"x-user-role": "admin"},
        json=dict(evidence_payload, mode="preview"),
    )
    assert evidence_preview_response.status_code == 200
    evidence_preview_payload = evidence_preview_response.json()
    evidence_apply_response = seeded_wifi_ap_db.post(
        "/admin/api/sheet/evidence",
        headers={"x-user-role": "admin"},
        json=dict(evidence_payload, mode="apply", preview_hash=evidence_preview_payload["preview_hash"]),
    )
    assert evidence_apply_response.status_code == 200

    preview_response = seeded_wifi_ap_db.patch(
        f"/admin/api/sheet/defect/{defect_id}",
        headers={"x-user-role": "admin"},
        json={
            "mode": "preview",
            "changes": {"status": "ASSIGNED", "assigned_to": "Tester-B"},
            "reason": "test_sheet_apply",
        },
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["changed_count"] == 2
    assert {item["field"] for item in preview_payload["diff"]} == {"status", "assigned_to"}

    apply_response = seeded_wifi_ap_db.patch(
        f"/admin/api/sheet/defect/{defect_id}",
        headers={"x-user-role": "admin"},
        json={
            "mode": "apply",
            "changes": {"status": "ASSIGNED", "assigned_to": "Tester-B"},
            "preview_hash": preview_payload["preview_hash"],
            "reason": "test_sheet_apply",
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["changed_count"] == 2
    assert _count_status_transitions("product_test_defect", defect_id) == before_transition_count + 1


def test_sheet_evidence_create_preview_and_apply(seeded_wifi_ap_db):
    payload = {
        "result_id": "SQA_PRODUCT_TEST_RESULT_ID-20260504-0001",
        "procedure_result_id": "SQA_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0001",
        "evidence_type": "log",
        "file_path": "/evidence/2026/06/08/manual_log.txt",
        "file_name": "manual_log.txt",
        "file_hash": "abc123",
        "captured_at": "2026-06-08 21:00",
        "remark": "[원본] manual upload",
    }
    preview_response = seeded_wifi_ap_db.post(
        "/admin/api/sheet/evidence",
        headers={"x-user-role": "admin"},
        json=dict(payload, mode="preview"),
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["changed_count"] >= 4

    apply_response = seeded_wifi_ap_db.post(
        "/admin/api/sheet/evidence",
        headers={"x-user-role": "admin"},
        json=dict(payload, mode="apply", preview_hash=preview_payload["preview_hash"]),
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["table"] == "evidence"

    evidence_response = seeded_wifi_ap_db.get("/admin/api/sheet/evidence", headers={"x-user-role": "tester"})
    evidence_payload = evidence_response.json()
    assert any(row["file_path"] == payload["file_path"] for row in evidence_payload["rows"])
