// tracking-highlight.js — gantt ↔ defect row highlight
/* ── 하이라이트 ─────────────────────────────────────────── */
function statusHighlightClass(status) {
    const s = (status || "").toUpperCase();
    if (["PASSED","QI_TEAM_RELEASED","APPROVED"].includes(s)) return "hl-passed";
    if (s === "BLOCKED") return "hl-blocked";
    if (s === "TESTING") return "hl-testing";
    return "hl-default";
}
function clearAllHighlights() {
    document.querySelectorAll("tr.trk_row_highlighted").forEach(r => r.classList.remove("trk_row_highlighted","hl-passed","hl-blocked","hl-testing","hl-default"));
    document.querySelectorAll(".gantt_hl").forEach(r => r.classList.remove("gantt_hl","hl-passed","hl-blocked","hl-testing","hl-default"));
}
function bindHighlights(root) {
    function findGanttRowById(rowId) {
        if (!rowId) return null;
        return root.querySelector(`.gantt_row[data-row-id="${rowId}"]`);
    }

    function highlightDefectsByDeviceRows(deviceRowIds) {
        let first = null;
        deviceRowIds.forEach(id => {
            root.querySelectorAll(`tr[data-parent-release-id="${id}"]`).forEach(r => {
                r.classList.add("trk_row_highlighted", "hl-blocked");
                if (!first) first = r;
            });
        });
        if (first) first.scrollIntoView({ behavior:"smooth", block:"nearest" });
    }
    // 간트 부모 행 클릭 → 자식 장비행 기준으로 결함 하이라이트
    root.querySelectorAll(".gantt_row:not(.gantt_row_child)").forEach(row => {
        row.addEventListener("click", e => {
            if (e.target.closest(".trk_status_editable,.trk_status_readonly,.gantt_fold_btn")) return;
            const releaseId = row.dataset.rowId;
            const isSelected = row.classList.contains("gantt_hl");
            clearAllHighlights();
            if (!isSelected && releaseId) {
                row.classList.add("gantt_hl", statusHighlightClass(row.dataset.status));
                const childRows = Array.from(root.querySelectorAll(`.gantt_row_child[data-parent-id="${releaseId}"]`));
                childRows.forEach(c => c.classList.add("gantt_hl", statusHighlightClass(c.dataset.status)));
                const deviceIds = childRows.map(c => c.dataset.rowId).filter(Boolean);
                if (!deviceIds.length) deviceIds.push(releaseId);
                highlightDefectsByDeviceRows(deviceIds);
            }
        });
    });
    // 간트 자식 행 클릭 → 해당 장비행(rowId) 기준 결함 하이라이트
    root.querySelectorAll(".gantt_row_child").forEach(row => {
        row.addEventListener("click", e => {
            if (e.target.closest(".trk_status_editable,.trk_status_readonly")) return;
            const rowId = row.dataset.rowId;
            const isSelected = row.classList.contains("gantt_hl");
            clearAllHighlights();
            if (!isSelected && rowId) {
                row.classList.add("gantt_hl", statusHighlightClass(row.dataset.status));
                highlightDefectsByDeviceRows([rowId]);
            }
        });
    });
    // 결함 행 클릭 → 간트 장비행 + 부모 행 하이라이트
    root.querySelectorAll(".trk_defect_table tbody tr").forEach(tr => {
        tr.style.cursor = "pointer";
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;
            const deviceRowId = tr.dataset.parentReleaseId || "";
            clientLog("[HL] defect click", {parentReleaseId: deviceRowId});
            tr.classList.add("trk_row_highlighted", "hl-blocked");
            if (deviceRowId) {
                const deviceRow = findGanttRowById(deviceRowId);
                clientLog("[HL] deviceRow", deviceRow ? deviceRow.dataset.rowId : "NOT FOUND");
                if (deviceRow) {
                    deviceRow.classList.add("gantt_hl", statusHighlightClass(deviceRow.dataset.status));
                    const parentId = deviceRow.dataset.parentId;
                    if (parentId) {
                        const parentRow = root.querySelector(`.gantt_row[data-row-id="${parentId}"]`);
                        if (parentRow) parentRow.classList.add("gantt_hl", statusHighlightClass(parentRow.dataset.status));
                    }
                    deviceRow.scrollIntoView({ behavior:"smooth", block:"nearest" });
                }
            }
        });
    });
}
