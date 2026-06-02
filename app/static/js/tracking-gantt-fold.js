// tracking-gantt-fold.js — gantt row fold/unfold
function getFoldState(id) {
    try { return JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}")[id] === true; } catch(e) { return false; }
}
function saveFoldState(id, folded) {
    try { const s = JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}"); s[id] = folded; localStorage.setItem(GANTT_FOLD_KEY, JSON.stringify(s)); } catch(e) {}
}
function _applyFold(root, id, folded) {
    root.querySelectorAll(`[data-parent-id="${id}"]`).forEach(row => { row.style.display = folded ? "none" : ""; });
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
