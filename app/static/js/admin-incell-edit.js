(function () {
    "use strict";

    const showNotice = (message, level = "info") => {
        if (typeof window.showCenterNonModalV2 === "function") {
            window.showCenterNonModalV2(message, level);
            return;
        }
        if (typeof window.openMessageModal === "function") {
            window.openMessageModal(message);
        }
    };

    const escapeHtml = (value) =>
        String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");

    const optionsForCell = (cell) =>
        String(cell.dataset.options || "")
            .split("|")
            .map((value) => value.trim())
            .filter(Boolean);

    const displayValue = (cell) => {
        const control = cell.querySelector("input, select, textarea");
        if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) {
            return control.value;
        }
        if (control instanceof HTMLSelectElement) {
            return control.value;
        }
        const badge = cell.querySelector(".status_badge");
        if (badge) {
            return String(badge.textContent || "").trim();
        }
        return String(cell.textContent || "").trim();
    };

    const renderCellValue = (cell, value) => {
        const text = String(value ?? "").trim();
        if (cell.dataset.options) {
            cell.innerHTML = text
                ? `<span class="status_badge status-${escapeHtml(text.toLowerCase())}">${escapeHtml(text)}</span>`
                : "";
            return;
        }
        cell.textContent = text;
    };

    const restoreCell = (cell, value) => {
        renderCellValue(cell, value);
        cell.classList.remove("admin_incell_editing");
    };

    const postBulkUpdate = async (descriptor, value) => {
        const response = await fetch("/admin/api/product-test/fields/bulk-update", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({
                updates: [
                    {
                        entity_type: descriptor.entityType,
                        entity_id: descriptor.entityId,
                        field_name: descriptor.fieldName,
                        value,
                    },
                ],
            }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) {
            throw new Error(payload.message || `저장 실패 (HTTP ${response.status})`);
        }
        return payload;
    };

    const beginExistingCellEdit = (cell) => {
        const row = cell.closest("tr");
        const table = cell.closest("[data-incell-edit-table]");
        if (!row || !table || row.dataset.draftRow === "1") {
            return;
        }
        if (!cell.dataset.field || cell.dataset.primaryKey === "1" || cell.dataset.readonly === "1") {
            return;
        }
        if (cell.classList.contains("admin_incell_editing")) {
            return;
        }

        const entityType = row.dataset.entityType || table.dataset.entityType || "";
        const entityId = row.dataset.entityId || "";
        const fieldName = cell.dataset.field || "";
        if (!entityType || !entityId || !fieldName) {
            return;
        }

        const originalValue = displayValue(cell);
        const options = optionsForCell(cell);
        const control = options.length > 0 ? document.createElement("select") : document.createElement("input");
        control.className = "admin_incell_control";
        if (control instanceof HTMLInputElement) {
            control.type = "text";
            control.value = originalValue;
        } else {
            options.forEach((optionValue) => {
                const option = document.createElement("option");
                option.value = optionValue;
                option.textContent = optionValue;
                control.appendChild(option);
            });
            control.value = originalValue || options[0] || "";
        }

        let finished = false;
        const finish = async (save) => {
            if (finished) {
                return;
            }
            finished = true;
            const nextValue = control.value.trim();
            if (!save || nextValue === originalValue) {
                restoreCell(cell, originalValue);
                return;
            }
            cell.classList.add("admin_incell_saving");
            try {
                await postBulkUpdate({ entityType, entityId, fieldName }, nextValue);
                restoreCell(cell, nextValue);
                showNotice("셀 저장 완료", "success");
            } catch (error) {
                restoreCell(cell, originalValue);
                row.classList.add("admin_incell_error");
                showNotice(error.message || "셀 저장 실패", "error");
            } finally {
                cell.classList.remove("admin_incell_saving");
            }
        };

        cell.classList.add("admin_incell_editing");
        cell.innerHTML = "";
        cell.appendChild(control);
        control.focus();
        if (control instanceof HTMLInputElement) {
            control.select();
        }
        control.addEventListener("blur", () => void finish(true));
        control.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                void finish(true);
            } else if (event.key === "Escape") {
                event.preventDefault();
                void finish(false);
            }
        });
    };

    const buildDraftCell = (sourceCell) => {
        const cell = document.createElement("td");
        if (sourceCell.dataset.field) {
            cell.dataset.field = sourceCell.dataset.field;
        }
        if (sourceCell.dataset.required === "1") {
            cell.dataset.required = "1";
        }
        if (sourceCell.dataset.options) {
            cell.dataset.options = sourceCell.dataset.options;
        }
        if (sourceCell.dataset.readonly === "1") {
            cell.dataset.readonly = "1";
        }
        return cell;
    };

    const makeDraftControl = (cell) => {
        if (cell.dataset.readonly === "1") {
            return null;
        }
        const options = optionsForCell(cell);
        const control = options.length > 0 ? document.createElement("select") : document.createElement("input");
        control.className = "admin_incell_control";
        control.name = cell.dataset.field || "";
        if (control instanceof HTMLInputElement) {
            control.type = "text";
            control.placeholder = cell.dataset.required === "1" ? "required" : "";
        } else {
            options.forEach((optionValue) => {
                const option = document.createElement("option");
                option.value = optionValue;
                option.textContent = optionValue;
                control.appendChild(option);
            });
            control.value = options[0] || "";
        }
        cell.appendChild(control);
        return control;
    };

    const rowPayload = (row) => {
        const payload = new FormData();
        row.querySelectorAll("td[data-field]").forEach((cell) => {
            const fieldName = cell.dataset.field || "";
            const control = cell.querySelector("input, select, textarea");
            if (!fieldName || !control) {
                return;
            }
            payload.append(fieldName, control.value.trim());
        });
        payload.append("return_to", window.location.pathname);
        return payload;
    };

    const validateDraftRow = (row) => {
        for (const cell of row.querySelectorAll("td[data-required='1']")) {
            const control = cell.querySelector("input, select, textarea");
            const value = control ? control.value.trim() : "";
            if (!value) {
                cell.classList.add("admin_incell_required_missing");
                return false;
            }
            cell.classList.remove("admin_incell_required_missing");
        }
        return true;
    };

    const replaceDraftWithCreatedRow = (row, createdRow) => {
        const table = row.closest("[data-incell-edit-table]");
        if (!table) {
            row.remove();
            return;
        }
        row.dataset.draftRow = "0";
        row.dataset.entityType = table.dataset.entityType || "";
        row.dataset.entityId = createdRow.product_test_case_id || "";
        row.classList.remove("admin_incell_draft", "admin_incell_error");
        row.innerHTML = `
            <td data-field="product_test_case_id" data-primary-key="1">${escapeHtml(createdRow.product_test_case_id)}</td>
            <td data-field="product_test_case_title" data-required="1">${escapeHtml(createdRow.product_test_case_title)}</td>
            <td data-field="test_category" data-required="1">${escapeHtml(createdRow.test_category)}</td>
            <td data-field="test_objective">${escapeHtml(createdRow.test_objective || "")}</td>
            <td data-field="precondition">${escapeHtml(createdRow.precondition || "")}</td>
            <td data-field="expected_result">${escapeHtml(createdRow.expected_result || "")}</td>
            <td data-field="product_test_case_status" data-options="DRAFT|ACTIVE|DEPRECATED"><span class="status_badge status-${escapeHtml(String(createdRow.product_test_case_status || "").toLowerCase())}">${escapeHtml(createdRow.product_test_case_status)}</span></td>
            <td data-field="remark">${escapeHtml(createdRow.remark || "")}</td>
            <td data-readonly="1">${escapeHtml(createdRow.updated_at || "")}</td>
            <td data-readonly="1"></td>
        `;
    };

    const saveDraftRow = async (row) => {
        const table = row.closest("[data-incell-edit-table]");
        const action = table?.dataset?.createAction || "";
        if (!table || !action || !validateDraftRow(row)) {
            showNotice("필수 셀을 먼저 입력하세요.", "error");
            return;
        }
        row.classList.add("admin_incell_saving");
        try {
            const response = await fetch(action, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: rowPayload(row),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || payload.ok === false) {
                throw new Error(payload.message || `생성 실패 (HTTP ${response.status})`);
            }
            replaceDraftWithCreatedRow(row, payload.created_row || {});
            showNotice("행 생성 완료", "success");
        } catch (error) {
            row.classList.add("admin_incell_error");
            showNotice(error.message || "행 생성 실패", "error");
        } finally {
            row.classList.remove("admin_incell_saving");
        }
    };

    const addDraftRow = (table) => {
        const body = table.querySelector("tbody");
        const templateRow = body?.querySelector("tr:not([data-draft-row='1'])");
        if (!body || !templateRow) {
            return;
        }
        const row = document.createElement("tr");
        row.className = "admin_incell_draft";
        row.dataset.draftRow = "1";
        Array.from(templateRow.cells).forEach((sourceCell, index) => {
            const cell = buildDraftCell(sourceCell);
            if (index === templateRow.cells.length - 1) {
                cell.innerHTML = '<button type="button" class="project_standard_button" data-incell-save-row>저장</button> <button type="button" class="project_standard_button" data-incell-cancel-row>취소</button>';
            } else {
                makeDraftControl(cell);
            }
            row.appendChild(cell);
        });
        body.prepend(row);
        const first = row.querySelector("input, select, textarea");
        if (first instanceof HTMLElement) {
            first.focus();
        }
    };

    const initAdminIncellEdit = (root) => {
        (root || document).querySelectorAll("[data-incell-edit-table]").forEach((table) => {
            if (table.dataset.incellInit === "1") {
                return;
            }
            table.dataset.incellInit = "1";
            table.addEventListener("click", (event) => {
                const target = event.target;
                if (!(target instanceof Element)) {
                    return;
                }
                const saveButton = target.closest("[data-incell-save-row]");
                if (saveButton) {
                    const row = saveButton.closest("tr");
                    if (row) {
                        void saveDraftRow(row);
                    }
                    return;
                }
                const cancelButton = target.closest("[data-incell-cancel-row]");
                if (cancelButton) {
                    cancelButton.closest("tr")?.remove();
                    return;
                }
                if (target.closest("input, select, textarea, button")) {
                    return;
                }
                const cell = target.closest("td");
                if (cell && table.contains(cell)) {
                    beginExistingCellEdit(cell);
                }
            });
        });

        (root || document).querySelectorAll("[data-incell-add-row]").forEach((button) => {
            if (button.dataset.incellAddInit === "1") {
                return;
            }
            button.dataset.incellAddInit = "1";
            button.addEventListener("click", () => {
                const card = button.closest(".card");
                const table = card?.querySelector("[data-incell-edit-table]");
                if (table) {
                    addDraftRow(table);
                }
            });
        });
    };

    document.addEventListener("DOMContentLoaded", () => initAdminIncellEdit(document));
    window.initAdminIncellEdit = initAdminIncellEdit;
})();
