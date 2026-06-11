"""TASK 15-5 code sync: product_test_release -> test_round_id (atomic writes)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def atomic_write(path: Path, content: str) -> None:
    if not content.strip():
        raise ValueError(f"refusing empty write: {path}")
    tmp = path.with_suffix(path.suffix + ".tmp15_5")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    raw = path.read_bytes().rstrip(b"\x00")
    path.write_bytes(raw)


def sync_run_service(text: str) -> str:
    text = text.replace("ProductTestRelease,", "ProductTestRound,")
    text = text.replace(
        '    "product_test_release",\n    "product_test_run",',
        '    "product_test_run",',
    )
    text = re.sub(
        r'\n    "product_test_release": \{[^}]+\},\n',
        "\n",
        text,
        count=1,
    )
    text = re.sub(
        r"_sample_product_test_release_rows = \[[\s\S]*?\]\n\n",
        "",
        text,
        count=1,
    )
    text = text.replace('"product_test_release": ProductTestRelease,', "")
    text = text.replace("_raise_locked_release_error", "_raise_locked_round_error")
    text = text.replace(
        "This Product Test Release has an approved Product Test Report.",
        "This test round has an approved Product Test Report.",
    )
    text = text.replace("_release_is_locked", "_round_is_locked")
    text = text.replace("_ensure_release_not_locked_for_source_mutation", "_ensure_round_not_locked_for_source_mutation")
    text = text.replace("product_test_release_id:", "test_round_id:")
    text = text.replace("product_test_release_id=", "test_round_id=")
    text = text.replace("ProductTestReport.product_test_release_id", "ProductTestReport.test_round_id")
    text = text.replace("ProductTestRun.product_test_release_id", "ProductTestRun.test_round_id")
    text = text.replace("run_row.product_test_release_id", "run_row.test_round_id")
    text = text.replace("report_row.product_test_release_id", "report_row.test_round_id")
    text = text.replace("_collect_release_graph", "_collect_round_graph")
    text = text.replace('graph["release"]', 'graph["round"]')
    text = text.replace("release_summary", "round_summary")
    text = text.replace("list_release_options", "list_round_options")
    text = text.replace("release_options", "round_options")
    text = text.replace("locked_release_count", "locked_round_count")
    text = text.replace('"wifi_release"', '"wifi_round"')
    text = text.replace("get_release_id_by_run_id", "get_test_round_id_by_run_id")
    text = text.replace("get_release_id_by_result_id", "get_test_round_id_by_result_id")
    text = text.replace("Unknown product_test_release_id.", "Unknown test_round_id.")
    text = text.replace("product_test_release_id and product_test_report_title", "test_round_id and product_test_report_title")
    text = text.replace("Open defects exist for this release.", "Open defects exist for this round.")
    text = text.replace("Snapshots belong to different product_test_release_id values.", "Snapshots belong to different test_round_id values.")
    text = text.replace('entity_type == "product_test_release"', 'entity_type == "product_test_round"')
    text = text.replace("Release Summary", "Round Summary")

    text = text.replace(
        "def list_product_test_releases(database_session: Session) -> list[dict[str, Any]]:\n"
        "    return _list_rows_as_dicts(\n"
        "        database_session,\n"
        "        model=ProductTestRelease,\n"
        "        columns=[\n"
        '            "product_test_release_id",\n'
        '            "upstream_release_id",\n'
        '            "upstream_release_system",\n'
        '            "release_stage",\n'
        '            "release_sequence",\n'
        '            "product_test_release_status",\n'
        '            "created_at",\n'
        '            "created_by",\n'
        '            "updated_at",\n'
        '            "updated_by",\n'
        '            "remark",\n'
        "        ],\n"
        '        order_by_column="created_at",\n'
        "    )\n",
        "def list_product_test_rounds(database_session: Session) -> list[dict[str, Any]]:\n"
        "    return _list_rows_as_dicts(\n"
        "        database_session,\n"
        "        model=ProductTestRound,\n"
        "        columns=[\n"
        '            "test_round_id",\n'
        '            "test_round_name",\n'
        '            "workday",\n'
        '            "start_date",\n'
        '            "end_date",\n'
        '            "date_quality",\n'
        '            "migration_status",\n'
        '            "created_at",\n'
        '            "created_by",\n'
        '            "updated_at",\n'
        '            "updated_by",\n'
        "        ],\n"
        '        order_by_column="test_round_id",\n'
        "    )\n",
    )
    text = text.replace(
        "def list_release_options(database_session: Session) -> list[dict[str, Any]]:\n"
        "    return list_product_test_releases(database_session)\n",
        "def list_round_options(database_session: Session) -> list[dict[str, Any]]:\n"
        "    return list_product_test_rounds(database_session)\n",
    )
    text = re.sub(
        r"def create_product_test_release\([\s\S]*?^\)\n\n",
        "",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = text.replace(
        "def _collect_round_graph(database_session: Session, test_round_id: str) -> dict[str, Any]:\n"
        "    release_row = database_session.get(ProductTestRelease, test_round_id)",
        "def _collect_round_graph(database_session: Session, test_round_id: str) -> dict[str, Any]:\n"
        "    round_row = database_session.get(ProductTestRound, test_round_id)",
    )
    text = text.replace('"release": release_row,', '"round": round_row,')
    text = text.replace(
        "    release = database_session.get(ProductTestRelease, str(test_round_id or \"\").strip())\n"
        "    target = database_session.get(ProductTestTargetUnified, str(product_test_target_id or \"\").strip())\n"
        "    environment = database_session.get(ProductTestEnvironment, str(product_test_environment_id or \"\").strip())\n"
        "    if release is None:\n"
        "        raise ValueError(\"Unknown test_round_id.\")\n",
        "    round_row = database_session.get(ProductTestRound, str(test_round_id or \"\").strip())\n"
        "    target = database_session.get(ProductTestTargetUnified, str(product_test_target_id or \"\").strip())\n"
        "    environment = database_session.get(ProductTestEnvironment, str(product_test_environment_id or \"\").strip())\n"
        "    if round_row is None:\n"
        "        raise ValueError(\"Unknown test_round_id.\")\n",
    )
    text = text.replace(
        "        test_round_id=release.test_round_id,\n",
        "        test_round_id=round_row.test_round_id,\n",
    )
    text = text.replace(
        "    if database_session.get(ProductTestRelease, test_round_id) is None:\n",
        "    if database_session.get(ProductTestRound, test_round_id) is None:\n",
    )
    text = text.replace(
        '        "wifi_round": database_session.get(ProductTestRelease, "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1") is not None,',
        '        "wifi_round": database_session.get(ProductTestRound, "ROUND-WIFI_1ST") is not None,',
    )
    text = text.replace('"product_test_release_id"', '"test_round_id"')
    text = text.replace("product_test_release_status", "migration_status")
    return text


def sync_tracking_router(text: str) -> str:
    text = text.replace("ProductTestRelease, get_utc_now_datetime", "get_utc_now_datetime")
    text = text.replace("run.product_test_release_id", "run.test_round_id")
    text = text.replace("run2.product_test_release_id", "run2.test_round_id")
    text = text.replace("product_test_release_id", "test_round_id")
    text = text.replace("product_test_release_status", "migration_status")
    text = text.replace("FROM product_test_release r", "FROM product_test_round r")
    text = text.replace("r.product_test_release_id", "r.test_round_id")
    text = text.replace("r.release_stage", "r.migration_status")
    text = text.replace("r.upstream_release_id", "r.test_round_name")
    text = text.replace("r.upstream_release_system", "''")
    text = text.replace("COALESCE(r.release_visible, 1)", "1")
    text = text.replace("WHERE (r.migration_status IS NULL OR r.migration_status != 'round_legacy')", "")
    text = text.replace("ORDER BY r.release_sequence, r.test_round_id", "ORDER BY r.test_round_id")
    text = text.replace("GROUP BY r.test_round_id", "GROUP BY r.test_round_id")
    text = text.replace('"releases": releases,', '"rounds": releases,\n        "releases": releases,')
    text = text.replace('"test_releases": releases,', '"test_rounds": releases,\n        "test_releases": releases,')
    patch_old = '''@tracking_router.patch("/admin/api/release/{release_id}/status")
def patch_release_status(
    release_id: str,
    body: ReleaseStatusBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    new_status = normalize_status(body.status)
    if new_status not in VALID_RELEASE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    row = database_session.query(ProductTestRelease).filter_by(
        test_round_id=release_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Release not found.")
    row.migration_status = new_status
    row.updated_at = get_utc_now_datetime()
    database_session.commit()
    return JSONResponse({"ok": True, "status": new_status})'''
    patch_new = '''@tracking_router.patch("/admin/api/release/{release_id}/status")
def patch_release_status(
    release_id: str,
    body: ReleaseStatusBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    raise HTTPException(status_code=410, detail="Release status API removed in v2 (use round/run model).")'''
    if patch_old in text:
        text = text.replace(patch_old, patch_new)
    else:
        text = re.sub(
            r'@tracking_router\.patch\("/admin/api/release/\{release_id\}/status"\)[\s\S]*?return JSONResponse\(\{"ok": True, "status": new_status\}\)',
            patch_new,
            text,
            count=1,
        )
    return text


def simple_replace(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    atomic_write(path, text)


def main() -> int:
    run_svc = ROOT / "app/services/product_test_run_service.py"
    atomic_write(run_svc, sync_run_service(run_svc.read_text(encoding="utf-8")))

    tr = ROOT / "app/routers/tracking_router.py"
    atomic_write(tr, sync_tracking_router(tr.read_text(encoding="utf-8")))

    admin = ROOT / "app/routers/admin_router.py"
    text = admin.read_text(encoding="utf-8")
    text = text.replace("create_product_test_release,\n", "")
    text = text.replace("list_product_test_releases,\n", "list_product_test_rounds,\n")
    text = text.replace("get_release_id_by_result_id,", "get_test_round_id_by_result_id,")
    text = text.replace("get_release_id_by_run_id,", "get_test_round_id_by_run_id,")
    text = text.replace(
        '        "release_rows": list_product_test_releases(database_session),\n'
        '        "release_stage_values": RELEASE_STAGE_VALUES,\n'
        '        "product_test_release_status_values": PRODUCT_TEST_RELEASE_STATUS_VALUES,\n',
        '        "round_rows": list_product_test_rounds(database_session),\n',
    )
    text = re.sub(r"def _sample_product_test_release_rows\(\)[\s\S]*?return rows\n\n", "", text, count=1)
    text = text.replace("product_test_release_id: str = Form(\"\")", "test_round_id: str = Form(\"\")")
    text = text.replace("product_test_release_id=product_test_release_id", "test_round_id=test_round_id")
    atomic_write(admin, text)

    for rel, reps in [
        ("app/services/product_test_field_update_service.py", [
            ("ProductTestRelease,\n", "ProductTestRound,\n"),
            ('    "product_test_release": ProductTestRelease,\n', ""),
            ('    "product_test_release": "product_test_release_status",\n', ""),
        ]),
        ("app/services/sheet_service.py", [
            ("ProductTestRelease,", "ProductTestRound,"),
            ('    "release": ProductTestRelease,\n', ""),
            ("FROM product_test_release", "FROM product_test_round"),
            ("product_test_release_id", "test_round_id"),
            ("run.product_test_release_id", "run.test_round_id"),
        ]),
    ]:
        simple_replace(ROOT / rel, reps)

    for rel, reps in [
        ("app/services/admin_product_test_ui_service.py", [
            ("product_test_release_id", "test_round_id"),
            ("/admin/product-test-releases/create", "/admin"),
            ("product_test_release", "product_test_round"),
        ]),
        ("app/services/admin_qc_e2e_service.py", [
            ("product_test_release_id", "test_round_id"),
            ("product_test_release", "product_test_round"),
        ]),
        ("app/static/js/tracking-render.js", [
            ('"Test Release"', '"Test Round"'),
            ("product_test_release", "product_test_round"),
            ("test_releases", "test_rounds"),
            ('{ key: "id", label: "Release ID"', '{ key: "id", label: "Round ID"'),
            ('field: "product_test_release_status"', 'field: "migration_status"'),
            ('field: "upstream_release_id"', 'field: "test_round_name"'),
        ]),
        ("app/static/js/table-cell-f2-edit.js", [
            ("product_test_release", "product_test_round"),
            ("product-test-releases", "product-test-rounds"),
        ]),
        ("app/static/js/sheet-view.js", [
            ('tab: "release"', 'tab: "round"'),
            ("product_test_release_id", "test_round_id"),
        ]),
    ]:
        simple_replace(ROOT / rel, reps)

    for tpl in [
        "admin_dashboard.html",
        "product_test_trace_admin.html",
        "product_test_reports_admin.html",
        "product_test_report_detail_admin.html",
        "product_test_report_print_admin.html",
        "product_test_report_snapshots_admin.html",
        "product_test_report_snapshot_detail_admin.html",
        "product_test_system_check_admin.html",
    ]:
        p = ROOT / "app/templates" / tpl
        text = p.read_text(encoding="utf-8")
        text = text.replace("product_test_release_id", "test_round_id")
        text = text.replace("product-test-releases", "product-test-rounds")
        text = text.replace("Release", "Round") if "product_test_releases" not in tpl else text
        text = text.replace("locked_release_count", "locked_round_count")
        text = text.replace("release_rows", "round_rows")
        atomic_write(p, text)

    releases_tpl = ROOT / "app/templates/product_test_releases_admin.html"
    atomic_write(
        releases_tpl,
        releases_tpl.read_text(encoding="utf-8").replace(
            "product_test_release",
            "product_test_round",
        ) + "\n<!-- deprecated: release admin removed in TASK 15-5 -->\n",
    )

    seed = ROOT / "app/scripts/seed_product_test_wifi_ap_e2e.py"
    simple_replace(seed, [("product_test_release_id", "test_round_id"), ("ProductTestRelease", "ProductTestRound")])

    remaining = subprocess.run(
        ["rg", "product_test_release", str(ROOT / "app")],
        capture_output=True,
        text=True,
    )
    print("remaining refs:", remaining.stdout or "(none)")
    py_files = list((ROOT / "app").rglob("*.py"))
    for pf in py_files:
        subprocess.run([sys.executable, "-m", "py_compile", str(pf)], check=True)
    return 0 if not remaining.stdout.strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
