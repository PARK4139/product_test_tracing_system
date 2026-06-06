/**
 * 테이블 셀 선택 + F2 멀티편집
 * - 연결된 행/필드(구성·케이스·체크·하이라이트·동일 name)에 값 동기화
 */
(function () {
    "use strict";

    let selectedCell = null;
    let multiEditCells = [];
    let multiEditPrimary = null;
    let multiEditOnInput = null;
    let multiEditSnapshots = [];
    let multiEditPersistInFlight = false;

    const ADMIN_OUTPUT_TABLE_CONFIG = {
        "/admin/product-test-releases/create": {
            entityType: "product_test_release",
            idColumnIndex: 1,
            fieldsByIndex: {
                2: "upstream_release_id",
                3: "upstream_release_system",
                5: "product_test_release_status",
                6: "remark",
            },
        },
        "/admin/product-test-target-definitions/create": {
            entityType: "product_test_target_definition",
            idColumnIndex: 1,
            fieldsByIndex: {
                2: "product_code",
                3: "manufacturer",
                4: "model_name",
                5: "hardware_revision",
                6: "default_software_version",
                7: "default_firmware_version",
                8: "product_test_target_definition_status",
                9: "remark",
            },
        },
        "/admin/product-test-targets/create": {
            entityType: "product_test_target",
            idColumnIndex: 1,
            fieldsByIndex: {
                3: "serial_number",
                4: "software_version",
                5: "firmware_version",
                6: "manufacture_lot",
                7: "product_test_target_status",
                8: "remark",
            },
        },
        "/admin/product-test-environment-definitions/create": {
            entityType: "product_test_environment_definition",
            idColumnIndex: 1,
            fieldsByIndex: {
                2: "product_test_environment_definition_name",
                3: "test_country",
                4: "test_city",
                5: "test_company",
                6: "test_room",
                7: "network_type",
                8: "test_computer_name",
                9: "operating_system_version",
                10: "test_tool_name",
                11: "test_tool_version",
                12: "power_voltage",
                13: "power_frequency",
                14: "power_connector_type",
                15: "power_condition",
                16: "product_test_environment_definition_status",
                17: "remark",
            },
        },
        "/admin/product-test-environments/create": {
            entityType: "product_test_environment",
            idColumnIndex: 1,
            fieldsByIndex: {
                3: "product_test_environment_name",
                4: "test_computer_name",
                5: "operating_system_version",
                6: "test_tool_version",
                7: "network_type",
                8: "power_voltage",
                9: "power_frequency",
                10: "power_connector_type",
                11: "captured_at",
                12: "product_test_environment_status",
                13: "remark",
            },
        },
        "/admin/product-test-cases/create": {
            entityType: "product_test_case",
            idColumnIndex: 1,
            fieldsByIndex: {
                2: "product_test_case_title",
                3: "test_category",
                4: "test_objective",
                5: "precondition",
                6: "expected_result",
                7: "product_test_case_status",
                8: "remark",
            },
        },
        "/admin/product-test-procedures/create": {
            entityType: "product_test_procedure",
            idColumnIndex: 1,
            fieldsByIndex: {
                4: "procedure_action",
                5: "expected_result",
                6: "acceptance_criteria",
                7: "required_evidence_type",
                8: "product_test_procedure_status",
                9: "remark",
            },
        },
        "/admin/product-test-reports/create": {
            entityType: "product_test_report",
            idColumnIndex: 1,
            fieldsByIndex: {
                3: "product_test_report_type",
                4: "product_test_report_status",
                5: "product_test_report_title",
                6: "remark",
            },
        },
    };

    const TRACKING_TABLE_CONFIG = {
        trk_defect_table: {
            entityType: "product_test_defect",
            idDataset: "entityId",
            fieldsByIndex: {
                1: "defect_severity",
                2: "defect_priority",
                3: "defect_title",
                4: "assigned_to",
                5: "expected_resolution_date",
            },
        },
        trk_case_table: {
            entityType: "product_test_case",
            idDataset: "entityId",
            fieldsByIndex: { 1: "product_test_case_title" },
        },
        trk_procedure_table: {
            entityType: "product_test_procedure",
            idDataset: "entityId",
            fieldsByIndex: { 3: "procedure_action" },
        },
        trk_proc_result_table: {
            entityType: "product_test_procedure_result",
            idDataset: "entityId",
            fieldsByIndex: { 4: "product_test_procedure_result_status" },
        },
    };

    const extractCellPersistValue = (cell) => {
        const badge = cell.querySelector(".status_badge, .trk_sev, .trk_prio_label");
        if (badge) {
            return String(badge.textContent || "").trim();
        }
        return getCellDisplayValue(cell);
    };

    const findAdminOutputConfig = (cell) => {
        const card = cell.closest(".card");
        if (!card) {
            return null;
        }
        const form = card.querySelector("form.admin_autosubmit_form");
        if (!form) {
            return null;
        }
        const action = String(form.getAttribute("action") || "");
        return ADMIN_OUTPUT_TABLE_CONFIG[action] || null;
    };

    const resolveCellSaveDescriptor = (cell) => {
        const row = cell.closest("tr");
        if (!row) {
            return null;
        }

        const control = findEditableInCell(cell);
        const controlName = control
            ? control.getAttribute("name") || control.getAttribute("data-field") || ""
            : "";
        const entityType = row.dataset.entityType || "";
        const entityId = row.dataset.entityId || "";
        if (controlName && entityType && entityId) {
            return { entity_type: entityType, entity_id: entityId, field_name: controlName };
        }
        if (controlName && !entityType) {
            return null;
        }
        if (cell.dataset.field && entityType && entityId) {
            return {
                entity_type: entityType,
                entity_id: entityId,
                field_name: cell.dataset.field,
            };
        }

        const table = cell.closest("table");
        if (!table) {
            return null;
        }
        const colIndex = cell.cellIndex;

        for (const className of Object.keys(TRACKING_TABLE_CONFIG)) {
            if (!table.classList.contains(className)) {
                continue;
            }
            const cfg = TRACKING_TABLE_CONFIG[className];
            const fieldName = cfg.fieldsByIndex[colIndex];
            const rowEntityId = row.dataset[cfg.idDataset] || row.dataset.entityId || "";
            if (!fieldName || !rowEntityId) {
                return null;
            }
            return {
                entity_type: cfg.entityType,
                entity_id: rowEntityId,
                field_name: fieldName,
            };
        }

        const adminCfg = findAdminOutputConfig(cell);
        if (adminCfg) {
            const outputTables = Array.from(
                cell.closest(".card")?.querySelectorAll(".tester_table_wrap table.basic_table") || [],
            );
            const isOutputTable = outputTables.length >= 2 && table === outputTables[1];
            if (!isOutputTable) {
                return null;
            }
            const fieldName = adminCfg.fieldsByIndex[colIndex];
            const rowEntityId = String(row.cells[adminCfg.idColumnIndex]?.textContent || "").trim();
            if (!fieldName || !rowEntityId) {
                return null;
            }
            if (fieldName === "procedure_sequence") {
                return null;
            }
            return {
                entity_type: adminCfg.entityType,
                entity_id: rowEntityId,
                field_name: fieldName,
            };
        }

        return null;
    };

    const persistMultiEditChanges = async () => {
        if (multiEditSnapshots.length === 0 || multiEditPersistInFlight) {
            return;
        }
        const updates = [];
        const seen = new Set();
        for (const snap of multiEditSnapshots) {
            const descriptor = snap.descriptor;
            if (!descriptor) {
                continue;
            }
            const nextValue = extractCellPersistValue(snap.cell);
            if (nextValue === snap.originalValue) {
                continue;
            }
            const key = `${descriptor.entity_type}|${descriptor.entity_id}|${descriptor.field_name}`;
            if (seen.has(key)) {
                continue;
            }
            seen.add(key);
            updates.push({
                entity_type: descriptor.entity_type,
                entity_id: descriptor.entity_id,
                field_name: descriptor.field_name,
                value: nextValue,
            });
        }
        if (updates.length === 0) {
            multiEditSnapshots = [];
            return;
        }

        multiEditPersistInFlight = true;
        try {
            const response = await fetch("/admin/api/product-test/fields/bulk-update", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({ updates }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.ok) {
                const message = (data && data.message) || `저장 실패 (HTTP ${response.status})`;
                if (typeof window.showCenterNonModalV2 === "function") {
                    window.showCenterNonModalV2(message, "error");
                } else if (typeof window.openMessageModal === "function") {
                    window.openMessageModal(message);
                }
                return;
            }
            if (typeof window.showCenterNonModalV2 === "function") {
                window.showCenterNonModalV2(`DB 저장 완료 (${data.updated || updates.length}건)`, "success");
            }
            const refreshBtn = document.getElementById("trk_refresh_btn");
            if (refreshBtn && updates.some((u) => u.entity_type.startsWith("product_test_"))) {
                refreshBtn.dataset.preserveScroll = "1";
                refreshBtn.click();
            }
        } catch (_error) {
            if (typeof window.showCenterNonModalV2 === "function") {
                window.showCenterNonModalV2("DB 저장 중 네트워크 오류가 발생했습니다.", "error");
            }
        } finally {
            multiEditPersistInFlight = false;
            multiEditSnapshots = [];
        }
    };

    const isModalOpen = () => {
        const overlay = document.getElementById("app_message_modal");
        return overlay && overlay.classList.contains("is_open");
    };

    const clearSelectedCell = () => {
        if (!selectedCell) {
            return;
        }
        selectedCell.classList.remove("table_cell_selected");
        selectedCell.removeAttribute("aria-selected");
        selectedCell = null;
    };

    const selectCell = (cell) => {
        if (!(cell instanceof HTMLTableCellElement) || cell.tagName === "TH") {
            return;
        }
        endMultiEdit();
        clearSelectedCell();
        selectedCell = cell;
        cell.classList.add("table_cell_selected");
        cell.setAttribute("aria-selected", "true");
    };

    const getColumnKey = (table, colIndex) => {
        if (!(table instanceof HTMLTableElement)) {
            return `col:${colIndex}`;
        }
        const th = table.querySelectorAll("thead tr th")[colIndex];
        const label = th ? String(th.textContent || "").trim() : "";
        return label || `col:${colIndex}`;
    };

    const findColumnIndexByKey = (table, columnKey) => {
        if (!(table instanceof HTMLTableElement) || !columnKey) {
            return -1;
        }
        const headers = Array.from(table.querySelectorAll("thead tr th"));
        const idx = headers.findIndex((th) => String(th.textContent || "").trim() === columnKey);
        return idx >= 0 ? idx : -1;
    };

    const getActiveTopoIds = () => {
        const ids = new Set();
        document.querySelectorAll("#trk_root .gantt_row.gantt_hl[data-row-id]").forEach((row) => {
            if (row.dataset.rowId) {
                ids.add(row.dataset.rowId);
            }
        });
        document.querySelectorAll("#trk_root tr.trk_row_highlighted[data-parent-release-id]").forEach((row) => {
            if (row.dataset.parentReleaseId) {
                ids.add(row.dataset.parentReleaseId);
            }
        });
        return ids;
    };

    const isRowChecked = (row) => {
        if (!(row instanceof HTMLTableRowElement)) {
            return false;
        }
        const checkbox = row.querySelector('input[type="checkbox"]');
        return !!(checkbox && checkbox.checked && !checkbox.disabled);
    };

    const rowMatchesLink = (row, link) => {
        if (!(row instanceof HTMLTableRowElement)) {
            return false;
        }
        if (link.parentReleaseId && row.dataset.parentReleaseId === link.parentReleaseId) {
            return true;
        }
        if (link.caseId && row.dataset.caseId === link.caseId) {
            return true;
        }
        if (link.releaseId && row.dataset.releaseId === link.releaseId) {
            return true;
        }
        if (link.topoIds.size > 0 && link.topoIds.has(row.dataset.parentReleaseId || "")) {
            return true;
        }
        return false;
    };

    const findEditableInCell = (cell) => {
        const candidates = Array.from(
            cell.querySelectorAll(
                "input:not([type=hidden]):not([disabled]):not([readonly]), " +
                    "select:not([disabled]), textarea:not([disabled]):not([readonly]), " +
                    "[contenteditable='true'], [contenteditable='']",
            ),
        );
        for (const el of candidates) {
            if (!(el instanceof HTMLElement)) {
                continue;
            }
            if (el.offsetParent === null && getComputedStyle(el).display === "none") {
                continue;
            }
            return el;
        }
        return null;
    };

    const getControlValue = (control) => {
        if (!control) {
            return "";
        }
        if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) {
            return control.value;
        }
        if (control instanceof HTMLSelectElement) {
            return control.value;
        }
        if (control.isContentEditable) {
            return control.textContent || "";
        }
        return "";
    };

    const getCellDisplayValue = (cell) => {
        const control = findEditableInCell(cell);
        if (control) {
            return getControlValue(control);
        }
        if (cell.querySelector(".status_badge")) {
            return "";
        }
        return String(cell.textContent || "").trim();
    };

    const setControlValue = (control, value) => {
        if (!control) {
            return;
        }
        if (control instanceof HTMLSelectElement) {
            const text = String(value ?? "");
            let matched = false;
            Array.from(control.options).forEach((opt) => {
                if (opt.value === text || String(opt.textContent || "").trim() === text) {
                    control.value = opt.value;
                    matched = true;
                }
            });
            if (!matched) {
                control.value = text;
            }
            control.dispatchEvent(new Event("input", { bubbles: true }));
            control.dispatchEvent(new Event("change", { bubbles: true }));
            return;
        }
        if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) {
            control.value = String(value ?? "");
            control.dispatchEvent(new Event("input", { bubbles: true }));
            control.dispatchEvent(new Event("change", { bubbles: true }));
            return;
        }
        if (control.isContentEditable) {
            control.textContent = String(value ?? "");
            control.dispatchEvent(new Event("input", { bubbles: true }));
        }
    };

    const setCellDisplayValue = (cell, value) => {
        if (!(cell instanceof HTMLTableCellElement)) {
            return;
        }
        if (cell.querySelector(".status_badge, .trk_status_editable, .trk_status_readonly")) {
            return;
        }
        const control = findEditableInCell(cell);
        if (control) {
            setControlValue(control, value);
            return;
        }
        const injected = cell.querySelector("input[data-sync-injected='1']");
        if (injected instanceof HTMLInputElement) {
            injected.value = String(value ?? "");
            return;
        }
        cell.textContent = String(value ?? "");
    };

    const activateCellEditor = (cell) => {
        const existing = findEditableInCell(cell);
        if (existing) {
            return existing;
        }
        if (cell.querySelector(".status_badge, .trk_status_editable, button")) {
            return null;
        }
        const prior = cell.querySelector("input[data-sync-injected='1']");
        if (prior instanceof HTMLInputElement) {
            return prior;
        }

        const input = document.createElement("input");
        input.type = "text";
        input.className = "table_cell_sync_input";
        input.dataset.syncInjected = "1";
        input.value = getCellDisplayValue(cell);
        if (!cell.dataset.syncOriginalHtml) {
            cell.dataset.syncOriginalHtml = cell.innerHTML;
        }
        cell.innerHTML = "";
        cell.appendChild(input);
        return input;
    };

    const collectLinkedCells = (cell) => {
        const table = cell.closest("table");
        const row = cell.closest("tr");
        const colIndex = cell.cellIndex;
        const columnKey = table ? getColumnKey(table, colIndex) : `col:${colIndex}`;
        const linked = new Set();

        const addCell = (td) => {
            if (!(td instanceof HTMLTableCellElement) || td.tagName === "TH") {
                return;
            }
            if (td.querySelector(".trk_status_editable, .trk_status_readonly")) {
                return;
            }
            linked.add(td);
        };

        const anchorControl = findEditableInCell(cell);
        const fieldName =
            (anchorControl && (anchorControl.getAttribute("name") || anchorControl.getAttribute("data-field"))) ||
            "";
        if (fieldName) {
            document
                .querySelectorAll(
                    `[name="${CSS.escape(fieldName)}"], [data-field="${CSS.escape(fieldName)}"]`,
                )
                .forEach((el) => {
                    const td = el.closest("td");
                    if (td) {
                        addCell(td);
                    }
                });
        }

        const link = {
            parentReleaseId: row?.dataset?.parentReleaseId || "",
            caseId: row?.dataset?.caseId || "",
            releaseId: row?.dataset?.releaseId || "",
            topoIds: getActiveTopoIds(),
        };

        const scanRoot = (root) => {
            if (!root) {
                return;
            }
            root.querySelectorAll("table").forEach((tbl) => {
                const idxByHeader = findColumnIndexByKey(tbl, columnKey);
                tbl.querySelectorAll("tbody tr").forEach((tr) => {
                    const useChecked = isRowChecked(tr);
                    if (!rowMatchesLink(tr, link) && !useChecked) {
                        return;
                    }
                    const idx = idxByHeader >= 0 ? idxByHeader : colIndex;
                    if (tr.cells[idx]) {
                        addCell(tr.cells[idx]);
                    }
                });
            });
        };

        if (table) {
            scanRoot(table.closest(".card") || table.parentElement || table);
        }
        scanRoot(document.getElementById("trk_root"));

        link.topoIds.forEach((topoId) => {
            document.querySelectorAll(`tr[data-parent-release-id="${topoId}"]`).forEach((tr) => {
                const tbl = tr.closest("table");
                const idx = tbl ? findColumnIndexByKey(tbl, columnKey) : colIndex;
                const targetIdx = idx >= 0 ? idx : colIndex;
                if (tr.cells[targetIdx]) {
                    addCell(tr.cells[targetIdx]);
                }
            });
        });

        if (link.caseId) {
            document.querySelectorAll(`tr[data-case-id="${CSS.escape(link.caseId)}"]`).forEach((tr) => {
                const tbl = tr.closest("table");
                const idx = tbl ? findColumnIndexByKey(tbl, columnKey) : colIndex;
                const targetIdx = idx >= 0 ? idx : colIndex;
                if (tr.cells[targetIdx]) {
                    addCell(tr.cells[targetIdx]);
                }
            });
        }

        addCell(cell);
        return Array.from(linked);
    };

    const endMultiEdit = () => {
        const snapshotsToSave = multiEditSnapshots.slice();
        if (multiEditPrimary && multiEditOnInput) {
            multiEditPrimary.removeEventListener("input", multiEditOnInput);
            multiEditPrimary.removeEventListener("change", multiEditOnInput);
        }
        multiEditPrimary = null;
        multiEditOnInput = null;

        document.querySelectorAll("input[data-sync-injected='1']").forEach((input) => {
            const td = input.closest("td");
            if (!(td instanceof HTMLTableCellElement)) {
                return;
            }
            td.textContent = input.value;
            delete td.dataset.syncOriginalHtml;
            td.classList.remove("table_cell_sync_target", "table_cell_editing");
        });

        multiEditCells.forEach((td) => {
            td.classList.remove("table_cell_sync_target", "table_cell_editing");
        });
        multiEditCells = [];

        if (snapshotsToSave.length > 0) {
            multiEditSnapshots = snapshotsToSave;
            void persistMultiEditChanges();
        }
    };

    const startMultiEdit = (cell) => {
        endMultiEdit();
        multiEditCells = collectLinkedCells(cell);
        multiEditSnapshots = multiEditCells.map((td) => ({
            cell: td,
            descriptor: resolveCellSaveDescriptor(td),
            originalValue: extractCellPersistValue(td),
        }));
        if (!multiEditSnapshots.some((snap) => snap.descriptor)) {
            if (typeof window.showCenterNonModalV2 === "function") {
                window.showCenterNonModalV2("DB 저장 매핑이 없는 셀입니다. 원본 DB 컬럼 셀만 편집할 수 있습니다.", "info");
            }
            multiEditCells = [];
            multiEditSnapshots = [];
            return false;
        }
        multiEditCells.forEach((td) => td.classList.add("table_cell_sync_target"));

        let primary = activateCellEditor(cell) || findEditableInCell(cell);
        if (!primary) {
            for (const td of multiEditCells) {
                primary = activateCellEditor(td) || findEditableInCell(td);
                if (primary) {
                    break;
                }
            }
        }
        if (!primary) {
            if (typeof window.showCenterNonModalV2 === "function") {
                window.showCenterNonModalV2(
                    "이 셀은 상태/버튼 전용입니다. 편집 가능한 열을 선택해 주세요.",
                    "info",
                );
            }
            endMultiEdit();
            return false;
        }

        cell.classList.add("table_cell_editing");
        multiEditPrimary = primary;

        const applySync = () => {
            const value = getControlValue(multiEditPrimary);
            multiEditCells.forEach((td) => {
                setCellDisplayValue(td, value);
            });
        };

        multiEditOnInput = () => applySync();
        multiEditPrimary.addEventListener("input", multiEditOnInput);
        multiEditPrimary.addEventListener("change", multiEditOnInput);

        multiEditPrimary.focus();
        if (multiEditPrimary instanceof HTMLInputElement) {
            const type = (multiEditPrimary.type || "text").toLowerCase();
            if (["text", "search", "tel", "url", ""].includes(type)) {
                const len = multiEditPrimary.value.length;
                try {
                    multiEditPrimary.setSelectionRange(len, len);
                } catch (_e) {
                    // ignore
                }
            }
        }

        if (typeof window.showCenterNonModalV2 === "function" && multiEditCells.length > 1) {
            window.showCenterNonModalV2(
                `연결된 ${multiEditCells.length}개 셀 동시 편집 중입니다. (Esc: 종료)`,
                "info",
            );
        }
        return true;
    };

    const initTableCellF2 = (root) => {
        (root || document).querySelectorAll("table").forEach((table) => {
            if (!(table instanceof HTMLTableElement)) {
                return;
            }
            if (table.dataset.cellF2Init === "1") {
                return;
            }
            table.dataset.cellF2Init = "1";

            table.addEventListener(
                "click",
                (event) => {
                    const target = event.target;
                    if (!(target instanceof Element)) {
                        return;
                    }
                    if (target.closest(".column_resize_handle, .trk_status_dropdown")) {
                        return;
                    }
                    const cell = target.closest("td");
                    if (!cell || !table.contains(cell)) {
                        return;
                    }
                    selectCell(cell);
                },
                true,
            );
        });
    };

    document.addEventListener("keydown", (event) => {
        if (event.ctrlKey || event.metaKey) {
            return;
        }

        if (event.key === "Escape") {
            multiEditSnapshots = [];
            endMultiEdit();
            clearSelectedCell();
            return;
        }

        if (multiEditPrimary && event.key === "Enter" && !event.shiftKey) {
            const tag = (multiEditPrimary.tagName || "").toLowerCase();
            if (tag !== "textarea" && multiEditPrimary instanceof HTMLInputElement) {
                event.preventDefault();
                endMultiEdit();
                return;
            }
        }

        if (event.key !== "F2") {
            return;
        }

        if (isModalOpen()) {
            return;
        }

        if (!selectedCell || !document.body.contains(selectedCell)) {
            if (typeof window.showCenterNonModalV2 === "function") {
                window.showCenterNonModalV2("편집할 셀을 먼저 클릭해 주세요.", "info");
            }
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        startMultiEdit(selectedCell);
    });

    document.addEventListener(
        "click",
        (event) => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }
            if (target.closest("td, #app_message_modal, .trk_status_dropdown")) {
                return;
            }
            endMultiEdit();
            clearSelectedCell();
        },
        true,
    );

    document.addEventListener("DOMContentLoaded", () => initTableCellF2(document));

    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) {
                    initTableCellF2(node);
                }
            });
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });

    window.initTableCellF2 = initTableCellF2;
    window.clearTableCellSelection = clearSelectedCell;
    window.endTableCellMultiEdit = endMultiEdit;
})();
