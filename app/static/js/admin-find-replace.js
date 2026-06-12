/**
 * admin-find-replace.js
 * Ctrl+H 전역 찾아 바꾸기 (Global Find & Replace)
 * - 모든 [data-incell-edit-table] 테이블 대상 스캔
 * - bulk-update API (POST /admin/api/product-test/fields/bulk-update) 재사용
 */
(function () {
    "use strict";

    /* ── 상수 ──────────────────────────────────────────────────────── */
    const CHUNK_SIZE = 50;
    const MODAL_ID   = "admin_fr_modal";

    /* ── 유틸 ──────────────────────────────────────────────────────── */
    const esc = (s) =>
        String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;")
                       .replace(/>/g,"&gt;").replace(/"/g,"&quot;");

    function showNotice(msg, level = "info") {
        if (typeof window.showCenterNonModalV2 === "function") {
            window.showCenterNonModalV2(msg, level);
        } else if (typeof window.openMessageModal === "function") {
            window.openMessageModal(msg);
        }
    }

    /* ── 셀 텍스트 읽기 (admin-incell-edit.js와 동일 로직) ─────────── */
    function readCellText(cell) {
        const badge = cell.querySelector(".status_badge");
        if (badge) return String(badge.textContent || "").trim();
        return String(cell.textContent || "").trim();
    }

    /* ── 셀이 저장 가능한지 판정 ──────────────────────────────────── */
    function isSaveable(cell, row, table) {
        if (!table.dataset.incellEditTable) return false;
        if (!cell.dataset.field)           return false;
        if (cell.dataset.incellActions === "1") return false;
        if (cell.dataset.readonly === "1") return false;
        if (cell.dataset.updateReadonly === "1") return false;
        if (!row.dataset.entityId)         return false;
        const entityType = row.dataset.entityType || table.dataset.entityType || "";
        if (!entityType)                   return false;
        return true;
    }

    function isPK(cell) {
        return cell.dataset.primaryKey === "1";
    }

    /* ── 전체 테이블 스캔 → 매칭 셀 목록 반환 ─────────────────────── */
    function scanTables(opts) {
        const { findText, matchWhole, caseSensitive } = opts;
        if (!findText) return [];

        const needle = caseSensitive ? findText : findText.toLowerCase();

        const results = [];
        document.querySelectorAll("[data-incell-edit-table]").forEach((table) => {
            table.querySelectorAll("tbody tr").forEach((row) => {
                if (row.dataset.draftRow === "1") return;
                const entityType = row.dataset.entityType || table.dataset.entityType || "";
                const entityId   = row.dataset.entityId   || "";
                if (!entityType || !entityId) return;

                row.querySelectorAll("td[data-field]").forEach((cell) => {
                    if (cell.dataset.incellActions === "1") return;

                    const raw  = readCellText(cell);
                    const haystack = caseSensitive ? raw : raw.toLowerCase();
                    const matched  = matchWhole ? haystack === needle : haystack.includes(needle);
                    if (!matched) return;

                    results.push({
                        cell,
                        row,
                        table,
                        entityType,
                        entityId,
                        fieldName:  cell.dataset.field,
                        originalValue: raw,
                        saveable: isSaveable(cell, row, table),
                        pk: isPK(cell),
                    });
                });
            });
        });
        return results;
    }

    /* ── old→new 치환 (부분/전체) ───────────────────────────────────── */
    function applyReplace(original, findText, replaceText, matchWhole, caseSensitive) {
        if (matchWhole) {
            const cmp = caseSensitive ? original : original.toLowerCase();
            const needle = caseSensitive ? findText : findText.toLowerCase();
            return cmp === needle ? replaceText : original;
        }
        if (caseSensitive) {
            return original.split(findText).join(replaceText);
        }
        const re = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
        return original.replace(re, replaceText);
    }

    /* ── bulk-update 청크 전송 ──────────────────────────────────────── */
    async function sendBulkUpdate(updates) {
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
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) {
            throw new Error(payload.message || `저장 실패 (HTTP ${response.status})`);
        }
        return payload;
    }

    /* ── 셀 DOM 갱신 ───────────────────────────────────────────────── */
    function renderCellValue(cell, value) {
        const text = String(value ?? "").trim();
        if (cell.dataset.options) {
            cell.innerHTML = text
                ? `<span class="status_badge status-${esc(text.toLowerCase())}">${esc(text)}</span>`
                : "";
            return;
        }
        cell.textContent = text;
    }

    /* ══════════════════ 모달 ══════════════════════════════════════════ */

    function getModal() { return document.getElementById(MODAL_ID); }

    function buildModal() {
        if (getModal()) return;
        const modal = document.createElement("div");
        modal.id   = MODAL_ID;
        modal.className = "admin_fr_backdrop";
        modal.setAttribute("role", "dialog");
        modal.setAttribute("aria-modal", "true");
        modal.setAttribute("aria-label", "찾아 바꾸기");
        modal.innerHTML = `
<div class="admin_fr_dialog">
  <div class="admin_fr_header">
    <span class="admin_fr_title">찾아 바꾸기 (Ctrl+H)</span>
    <button type="button" class="admin_fr_close" aria-label="닫기">&times;</button>
  </div>
  <div class="admin_fr_body">
    <div class="admin_fr_row">
      <label class="admin_fr_label">찾을 텍스트</label>
      <input id="admin_fr_find" class="admin_fr_input" type="text" placeholder="찾을 텍스트 입력…" autocomplete="off">
    </div>
    <div class="admin_fr_row">
      <label class="admin_fr_label">바꿀 텍스트</label>
      <input id="admin_fr_replace" class="admin_fr_input" type="text" placeholder="바꿀 텍스트 입력…" autocomplete="off">
    </div>
    <div class="admin_fr_options">
      <label class="admin_fr_opt">
        <input type="checkbox" id="admin_fr_whole"> 셀 전체 일치
      </label>
      <label class="admin_fr_opt">
        <input type="checkbox" id="admin_fr_case"> 대소문자 구분
      </label>
    </div>
    <div id="admin_fr_preview" class="admin_fr_preview" hidden></div>
  </div>
  <div class="admin_fr_footer">
    <button type="button" id="admin_fr_scan_btn"  class="project_standard_button">미리보기</button>
    <button type="button" id="admin_fr_apply_btn" class="project_standard_button admin_fr_apply_btn" hidden>적용</button>
    <button type="button" class="admin_fr_close_btn">취소</button>
  </div>
</div>`;
        document.body.appendChild(modal);

        /* 닫기 버튼들 */
        modal.querySelectorAll(".admin_fr_close, .admin_fr_close_btn").forEach((btn) => {
            btn.addEventListener("click", closeModal);
        });
        /* backdrop 클릭 닫기 */
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeModal();
        });
        /* 미리보기 버튼 */
        document.getElementById("admin_fr_scan_btn").addEventListener("click", runPreview);
        /* 적용 버튼 */
        document.getElementById("admin_fr_apply_btn").addEventListener("click", runApply);
        /* 입력 변경 시 미리보기 리셋 */
        ["admin_fr_find","admin_fr_replace","admin_fr_whole","admin_fr_case"].forEach((id) => {
            document.getElementById(id).addEventListener("input", resetPreview);
            document.getElementById(id).addEventListener("change", resetPreview);
        });
    }

    function openModal() {
        buildModal();
        const modal = getModal();
        modal.removeAttribute("hidden");
        modal.style.display = "";
        resetPreview();
        setTimeout(() => document.getElementById("admin_fr_find")?.focus(), 50);
    }

    function closeModal() {
        const modal = getModal();
        if (modal) modal.style.display = "none";
    }

    function resetPreview() {
        const preview  = document.getElementById("admin_fr_preview");
        const applyBtn = document.getElementById("admin_fr_apply_btn");
        if (preview)  { preview.hidden = true; preview.innerHTML = ""; }
        if (applyBtn) applyBtn.hidden = true;
        // 이전 하이라이트 제거
        document.querySelectorAll(".admin_fr_cell_match").forEach((el) =>
            el.classList.remove("admin_fr_cell_match","admin_fr_cell_match_pk"));
    }

    /* ── 미리보기 실행 ──────────────────────────────────────────────── */
    function getOpts() {
        return {
            findText:      (document.getElementById("admin_fr_find")?.value    ?? "").trim(),
            replaceText:   (document.getElementById("admin_fr_replace")?.value ?? ""),
            matchWhole:    document.getElementById("admin_fr_whole")?.checked  ?? false,
            caseSensitive: document.getElementById("admin_fr_case")?.checked   ?? false,
        };
    }

    let _lastScanResults = [];

    function runPreview() {
        resetPreview();
        const opts = getOpts();
        if (!opts.findText) {
            showNotice("찾을 텍스트를 입력하세요.", "error");
            return;
        }

        const all     = scanTables(opts);
        const saveable = all.filter((r) => r.saveable);
        const skipped  = all.filter((r) => !r.saveable);
        const pkItems  = saveable.filter((r) => r.pk);

        _lastScanResults = saveable;

        /* 셀 하이라이트 */
        saveable.forEach((r) => {
            r.cell.classList.add("admin_fr_cell_match");
            if (r.pk) r.cell.classList.add("admin_fr_cell_match_pk");
        });

        /* 테이블별 요약 */
        const byTable = {};
        saveable.forEach((r) => {
            const key = r.table.dataset.entityType || r.table.id || "unknown";
            byTable[key] = (byTable[key] || 0) + 1;
        });
        const tableRows = Object.entries(byTable)
            .map(([k,v]) => `<tr><td>${esc(k)}</td><td>${v}건</td></tr>`)
            .join("");

        const preview = document.getElementById("admin_fr_preview");
        const applyBtn = document.getElementById("admin_fr_apply_btn");

        if (saveable.length === 0) {
            preview.innerHTML = `<div class="admin_fr_preview_none">매칭 셀 없음${skipped.length ? ` (저장 불가 셀 ${skipped.length}개 제외)` : ""}.</div>`;
            preview.hidden = false;
            return;
        }

        preview.innerHTML = `
<div class="admin_fr_preview_summary">
  <strong>변경될 셀: ${saveable.length}개</strong>
  ${pkItems.length ? `<span class="admin_fr_pk_warn"> (PK/FK 포함 ${pkItems.length}건 ⚠️)</span>` : ""}
  ${skipped.length ? `<span class="admin_fr_skip_note"> · 저장 불가(파생) 셀 ${skipped.length}개 제외</span>` : ""}
</div>
<table class="admin_fr_table_summary">
  <thead><tr><th>entity_type</th><th>건수</th></tr></thead>
  <tbody>${tableRows}</tbody>
</table>`;
        preview.hidden = false;
        applyBtn.hidden = false;
    }

    /* ── 적용 실행 ──────────────────────────────────────────────────── */
    async function runApply() {
        const opts = getOpts();
        const results = _lastScanResults;
        if (!results.length) return;

        const applyBtn = document.getElementById("admin_fr_apply_btn");
        const scanBtn  = document.getElementById("admin_fr_scan_btn");
        applyBtn.disabled = true;
        scanBtn.disabled  = true;
        applyBtn.textContent = "적용 중…";

        /* updates 배열 구성 */
        const updates = results.map((r) => ({
            entity_type: r.entityType,
            entity_id:   r.entityId,
            field_name:  r.fieldName,
            value: applyReplace(r.originalValue, opts.findText, opts.replaceText, opts.matchWhole, opts.caseSensitive),
        }));

        /* 청크 분할 전송 */
        let successCount = 0;
        let errorMsg = "";
        for (let i = 0; i < updates.length; i += CHUNK_SIZE) {
            const chunk = updates.slice(i, i + CHUNK_SIZE);
            try {
                await sendBulkUpdate(chunk);
                successCount += chunk.length;
            } catch (err) {
                errorMsg = err.message;
                break;
            }
        }

        /* DOM 갱신 */
        if (successCount > 0) {
            const saved = updates.slice(0, successCount);
            saved.forEach((upd, idx) => {
                const r = results[idx];
                r.cell.classList.remove("admin_fr_cell_match","admin_fr_cell_match_pk");
                renderCellValue(r.cell, upd.value);
            });
        }

        applyBtn.disabled = false;
        scanBtn.disabled  = false;
        applyBtn.textContent = "적용";

        if (errorMsg) {
            showNotice(`일부 실패 (${successCount}/${updates.length}건 완료): ${errorMsg}`, "error");
        } else {
            showNotice(`${successCount}건 치환 완료`, "success");
            closeModal();
            resetPreview();
            _lastScanResults = [];
        }
    }

    /* ── Ctrl+H 핸들러 ──────────────────────────────────────────────── */
    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "h") {
            event.preventDefault();
            openModal();
        }
    });

    /* ── ESC 닫기 ───────────────────────────────────────────────────── */
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            const modal = getModal();
            if (modal && modal.style.display !== "none") closeModal();
        }
    });

    /* 외부 노출 */
    window.openAdminFindReplace = openModal;
})();
