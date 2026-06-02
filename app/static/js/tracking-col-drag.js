// tracking-col-drag.js — defect table column drag/drop & order persistence
// tracking-table.js — column drag/drop, status dropdown, stat clickable
/* ── 컬럼 드래그 앤 드롭 + 위치 저장/복원 ──────────────────────── */
const TRK_COL_KEY = "trk_col_order";
function getColKey(table) {
    return table.classList.contains("trk_timeline_table") ? "timeline" : "defect";
}
function saveColOrder(table) {
    const key = getColKey(table);
    const order = Array.from(table.querySelectorAll("thead tr th")).map(th => th.textContent.trim());
    try { const s = JSON.parse(localStorage.getItem(TRK_COL_KEY)||"{}"); s[key]=order; localStorage.setItem(TRK_COL_KEY,JSON.stringify(s)); } catch(e) {}
}
function restoreColOrder(table) {
    const key = getColKey(table);
    try {
        const order = (JSON.parse(localStorage.getItem(TRK_COL_KEY)||"{}") )[key];
        if (!order || !Array.isArray(order)) return;
        order.forEach((label, targetIdx) => {
            const ths = Array.from(table.querySelectorAll("thead tr th"));
            const srcIdx = ths.findIndex(th => th.textContent.trim() === label);
            if (srcIdx === -1 || srcIdx === targetIdx) return;
            swapCols(table, srcIdx, targetIdx);
        });
    } catch(e) {}
}
function swapCols(table, srcIdx, dstIdx) {
    Array.from(table.querySelectorAll("tr")).forEach(row => {
        const cells = Array.from(row.children);
        if (cells.length <= Math.max(srcIdx, dstIdx)) return;
        const a = cells[srcIdx], b = cells[dstIdx];
        if (srcIdx < dstIdx) b.parentNode.insertBefore(a, b.nextSibling);
        else b.parentNode.insertBefore(a, b);
    });
}
function bindColumnDragDrop(root) {
    root.querySelectorAll(".trk_timeline_table, .trk_defect_table").forEach(table => {
        restoreColOrder(table);
        let dragSrcIdx = null;
        const rebind = () => {
            const ths = Array.from(table.querySelectorAll("thead tr th"));
            ths.forEach((th, idx) => {
                th.draggable = true; th.style.cursor = "grab";
                th.ondragstart = e => { dragSrcIdx = idx; th.style.opacity = "0.5"; e.dataTransfer.effectAllowed = "move"; };
                th.ondragend = () => { th.style.opacity = ""; ths.forEach(t => t.classList.remove("trk_col_drag_over")); };
                th.ondragover = e => { e.preventDefault(); ths.forEach(t => t.classList.remove("trk_col_drag_over")); th.classList.add("trk_col_drag_over"); };
                th.ondrop = e => {
                    e.preventDefault();
                    const dstIdx = Array.from(table.querySelectorAll("thead tr th")).indexOf(th);
                    if (dragSrcIdx === null || dragSrcIdx === dstIdx) return;
                    swapCols(table, dragSrcIdx, dstIdx);
                    saveColOrder(table); dragSrcIdx = null; rebind();
                };
            });
        };
        rebind();
    });
}
