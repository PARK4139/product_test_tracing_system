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

const sheetTabGroups = new Map();
let sheetTabDragState = null;

function sheetTabId(tab) {
    return tab?.dataset?.sheetTab || tab?.dataset?.trkTab || tab?.dataset?.adminMasterTab || "";
}

function sheetPanelId(panel) {
    return panel?.dataset?.sheetPanel || panel?.dataset?.trkPanel || panel?.dataset?.adminMasterPanel || "";
}

function readSheetTabLocations() {
    try {
        const parsed = JSON.parse(localStorage.getItem("sheet_tab_locations") || "{}");
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_) {
        return {};
    }
}

function readStoredSheetOrder(storageKey) {
    try {
        const parsed = JSON.parse(localStorage.getItem(storageKey) || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
        return [];
    }
}

function applyStoredSheetGroupOrder(group) {
    const order = readStoredSheetOrder(group.storageKey);
    if (!order.length) return;
    const tabs = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]"));
    const panels = Array.from(group.tabsRoot.querySelectorAll("[data-sheet-panel]"));
    const tabsById = new Map(tabs.map(tab => [sheetTabId(tab), tab]));
    const panelsById = new Map(panels.map(panel => [sheetPanelId(panel), panel]));
    const orderedIds = order.filter(id => tabsById.has(id));
    tabs.map(sheetTabId).forEach(id => {
        if (!orderedIds.includes(id)) orderedIds.push(id);
    });
    orderedIds.forEach(id => {
        group.tabbar.appendChild(tabsById.get(id));
        group.tabsRoot.appendChild(panelsById.get(id));
    });
}

function saveAllSheetTabState() {
    const locations = readSheetTabLocations();
    sheetTabGroups.forEach(group => {
        const ids = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]")).map(sheetTabId);
        ids.forEach(id => {
            if (id) locations[id] = group.groupKey;
        });
        if (group.storageKey) {
            localStorage.setItem(group.storageKey, JSON.stringify(ids));
        }
    });
    localStorage.setItem("sheet_tab_locations", JSON.stringify(locations));
}

function findSheetTabEntry(id) {
    for (const group of sheetTabGroups.values()) {
        const tab = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]")).find(item => sheetTabId(item) === id);
        const panel = Array.from(group.tabsRoot.querySelectorAll("[data-sheet-panel]")).find(item => sheetPanelId(item) === id);
        if (tab && panel) return { group, tab, panel };
    }
    return null;
}

function ensureSheetGroupActive(group, preferredId) {
    const tabs = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]"));
    if (!tabs.length) return;
    const activeId = tabs.some(tab => sheetTabId(tab) === preferredId)
        ? preferredId
        : (tabs.find(tab => tab.classList.contains("is-active")) && sheetTabId(tabs.find(tab => tab.classList.contains("is-active")))) || sheetTabId(tabs[0]);
    group.activate(activeId);
}

function moveSheetTabToGroup(sourceId, targetGroupKey, targetId) {
    if (!sourceId || !targetGroupKey) return;
    const source = findSheetTabEntry(sourceId);
    const targetGroup = sheetTabGroups.get(targetGroupKey);
    if (!source || !targetGroup) return;

    const targetTab = targetId
        ? Array.from(targetGroup.tabbar.querySelectorAll("[data-sheet-tab]")).find(tab => sheetTabId(tab) === targetId)
        : null;
    const targetPanel = targetId
        ? Array.from(targetGroup.tabsRoot.querySelectorAll("[data-sheet-panel]")).find(panel => sheetPanelId(panel) === targetId)
        : null;

    if (source.tab === targetTab) return;
    if (targetTab) {
        targetGroup.tabbar.insertBefore(source.tab, targetTab);
    } else {
        targetGroup.tabbar.appendChild(source.tab);
    }
    if (targetPanel) {
        targetGroup.tabsRoot.insertBefore(source.panel, targetPanel);
    } else {
        targetGroup.tabsRoot.appendChild(source.panel);
    }

    source.tab.dataset.sheetCurrentGroup = targetGroupKey;
    source.panel.dataset.sheetCurrentGroup = targetGroupKey;
    saveAllSheetTabState();
    ensureSheetGroupActive(source.group, "");
    ensureSheetGroupActive(targetGroup, sourceId);
}

function applySavedSheetTabLocations() {
    const locations = readSheetTabLocations();
    Object.entries(locations).forEach(([id, groupKey]) => {
        const current = findSheetTabEntry(id);
        if (current && current.group.groupKey !== groupKey && sheetTabGroups.has(groupKey)) {
            moveSheetTabToGroup(id, groupKey, "");
        }
    });
    sheetTabGroups.forEach(applyStoredSheetGroupOrder);
}

function registerSheetTabGroup(options) {
    sheetTabGroups.set(options.groupKey, options);
    applySavedSheetTabLocations();
}

function initTrackingDataTabs(root) {
    const headers = Array.from(root.querySelectorAll(".trk_sub_header"));
    if (headers.length === 0 || root.querySelector(".trk_data_tabs")) return;

    const dataTableSelector = [
        ".trk_defect_table",
        ".trk_test_release_table",
        ".trk_test_target_definition_table",
        ".trk_test_target_table",
        ".trk_test_environment_definition_table",
        ".trk_test_environment_table",
        ".trk_test_case_master_table",
        ".trk_test_procedure_master_table",
        ".trk_target_table",
        ".trk_env_table",
        ".trk_result_table",
        ".trk_case_table",
        ".trk_procedure_table",
        ".trk_proc_result_table",
        ".trk_evidence_table",
        ".trk_report_table",
        ".gantt_wrap"
    ].join(",");

    const labelBySelector = [
        [".gantt_wrap", "Timeline"],
        [".trk_defect_table", "Defects"],
        [".trk_test_release_table", "Test Release"],
        [".trk_test_target_definition_table", "Test Target Definition"],
        [".trk_test_target_table", "Test Target"],
        [".trk_test_environment_definition_table", "Test Environment Definition"],
        [".trk_test_environment_table", "Test Environment"],
        [".trk_test_case_master_table", "Test Case"],
        [".trk_test_procedure_master_table", "Test Procedure"],
        [".trk_target_table", "Target"],
        [".trk_env_table", "Environment"],
        [".trk_result_table", "Results"],
        [".trk_case_table", "Test Case"],
        [".trk_procedure_table", "Test Procedure"],
        [".trk_proc_result_table", "Procedure Results"],
        [".trk_evidence_table", "Evidence"],
        [".trk_report_table", "Reports"]
    ];

    const groups = [];
    headers.forEach((header, index) => {
        const nodes = [header];
        let cursor = header.nextElementSibling;
        while (cursor && !cursor.classList.contains("trk_sub_header")) {
            nodes.push(cursor);
            cursor = cursor.nextElementSibling;
        }

        const hasDataView = nodes.some(node =>
            node.querySelector && (
                node.matches?.(".gantt_wrap")
                || node.querySelector("table")
                || node.querySelector(".gantt_wrap")
            )
        );
        if (!hasDataView) return;

        const labelMatch = labelBySelector.find(([selector]) =>
            nodes.some(node => node.matches?.(selector) || node.querySelector?.(selector))
        );
        const rowCount = nodes.reduce((count, node) => {
            if (!node.querySelectorAll) return count;
            const tableRows = node.querySelectorAll("tbody tr").length;
            const ganttRows = node.querySelectorAll(".gantt_row").length;
            return count + tableRows + ganttRows;
        }, 0);

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
    tabsRoot.dataset.sheetGroup = "user";
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
        tab.dataset.sheetTab = group.id;
        tab.dataset.sheetCurrentGroup = "user";
        tab.dataset.sheetLabelStorageKey = "trk_data_tab_labels";
        tab.dataset.trkTab = group.id;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", group.id === activeGroup.id ? "true" : "false");
        tab.innerHTML = `<span class="trk_sheet_label">${escapeSheetTabText(getSheetTabLabel("trk_data_tab_labels", group.id, group.label))}</span><span class="trk_sheet_count">${group.count}</span>`;
        tabbar.appendChild(tab);

        const panel = document.createElement("div");
        panel.className = `trk_sheet_panel${group.id === activeGroup.id ? " is-active" : ""}`;
        panel.dataset.sheetPanel = group.id;
        panel.dataset.sheetCurrentGroup = "user";
        panel.dataset.trkPanel = group.id;
        panel.hidden = group.id !== activeGroup.id;
        panel.setAttribute("role", "tabpanel");
        group.nodes.forEach(node => panel.appendChild(node));
        tabsRoot.appendChild(panel);
    });

    const anchor = root.querySelector(".trk_stat_table_wrap");
    if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(tabsRoot, anchor.nextSibling);
    } else {
        root.appendChild(tabsRoot);
    }

    function activate(id) {
        tabsRoot.querySelectorAll("[data-sheet-tab]").forEach(tab => {
            const active = sheetTabId(tab) === id;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
        });
        tabsRoot.querySelectorAll("[data-sheet-panel]").forEach(panel => {
            const active = sheetPanelId(panel) === id;
            panel.classList.toggle("is-active", active);
            panel.hidden = !active;
        });
        localStorage.setItem("trk_data_tab", id);

        const activePanel = Array.from(tabsRoot.querySelectorAll("[data-sheet-panel]")).find(panel => sheetPanelId(panel) === id);
        if (activePanel && typeof initTableColumnFeatures === "function") {
            initTableColumnFeatures(activePanel);
        }
        const ganttWrap = activePanel && activePanel.querySelector(".gantt_wrap");
        if (ganttWrap) {
            initGanttResize(ganttWrap);
            initDeadlineDrag(ganttWrap);
        }
    }

    tabbar.addEventListener("click", event => {
        const tab = event.target.closest("[data-sheet-tab]");
        if (!tab) return;
        activate(sheetTabId(tab));
    });
    bindSheetTabDragDrop({
        groupKey: "user",
        tabsRoot,
        tabbar,
        tabSelector: "[data-sheet-tab]",
        panelSelector: "[data-sheet-panel]",
        tabId: sheetTabId,
        panelId: sheetPanelId,
        storageKey: "trk_data_tab_order",
        labelStorageKey: "trk_data_tab_labels",
        activate
    });
    registerSheetTabGroup({ groupKey: "user", tabsRoot, tabbar, storageKey: "trk_data_tab_order", activate });

    root.querySelectorAll(dataTableSelector).forEach(table => {
        if (table.closest(".trk_data_tabs")) return;
        const wrap = table.closest(".trk_timeline_wrap") || table;
        const header = wrap.previousElementSibling;
        if (header && header.classList.contains("trk_sub_header")) {
            header.hidden = true;
        }
        wrap.hidden = true;
    });
}

function bindSheetTabDragDrop(options) {
    const groupKey = options.groupKey;
    const tabsRoot = options.tabsRoot;
    const tabbar = options.tabbar;
    const tabSelector = options.tabSelector;
    const panelSelector = options.panelSelector;
    const tabId = options.tabId;
    const panelId = options.panelId;
    const storageKey = options.storageKey;
    const labelStorageKey = options.labelStorageKey;
    function readOrder() {
        return readStoredSheetOrder(storageKey);
    }

    function currentTabs() {
        return Array.from(tabbar.querySelectorAll(tabSelector));
    }

    function currentPanels() {
        return Array.from(tabsRoot.querySelectorAll(panelSelector));
    }

    function saveOrder() {
        saveAllSheetTabState();
    }

    function applyOrder(order) {
        if (!order.length) return;
        const tabsById = new Map(currentTabs().map(tab => [tabId(tab), tab]));
        const panelsById = new Map(currentPanels().map(panel => [panelId(panel), panel]));
        const orderedIds = order.filter(id => tabsById.has(id));
        currentTabs().map(tabId).forEach(id => {
            if (!orderedIds.includes(id)) orderedIds.push(id);
        });
        orderedIds.forEach(id => {
            tabbar.appendChild(tabsById.get(id));
            tabsRoot.appendChild(panelsById.get(id));
        });
    }

    function currentGroupKeyForTab(tab) {
        return tab.closest(".trk_data_tabs")?.dataset?.sheetGroup || groupKey;
    }

    function moveBefore(sourceId, targetId, targetTab) {
        if (!sourceId || !targetId || sourceId === targetId) return;
        moveSheetTabToGroup(sourceId, currentGroupKeyForTab(targetTab), targetId);
    }

    applyOrder(readOrder());
    currentTabs().forEach(tab => {
        tab.draggable = true;
        tab.addEventListener("dragstart", event => {
            const id = tabId(tab);
            sheetTabDragState = { id, groupKey: currentGroupKeyForTab(tab) };
            tab.classList.add("trk_sheet_tab_dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", id);
        });
        tab.addEventListener("dragend", () => {
            sheetTabDragState = null;
            document.querySelectorAll(".trk_sheet_tab, .trk_sheet_tabbar").forEach(item => {
                item.classList.remove("trk_sheet_tab_dragging", "trk_sheet_tab_drag_over", "trk_sheet_tabbar_drag_over");
            });
        });
        tab.addEventListener("dragover", event => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            document.querySelectorAll(".trk_sheet_tab_drag_over").forEach(item => item.classList.remove("trk_sheet_tab_drag_over"));
            const sourceId = sheetTabDragState?.id || event.dataTransfer.getData("text/plain");
            if (sourceId && sourceId !== tabId(tab)) tab.classList.add("trk_sheet_tab_drag_over");
        });
        tab.addEventListener("dragleave", () => {
            tab.classList.remove("trk_sheet_tab_drag_over");
        });
        tab.addEventListener("drop", event => {
            event.preventDefault();
            tab.classList.remove("trk_sheet_tab_drag_over");
            moveBefore(sheetTabDragState?.id || event.dataTransfer.getData("text/plain"), tabId(tab), tab);
        });
        tab.addEventListener("keydown", event => {
            if (event.key !== "F2") return;
            event.preventDefault();
            event.stopPropagation();
            beginSheetTabRename(tab, tabId(tab), tab.dataset.sheetLabelStorageKey || labelStorageKey);
        });
    });

    tabbar.addEventListener("dragover", event => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        tabbar.classList.add("trk_sheet_tabbar_drag_over");
    });
    tabbar.addEventListener("dragleave", event => {
        if (!tabbar.contains(event.relatedTarget)) {
            tabbar.classList.remove("trk_sheet_tabbar_drag_over");
        }
    });
    tabbar.addEventListener("drop", event => {
        event.preventDefault();
        tabbar.classList.remove("trk_sheet_tabbar_drag_over");
        if (event.target.closest(tabSelector)) return;
        moveSheetTabToGroup(sheetTabDragState?.id || event.dataTransfer.getData("text/plain"), groupKey, "");
    });
}

function escapeSheetTabText(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function readSheetTabMap(storageKey) {
    try {
        const parsed = JSON.parse(localStorage.getItem(storageKey) || "{}");
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_) {
        return {};
    }
}

function getSheetTabLabel(storageKey, id, fallback) {
    const labels = readSheetTabMap(storageKey);
    return labels[id] || fallback;
}

function setSheetTabLabel(storageKey, id, label) {
    const labels = readSheetTabMap(storageKey);
    const nextLabel = String(label || "").trim();
    if (nextLabel) {
        labels[id] = nextLabel;
    } else {
        delete labels[id];
    }
    localStorage.setItem(storageKey, JSON.stringify(labels));
}

function beginSheetTabRename(tab, id, labelStorageKey) {
    if (!labelStorageKey || tab.querySelector(".trk_sheet_label_input")) return;
    const labelSpan = tab.querySelector(".trk_sheet_label");
    if (!labelSpan) return;

    const previousLabel = labelSpan.textContent || "";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "trk_sheet_label_input";
    input.value = previousLabel;
    input.setAttribute("aria-label", "Tab name");

    let finished = false;
    function finish(save) {
        if (finished) return;
        finished = true;
        const nextLabel = save ? input.value.trim() : previousLabel;
        labelSpan.textContent = nextLabel || previousLabel;
        if (save) setSheetTabLabel(labelStorageKey, id, nextLabel || previousLabel);
        input.replaceWith(labelSpan);
        tab.draggable = true;
        tab.focus();
    }

    tab.draggable = false;
    labelSpan.replaceWith(input);
    input.focus();
    input.select();
    input.addEventListener("click", event => event.stopPropagation());
    input.addEventListener("keydown", event => {
        if (event.ctrlKey || event.metaKey) return;
        event.stopPropagation();
        if (event.key === "Enter") {
            event.preventDefault();
            finish(true);
        } else if (event.key === "Escape") {
            event.preventDefault();
            finish(false);
        }
    });
    input.addEventListener("blur", () => finish(true));
}

function initAdminMasterDataTabs() {
    const workCalendar = document.getElementById("work_calendar_card");
    if (document.querySelector(".admin_master_data_tabs")) return true;
    if (!workCalendar) return false;

    const labelByAction = [
        ["/admin/product-test-releases/create", "Test Release"],
        ["/admin/product-test-target-definitions/create", "Test Target"],
        ["/admin/product-test-targets/create", "Test Target"],
        ["/admin/product-test-environment-definitions/create", "Test Environment Definition"],
        ["/admin/product-test-environments/create", "Test Environment"],
        ["/admin/product-test-cases/create", "Test Case"],
        ["/admin/product-test-procedures/create", "Test Procedure"]
    ];
    const cards = Array.from(document.querySelectorAll("section.card"));
    const groups = cards
        .filter(card => card.compareDocumentPosition(workCalendar) & Node.DOCUMENT_POSITION_FOLLOWING)
        .map(card => {
            const actions = Array.from(card.querySelectorAll("form[action]"))
            .map(form => form.getAttribute("action") || "");
            const labelMatch = labelByAction.find(([action]) => actions.includes(action));
            if (!labelMatch) return null;
            const title = labelMatch[1];
            return {
                id: `admin_master_tab_${title.replace(/\W+/g, "_").toLowerCase()}`,
                label: title,
                count: card.querySelectorAll("tbody tr").length,
                node: card
            };
        })
        .filter(Boolean);
    groups.push({
        id: "admin_master_tab_work_calendar",
        label: "Work Calendar",
        count: workCalendar.querySelectorAll("tbody tr").length,
        node: workCalendar
    });

    if (groups.length <= 1) return false;

    const firstCard = groups[0].node;
    const hostParent = firstCard.parentNode;
    const groupNodes = new Set(groups.map(group => group.node));
    let cursor = firstCard.nextElementSibling;
    while (cursor && cursor !== workCalendar) {
        const next = cursor.nextElementSibling;
        if (!groupNodes.has(cursor)) cursor.hidden = true;
        cursor = next;
    }

    const tabsRoot = document.createElement("section");
    tabsRoot.className = "trk_data_tabs admin_master_data_tabs";
    tabsRoot.dataset.sheetGroup = "admin";
    const tabbar = document.createElement("div");
    tabbar.className = "trk_sheet_tabbar";
    tabbar.setAttribute("role", "tablist");
    tabbar.setAttribute("aria-label", "Admin master data tables");
    tabsRoot.appendChild(tabbar);
    hostParent.insertBefore(tabsRoot, firstCard);

    const storedId = localStorage.getItem("admin_master_data_tab") || "";
    const activeGroup = groups.find(group => group.id === storedId) || groups[0];

    groups.forEach(group => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = `trk_sheet_tab${group.id === activeGroup.id ? " is-active" : ""}`;
        tab.dataset.sheetTab = group.id;
        tab.dataset.sheetCurrentGroup = "admin";
        tab.dataset.sheetLabelStorageKey = "admin_master_data_tab_labels";
        tab.dataset.adminMasterTab = group.id;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", group.id === activeGroup.id ? "true" : "false");
        tab.innerHTML = `<span class="trk_sheet_label">${escapeSheetTabText(getSheetTabLabel("admin_master_data_tab_labels", group.id, group.label))}</span><span class="trk_sheet_count">${group.count}</span>`;
        tabbar.appendChild(tab);

        const panel = document.createElement("div");
        panel.className = `trk_sheet_panel${group.id === activeGroup.id ? " is-active" : ""}`;
        panel.dataset.sheetPanel = group.id;
        panel.dataset.sheetCurrentGroup = "admin";
        panel.dataset.adminMasterPanel = group.id;
        panel.hidden = group.id !== activeGroup.id;
        panel.setAttribute("role", "tabpanel");
        panel.appendChild(group.node);
        tabsRoot.appendChild(panel);
    });

    function activate(id) {
        tabsRoot.querySelectorAll("[data-sheet-tab]").forEach(tab => {
            const active = sheetTabId(tab) === id;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
        });
        tabsRoot.querySelectorAll("[data-sheet-panel]").forEach(panel => {
            const active = sheetPanelId(panel) === id;
            panel.classList.toggle("is-active", active);
            panel.hidden = !active;
        });
        localStorage.setItem("admin_master_data_tab", id);

        const activePanel = Array.from(tabsRoot.querySelectorAll("[data-sheet-panel]")).find(panel => sheetPanelId(panel) === id);
        if (activePanel && typeof initTableColumnFeatures === "function") {
            initTableColumnFeatures(activePanel);
        }
        const ganttWrap = activePanel && activePanel.querySelector(".gantt_wrap");
        if (ganttWrap) {
            initGanttResize(ganttWrap);
            initDeadlineDrag(ganttWrap);
        }
    }

    tabbar.addEventListener("click", event => {
        const tab = event.target.closest("[data-sheet-tab]");
        if (!tab) return;
        activate(sheetTabId(tab));
    });
    bindSheetTabDragDrop({
        groupKey: "admin",
        tabsRoot,
        tabbar,
        tabSelector: "[data-sheet-tab]",
        panelSelector: "[data-sheet-panel]",
        tabId: sheetTabId,
        panelId: sheetPanelId,
        storageKey: "admin_master_data_tab_order",
        labelStorageKey: "admin_master_data_tab_labels",
        activate
    });
    registerSheetTabGroup({ groupKey: "admin", tabsRoot, tabbar, storageKey: "admin_master_data_tab_order", activate });
    return true;
}

let adminMasterDataTabsObserver = null;
function scheduleAdminMasterDataTabs(attempt) {
    const attemptNo = attempt || 0;
    if (initAdminMasterDataTabs()) {
        if (adminMasterDataTabsObserver) {
            adminMasterDataTabsObserver.disconnect();
            adminMasterDataTabsObserver = null;
        }
        return;
    }
    if (!adminMasterDataTabsObserver && document.body) {
        adminMasterDataTabsObserver = new MutationObserver(() => {
            if (initAdminMasterDataTabs()) {
                adminMasterDataTabsObserver.disconnect();
                adminMasterDataTabsObserver = null;
            }
        });
        adminMasterDataTabsObserver.observe(document.body, { childList: true, subtree: true });
    }
    if (attemptNo >= 60) return;
    setTimeout(() => scheduleAdminMasterDataTabs(attemptNo + 1), 100);
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

document.addEventListener("DOMContentLoaded", () => {
    updateToggleLabel();
    loadTracking();
    scheduleAdminMasterDataTabs();
});
scheduleAdminMasterDataTabs();
document.getElementById("trk_refresh_btn")
    && document.getElementById("trk_refresh_btn").addEventListener("click", event => {
        const btn = event.currentTarget;
        const preserveScroll = btn && btn.dataset.preserveScroll === "1";
        if (btn) delete btn.dataset.preserveScroll;
        updateToggleLabel();
        loadTracking({ preserveScroll });
    });
})();
