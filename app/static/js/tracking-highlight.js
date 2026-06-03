// tracking-highlight.js — full cross-table highlight
/* ── highlight ─────────────────────────────────────────── */
function statusHighlightClass(status) {
    const s = (status || "").toUpperCase();
    if (["PASSED","QI_TEAM_RELEASED","APPROVED"].includes(s)) return "hl-passed";
    if (s === "BLOCKED") return "hl-blocked";
    if (s === "TESTING") return "hl-testing";
    return "hl-default";
}
function clearAllHighlights() {
    const cls = ["trk_row_highlighted","hl-passed","hl-blocked","hl-testing","hl-default"];
    document.querySelectorAll("tr.trk_row_highlighted").forEach(r => r.classList.remove(...cls));
    document.querySelectorAll(".gantt_hl").forEach(r => r.classList.remove("gantt_hl",...cls));
}

function bindHighlights(root) {
    function findGanttRowById(rowId) {
        if (!rowId) return null;
        return root.querySelector(`.gantt_row[data-row-id="${rowId}"]`);
    }

    // ── per-table highlight helpers ──
    function hlByTopo(tableClass, topoId, hlClass) {
        root.querySelectorAll(`.${tableClass} tbody tr[data-parent-release-id="${topoId}"]`).forEach(r => {
            r.classList.add("trk_row_highlighted", hlClass || "hl-blocked");
        });
    }
    function hlAllTablesByTopo(topoId) {
        hlByTopo("trk_run_table", topoId);
        hlByTopo("trk_result_table", topoId);
        hlByTopo("trk_proc_result_table", topoId);
        hlByTopo("trk_evidence_table", topoId);
    }
    function hlDefectsByTopoIds(topoIds) {
        let first = null;
        topoIds.forEach(id => {
            root.querySelectorAll(`.trk_defect_table tbody tr[data-parent-release-id="${id}"]`).forEach(r => {
                r.classList.add("trk_row_highlighted", "hl-blocked");
                if (!first) first = r;
            });
        });
        return first;
    }

    // ── gantt parent row click ──
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
                const topoIds = childRows.map(c => c.dataset.rowId).filter(Boolean);
                if (!topoIds.length) topoIds.push(releaseId);
                topoIds.forEach(id => hlAllTablesByTopo(id));
                hlDefectsByTopoIds(topoIds);
            }
        });
    });

    // ── gantt child (topology) row click ──
    root.querySelectorAll(".gantt_row_child").forEach(row => {
        row.addEventListener("click", e => {
            if (e.target.closest(".trk_status_editable,.trk_status_readonly")) return;
            const rowId = row.dataset.rowId;
            const isSelected = row.classList.contains("gantt_hl");
            clearAllHighlights();
            if (!isSelected && rowId) {
                row.classList.add("gantt_hl", statusHighlightClass(row.dataset.status));
                hlAllTablesByTopo(rowId);
                const first = hlDefectsByTopoIds([rowId]);
                if (first) first.scrollIntoView({ behavior:"smooth", block:"nearest" });
            }
        });
    });

    // ── defect row click ──
    root.querySelectorAll(".trk_defect_table tbody tr").forEach(tr => {
        tr.style.cursor = "pointer";
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;
            const topoId = tr.dataset.parentReleaseId || "";
            clientLog("[HL] defect click", {parentReleaseId: topoId});
            tr.classList.add("trk_row_highlighted", "hl-blocked");
            if (topoId) {
                const topoRow = findGanttRowById(topoId);
                if (topoRow) {
                    topoRow.classList.add("gantt_hl", "hl-blocked");
                    topoRow.scrollIntoView({ behavior:"smooth", block:"nearest" });
                }
                hlAllTablesByTopo(topoId);
            }
        });
    });

    // ── run table row click ──
    root.querySelectorAll(".trk_run_table tbody tr").forEach(tr => {
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;
            const topoId = tr.dataset.parentReleaseId || "";
            tr.classList.add("trk_row_highlighted", "hl-testing");
            if (topoId) {
                const topoRow = findGanttRowById(topoId);
                if (topoRow) {
                    topoRow.classList.add("gantt_hl", statusHighlightClass(topoRow.dataset.status));
                    topoRow.scrollIntoView({ behavior:"smooth", block:"nearest" });
                }
                hlAllTablesByTopo(topoId);
                hlDefectsByTopoIds([topoId]);
            }
        });
    });

    // ── result table row click ──
    root.querySelectorAll(".trk_result_table tbody tr").forEach(tr => {
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;
            const topoId = tr.dataset.parentReleaseId || "";
            tr.classList.add("trk_row_highlighted", "hl-testing");
            if (topoId) {
                const topoRow = findGanttRowById(topoId);
                if (topoRow) {
                    topoRow.classList.add("gantt_hl", statusHighlightClass(topoRow.dataset.status));
                    topoRow.scrollIntoView({ behavior:"smooth", block:"nearest" });
                }
                hlAllTablesByTopo(topoId);
                let defectIds = [];
                try { defectIds = JSON.parse(tr.dataset.defectIds || "[]"); } catch(e) {}
                defectIds.forEach(did => {
                    root.querySelectorAll(`.trk_defect_table tbody tr[data-defect-id="${did}"]`).forEach(r => {
                        r.classList.add("trk_row_highlighted", "hl-blocked");
                    });
                });
            }
        });
    });

    // ── procedure result table row click ──
    root.querySelectorAll(".trk_proc_result_table tbody tr").forEach(tr => {
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;
            const topoId = tr.dataset.parentReleaseId || "";
            tr.classList.add("trk_row_highlighted", "hl-testing");
            if (topoId) {
                const topoRow = findGanttRowById(topoId);
                if (topoRow) {
                    topoRow.classList.add("gantt_hl", statusHighlightClass(topoRow.dataset.status));
                    topoRow.scrollIntoView({ behavior:"smooth", block:"nearest" });
                }
                hlAllTablesByTopo(topoId);
                hlDefectsByTopoIds([topoId]);
            }
        });
    });

    // ── evidence table row click ──
    root.querySelectorAll(".trk_evidence_table tbody tr").forEach(tr => {
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;
            const topoId = tr.dataset.parentReleaseId || "";
            tr.classList.add("trk_row_highlighted", "hl-testing");
            if (topoId) {
                const topoRow = findGanttRowById(topoId);
                if (topoRow) {
                    topoRow.classList.add("gantt_hl", statusHighlightClass(topoRow.dataset.status));
                    topoRow.scrollIntoView({ behavior:"smooth", block:"nearest" });
                }
                hlAllTablesByTopo(topoId);
                hlDefectsByTopoIds([topoId]);
            }
        });
    });
}
