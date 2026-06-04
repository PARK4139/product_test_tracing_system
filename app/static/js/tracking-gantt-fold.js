// tracking-gantt-fold.js — gantt row fold/unfold
function getFoldState(id) {
    try { return JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}")[id] === true; } catch(e) { return false; }
}
function saveFoldState(id, folded) {
    try { const s = JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}"); s[id] = folded; localStorage.setItem(GANTT_FOLD_KEY, JSON.stringify(s)); } catch(e) {}
}
function _applyFold(root, id, folded) {
    // 직계 자식 숨김/표시
    root.querySelectorAll(`[data-parent-id="${id}"]`).forEach(row => {
        row.style.display = folded ? "none" : "";
        // 자식이 접혀있지 않으면 손자도 함께 숨김/표시
        const childId = row.dataset.rowId;
        if (childId) {
            const childFolded = folded || getFoldState(childId);
            root.querySelectorAll(`[data-parent-id="${childId}"]`).forEach(grandRow => {
                grandRow.style.display = childFolded ? "none" : "";
            });
        }
    });
}
function bindGanttFold(root) {
    const viewMode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
    root.querySelectorAll(".gantt_fold_btn").forEach(btn => {
        const id = btn.dataset.foldId;
        if (viewMode === 2 && getFoldState(id)) { _applyFold(root, id, true); btn.textContent = "▶"; }
        btn.addEventListener("click", e => {
            e.stopPropagation();
            const folded = btn.textContent === "▼";
            _applyFold(root, id, folded);
            btn.textContent = folded ? "▶" : "▼";
            saveFoldState(id, folded);
        });
    });
}
