(function () {
"use strict";

/* ── 서버 파일 로그 ──────────────────────────────────────────────
 *  clientLog(tag, message, level?)
 *  → POST /admin/debug/client-log  →  data/logs/client.log
 *  브라우저를 열지 않아도 서버 로그 파일로 JS 디버그 확인 가능.
 * ─────────────────────────────────────────────────────────────── */
const _clientLogQueue = [];
let _clientLogTimer = null;

function clientLog(tag, message, level) {
    const entry = { level: level || "info", tag: String(tag), message: String(message) };
    console.log("[clientLog]", entry.tag, entry.message);
    _clientLogQueue.push(entry);
    if (!_clientLogTimer) {
        _clientLogTimer = setTimeout(function () {
            _clientLogTimer = null;
            const batch = _clientLogQueue.splice(0);
            if (!batch.length) return;
            fetch("/admin/debug/client-log", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(batch),
            }).catch(function () { /* 로그 실패는 무시 */ });
        }, 200);
    }
}

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
                relocateTrackingSummaryToTabView4(root);
                initTrackingDataTabs(root);
                bindStatusEditable(root);
                bindColumnDragDrop(document);
                initStatClickable(document);
                bindGanttFold(root);
                const ganttWrap = root.querySelector(".gantt_wrap");
                if (ganttWrap) { initGanttResize(ganttWrap); initDeadlineDrag(ganttWrap); }
                bindHighlights(document);
                bindDefectImages(document);
                initDefectColResize(document);
                if (typeof initTableColumnFeatures === "function") initTableColumnFeatures(root);
                queueSheetTabLayoutRestore();
                refreshTabViewFoldToggleButtons();
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
let sheetTabFinalizeTimer = null;
let sheetTabLayoutRestorePending = false;
const SHEET_TAB_LABELS_GLOBAL = "sheet_tab_labels";
const SHEET_TAB_LAYOUT_SNAPSHOT_KEY = "sheet_tab_layout_v2";

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

function writeSheetTabLocations(locations) {
    try {
        localStorage.setItem("sheet_tab_locations", JSON.stringify(locations || {}));
    } catch (_) {
        /* ignore */
    }
}

function getDefaultTabHomeGroupKey(tabId) {
    if (!tabId) {
        return null;
    }
    const adminMatch = tabId.match(/^admin_master_(primary|secondary|quaternary|legacy|configs)_(.+)$/);
    if (adminMatch) {
        return `admin_${adminMatch[1]}`;
    }
    if (/^trk_data_tab_\d+$/.test(tabId)) {
        return "user";
    }
    return null;
}

function isCrossGroupTabLocation(tabId, groupKey) {
    const home = getDefaultTabHomeGroupKey(tabId);
    return !!(home && groupKey && groupKey !== home);
}

function readMergedSheetTabLocations() {
    const merged = { ...readSheetTabLocations() };
    const v2 = readSheetTabLayoutSnapshot();
    const fromV2 =
        v2?.locations && typeof v2.locations === "object" && !Array.isArray(v2.locations)
            ? v2.locations
            : {};
    Object.entries(fromV2).forEach(([tabId, raw]) => {
        const entry = resolveSheetTabLocationEntry(raw);
        if (!entry) {
            return;
        }
        const current = resolveSheetTabLocationEntry(merged[tabId]);
        const entryIsCross = isCrossGroupTabLocation(tabId, entry.groupKey);
        const currentIsCross = current ? isCrossGroupTabLocation(tabId, current.groupKey) : false;
        if (!current || (entryIsCross && !currentIsCross) || (entryIsCross === currentIsCross)) {
            merged[tabId] = entry;
        }
    });
    return merged;
}

function patchSheetTabLayoutSnapshotLocations(locations) {
    const snap = readSheetTabLayoutSnapshot() || { version: 2, orders: {}, activeTabs: {} };
    snap.locations = locations || {};
    snap.savedAt = Date.now();
    try {
        localStorage.setItem(SHEET_TAB_LAYOUT_SNAPSHOT_KEY, JSON.stringify(snap));
    } catch (_) {
        /* ignore */
    }
}

function recordSheetTabLocation(tabId, groupKey, index) {
    if (!tabId || !groupKey) {
        return;
    }
    const locations = readMergedSheetTabLocations();
    if (isCrossGroupTabLocation(tabId, groupKey)) {
        locations[tabId] = {
            groupKey,
            index: Number.isFinite(index) ? index : 0,
        };
    } else {
        delete locations[tabId];
    }
    writeSheetTabLocations(locations);
    patchSheetTabLayoutSnapshotLocations(locations);
}

function readStoredSheetOrder(storageKey) {
    try {
        const parsed = JSON.parse(localStorage.getItem(storageKey) || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
        return [];
    }
}

function writeStoredSheetOrder(storageKey, ids) {
    if (!storageKey) {
        return;
    }
    const next = Array.isArray(ids) ? ids.filter(Boolean) : [];
    localStorage.setItem(storageKey, JSON.stringify(next));
}

function sortItemsByStoredOrder(items, storageKey, getId) {
    const order = readStoredSheetOrder(storageKey);
    if (!order.length || typeof getId !== "function") {
        return items;
    }
    const byId = new Map(items.map((item) => [getId(item), item]));
    const sorted = order.filter((id) => byId.has(id)).map((id) => byId.get(id));
    items.forEach((item) => {
        if (!sorted.includes(item)) {
            sorted.push(item);
        }
    });
    return sorted;
}

function getStoredTabInsertIndex(group, tabId) {
    if (!group?.storageKey || !tabId) {
        return null;
    }
    const order = readStoredSheetOrder(group.storageKey);
    const index = order.indexOf(tabId);
    return index >= 0 ? index : order.length;
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
    dedupeSheetTabGroupDom(group);
}

function readSheetTabLayoutSnapshot() {
    try {
        const parsed = JSON.parse(localStorage.getItem(SHEET_TAB_LAYOUT_SNAPSHOT_KEY) || "null");
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            return parsed;
        }
    } catch (_) {
        /* ignore */
    }
    return null;
}

function writeSheetTabLayoutSnapshot(locations, orders, activeTabs) {
    const snapshot = {
        version: 2,
        locations: locations || {},
        orders: orders || {},
        activeTabs: activeTabs || {},
        savedAt: Date.now(),
    };
    try {
        localStorage.setItem(SHEET_TAB_LAYOUT_SNAPSHOT_KEY, JSON.stringify(snapshot));
    } catch (_) {
        /* ignore */
    }
}

function removeTabIdFromStoredGroupOrder(groupKey, tabId) {
    const group = sheetTabGroups.get(groupKey);
    if (!group?.storageKey || !tabId) {
        return;
    }
    const next = readStoredSheetOrder(group.storageKey).filter((id) => id !== tabId);
    writeStoredSheetOrder(group.storageKey, next);
}

function removeTabIdFromOtherGroupOrders(keepGroupKey, tabId) {
    if (!tabId) {
        return;
    }
    sheetTabGroups.forEach((group) => {
        if (group.groupKey !== keepGroupKey) {
            removeTabIdFromStoredGroupOrder(group.groupKey, tabId);
        }
    });
}

function collectSheetTabLayoutFromDom() {
    const locations = {};
    const orders = {};
    const activeTabs = {};
    sheetTabGroups.forEach((group) => {
        const ids = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]"))
            .map(sheetTabId)
            .filter(Boolean);
        if (group.storageKey) {
            orders[group.storageKey] = ids;
        }
        ids.forEach((id, index) => {
            locations[id] = { groupKey: group.groupKey, index };
        });
        if (group.storageTabKey) {
            const active = ids.find((id) => {
                const tab = group.tabbar.querySelector(`[data-sheet-tab="${id}"]`);
                return tab && tab.classList.contains("is-active");
            });
            if (active) {
                activeTabs[group.storageTabKey] = active;
            } else if (group.storageTabKey) {
                const stored = localStorage.getItem(group.storageTabKey);
                if (stored && ids.includes(stored)) {
                    activeTabs[group.storageTabKey] = stored;
                }
            }
        }
    });
    return { locations, orders, activeTabs };
}

function migrateLegacySheetTabLayoutSnapshot() {
    const existing = readSheetTabLayoutSnapshot();
    const locations = readMergedSheetTabLocations();
    const orders = {};
    if (existing?.orders && typeof existing.orders === "object") {
        Object.assign(orders, existing.orders);
    }
    sheetTabGroups.forEach((group) => {
        if (group.storageKey && !orders[group.storageKey]) {
            orders[group.storageKey] = readStoredSheetOrder(group.storageKey);
        }
    });
    return {
        version: existing?.version || 1,
        locations,
        orders,
        activeTabs: existing?.activeTabs || {},
    };
}

function applySheetTabLayoutSnapshot(snapshot) {
    if (!snapshot) {
        return;
    }
    if (snapshot.orders && typeof snapshot.orders === "object") {
        Object.entries(snapshot.orders).forEach(([storageKey, ids]) => {
            if (Array.isArray(ids)) {
                writeStoredSheetOrder(storageKey, ids);
            }
        });
    }
    if (snapshot.locations && typeof snapshot.locations === "object") {
        localStorage.setItem("sheet_tab_locations", JSON.stringify(snapshot.locations));
    }
}

function saveAllSheetTabState() {
    if (sheetTabLayoutRestorePending) {
        return;
    }
    const { locations, orders, activeTabs } = collectSheetTabLayoutFromDom();
    Object.entries(orders).forEach(([storageKey, ids]) => {
        writeStoredSheetOrder(storageKey, ids);
    });
    localStorage.setItem("sheet_tab_locations", JSON.stringify(locations));
    writeSheetTabLayoutSnapshot(locations, orders, activeTabs);
}

function persistSheetTabLayoutSoon() {
    if (sheetTabLayoutRestorePending) {
        return;
    }
    saveAllSheetTabState();
}

function findSheetTabEntry(id) {
    for (const group of sheetTabGroups.values()) {
        const tab = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]")).find(item => sheetTabId(item) === id);
        const panel = Array.from(group.tabsRoot.querySelectorAll("[data-sheet-panel]")).find(item => sheetPanelId(item) === id);
        if (tab && panel) return { group, tab, panel };
    }
    return null;
}

function isTabsRootRegionFolded(tabsRoot) {
    if (!(tabsRoot instanceof HTMLElement)) {
        return false;
    }
    const shell = tabsRoot.closest(".admin_tab_region_shell");
    return !!(shell && shell.classList.contains("is-tabview-region-folded"));
}

function activateSheetTabGroupExclusive(tabsRoot, tabId, storageTabKey) {
    if (!(tabsRoot instanceof HTMLElement)) {
        return { activeTab: null, activePanel: null, activeId: "" };
    }
    const tabs = Array.from(tabsRoot.querySelectorAll("[data-sheet-tab]"));
    const panels = Array.from(tabsRoot.querySelectorAll("[data-sheet-panel]"));
    if (!tabs.length) {
        return { activeTab: null, activePanel: null, activeId: "" };
    }

    let resolvedId = tabId;
    if (!resolvedId || !tabs.some((tab) => sheetTabId(tab) === resolvedId)) {
        const stored = storageTabKey ? localStorage.getItem(storageTabKey) : "";
        resolvedId =
            stored && tabs.some((tab) => sheetTabId(tab) === stored)
                ? stored
                : sheetTabId(tabs[0]);
    }
    if (!resolvedId) {
        return { activeTab: null, activePanel: null, activeId: "" };
    }

    tabs.forEach((tab) => {
        const active = sheetTabId(tab) === resolvedId;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    const regionFolded = isTabsRootRegionFolded(tabsRoot);
    panels.forEach((panel) => {
        const active = sheetPanelId(panel) === resolvedId;
        panel.classList.toggle("is-active", active);
        panel.hidden = regionFolded ? true : !active;
    });
    if (storageTabKey) {
        localStorage.setItem(storageTabKey, resolvedId);
    }

    return {
        activeId: resolvedId,
        activeTab: tabs.find((tab) => sheetTabId(tab) === resolvedId) || null,
        activePanel: panels.find((panel) => sheetPanelId(panel) === resolvedId) || null,
    };
}

function syncAllSheetTabGroupActives() {
    sheetTabGroups.forEach((group) => {
        if (!(group.tabsRoot instanceof HTMLElement) || typeof group.activate !== "function") {
            return;
        }
        const tabs = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]"));
        if (!tabs.length) {
            return;
        }
        const key = group.storageTabKey;
        let id = key ? localStorage.getItem(key) : "";
        if (!id || !tabs.some((tab) => sheetTabId(tab) === id)) {
            const current = tabs.find((tab) => tab.classList.contains("is-active"));
            id = current ? sheetTabId(current) : sheetTabId(tabs[0]);
        }
        group.activate(id);
    });
}

function ensureSheetGroupActive(group, preferredId) {
    const tabs = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]"));
    if (!tabs.length || typeof group.activate !== "function") {
        return;
    }
    let activeId = preferredId && tabs.some((tab) => sheetTabId(tab) === preferredId) ? preferredId : "";
    if (!activeId && group.storageTabKey) {
        const stored = localStorage.getItem(group.storageTabKey) || "";
        if (stored && tabs.some((tab) => sheetTabId(tab) === stored)) {
            activeId = stored;
        }
    }
    if (!activeId) {
        activeId = sheetTabId(tabs[0]);
    }
    group.activate(activeId);
}

function getSheetTabInsertIndexFromPointer(tabbar, clientX) {
    const tabs = Array.from(tabbar.querySelectorAll("[data-sheet-tab]"));
    if (!tabs.length) {
        return 0;
    }
    for (let i = 0; i < tabs.length; i += 1) {
        const rect = tabs[i].getBoundingClientRect();
        if (clientX < rect.left + rect.width / 2) {
            return i;
        }
    }
    return tabs.length;
}

function getSheetTabInsertIndexFromTab(tab, clientX) {
    const tabbar = tab.parentElement;
    if (!tabbar) {
        return 0;
    }
    const tabs = Array.from(tabbar.querySelectorAll("[data-sheet-tab]"));
    const index = tabs.indexOf(tab);
    if (index < 0) {
        return tabs.length;
    }
    const rect = tab.getBoundingClientRect();
    return clientX < rect.left + rect.width / 2 ? index : index + 1;
}

function clearSheetTabInsertIndicators() {
    document.querySelectorAll(".trk_sheet_tab_insert_before, .trk_sheet_tab_insert_after").forEach((el) => {
        el.classList.remove("trk_sheet_tab_insert_before", "trk_sheet_tab_insert_after");
    });
}

function showSheetTabInsertIndicator(tabbar, insertIndex) {
    clearSheetTabInsertIndicators();
    const tabs = Array.from(tabbar.querySelectorAll("[data-sheet-tab]"));
    if (!tabs.length) {
        return;
    }
    if (insertIndex <= 0) {
        tabs[0].classList.add("trk_sheet_tab_insert_before");
        return;
    }
    if (insertIndex >= tabs.length) {
        tabs[tabs.length - 1].classList.add("trk_sheet_tab_insert_after");
        return;
    }
    tabs[insertIndex].classList.add("trk_sheet_tab_insert_before");
}

function buildSheetTabOrderIds(tabbar, sourceId, insertIndex) {
    const tabs = Array.from(tabbar.querySelectorAll("[data-sheet-tab]"));
    const ids = tabs.map(sheetTabId).filter(Boolean);
    const fromIndex = ids.indexOf(sourceId);
    const working = fromIndex >= 0 ? ids.filter((id, index) => index !== fromIndex) : ids.slice();
    let to = insertIndex;
    if (fromIndex >= 0 && fromIndex < insertIndex) {
        to -= 1;
    }
    to = Math.max(0, Math.min(to, working.length));
    const next = working.slice();
    next.splice(to, 0, sourceId);
    const seen = new Set();
    const unique = next.filter((id) => {
        if (!id || seen.has(id)) {
            return false;
        }
        seen.add(id);
        return true;
    });
    const unchanged =
        unique.length === ids.length && unique.every((id, index) => id === ids[index]);
    return { fromIndex, to, unique, unchanged };
}

function dedupeSheetTabGroupDom(group) {
    if (!group?.tabbar || !group?.tabsRoot) {
        return;
    }
    const seenTabs = new Set();
    Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]")).forEach((tab) => {
        const id = sheetTabId(tab);
        if (!id || seenTabs.has(id)) {
            tab.remove();
            return;
        }
        seenTabs.add(id);
    });
    const seenPanels = new Set();
    Array.from(group.tabsRoot.querySelectorAll("[data-sheet-panel]")).forEach((panel) => {
        const id = sheetPanelId(panel);
        if (!id || seenPanels.has(id)) {
            panel.remove();
            return;
        }
        seenPanels.add(id);
    });
}

function reorderSheetTabsInGroup(sourceId, targetGroupKey, insertIndex) {
    if (!sourceId || !targetGroupKey) {
        return;
    }
    const source = findSheetTabEntry(sourceId);
    const targetGroup = sheetTabGroups.get(targetGroupKey);
    if (!source || !targetGroup) {
        return;
    }

    const { unique: ids, unchanged } = buildSheetTabOrderIds(
        targetGroup.tabbar,
        sourceId,
        insertIndex,
    );
    if (unchanged) {
        return;
    }

    source.tab.dataset.sheetCurrentGroup = targetGroupKey;
    source.panel.dataset.sheetCurrentGroup = targetGroupKey;

    ids.forEach((id) => {
        const entry = findSheetTabEntry(id);
        if (!entry) {
            return;
        }
        targetGroup.tabbar.appendChild(entry.tab);
        targetGroup.tabsRoot.appendChild(entry.panel);
    });
    dedupeSheetTabGroupDom(targetGroup);

    if (source.group.groupKey !== targetGroupKey) {
        const labelKey = targetGroup.labelStorageKey || source.tab.dataset.sheetLabelStorageKey || "";
        if (labelKey) {
            source.tab.dataset.sheetLabelStorageKey = labelKey;
        }
        removeTabIdFromOtherGroupOrders(targetGroupKey, sourceId);
        const targetOrder = readStoredSheetOrder(targetGroup.storageKey);
        if (!targetOrder.includes(sourceId)) {
            const insertAt = Math.max(0, Math.min(insertIndex, targetOrder.length));
            const nextOrder = targetOrder.slice();
            nextOrder.splice(insertAt, 0, sourceId);
            writeStoredSheetOrder(targetGroup.storageKey, nextOrder);
        }
    }

    const finalIndex = ids.indexOf(sourceId);
    recordSheetTabLocation(sourceId, targetGroupKey, finalIndex >= 0 ? finalIndex : insertIndex);
    if (!sheetTabLayoutRestorePending) {
        saveAllSheetTabState();
    }
    if (source.group.groupKey !== targetGroupKey) {
        refreshGroupTabLabels(source.group);
        ensureSheetGroupActive(source.group, "");
    }
    refreshGroupTabLabels(targetGroup);
    ensureSheetGroupActive(targetGroup, sourceId);
}

function moveSheetTabToGroup(sourceId, targetGroupKey, targetId) {
    const targetGroup = sheetTabGroups.get(targetGroupKey);
    if (!targetGroup) {
        return;
    }
    const tabs = Array.from(targetGroup.tabbar.querySelectorAll("[data-sheet-tab]"));
    let index = tabs.length;
    if (targetId) {
        const fromTarget = tabs.findIndex((tab) => sheetTabId(tab) === targetId);
        if (fromTarget >= 0) {
            index = fromTarget;
        }
    } else {
        const storedIndex = getStoredTabInsertIndex(targetGroup, sourceId);
        if (storedIndex != null) {
            index = storedIndex;
        }
    }
    reorderSheetTabsInGroup(sourceId, targetGroupKey, Math.max(0, index));
}

function resolveSheetTabLocationEntry(raw) {
    if (typeof raw === "string" && raw) {
        return { groupKey: raw, index: null };
    }
    if (raw && typeof raw === "object" && raw.groupKey) {
        const index = Number.isFinite(raw.index) ? raw.index : null;
        return { groupKey: String(raw.groupKey), index };
    }
    return null;
}

function hasPendingCrossGroupTabLocations() {
    const locations = readMergedSheetTabLocations();
    return Object.entries(locations).some(([id, raw]) => {
        const entry = resolveSheetTabLocationEntry(raw);
        if (!entry) {
            return false;
        }
        if (!sheetTabGroups.has(entry.groupKey)) {
            return true;
        }
        const current = findSheetTabEntry(id);
        return !!(current && current.group.groupKey !== entry.groupKey);
    });
}

function applyCrossGroupSheetTabLocations() {
    const locations = readMergedSheetTabLocations();
    const ids = Object.keys(locations).filter((id) => {
        const entry = resolveSheetTabLocationEntry(locations[id]);
        return entry && isCrossGroupTabLocation(id, entry.groupKey);
    });
    if (!ids.length) {
        return;
    }
    let pass = 0;
    let moved = true;
    while (moved && pass < ids.length + 2) {
        moved = false;
        pass += 1;
        ids.forEach((id) => {
            const raw = locations[id];
            const entry = resolveSheetTabLocationEntry(raw);
            if (!entry || !sheetTabGroups.has(entry.groupKey)) {
                return;
            }
            const current = findSheetTabEntry(id);
            if (!current || current.group.groupKey === entry.groupKey) {
                return;
            }
            const targetGroup = sheetTabGroups.get(entry.groupKey);
            const insertIndex =
                entry.index != null
                    ? entry.index
                    : getStoredTabInsertIndex(targetGroup, id);
            reorderSheetTabsInGroup(id, entry.groupKey, insertIndex);
            moved = true;
        });
    }
}

function collectKnownSheetTabIds() {
    const known = new Set();
    sheetTabGroups.forEach((group) => {
        if (!(group.tabbar instanceof HTMLElement)) {
            return;
        }
        Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]")).forEach((tab) => {
            const id = sheetTabId(tab);
            if (id) {
                known.add(id);
            }
        });
    });
    return known;
}

function pruneStaleSheetTabStorage() {
    const knownIds = collectKnownSheetTabIds();
    const locations = readMergedSheetTabLocations();
    let locationsChanged = false;
    Object.keys(locations).forEach((id) => {
        if (!knownIds.has(id)) {
            delete locations[id];
            locationsChanged = true;
        }
    });
    if (locationsChanged) {
        writeSheetTabLocations(locations);
        patchSheetTabLayoutSnapshotLocations(locations);
    }
    sheetTabGroups.forEach((group) => {
        if (!group.storageKey) {
            return;
        }
        const order = readStoredSheetOrder(group.storageKey).filter((id) => knownIds.has(id));
        writeStoredSheetOrder(group.storageKey, order);
    });
}

function restoreSheetTabLayoutFromStorage() {
    if (!sheetTabGroups.size) {
        return;
    }
    sheetTabLayoutRestorePending = true;
    const snapshot = migrateLegacySheetTabLayoutSnapshot();
    applySheetTabLayoutSnapshot(snapshot);
    applyCrossGroupSheetTabLocations();
    pruneStaleSheetTabStorage();
    sheetTabGroups.forEach(applyStoredSheetGroupOrder);
    if (snapshot?.activeTabs && typeof snapshot.activeTabs === "object") {
        sheetTabGroups.forEach((group) => {
            if (!group.storageTabKey) {
                return;
            }
            const storedActive = snapshot.activeTabs[group.storageTabKey];
            if (storedActive && typeof group.activate === "function") {
                group.activate(storedActive);
                return;
            }
        });
    }
    syncAllSheetTabGroupActives();
    sheetTabGroups.forEach(refreshGroupTabLabels);
    syncAllTabViewRegionFolds();
    sheetTabLayoutRestorePending = false;
    if (!hasPendingCrossGroupTabLocations()) {
        sheetTabLayoutRestoreAttempts = 0;
        saveAllSheetTabState();
    } else if (sheetTabLayoutRestoreAttempts < SHEET_TAB_LAYOUT_RESTORE_MAX) {
        sheetTabLayoutRestoreAttempts += 1;
        queueSheetTabLayoutRestore(100);
    }
    refreshTabViewFoldToggleButtons();
}

function refreshSheetTabButtonLabel(tab, id, defaultLabel) {
    const label = getSheetTabLabel(tab.dataset.sheetLabelStorageKey || null, id, defaultLabel);
    const countEl = tab.querySelector(".trk_sheet_count");
    const count = countEl ? countEl.textContent : "0";
    if (defaultLabel && !tab.dataset.sheetTabDefaultLabel) {
        tab.dataset.sheetTabDefaultLabel = defaultLabel;
    }
    tab.innerHTML = `<span class="trk_sheet_label">${escapeSheetTabText(label)}</span><span class="trk_sheet_count">${count}</span>`;
}

function refreshGroupTabLabels(group) {
    if (!group?.tabbar) {
        return;
    }
    Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]")).forEach((tab) => {
        const id = sheetTabId(tab);
        const entry = findSheetTabEntry(id);
        const defaultLabel = getSheetTabDefaultDisplayLabel(tab, entry?.panel);
        refreshSheetTabButtonLabel(tab, id, defaultLabel);
        syncSheetTabPanelTitleFromTab(tab);
    });
}

let sheetTabLayoutRestoreQueued = false;
let sheetTabLayoutRestoreAttempts = 0;
const SHEET_TAB_LAYOUT_RESTORE_MAX = 80;

function queueSheetTabLayoutRestore(delayMs) {
    const waitMs = Number.isFinite(delayMs) ? delayMs : 0;
    if (sheetTabLayoutRestoreQueued) {
        return;
    }
    sheetTabLayoutRestoreQueued = true;
    clearTimeout(sheetTabFinalizeTimer);
    sheetTabFinalizeTimer = setTimeout(() => {
        sheetTabLayoutRestoreQueued = false;
        sheetTabFinalizeTimer = null;
        restoreSheetTabLayoutFromStorage();
    }, waitMs);
}

function finalizeSheetTabGroups() {
    queueSheetTabLayoutRestore();
}

function scheduleFinalizeSheetTabGroups() {
    queueSheetTabLayoutRestore();
}

function ensureCardHeaderActions(headerRow) {
    if (!(headerRow instanceof HTMLElement)) {
        return null;
    }
    let actions = headerRow.querySelector(":scope > .card_header_actions");
    if (!actions) {
        actions = document.createElement("div");
        actions.className = "card_header_actions";
        headerRow.appendChild(actions);
    }
    return actions;
}

function moveActionBarChildrenToHeaderActions(actionBar, actions) {
    if (!(actionBar instanceof HTMLElement) || !(actions instanceof HTMLElement)) {
        return;
    }
    while (actionBar.firstElementChild) {
        actions.appendChild(actionBar.firstElementChild);
    }
    actionBar.dataset.headerActionsMoved = "1";
    actionBar.hidden = true;
}

function consolidateCardHeaderToolbar(root) {
    const scope = root instanceof HTMLElement ? root : document;
    scope.querySelectorAll("section.card").forEach((card) => {
        const header = card.querySelector(
            ":scope > .section_header_row, :scope > .admin_tab_region_title",
        );
        if (!header) {
            return;
        }
        const actions = ensureCardHeaderActions(header);
        card.querySelectorAll(":scope > .table_action_bar").forEach((bar) => {
            if (bar.closest("table, td, th")) {
                return;
            }
            moveActionBarChildrenToHeaderActions(bar, actions);
        });
        const headerBar = header.querySelector(":scope > .table_action_bar");
        if (headerBar) {
            moveActionBarChildrenToHeaderActions(headerBar, actions);
        }
    });
}

const TAB_VIEW_TABLE_FOLD_META = {
    admin_configs: { regionKey: "tabview_1", shell: "#admin_tab_region_configs", groupKey: "admin_configs" },
    admin_primary: { regionKey: "tabview_2", shell: "#admin_tab_region_primary", groupKey: "admin_primary" },
    admin_secondary: { regionKey: "tabview_3", shell: "#admin_tab_region_secondary", groupKey: "admin_secondary" },
    admin_quaternary: { regionKey: "tabview_4", shell: "#admin_tab_region_quaternary", groupKey: "admin_quaternary" },
};
const TABVIEW_REGION_FOLD_KEY = "tabview_region_fold_v1";
const SHEET_TAB_TABLE_FOLD_KEY = "sheet_tab_table_fold_v1";
let tabViewRegionFoldLegacyMigrated = false;

function readTabViewRegionFoldStates() {
    try {
        const parsed = JSON.parse(localStorage.getItem(TABVIEW_REGION_FOLD_KEY) || "{}");
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_) {
        return {};
    }
}

function writeTabViewRegionFoldStates(states) {
    try {
        localStorage.setItem(TABVIEW_REGION_FOLD_KEY, JSON.stringify(states));
    } catch (_) {
        /* ignore */
    }
}

function migrateLegacyTabViewRegionFoldStates() {
    if (tabViewRegionFoldLegacyMigrated) {
        return;
    }
    tabViewRegionFoldLegacyMigrated = true;
    const states = readTabViewRegionFoldStates();
    let changed = false;
    let legacy = {};
    try {
        legacy = JSON.parse(localStorage.getItem(SHEET_TAB_TABLE_FOLD_KEY) || "{}");
        if (!legacy || typeof legacy !== "object" || Array.isArray(legacy)) {
            legacy = {};
        }
    } catch (_) {
        legacy = {};
    }
    Object.values(TAB_VIEW_TABLE_FOLD_META).forEach((meta) => {
        if (states[meta.regionKey] === true) {
            return;
        }
        const region = legacy[meta.regionKey];
        if (region && typeof region === "object" && Object.values(region).some((value) => value === true)) {
            states[meta.regionKey] = true;
            changed = true;
        }
    });
    if (changed) {
        writeTabViewRegionFoldStates(states);
    }
}

function isTabViewRegionFolded(regionKey) {
    migrateLegacyTabViewRegionFoldStates();
    return !!readTabViewRegionFoldStates()[regionKey];
}

function setTabViewRegionFolded(regionKey, folded) {
    if (!regionKey) {
        return;
    }
    const states = readTabViewRegionFoldStates();
    if (folded) {
        states[regionKey] = true;
    } else {
        delete states[regionKey];
    }
    writeTabViewRegionFoldStates(states);
}

function tabViewRegionHasFoldableContent(meta) {
    const shell = document.querySelector(meta.shell);
    if (!shell) {
        return false;
    }
    const body = shell.querySelector(".admin_tab_region_body");
    return !!(
        body &&
        body.querySelector(
            ".admin_master_data_tabs [data-sheet-tab], .trk_data_tabs [data-sheet-tab]",
        )
    );
}

function applyTabViewRegionFold(meta, folded) {
    const shell = document.querySelector(meta.shell);
    if (!shell) {
        return;
    }
    shell.classList.toggle("is-tabview-region-folded", !!folded);
    shell.querySelectorAll(".trk_sheet_panel.is-table-folded").forEach((panel) => {
        panel.classList.remove("is-table-folded");
    });

    const regionBody = shell.querySelector(".admin_tab_region_body");
    if (regionBody) {
        regionBody.querySelectorAll(":scope > section.card").forEach((card) => {
            if (folded) {
                if (card.dataset.tabviewRegionFoldOrphanStored !== "1") {
                    card.dataset.tabviewRegionFoldOrphanStored = "1";
                    card.dataset.tabviewRegionFoldOrphanWasHidden = card.hidden ? "1" : "0";
                }
                card.hidden = true;
            } else if (card.dataset.tabviewRegionFoldOrphanStored === "1") {
                card.hidden = card.dataset.tabviewRegionFoldOrphanWasHidden === "1";
                delete card.dataset.tabviewRegionFoldOrphanStored;
                delete card.dataset.tabviewRegionFoldOrphanWasHidden;
            }
        });
    }

    const tabsRoot = shell.querySelector(".admin_master_data_tabs, .trk_data_tabs");
    if (tabsRoot instanceof HTMLElement) {
        tabsRoot.classList.toggle("is-tabview-region-folded", !!folded);
        const panels = Array.from(tabsRoot.querySelectorAll("[data-sheet-panel]"));
        if (folded) {
            panels.forEach((panel) => {
                if (panel.dataset.tabviewRegionFoldStored !== "1") {
                    panel.dataset.tabviewRegionFoldStored = "1";
                    panel.dataset.tabviewRegionFoldWasHidden = panel.hidden ? "1" : "0";
                }
                panel.hidden = true;
            });
        } else {
            panels.forEach((panel) => {
                if (panel.dataset.tabviewRegionFoldStored !== "1") {
                    return;
                }
                const wasHidden = panel.dataset.tabviewRegionFoldWasHidden === "1";
                delete panel.dataset.tabviewRegionFoldStored;
                delete panel.dataset.tabviewRegionFoldWasHidden;
                panel.hidden = wasHidden;
            });

            const group = sheetTabGroups.get(meta.groupKey);
            if (group && typeof group.activate === "function") {
                const tabs = Array.from(group.tabbar.querySelectorAll("[data-sheet-tab]"));
                let id = group.storageTabKey ? localStorage.getItem(group.storageTabKey) : "";
                if (!id || !tabs.some((tab) => sheetTabId(tab) === id)) {
                    const activeTab = tabs.find((tab) => tab.classList.contains("is-active"));
                    id = activeTab ? sheetTabId(activeTab) : "";
                }
                if (id) {
                    group.activate(id);
                }
            }
        }
    }
}

function updateTabViewRegionFoldButton(meta, folded) {
    const shell = document.querySelector(meta.shell);
    if (!shell) {
        return;
    }
    const btn = shell.querySelector(`[data-sheet-tab-table-fold-toggle="${meta.regionKey}"]`);
    if (!btn) {
        ensureSheetTabFoldToggleButton(meta);
        return;
    }
    const hasContent = tabViewRegionHasFoldableContent(meta);
    btn.disabled = !hasContent;
    btn.textContent = folded ? "탭뷰 펼치기" : "탭뷰 접기";
    btn.title = folded ? "탭 패널 펼치기 (탭바 유지)" : "탭 패널 접기 (탭바 유지)";
    btn.setAttribute("aria-expanded", folded ? "false" : "true");
}

function syncTabViewRegionFold(meta) {
    const folded = isTabViewRegionFolded(meta.regionKey);
    applyTabViewRegionFold(meta, folded);
    updateTabViewRegionFoldButton(meta, folded);
    updateAllTabViewsRegionFoldToggleButton();
}

function syncAllTabViewRegionFolds() {
    Object.values(TAB_VIEW_TABLE_FOLD_META).forEach((meta) => syncTabViewRegionFold(meta));
    updateAllTabViewsRegionFoldToggleButton();
}

function getFoldableTabViewMetas() {
    return Object.values(TAB_VIEW_TABLE_FOLD_META).filter((meta) => tabViewRegionHasFoldableContent(meta));
}

function areAllTabViewsRegionFolded() {
    const metas = getFoldableTabViewMetas();
    if (!metas.length) {
        return false;
    }
    return metas.every((meta) => isTabViewRegionFolded(meta.regionKey));
}

function updateAllTabViewsRegionFoldToggleButton() {
    const btn = document.getElementById("all_tabviews_region_fold_toggle");
    if (!btn) {
        return;
    }
    const metas = getFoldableTabViewMetas();
    const allFolded = areAllTabViewsRegionFolded();
    btn.disabled = !metas.length;
    btn.textContent = allFolded ? "모든탭뷰펼치기" : "모든탭뷰접기";
    btn.title = allFolded ? "Tab View 1~4 패널 모두 펼치기" : "Tab View 1~4 패널 모두 접기 (탭바 유지)";
    btn.setAttribute("aria-expanded", allFolded ? "false" : "true");
}

function setAllTabViewsRegionFolded(folded) {
    const metas = getFoldableTabViewMetas();
    if (!metas.length) {
        return;
    }
    const states = readTabViewRegionFoldStates();
    metas.forEach((meta) => {
        if (folded) {
            states[meta.regionKey] = true;
        } else {
            delete states[meta.regionKey];
        }
    });
    writeTabViewRegionFoldStates(states);
    metas.forEach((meta) => {
        applyTabViewRegionFold(meta, folded);
        updateTabViewRegionFoldButton(meta, folded);
    });
    updateAllTabViewsRegionFoldToggleButton();
}

function toggleAllTabViewsRegionFold() {
    setAllTabViewsRegionFolded(!areAllTabViewsRegionFolded());
}

function initAllTabViewsRegionFoldToggleButton() {
    const btn = document.getElementById("all_tabviews_region_fold_toggle");
    if (!btn || btn.dataset.tabviewFoldAllBound === "1") {
        updateAllTabViewsRegionFoldToggleButton();
        return;
    }
    btn.dataset.tabviewFoldAllBound = "1";
    btn.addEventListener("click", (event) => {
        event.preventDefault();
        toggleAllTabViewsRegionFold();
    });
    updateAllTabViewsRegionFoldToggleButton();
}

function toggleTabViewRegionFold(meta) {
    const folded = !isTabViewRegionFolded(meta.regionKey);
    setTabViewRegionFolded(meta.regionKey, folded);
    applyTabViewRegionFold(meta, folded);
    updateTabViewRegionFoldButton(meta, folded);
    updateAllTabViewsRegionFoldToggleButton();
}

function ensureSheetTabFoldToggleButton(meta) {
    const shell = document.querySelector(meta.shell);
    if (!shell) {
        return null;
    }
    consolidateCardHeaderToolbar(shell);
    const header = shell.querySelector(
        ":scope > .section_header_row, :scope > .admin_tab_region_title, :scope > .section_header_row.admin_tab_region_title",
    );
    if (!header) {
        return null;
    }
    const actions = ensureCardHeaderActions(header);
    let btn = shell.querySelector(`[data-sheet-tab-table-fold-toggle="${meta.regionKey}"]`);
    if (btn) {
        return btn;
    }
    btn = document.createElement("button");
    btn.type = "button";
    btn.className = "qc_mode_action_button trk_tabview_table_fold_btn";
    btn.dataset.sheetTabTableFoldToggle = meta.regionKey;
    btn.setAttribute("data-sheet-tab-table-fold-toggle", meta.regionKey);
    btn.dataset.sheetTabFoldGroupKey = meta.groupKey;
    btn.textContent = "탭뷰 접기";
    btn.title = "탭 패널 접기 (탭바 유지)";
    btn.setAttribute("aria-expanded", "true");
    btn.disabled = true;
    btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleTabViewRegionFold(meta);
    });
    actions.appendChild(btn);
    return btn;
}

function initTabViewTableFoldToggleButtons() {
    consolidateCardHeaderToolbar(document);
    Object.values(TAB_VIEW_TABLE_FOLD_META).forEach((meta) => ensureSheetTabFoldToggleButton(meta));
}

function refreshTabViewFoldToggleButtons() {
    consolidateCardHeaderToolbar(document);
    initTabViewTableFoldToggleButtons();
    syncAllTabViewRegionFolds();
    initAllTabViewsRegionFoldToggleButton();
}

function attachSheetTabFoldHandlers(group) {
    const meta = TAB_VIEW_TABLE_FOLD_META[group?.groupKey];
    if (!meta) {
        return;
    }
    ensureSheetTabFoldToggleButton(meta);
    syncTabViewRegionFold(meta);
}

function registerSheetTabGroup(options) {
    sheetTabGroups.set(options.groupKey, {
        ...options,
        storageTabKey: options.storageTabKey || null,
        labelStorageKey: options.labelStorageKey || null,
    });
    const group = sheetTabGroups.get(options.groupKey);
    if (group) {
        attachSheetTabFoldHandlers(group);
    }
    scheduleFinalizeSheetTabGroups();
}

function createAdminSummaryCard(label, nodes) {
    const usable = (nodes || []).filter((node) => node instanceof HTMLElement);
    if (!usable.length) {
        return null;
    }
    const card = document.createElement("section");
    card.className = "card";
    card.dataset.adminTabLabel = label;
    const headerRow = document.createElement("div");
    headerRow.className = "section_header_row";
    const title = document.createElement("h3");
    title.textContent = label;
    headerRow.appendChild(title);
    card.appendChild(headerRow);
    usable.forEach((node) => card.appendChild(node));
    return card;
}

function refreshAdminTabRegion(regionKey) {
    const regionBody = document.querySelector(`[data-admin-tab-region="${regionKey}"]`);
    if (!(regionBody instanceof HTMLElement)) {
        return false;
    }
    const tabs = regionBody.querySelector(".admin_master_data_tabs");
    if (tabs) {
        Array.from(tabs.querySelectorAll("[data-sheet-panel]")).forEach((panel) => {
            Array.from(panel.querySelectorAll(":scope > section.card")).forEach((card) => {
                regionBody.appendChild(card);
            });
        });
        tabs.remove();
    }
    regionBody.dataset.adminTabsInit = "0";
    const ok = initAdminMasterDataTabRegion(regionBody);
    if (ok) {
        queueSheetTabLayoutRestore();
    }
    return ok;
}

function relocateTrackingSummaryToTabView4(root) {
    if (!(root instanceof HTMLElement)) {
        return;
    }
    const regionBody = document.querySelector('[data-admin-tab-region="quaternary"]');
    if (!(regionBody instanceof HTMLElement)) {
        return;
    }

    const statWrap = root.querySelector(".trk_stat_table_wrap");
    if (statWrap && !regionBody.querySelector('[data-admin-tab-label="Statistics"]')) {
        const statCard = createAdminSummaryCard("Statistics", [statWrap]);
        if (statCard) {
            regionBody.appendChild(statCard);
        }
    }

    const defectHeader = Array.from(root.querySelectorAll(".trk_sub_header")).find((header) =>
        (header.textContent || "").includes("미결 결함"),
    );
    if (defectHeader && !regionBody.querySelector('[data-admin-tab-label="Open Defects"]')) {
        const nodes = [defectHeader];
        let cursor = defectHeader.nextElementSibling;
        while (cursor && !cursor.classList.contains("trk_sub_header")) {
            nodes.push(cursor);
            cursor = cursor.nextElementSibling;
        }
        const defectCard = createAdminSummaryCard("Open Defects", nodes);
        if (defectCard) {
            regionBody.appendChild(defectCard);
        }
    }

    regionBody.dataset.trkSummaryRelocated = "1";
    refreshAdminTabRegion("quaternary");
}

function initTrackingDataTabs(root) {
    const headers = Array.from(root.querySelectorAll(".trk_sub_header")).filter(
        (header) =>
            !header.closest(".trk_data_tabs") && !(header.textContent || "").includes("미결 결함"),
    );
    if (headers.length === 0 || root.querySelector(".trk_data_tabs")) {
        return;
    }

    const dataTableSelector = [
        ".trk_defect_table",
        ".trk_test_release_table",
        ".trk_test_target_table",
        ".trk_test_environment_table",
        ".trk_test_case_master_table",
        ".trk_test_procedure_master_table",
        ".trk_result_table",
        ".trk_case_table",
        ".trk_proc_result_table",
        ".trk_evidence_table",
        ".trk_report_table",
        ".gantt_wrap"
    ].join(",");

    const labelBySelector = [
        [".gantt_wrap", "Timeline"],
        [".trk_test_release_table", "Test Release"],
        [".trk_test_target_table", "Test Targets"],
        [".trk_test_environment_table", "Test Configs"],
        [".trk_test_case_master_table", "Test Case"],
        [".trk_test_procedure_master_table", "Test Procedure"],
        [".trk_result_table", "Results"],
        [".trk_case_table", "Test Case"],
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

    const sortedGroups = sortItemsByStoredOrder(groups, "trk_data_tab_order", (group) => group.id);

    const tabsRoot = document.createElement("section");
    tabsRoot.className = "trk_data_tabs";
    tabsRoot.dataset.sheetGroup = "user";
    const tabbar = document.createElement("div");
    tabbar.className = "trk_sheet_tabbar";
    tabbar.setAttribute("role", "tablist");
    tabbar.setAttribute("aria-label", "Tab View 1");
    tabsRoot.appendChild(tabbar);

    const storedId = localStorage.getItem("trk_data_tab") || "";
    const activeGroup = sortedGroups.find((group) => group.id === storedId) || sortedGroups[0];

    sortedGroups.forEach((group) => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = `trk_sheet_tab${group.id === activeGroup.id ? " is-active" : ""}`;
        tab.dataset.sheetTab = group.id;
        tab.dataset.sheetCurrentGroup = "user";
        tab.dataset.sheetLabelStorageKey = "trk_data_tab_labels";
        tab.dataset.sheetTabDefaultLabel = group.label;
        tab.dataset.trkTab = group.id;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", group.id === activeGroup.id ? "true" : "false");
        tab.innerHTML = `<span class="trk_sheet_label">${escapeSheetTabText(getSheetTabLabel("trk_data_tab_labels", group.id, group.label))}</span><span class="trk_sheet_count">${group.count}</span>`;
        tabbar.appendChild(tab);

        const panel = document.createElement("div");
        panel.className = `trk_sheet_panel${group.id === activeGroup.id ? " is-active" : ""}`;
        panel.dataset.sheetPanel = group.id;
        panel.dataset.sheetCurrentGroup = "user";
        panel.dataset.sheetTabDefaultLabel = group.label;
        panel.dataset.trkPanel = group.id;
        panel.hidden = group.id !== activeGroup.id;
        panel.setAttribute("role", "tabpanel");
        group.nodes.forEach((node) => panel.appendChild(node));
        tabsRoot.appendChild(panel);
    });

    const anchor = headers[0] || root.firstElementChild;
    if (anchor && anchor.parentNode === root) {
        root.insertBefore(tabsRoot, anchor);
    } else {
        root.prepend(tabsRoot);
    }

    function activate(id) {
        const { activePanel, activeTab } = activateSheetTabGroupExclusive(tabsRoot, id, "trk_data_tab");
        if (activeTab) {
            syncSheetTabPanelTitleFromTab(activeTab);
        }
        if (activePanel && typeof initTableColumnFeatures === "function") {
            initTableColumnFeatures(activePanel);
        }
        const ganttWrap = activePanel && activePanel.querySelector(".gantt_wrap");
        if (ganttWrap) {
            initGanttResize(ganttWrap);
            initDeadlineDrag(ganttWrap);
        }
    }

    Array.from(tabbar.querySelectorAll("[data-sheet-tab]")).forEach((tab) => syncSheetTabPanelTitleFromTab(tab));

    tabbar.addEventListener("click", (event) => {
        const tab = event.target.closest("[data-sheet-tab]");
        if (!tab || !tabbar.contains(tab)) {
            return;
        }
        event.stopPropagation();
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
        activate,
    });
    registerSheetTabGroup({
        groupKey: "user",
        tabsRoot,
        tabbar,
        storageKey: "trk_data_tab_order",
        storageTabKey: "trk_data_tab",
        labelStorageKey: "trk_data_tab_labels",
        activate,
    });
    activate(activeGroup.id);
    consolidateCardHeaderToolbar(root);

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

    applyOrder(readOrder());
    currentTabs().forEach(tab => {
        if (tab.dataset.sheetTabDragBound === "1") {
            return;
        }
        tab.dataset.sheetTabDragBound = "1";
        tab.draggable = true;
        tab.addEventListener("dragstart", event => {
            const id = tabId(tab);
            sheetTabDragState = { id, groupKey: currentGroupKeyForTab(tab) };
            tab.classList.add("trk_sheet_tab_dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.dropEffect = "move";
            event.dataTransfer.setData("text/plain", id);
        });
        tab.addEventListener("dragend", () => {
            sheetTabDragState = null;
            clearSheetTabInsertIndicators();
            document.querySelectorAll(".trk_sheet_tab, .trk_sheet_tabbar").forEach(item => {
                item.classList.remove("trk_sheet_tab_dragging", "trk_sheet_tab_drag_over", "trk_sheet_tabbar_drag_over");
            });
        });
        tab.addEventListener("dragover", event => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            const sourceId = sheetTabDragState?.id || event.dataTransfer.getData("text/plain");
            if (!sourceId || sourceId === tabId(tab)) {
                return;
            }
            const insertIndex = getSheetTabInsertIndexFromTab(tab, event.clientX);
            sheetTabDragState.insertIndex = insertIndex;
            sheetTabDragState.groupKey = currentGroupKeyForTab(tab);
            showSheetTabInsertIndicator(tabbar, insertIndex);
        });
        tab.addEventListener("dragleave", () => {
            tab.classList.remove("trk_sheet_tab_drag_over");
        });
        tab.addEventListener("drop", event => {
            event.preventDefault();
            event.stopPropagation();
            tab.classList.remove("trk_sheet_tab_drag_over");
            clearSheetTabInsertIndicators();
            const sourceId = sheetTabDragState?.id || event.dataTransfer.getData("text/plain");
            if (!sourceId || sourceId === tabId(tab)) {
                return;
            }
            const insertIndex = getSheetTabInsertIndexFromTab(tab, event.clientX);
            reorderSheetTabsInGroup(sourceId, currentGroupKeyForTab(tab), insertIndex);
        });
        tab.addEventListener("keydown", event => {
            if (event.key !== "F2") return;
            event.preventDefault();
            event.stopPropagation();
            beginSheetTabRename(tab, tabId(tab), tab.dataset.sheetLabelStorageKey || labelStorageKey);
        });
    });

    if (tabbar.dataset.sheetTabbarDragBound !== "1") {
        tabbar.dataset.sheetTabbarDragBound = "1";
        tabbar.addEventListener("dragenter", (event) => {
            event.preventDefault();
        });
        tabbar.addEventListener("dragover", event => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            tabbar.classList.add("trk_sheet_tabbar_drag_over");
            const sourceId = sheetTabDragState?.id || event.dataTransfer.getData("text/plain");
            if (!sourceId) {
                return;
            }
            const insertIndex = getSheetTabInsertIndexFromPointer(tabbar, event.clientX);
            sheetTabDragState.insertIndex = insertIndex;
            sheetTabDragState.groupKey = groupKey;
            showSheetTabInsertIndicator(tabbar, insertIndex);
        });
        tabbar.addEventListener("dragleave", event => {
            if (!tabbar.contains(event.relatedTarget)) {
                tabbar.classList.remove("trk_sheet_tabbar_drag_over");
                clearSheetTabInsertIndicators();
            }
        });
        tabbar.addEventListener("drop", event => {
            event.preventDefault();
            event.stopPropagation();
            tabbar.classList.remove("trk_sheet_tabbar_drag_over");
            clearSheetTabInsertIndicators();
            const sourceId = sheetTabDragState?.id || event.dataTransfer.getData("text/plain");
            if (!sourceId) {
                return;
            }
            if (event.target.closest(tabSelector)) {
                return;
            }
            const insertIndex = getSheetTabInsertIndexFromPointer(tabbar, event.clientX);
            reorderSheetTabsInGroup(sourceId, groupKey, insertIndex);
        });
    }
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

function migrateSheetTabLabelToGlobal(id, label) {
    const global = readSheetTabMap(SHEET_TAB_LABELS_GLOBAL);
    const nextLabel = String(label || "").trim();
    if (!id || !nextLabel || global[id]) {
        return;
    }
    global[id] = nextLabel;
    localStorage.setItem(SHEET_TAB_LABELS_GLOBAL, JSON.stringify(global));
}

function getSheetTabLabel(storageKey, id, fallback) {
    const global = readSheetTabMap(SHEET_TAB_LABELS_GLOBAL);
    if (global[id]) {
        return global[id];
    }
    if (storageKey) {
        const legacy = readSheetTabMap(storageKey);
        if (legacy[id]) {
            migrateSheetTabLabelToGlobal(id, legacy[id]);
            return legacy[id];
        }
    }
    return fallback;
}

function getSheetTabDefaultDisplayLabel(tab, panel) {
    const scopePanel = panel instanceof HTMLElement ? panel : findSheetTabEntry(sheetTabId(tab))?.panel;
    const scopeTab = tab instanceof HTMLElement ? tab : null;
    const card = scopePanel?.querySelector(":scope > section.card, :scope > .card, #work_calendar_card");
    const header = card?.querySelector(":scope > .section_header_row > h3");
    if (header) {
        if (!header.dataset.sheetTabDefaultTitle) {
            header.dataset.sheetTabDefaultTitle = header.textContent.trim();
        }
        return header.dataset.sheetTabDefaultTitle;
    }
    return (
        scopePanel?.dataset?.sheetTabDefaultLabel ||
        scopeTab?.dataset?.sheetTabDefaultLabel ||
        ""
    ).trim();
}

function setSheetTabLabel(storageKey, id, label) {
    const labels = readSheetTabMap(SHEET_TAB_LABELS_GLOBAL);
    const nextLabel = String(label || "").trim();
    const entry = findSheetTabEntry(id);
    const defaultLabel = getSheetTabDefaultDisplayLabel(entry?.tab, entry?.panel);
    if (nextLabel && (!defaultLabel || nextLabel !== defaultLabel)) {
        labels[id] = nextLabel;
    } else {
        delete labels[id];
    }
    localStorage.setItem(SHEET_TAB_LABELS_GLOBAL, JSON.stringify(labels));
    if (storageKey && storageKey !== SHEET_TAB_LABELS_GLOBAL) {
        const legacy = readSheetTabMap(storageKey);
        if (legacy[id]) {
            delete legacy[id];
            localStorage.setItem(storageKey, JSON.stringify(legacy));
        }
    }
}

function syncSheetTabPanelTitle(tab, label) {
    if (!(tab instanceof HTMLElement)) {
        return;
    }
    const id = sheetTabId(tab);
    if (!id) {
        return;
    }
    const panel = findSheetTabEntry(id)?.panel;
    if (!panel) {
        return;
    }
    const text = String(label || "").trim();
    if (!text) {
        return;
    }

    const card = panel.querySelector(
        ":scope > section.card, :scope > .card, :scope > #work_calendar_card",
    );
    const header = card && card.querySelector(":scope > .section_header_row > h3");
    if (header) {
        if (!header.dataset.sheetTabDefaultTitle) {
            header.dataset.sheetTabDefaultTitle = header.textContent.trim();
        }
        if (card && !card.dataset.cardTitleKey) {
            card.dataset.cardTitleKey = header.dataset.sheetTabDefaultTitle;
        }
        header.textContent = text;
        return;
    }

    const subHeader = panel.querySelector(".trk_sub_header");
    if (subHeader) {
        if (!subHeader.dataset.sheetTabDefaultTitle) {
            subHeader.dataset.sheetTabDefaultTitle = (subHeader.textContent || "").trim();
        }
        const labelSpan = subHeader.querySelector(".trk_sub_header_label");
        if (labelSpan) {
            labelSpan.textContent = text;
            return;
        }
        Array.from(subHeader.childNodes).forEach((node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                node.textContent = "";
            }
        });
        subHeader.insertBefore(document.createTextNode(text), subHeader.firstChild);
    }
}

function syncSheetTabPanelTitleFromTab(tab) {
    if (!(tab instanceof HTMLElement)) {
        return;
    }
    const id = sheetTabId(tab);
    if (!id) {
        return;
    }
    const entry = findSheetTabEntry(id);
    const labelStorageKey = tab.dataset.sheetLabelStorageKey || "";
    const fallback = getSheetTabDefaultDisplayLabel(tab, entry?.panel);
    const label = getSheetTabLabel(labelStorageKey, id, fallback);
    syncSheetTabPanelTitle(tab, label);
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
        const finalLabel = nextLabel || previousLabel;
        labelSpan.textContent = finalLabel;
        if (save) {
            setSheetTabLabel(labelStorageKey, id, finalLabel);
            syncSheetTabPanelTitle(tab, finalLabel);
        }
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

const ADMIN_MASTER_LABEL_BY_ACTION = [
    ["/admin/product-test-releases/create", "Test Release"],
    ["/admin/product-test-target-definitions/create", "Test Target Definition"],
    ["/admin/product-test-targets/create", "Test Target"],
    ["/admin/product-test-environment-definitions/create", "Test Environment Definition"],
    ["/admin/product-test-environments/create", "Test Environment"],
    ["/admin/product-test-cases/create", "Test Case"],
    ["/admin/product-test-procedures/create", "Test Procedure"],
        ["/admin/product-test-reports/create", "Test Report"],
];

function adminMasterTabGroupFromCard(card, regionKey) {
    if (!(card instanceof HTMLElement)) {
        clientLog("tabGroup", "adminMasterTabGroupFromCard: card가 HTMLElement가 아님 regionKey=" + regionKey, "warn");
        return null;
    }
    const customLabel = card.dataset.adminTabLabel;
    if (customLabel) {
        const slug = customLabel.replace(/\W+/g, "_").toLowerCase();
        const linkCount = card.querySelectorAll("a.project_standard_button").length;
        const rowCount = card.querySelectorAll("tbody tr").length;
        const result = {
            id: `admin_master_${regionKey}_${slug}`,
            label: customLabel,
            count: rowCount || linkCount || 1,
            node: card,
        };
        clientLog("tabGroup", "adminMasterTabGroupFromCard customLabel=" + customLabel + " id=" + result.id);
        return result;
    }
    if (card.id === "work_calendar_card") {
        const wcHeader = card.querySelector(":scope > .section_header_row > h3");
        const wcLabel = (wcHeader?.textContent || "").trim() || "근무 캘린더";
        return {
            id: `admin_master_${regionKey}_work_calendar`,
            label: wcLabel,
            count: card.querySelectorAll("tbody tr").length,
            node: card,
        };
    }
    const actions = Array.from(card.querySelectorAll("form[action]")).map(
        (form) => form.getAttribute("action") || "",
    );
    clientLog("tabGroup", "adminMasterTabGroupFromCard regionKey=" + regionKey + " cardId=" + (card.id||"(none)") + " actions=" + JSON.stringify(actions));
    const labelMatch = ADMIN_MASTER_LABEL_BY_ACTION.find(([action]) => actions.includes(action));
    if (!labelMatch) {
        clientLog("tabGroup", "adminMasterTabGroupFromCard → NO MATCH (null 반환) actions=" + JSON.stringify(actions), "warn");
        return null;
    }
    // URL 마지막 세그먼트가 모두 "create"여서 ID 중복 발생 → label 텍스트 기반 slug 사용
    const slug = labelMatch[1].replace(/\W+/g, "_").toLowerCase();
    const result = {
        id: `admin_master_${regionKey}_${slug}`,
        label: labelMatch[1],
        count: card.querySelectorAll("tbody tr").length,
        node: card,
    };
    clientLog("tabGroup", "adminMasterTabGroupFromCard → match label=" + result.label + " id=" + result.id);
    return result;
}

function initAdminMasterDataTabRegion(regionBody) {
    if (!(regionBody instanceof HTMLElement)) {
        clientLog("tabRegion", "initAdminMasterDataTabRegion: HTMLElement 아님", "error");
        return false;
    }
    if (regionBody.dataset.adminTabsInit === "1" || regionBody.querySelector(".admin_master_data_tabs")) {
        clientLog("tabRegion", "initAdminMasterDataTabRegion: 이미 초기화됨 region=" + (regionBody.dataset.adminTabRegion || "?"));
        scheduleFinalizeSheetTabGroups();
        return true;
    }

    const regionKey = regionBody.dataset.adminTabRegion || "default";
    const sheetGroup = `admin_${regionKey}`;
    const storageTab = `admin_master_${regionKey}_tab`;
    const storageOrder = `admin_master_${regionKey}_tab_order`;
    const storageLabels = `admin_master_${regionKey}_tab_labels`;
    const ariaLabel = regionBody.dataset.tabAriaLabel || "Admin master data tables";

    const cards = Array.from(regionBody.querySelectorAll(":scope > section.card"));
    clientLog("tabRegion", "initAdminMasterDataTabRegion regionKey=" + regionKey + " cards.length=" + cards.length + " cardIds=" + cards.map(c => c.id || c.querySelector("h3")?.textContent?.trim() || "(no-id)").join(", "));

    const groups = cards.map((card) => adminMasterTabGroupFromCard(card, regionKey)).filter(Boolean);
    clientLog("tabRegion", "initAdminMasterDataTabRegion groups.length=" + groups.length + " ids=" + groups.map(g => g.id).join(", "));

    if (groups.length <= 1) {
        clientLog("tabRegion", "initAdminMasterDataTabRegion → groups <= 1, 탭바 생성 안 함 (false 반환)", "warn");
        return false;
    }

    const sortedGroups = sortItemsByStoredOrder(groups, storageOrder, (group) => group.id);

    const firstCard = sortedGroups[0].node;
    const groupNodes = new Set(sortedGroups.map((group) => group.node));
    let cursor = firstCard.nextElementSibling;
    while (cursor) {
        const next = cursor.nextElementSibling;
        if (!groupNodes.has(cursor)) {
            cursor.hidden = true;
        }
        cursor = next;
    }

    const tabsRoot = document.createElement("section");
    tabsRoot.className = "trk_data_tabs admin_master_data_tabs";
    tabsRoot.dataset.sheetGroup = sheetGroup;
    const tabbar = document.createElement("div");
    tabbar.className = "trk_sheet_tabbar";
    tabbar.setAttribute("role", "tablist");
    tabbar.setAttribute("aria-label", ariaLabel);
    tabsRoot.appendChild(tabbar);
    regionBody.insertBefore(tabsRoot, firstCard);

    const storedId = localStorage.getItem(storageTab) || "";
    const activeGroup = sortedGroups.find((group) => group.id === storedId) || sortedGroups[0];

    sortedGroups.forEach((group) => {
        const cardHeader = group.node.querySelector(":scope > .section_header_row > h3");
        const displayDefault = (cardHeader?.textContent || "").trim() || group.label;
        if (cardHeader && !cardHeader.dataset.sheetTabDefaultTitle) {
            cardHeader.dataset.sheetTabDefaultTitle = displayDefault;
        }
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = `trk_sheet_tab${group.id === activeGroup.id ? " is-active" : ""}`;
        tab.dataset.sheetTab = group.id;
        tab.dataset.sheetCurrentGroup = sheetGroup;
        tab.dataset.sheetLabelStorageKey = storageLabels;
        tab.dataset.sheetTabDefaultLabel = displayDefault;
        tab.dataset.adminMasterTab = group.id;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", group.id === activeGroup.id ? "true" : "false");
        tab.innerHTML = `<span class="trk_sheet_label">${escapeSheetTabText(getSheetTabLabel(storageLabels, group.id, displayDefault))}</span><span class="trk_sheet_count">${group.count}</span>`;
        tabbar.appendChild(tab);

        const panel = document.createElement("div");
        panel.className = `trk_sheet_panel${group.id === activeGroup.id ? " is-active" : ""}`;
        panel.dataset.sheetPanel = group.id;
        panel.dataset.sheetCurrentGroup = sheetGroup;
        panel.dataset.sheetTabDefaultLabel = displayDefault;
        panel.dataset.adminMasterPanel = group.id;
        panel.hidden = group.id !== activeGroup.id;
        panel.setAttribute("role", "tabpanel");
        panel.appendChild(group.node);
        tabsRoot.appendChild(panel);
        if (!group.node.dataset.cardTitleKey) {
            group.node.dataset.cardTitleKey = displayDefault;
        }
    });

    Array.from(tabbar.querySelectorAll("[data-sheet-tab]")).forEach((tab) => syncSheetTabPanelTitleFromTab(tab));

    function activate(id) {
        const { activePanel, activeTab } = activateSheetTabGroupExclusive(tabsRoot, id, storageTab);
        if (activeTab) {
            syncSheetTabPanelTitleFromTab(activeTab);
        }
        if (activePanel && typeof initTableColumnFeatures === "function") {
            initTableColumnFeatures(activePanel);
        }
        const ganttWrap = activePanel && activePanel.querySelector(".gantt_wrap");
        if (ganttWrap) {
            initGanttResize(ganttWrap);
            initDeadlineDrag(ganttWrap);
        }
        if (activePanel && activePanel.querySelector(".trk_defect_table")) {
            if (typeof initDefectColResize === "function") {
                initDefectColResize(activePanel);
            }
            if (typeof bindDefectImages === "function") {
                bindDefectImages(activePanel);
            }
        }
    }

    tabbar.addEventListener("click", (event) => {
        const tab = event.target.closest("[data-sheet-tab]");
        if (!tab || !tabbar.contains(tab)) {
            return;
        }
        event.stopPropagation();
        activate(sheetTabId(tab));
    });
    bindSheetTabDragDrop({
        groupKey: sheetGroup,
        tabsRoot,
        tabbar,
        tabSelector: "[data-sheet-tab]",
        panelSelector: "[data-sheet-panel]",
        tabId: sheetTabId,
        panelId: sheetPanelId,
        storageKey: storageOrder,
        labelStorageKey: storageLabels,
        activate,
    });
    registerSheetTabGroup({
        groupKey: sheetGroup,
        tabsRoot,
        tabbar,
        storageKey: storageOrder,
        storageTabKey: storageTab,
        labelStorageKey: storageLabels,
        activate,
    });
    activate(activeGroup.id);
    const foldMeta = TAB_VIEW_TABLE_FOLD_META[sheetGroup];
    if (foldMeta) {
        syncTabViewRegionFold(foldMeta);
    }
    consolidateCardHeaderToolbar(regionBody);
    regionBody.dataset.adminTabsInit = "1";
    clientLog("tabRegion", "initAdminMasterDataTabRegion → 탭바 생성 완료 regionKey=" + regionKey + " tabCount=" + sortedGroups.length);
    // 가시성 진단: 500ms 후 computed style 보고
    (function diagTabbar(tb, tr, rk) {
        setTimeout(function () {
            var cs = window.getComputedStyle(tb);
            var ps = window.getComputedStyle(tr);
            var shell = document.querySelector("#admin_tab_region_" + rk);
            var ss = shell ? window.getComputedStyle(shell) : null;
            var r = tb.getBoundingClientRect();
            clientLog("tabDiag", "regionKey=" + rk
                + " tabbar.display=" + cs.display
                + " tabbar.visibility=" + cs.visibility
                + " tabbar.height=" + cs.height
                + " tabbar.rect=" + JSON.stringify({w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top)})
                + " tabsRoot.display=" + ps.display
                + " tabsRoot.visibility=" + ps.visibility
                + " tabsRoot.height=" + ps.height
                + (ss ? " shell.display=" + ss.display + " shell.overflow=" + ss.overflow + " shell.height=" + ss.height : "")
                + " shellFolded=" + (shell ? shell.classList.contains("is-tabview-region-folded") : "?")
            );
        }, 500);
    }(tabbar, tabsRoot, regionKey));
    return true;
}

function initAdminMasterDataTabs() {
    const regions = Array.from(document.querySelectorAll(".admin_tab_region_body[data-admin-tab-region]"));
    clientLog("tabInit", "initAdminMasterDataTabs 호출 regions.length=" + regions.length + " keys=" + regions.map(r => r.dataset.adminTabRegion).join(", "));
    if (regions.length) {
        const built = regions.filter((region) => initAdminMasterDataTabRegion(region)).length;
        clientLog("tabInit", "initAdminMasterDataTabs built=" + built + "/" + regions.length);
        if (built > 0) {
            scheduleFinalizeSheetTabGroups();
        }
        return built > 0;
    }

    const workCalendar = document.getElementById("work_calendar_card");
    if (!workCalendar || document.querySelector(".admin_master_data_tabs")) {
        return !!document.querySelector(".admin_master_data_tabs");
    }

    const legacyHost = document.createElement("div");
    legacyHost.className = "admin_tab_region_body";
    legacyHost.dataset.adminTabRegion = "legacy";
    legacyHost.dataset.tabAriaLabel = "Admin master data tables";

    const cards = Array.from(document.querySelectorAll("section.card")).filter(
        (card) => card.compareDocumentPosition(workCalendar) & Node.DOCUMENT_POSITION_FOLLOWING,
    );
    if (!cards.length) {
        return false;
    }
    workCalendar.parentNode.insertBefore(legacyHost, cards[0]);
    cards.forEach((card) => legacyHost.appendChild(card));
    workCalendar.parentNode.insertBefore(workCalendar, legacyHost.nextSibling);
    legacyHost.appendChild(workCalendar);
    return initAdminMasterDataTabRegion(legacyHost);
}

let adminMasterDataTabsObserver = null;
function scheduleAdminMasterDataTabs(attempt) {
    const attemptNo = attempt || 0;
    clientLog("tabSchedule", "scheduleAdminMasterDataTabs attempt=" + attemptNo);
    if (initAdminMasterDataTabs()) {
        clientLog("tabSchedule", "scheduleAdminMasterDataTabs → 초기화 성공 attempt=" + attemptNo);
        if (adminMasterDataTabsObserver) {
            adminMasterDataTabsObserver.disconnect();
            adminMasterDataTabsObserver = null;
        }
        return;
    }
    clientLog("tabSchedule", "scheduleAdminMasterDataTabs → 아직 실패, MutationObserver 설정 attempt=" + attemptNo, "warn");
    if (!adminMasterDataTabsObserver && document.body) {
        adminMasterDataTabsObserver = new MutationObserver(() => {
            if (initAdminMasterDataTabs()) {
                adminMasterDataTabsObserver.disconnect();
                adminMasterDataTabsObserver = null;
            }
        });
        adminMasterDataTabsObserver.observe(document.body, { childList: true, subtree: true });
    }
    if (attemptNo >= 60) {
        clientLog("tabSchedule", "scheduleAdminMasterDataTabs → 60회 재시도 초과, 포기", "error");
        return;
    }
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

function bindSheetTabLayoutPersistence() {
    const flush = () => persistSheetTabLayoutSoon();
    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", flush);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
            flush();
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    bindSheetTabLayoutPersistence();
    initTabViewTableFoldToggleButtons();
    initAllTabViewsRegionFoldToggleButton();
    updateToggleLabel();
    scheduleAdminMasterDataTabs();
    if (document.getElementById("trk_root")) {
        loadTracking();
    }
});
initTabViewTableFoldToggleButtons();
initAllTabViewsRegionFoldToggleButton();
bindSheetTabLayoutPersistence();
scheduleAdminMasterDataTabs();
document.getElementById("trk_refresh_btn")
    && document.getElementById("trk_refresh_btn").addEventListener("click", event => {
        const btn = event.currentTarget;
        const preserveScroll = btn && btn.dataset.preserveScroll === "1";
        if (btn) delete btn.dataset.preserveScroll;
        updateToggleLabel();
        loadTracking({ preserveScroll });
    });

window.consolidateCardHeaderToolbar = consolidateCardHeaderToolbar;
window.ensureCardHeaderActions = ensureCardHeaderActions;
window.toggleAllTabViewsRegionFold = toggleAllTabViewsRegionFold;
window.updateAllTabViewsRegionFoldToggleButton = updateAllTabViewsRegionFoldToggleButton;
})();
