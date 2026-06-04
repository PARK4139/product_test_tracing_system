(function () {
"use strict";

/* ── fetch & mount ───────────────────────────────────────────── */
function loadTracking(options) {
    const opts = options || {};
    const restoreScroll = opts.preserveScroll
        ? { x: window.scrollX || 0, y: window.scrollY || 0 }
        : null;
    const root    = document.getElementById("trk_root");
    const loadMsg = document.getElementById("trk_loading_msg");
    if (loadMsg) loadMsg.style.display = "block";

    function showError(msg) {
        console.error("[tracking] loadTracking 실패:", msg);
        root.innerHTML = `<div style="color:#ef4444;font-family:monospace;white-space:pre-wrap;font-size:0.82rem;padding:16px;border:1px solid #ef4444;border-radius:6px;margin:8px 0"><b>⚠ 데이터 로드 실패</b>\n\n${msg}\n\n<span style="color:#94a3b8;font-size:0.75rem">서버가 실행 중인지 확인하세요. 브라우저 콘솔(F12)에서 상세 스택 확인 가능.</span></div>`;
    }

    // 10초 타임아웃
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    let _httpStatus = null;
    fetch("/admin/api/tracking/summary", { signal: controller.signal })
        .then(r => {
            clearTimeout(timeoutId);
            _httpStatus = r.status;
            if (!r.ok) return r.text().then(t => { throw new Error(`HTTP ${r.status}\n${t}`); });
            return r.json();
        })
        .then(data => {
            try {
                root.innerHTML = renderTracking(data);
                bindStatusEditable(root);
                bindColumnDragDrop(root);
                initStatClickable(root);
                bindGanttFold(root);
                const ganttWrap = root.querySelector(".gantt_wrap");
                if (ganttWrap) { initGanttResize(ganttWrap); initDeadlineDrag(ganttWrap); }
                bindHighlights(root);
                bindDefectImages(root);
                initDefectColResize(root);
                if (typeof initTableColumnFeatures === "function") initTableColumnFeatures(root);
                if (restoreScroll) {
                    window.scrollTo(restoreScroll.x, restoreScroll.y);
                } else {
                    window.scrollTo({ top: 0, behavior: "instant" });
                }
            } catch(renderErr) {
                showError(`렌더링 오류: ${renderErr.message}\n${renderErr.stack}`);
            }
        })
        .catch(err => {
            clearTimeout(timeoutId);
            const msg = err.name === "AbortError"
                ? "timeout (10s) - server not responding"
                : "HTTP " + (_httpStatus || "no connection") + "\n" + err.message;
            showError(msg);
        });
}


function updateToggleLabel() {
    const btn = document.getElementById("trk_view_toggle_btn");
    if (!btn) return;
    const mode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
    const VIEW_MODE_LABELS = ['보기모드: 전체', '보기모드: 시험중', '보기모드: 중단판정', '보기모드: 최상위'];
    btn.textContent = VIEW_MODE_LABELS[mode] || VIEW_MODE_LABELS[0];
    btn.title = VIEW_MODE_LABELS[mode] || VIEW_MODE_LABELS[0];
}

document.addEventListener("DOMContentLoaded", () => { updateToggleLabel(); loadTracking(); });
document.getElementById("trk_refresh_btn")
    && document.getElementById("trk_refresh_btn").addEventListener("click", event => {
        const btn = event.currentTarget;
        const preserveScroll = btn && btn.dataset.preserveScroll === "1";
        if (btn) delete btn.dataset.preserveScroll;
        updateToggleLabel();
        loadTracking({ preserveScroll });
    });
})();
