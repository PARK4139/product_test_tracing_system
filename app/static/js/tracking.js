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
                initTrackingDataTabs(root);
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

function initTrackingDataTabs(root) {
    const headers = Array.from(root.querySelectorAll(".trk_sub_header"));
    if (headers.length === 0 || root.querySelector(".trk_data_tabs")) return;

    const labelBySelector = [
        [".trk_defect_table", "Defects"],
        [".trk_test_release_table", "Test Release"],
        [".trk_test_target_definition_table", "Test Target Definition"],
        [".trk_test_target_table", "Test Target"],
        [".trk_test_environment_definition_table", "Test Environment Definition"],
        [".trk_test_environment_table", "Test Environment"],
        [".trk_test_case_master_table", "Test Case"],
        [".trk_test_procedure_master_table", "Test Procedure"],
        [".trk_target_table,.trk_env_table", "Target / Env"],
        [".trk_result_table", "Results"],
        [".trk_case_table,.trk_procedure_table", "Case / Procedure"],
        [".trk_proc_result_table", "Procedure Results"],
        [".trk_evidence_table", "Evidence"],
        [".trk_report_table", "Reports"]
    ];

    const groups = [];
    headers.forEach((header, index) => {
        if (header.querySelector("#trk_view_toggle_btn, #trk_sort_toggle_btn")) return;

        const nodes = [header];
        let cursor = header.nextElementSibling;
        while (cursor && !cursor.classList.contains("trk_sub_header")) {
            nodes.push(cursor);
            cursor = cursor.nextElementSibling;
        }

        const hasTable = nodes.some(node => node.querySelector && node.querySelector("table"));
        if (!hasTable) return;

        const labelMatch = labelBySelector.find(([selector]) =>
            nodes.some(node => node.matches?.(selector) || node.querySelector?.(selector))
        );
        const rowCount = nodes.reduce((count, node) => (
            count + (node.querySelectorAll ? node.querySelectorAll("tbody tr").length : 0)
        ), 0);

        groups.push({
            id: `trk_data_tab_${index}`,
            label: labelMatch ? labelMatch[1] : (header.textContent || "Data").trim(),
            count: rowCount,
            nodes
        });
    });

    if (groups.length <= 1) return;

    const tabsRoot = document.createElement("section");
    tabsRoot.className = "trk_data_tabs";
    const tabbar = document.createElement("div");
    tabbar.className = "trk_sheet_tabbar";
    tabbar.setAttribute("role", "tablist");
    tabbar.setAttribute("aria-label", "Tracking data tables");
    tabsRoot.appendChild(tabbar);

    const storedId = localStorage.getItem("trk_data_tab") || "";
    const activeGroup = groups.find(group => group.id === storedId) || groups[0];

    groups.forEach(group => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = `trk_sheet_tab${group.id === activeGroup.id ? " is-active" : ""}`;
        tab.dataset.trkTab = group.id;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", group.id === activeGroup.id ? "true" : "false");
        tab.innerHTML = `<span>${group.label}</span><span class="trk_sheet_count">${group.count}</span>`;
        tabbar.appendChild(tab);

        const panel = document.createElement("div");
        panel.className = `trk_sheet_panel${group.id === activeGroup.id ? " is-active" : ""}`;
        panel.dataset.trkPanel = group.id;
        panel.setAttribute("role", "tabpanel");
        group.nodes.forEach(node => panel.appendChild(node));
        tabsRoot.appendChild(panel);
    });

    const ganttWrap = root.querySelector(".gantt_wrap");
    const anchor = ganttWrap || root.querySelector(".trk_stat_table_wrap");
    if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(tabsRoot, anchor.nextSibling);
    } else {
        root.appendChild(tabsRoot);
    }

    function activate(id) {
        tabsRoot.querySelectorAll("[data-trk-tab]").forEach(tab => {
            const active = tab.dataset.trkTab === id;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
        });
        tabsRoot.querySelectorAll("[data-trk-panel]").forEach(panel => {
            panel.classList.toggle("is-active", panel.dataset.trkPanel === id);
        });
        localStorage.setItem("trk_data_tab", id);

        const activePanel = tabsRoot.querySelector(`[data-trk-panel="${id}"]`);
        if (activePanel && typeof initTableColumnFeatures === "function") {
            initTableColumnFeatures(activePanel);
        }
    }

    tabbar.addEventListener("click", event => {
        const tab = event.target.closest("[data-trk-tab]");
        if (!tab) return;
        activate(tab.dataset.trkTab);
    });
}


function updateToggleLabel() {
    const btn = document.getElementById("trk_view_toggle_btn");
    if (!btn) return;
    const mode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
    const VIEW_MODE_LABELS = ['보기모드: 전체', '보기모드: 시험중', '보기모드: 중단판정', '보기모드: 최상위'];
    btn.textContent = VIEW_MODE_LABELS[mode] || VIEW_MODE_LABELS[0];
    btn.title = VIEW_MODE_LABELS[mode] || VIEW_MODE_LABELS[0];

    const sortBtn = document.getElementById("trk_sort_toggle_btn");
    if (sortBtn) {
        const sm = parseInt(localStorage.getItem('trk_sort_mode') || '0', 10);
        const SORT_LABELS = ['정렬: 기본', '정렬: 시험종료일자별'];
        sortBtn.textContent = SORT_LABELS[sm] || SORT_LABELS[0];
        sortBtn.title = SORT_LABELS[sm] || SORT_LABELS[0];
    }
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
