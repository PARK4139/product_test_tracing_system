/**
 * Procedure action summary cell click -> modal editor for procedure_action.
 */
(function () {
    "use strict";

    const NUMBERED_LINE = /^\s*(?:\d+[\.\)]|[①-⑳]|\(\d+\))/;

    function countProcedureActionSteps(text) {
        const normalized = String(text || "").trim();
        if (!normalized) {
            return 0;
        }
        const lines = normalized.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        if (!lines.length) {
            return 1;
        }
        const numbered = lines.filter((line) => NUMBERED_LINE.test(line)).length;
        if (numbered >= 2) {
            return numbered;
        }
        if (lines.length >= 2) {
            return lines.length;
        }
        return 1;
    }

    function formatProcedureActionSummary(text) {
        const stepCount = countProcedureActionSteps(text);
        if (stepCount <= 0) {
            return "";
        }
        return Array.from({ length: stepCount }, (_v, index) => String(index + 1)).join(", ");
    }

    function ensureModal() {
        let overlay = document.getElementById("procedure_action_edit_modal");
        if (overlay) {
            return overlay;
        }
        overlay = document.createElement("div");
        overlay.id = "procedure_action_edit_modal";
        overlay.className = "guide_modal_overlay";
        overlay.setAttribute("aria-hidden", "true");
        overlay.style.display = "none";
        overlay.innerHTML = `
            <div class="guide_modal_card" role="dialog" aria-modal="true" aria-labelledby="procedure_action_edit_modal_title">
                <div class="section_header_row">
                    <h3 id="procedure_action_edit_modal_title">수행 절차 편집</h3>
                    <button type="button" id="procedure_action_edit_modal_close">닫기</button>
                </div>
                <div class="detail_guide" id="procedure_action_edit_modal_hint"></div>
                <textarea id="procedure_action_edit_modal_text" rows="12" style="width:100%;box-sizing:border-box;"></textarea>
                <div class="section_header_row" style="justify-content:flex-end;gap:8px;">
                    <button type="button" id="procedure_action_edit_modal_cancel">취소</button>
                    <button type="button" id="procedure_action_edit_modal_save" class="project_standard_button">저장</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }

    let activeCell = null;

    function closeModal() {
        const overlay = document.getElementById("procedure_action_edit_modal");
        if (!overlay) {
            return;
        }
        overlay.classList.remove("is_open");
        overlay.setAttribute("aria-hidden", "true");
        overlay.style.display = "none";
        activeCell = null;
    }

    async function saveProcedureAction(entityId, nextValue) {
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
                        entity_type: "product_test_procedure",
                        entity_id: entityId,
                        field_name: "procedure_action",
                        value: nextValue,
                    },
                ],
            }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
            const message = (data && data.message) || `저장 실패 (HTTP ${response.status})`;
            if (typeof window.showCenterNonModalV2 === "function") {
                window.showCenterNonModalV2(message, "error");
            } else if (typeof window.openMessageModal === "function") {
                window.openMessageModal(message);
            }
            return false;
        }
        if (typeof window.showCenterNonModalV2 === "function") {
            window.showCenterNonModalV2("수행 절차가 저장되었습니다.", "success");
        }
        return true;
    }

    function openModal(cell) {
        const entityId = String(cell.dataset.entityId || "").trim();
        const actionText = decodeProcedureActionCell(cell);
        if (!entityId) {
            return;
        }
        const overlay = ensureModal();
        const textarea = overlay.querySelector("#procedure_action_edit_modal_text");
        const hint = overlay.querySelector("#procedure_action_edit_modal_hint");
        if (!textarea || !hint) {
            return;
        }
        activeCell = cell;
        textarea.value = actionText;
        hint.textContent = `${entityId} · 하위 절차 ${countProcedureActionSteps(actionText)}단계`;
        overlay.classList.add("is_open");
        overlay.setAttribute("aria-hidden", "false");
        overlay.style.display = "";
        textarea.focus();
    }

    function bindModalEvents() {
        const overlay = ensureModal();
        if (overlay.dataset.bound === "1") {
            return;
        }
        overlay.dataset.bound = "1";
        overlay.querySelector("#procedure_action_edit_modal_close")?.addEventListener("click", closeModal);
        overlay.querySelector("#procedure_action_edit_modal_cancel")?.addEventListener("click", closeModal);
        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                closeModal();
            }
        });
        overlay.querySelector("#procedure_action_edit_modal_save")?.addEventListener("click", async () => {
            const cell = activeCell;
            const textarea = overlay.querySelector("#procedure_action_edit_modal_text");
            if (!cell || !textarea) {
                return;
            }
            const entityId = String(cell.dataset.entityId || "").trim();
            const nextValue = String(textarea.value || "").trim();
            if (!nextValue) {
                if (typeof window.showCenterNonModalV2 === "function") {
                    window.showCenterNonModalV2("procedure_action은 비울 수 없습니다.", "error");
                }
                return;
            }
            const ok = await saveProcedureAction(entityId, nextValue);
            if (!ok) {
                return;
            }
            cell.dataset.procedureActionB64 = btoa(
                String.fromCharCode(...new TextEncoder().encode(nextValue)),
            );
            cell.textContent = formatProcedureActionSummary(nextValue);
            closeModal();
        });
    }

    function decodeProcedureActionCell(cell) {
        const encoded = String(cell.dataset.procedureActionB64 || "").trim();
        if (encoded) {
            try {
                const binary = atob(encoded);
                const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
                return new TextDecoder().decode(bytes);
            } catch (_error) {
                return "";
            }
        }
        return String(cell.dataset.procedureAction || "").trim();
    }

    function decorateProcedureActionCell(cell) {
        if (!cell || cell.dataset.procedureActionBound === "1") {
            return;
        }
        const actionText = decodeProcedureActionCell(cell) || String(cell.textContent || "").trim();
        cell.dataset.procedureActionB64 = cell.dataset.procedureActionB64 || "";
        cell.dataset.procedureActionBound = "1";
        cell.classList.add("procedure_action_summary");
        cell.textContent = formatProcedureActionSummary(actionText);
        cell.title = "클릭하여 수행 절차 편집";
        cell.style.cursor = "pointer";
        cell.addEventListener("click", (event) => {
            event.stopPropagation();
            openModal(cell);
        });
    }

    function initProcedureActionCells(root) {
        bindModalEvents();
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll(".procedure_action_summary, td[data-procedure-action]").forEach((cell) => {
            decorateProcedureActionCell(cell);
        });
    }

    window.countProcedureActionSteps = countProcedureActionSteps;
    window.formatProcedureActionSummary = formatProcedureActionSummary;
    window.initProcedureActionCells = initProcedureActionCells;

    document.addEventListener("DOMContentLoaded", () => {
        initProcedureActionCells(document);
    });
})();
