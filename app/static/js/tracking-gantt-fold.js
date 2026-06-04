// tracking-gantt-fold.js — gantt row fold/unfold
function getFoldState(id) {
    try { return JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}")[id] === true; } catch(e) { return false; }
}
function saveFoldState(id, folded) {
    try { const s = JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}"); s[id] = folded; localStorage.setItem(GANTT_FOLD_KEY, JSON.stringify(s)); } catch(e) {}
}
function _applyFold(root, id, folded) {
    // 직계 자식 숨김/표시 후, 깊이에 상관없이 재귀로 모든 후손 처리
    // (라운드 → 세션 → 토폴로지 → 런 4단 계층 지원)
    root.querySelectorAll(`[data-parent-id="${id}"]`).forEach(row => {
        row.style.display = folded ? "none" : "";
        const childId = row.dataset.rowId;
        if (childId) {
            // 자식이 스스로 접혀있으면 그 후손은 계속 숨김
            const childFolded = folded || getFoldState(childId);
            _applyFold(root, childId, childFolded);
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
