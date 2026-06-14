/**
 * admin-row-delete.js
 * data-incell-edit-table 이 있는 모든 테이블에:
 *   - 첫 번째 열로 체크박스 삽입
 *   - 선택 시 하단 플로팅 바 표시 (건수 + 삭제 + 해제)
 *   - bulk-delete API 호출 → 성공 행 DOM 제거
 */
(function () {
    "use strict";

    var CB_COL_CLASS   = "admin_row_del_col";
    var ROW_CB_CLASS   = "admin_row_del_cb";
    var ALL_CB_CLASS   = "admin_row_del_all";
    var BAR_ID         = "admin_row_del_bar";
    var COUNT_ID       = "admin_row_del_count";

    /* ── 플로팅 바 ──────────────────────────────────────────────────── */
    function getBar() { return document.getElementById(BAR_ID); }

    function buildBar() {
        if (getBar()) return;
        var bar = document.createElement("div");
        bar.id        = BAR_ID;
        bar.className = "admin_row_del_bar";
        bar.style.display = "none";
        bar.innerHTML =
            "<span id=\"" + COUNT_ID + "\" class=\"admin_row_del_count\"></span>" +
            "<button type=\"button\" id=\"admin_row_del_btn\"" +
            "  class=\"project_standard_button admin_row_del_btn_del\">삭제</button>" +
            "<button type=\"button\" id=\"admin_row_desel_btn\"" +
            "  class=\"admin_row_del_btn_cancel\">선택 해제</button>";
        document.body.appendChild(bar);
        document.getElementById("admin_row_del_btn")  .addEventListener("click", onDeleteClick);
        document.getElementById("admin_row_desel_btn").addEventListener("click", deselectAll);
    }

    function updateBar() {
        var n   = getCheckedCbs().length;
        var bar = getBar();
        if (!bar) return;
        if (n === 0) {
            bar.style.display = "none";
        } else {
            document.getElementById(COUNT_ID).textContent = n + "행 선택됨";
            bar.style.display = "";
        }
    }

    /* ── 체크박스 수집 ───────────────────────────────────────────────── */
    function getCheckedCbs() {
        return Array.from(document.querySelectorAll("." + ROW_CB_CLASS + ":checked"));
    }

    function deselectAll() {
        document.querySelectorAll("." + ROW_CB_CLASS).forEach(function (cb) { cb.checked = false; });
        document.querySelectorAll("." + ALL_CB_CLASS).forEach(function (cb) {
            cb.checked = false;
            cb.indeterminate = false;
        });
        updateBar();
    }

    /* ── 삭제 실행 ───────────────────────────────────────────────────── */
    async function onDeleteClick() {
        var cbs = getCheckedCbs();
        if (!cbs.length) return;

        if (!confirm(cbs.length + "행을 삭제합니다.\n연관 데이터(결과·보고서 등)도 함께 삭제됩니다.\n\n계속하시겠습니까?")) return;

        /* entity_type 별 그룹화 */
        var groups = {};
        cbs.forEach(function (cb) {
            var row = cb.closest("tr");
            var et  = row && row.dataset.entityType;
            var eid = row && row.dataset.entityId;
            if (!et || !eid) return;
            if (!groups[et]) groups[et] = { rows: [], ids: [] };
            groups[et].rows.push(row);
            groups[et].ids.push(eid);
        });

        var btn = document.getElementById("admin_row_del_btn");
        btn.disabled = true;
        btn.textContent = "삭제 중…";

        var totalDeleted = 0;
        var errors = [];

        for (var et in groups) {
            var g = groups[et];
            try {
                var resp = await fetch("/admin/api/product-test/entities/bulk-delete", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        Accept: "application/json",
                    },
                    body: JSON.stringify({ entity_type: et, entity_ids: g.ids }),
                });
                var data = await resp.json().catch(function () { return {}; });
                if (!resp.ok || data.ok === false) {
                    errors.push("[" + et + "] " + (data.message || "삭제 실패"));
                } else {
                    g.rows.forEach(function (row) { row.remove(); });
                    totalDeleted += (data.deleted || g.ids.length);
                }
            } catch (err) {
                errors.push("[" + et + "] 네트워크 오류");
            }
        }

        btn.disabled = false;
        btn.textContent = "삭제";
        updateBar();

        var notice = typeof window.showCenterNonModalV2 === "function"
            ? function (msg, lvl) { window.showCenterNonModalV2(msg, lvl); }
            : function (msg) { alert(msg); };

        if (errors.length) {
            var msg = (totalDeleted ? totalDeleted + "건 삭제 완료.\n" : "") + "오류:\n" + errors.join("\n");
            notice(msg, "error");
        } else if (totalDeleted) {
            notice(totalDeleted + "행 삭제 완료.", "success");
        }
    }

    /* ── 체크박스 열 주입 ────────────────────────────────────────────── */
    function injectCheckboxCol(table) {
        /* thead: 전체선택 체크박스 */
        table.querySelectorAll("thead tr").forEach(function (tr) {
            if (tr.querySelector("." + CB_COL_CLASS)) return;
            var th = document.createElement("th");
            th.className = CB_COL_CLASS;
            var allCb = document.createElement("input");
            allCb.type      = "checkbox";
            allCb.className = ALL_CB_CLASS;
            allCb.title     = "전체 선택";
            allCb.addEventListener("change", function () {
                table.querySelectorAll("tbody tr:not([data-draft-row='1']) ." + ROW_CB_CLASS)
                    .forEach(function (cb) { cb.checked = allCb.checked; });
                updateBar();
            });
            th.appendChild(allCb);
            tr.insertBefore(th, tr.firstChild);
        });

        /* tbody: 각 행에 체크박스 */
        table.querySelectorAll("tbody tr:not([data-draft-row='1'])").forEach(function (tr) {
            injectRowCheckbox(tr, table);
        });
    }

    function injectRowCheckbox(tr, table) {
        if (tr.querySelector("." + CB_COL_CLASS)) return;
        var td = document.createElement("td");
        td.className = CB_COL_CLASS;
        var cb = document.createElement("input");
        cb.type      = "checkbox";
        cb.className = ROW_CB_CLASS;
        cb.addEventListener("change", function () {
            syncHeaderCheckbox(table || tr.closest("table"));
            updateBar();
        });
        td.appendChild(cb);
        tr.insertBefore(td, tr.firstChild);
    }

    function syncHeaderCheckbox(table) {
        if (!table) return;
        var all     = table.querySelectorAll("tbody tr:not([data-draft-row='1']) ." + ROW_CB_CLASS);
        var checked = table.querySelectorAll("tbody tr:not([data-draft-row='1']) ." + ROW_CB_CLASS + ":checked");
        var allCb   = table.querySelector("." + ALL_CB_CLASS);
        if (!allCb) return;
        allCb.checked       = all.length > 0 && checked.length === all.length;
        allCb.indeterminate = checked.length > 0 && checked.length < all.length;
    }

    /* ── MutationObserver: 새 행(행 추가/저장 확정) 에도 주입 ──────── */
    function observeTable(table) {
        var body = table.querySelector("tbody");
        if (!body) return;
        new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                m.addedNodes.forEach(function (node) {
                    if (node.nodeType !== 1 || node.tagName !== "TR") return;
                    if (node.dataset.draftRow === "1") return; /* 임시 행 제외 */
                    injectRowCheckbox(node, table);
                });
            });
        }).observe(body, { childList: true });
    }

    /* ── init ────────────────────────────────────────────────────────── */
    function init() {
        buildBar();
        document.querySelectorAll("[data-incell-edit-table]").forEach(function (table) {
            injectCheckboxCol(table);
            observeTable(table);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
