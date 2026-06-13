/**
 * admin-find-replace.js
 * BACKTICK key -> 고급기능 -> 일괄치환 모달
 */
(function () {
    "use strict";

    var CHUNK_SIZE = 50;
    var MODAL_ID   = "admin_fr_modal";
    var MENU_ID    = "admin_adv_edit_menu";
    var BACKTICK   = String.fromCharCode(96); // ` key

    /* util */
    function esc(s) {
        return String(s == null ? "" : s)
            .replace(/&/g,"&amp;").replace(/</g,"&lt;")
            .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    }

    function showNotice(msg, level) {
        level = level || "info";
        if (typeof window.showCenterNonModalV2 === "function") {
            window.showCenterNonModalV2(msg, level);
        } else if (typeof window.openMessageModal === "function") {
            window.openMessageModal(msg);
        }
    }

    /* cell text */
    function readCellText(cell) {
        var badge = cell.querySelector(".status_badge");
        if (badge) return String(badge.textContent || "").trim();
        return String(cell.textContent || "").trim();
    }

    function isSaveable(cell, row, table) {
        if (!('incellEditTable' in table.dataset))        return false;
        if (!cell.dataset.field)                   return false;
        if (cell.dataset.incellActions === "1")    return false;
        if (cell.dataset.readonly === "1")         return false;
        if (cell.dataset.updateReadonly === "1")   return false;
        if (!row.dataset.entityId)                 return false;
        var et = row.dataset.entityType || table.dataset.entityType || "";
        if (!et)                                   return false;
        return true;
    }

    function isPK(cell) { return cell.dataset.primaryKey === "1"; }

    /* scan */
    function scanTables(opts) {
        var findText      = opts.findText;
        var matchWhole    = opts.matchWhole;
        var caseSensitive = opts.caseSensitive;
        if (!findText) return [];
        var needle  = caseSensitive ? findText : findText.toLowerCase();
        var results = [];
        document.querySelectorAll("[data-incell-edit-table]").forEach(function (table) {
            table.querySelectorAll("tbody tr").forEach(function (row) {
                if (row.dataset.draftRow === "1") return;
                var entityType = row.dataset.entityType || table.dataset.entityType || "";
                var entityId   = row.dataset.entityId || "";
                if (!entityType || !entityId) return;
                row.querySelectorAll("td[data-field]").forEach(function (cell) {
                    if (cell.dataset.incellActions === "1") return;
                    var raw      = readCellText(cell);
                    var haystack = caseSensitive ? raw : raw.toLowerCase();
                    var matched  = matchWhole ? haystack === needle : haystack.indexOf(needle) !== -1;
                    if (!matched) return;
                    results.push({
                        cell: cell, row: row, table: table,
                        entityType: entityType, entityId: entityId,
                        fieldName: cell.dataset.field,
                        originalValue: raw,
                        saveable: isSaveable(cell, row, table),
                        pk: isPK(cell),
                    });
                });
            });
        });
        return results;
    }

    /* replace logic */
    function applyReplace(original, findText, replaceText, matchWhole, caseSensitive) {
        if (matchWhole) {
            var cmp    = caseSensitive ? original : original.toLowerCase();
            var needle = caseSensitive ? findText : findText.toLowerCase();
            return cmp === needle ? replaceText : original;
        }
        if (caseSensitive) return original.split(findText).join(replaceText);
        var re = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
        return original.replace(re, replaceText);
    }

    /* bulk-update API */
    async function sendBulkUpdate(updates) {
        var response = await fetch("/admin/api/product-test/fields/bulk-update", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({ updates: updates }),
        });
        var payload = await response.json().catch(function () { return {}; });
        if (!response.ok || payload.ok === false) {
            throw new Error(payload.message || ("저장 실패 (HTTP " + response.status + ")"));
        }
        return payload;
    }

    /* render cell */
    function renderCellValue(cell, value) {
        var text = String(value == null ? "" : value).trim();
        if (cell.dataset.options) {
            cell.innerHTML = text
                ? "<span class=\"status_badge status-" + esc(text.toLowerCase()) + "\">" + esc(text) + "</span>"
                : "";
            return;
        }
        cell.textContent = text;
    }

    /* ===== 일괄치환 모달 ===== */

    function getModal() { return document.getElementById(MODAL_ID); }

    function buildModal() {
        if (getModal()) return;
        var modal = document.createElement("div");
        modal.id        = MODAL_ID;
        modal.className = "admin_fr_backdrop";
        modal.setAttribute("role", "dialog");
        modal.setAttribute("aria-modal", "true");
        modal.setAttribute("aria-label", "일괄치환");
        modal.innerHTML =
            "<div class=\"admin_fr_dialog\">" +
              "<div class=\"admin_fr_header\">" +
                "<span class=\"admin_fr_title\">일괄치환</span>" +
                "<button type=\"button\" class=\"admin_fr_close\" aria-label=\"닫기\">&times;</button>" +
              "</div>" +
              "<div class=\"admin_fr_body\">" +
                "<div class=\"admin_fr_row\">" +
                  "<label class=\"admin_fr_label\">찾을 텍스트</label>" +
                  "<input id=\"admin_fr_find\" class=\"admin_fr_input\" type=\"text\" placeholder=\"찾을 텍스트 입력…\" autocomplete=\"off\">" +
                "</div>" +
                "<div class=\"admin_fr_row\">" +
                  "<label class=\"admin_fr_label\">바꿀 텍스트</label>" +
                  "<input id=\"admin_fr_replace\" class=\"admin_fr_input\" type=\"text\" placeholder=\"바꿀 텍스트 입력…\" autocomplete=\"off\">" +
                "</div>" +
                "<div class=\"admin_fr_options\">" +
                  "<label class=\"admin_fr_opt\"><input type=\"checkbox\" id=\"admin_fr_whole\"> 부분 문자열</label>" +
                  "<label class=\"admin_fr_opt\"><input type=\"checkbox\" id=\"admin_fr_case\"> 대소문자 구분</label>" +
                "</div>" +
                "<div id=\"admin_fr_preview\" class=\"admin_fr_preview\" hidden></div>" +
              "</div>" +
              "<div class=\"admin_fr_footer\">" +
                "<button type=\"button\" id=\"admin_fr_scan_btn\" class=\"project_standard_button\">미리보기</button>" +
                "<button type=\"button\" id=\"admin_fr_apply_btn\" class=\"project_standard_button admin_fr_apply_btn\" hidden>적용</button>" +
                "<button type=\"button\" class=\"admin_fr_close_btn\">취소</button>" +
              "</div>" +
            "</div>";
        document.body.appendChild(modal);

        modal.querySelectorAll(".admin_fr_close, .admin_fr_close_btn").forEach(function (btn) {
            btn.addEventListener("click", closeModal);
        });
        modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
        document.getElementById("admin_fr_scan_btn").addEventListener("click",  runPreview);
        document.getElementById("admin_fr_apply_btn").addEventListener("click", runApply);
        ["admin_fr_find","admin_fr_replace","admin_fr_whole","admin_fr_case"].forEach(function (id) {
            document.getElementById(id).addEventListener("input",  resetPreview);
            document.getElementById(id).addEventListener("change", resetPreview);
        });
        document.getElementById("admin_fr_find").addEventListener("input", function () { lsSave("find", this.value); });
        document.getElementById("admin_fr_replace").addEventListener("input", function () { lsSave("replace", this.value); });
        document.getElementById("admin_fr_whole").addEventListener("change", function () { lsSave("substring", this.checked ? "1" : ""); });
        document.getElementById("admin_fr_case").addEventListener("change", function () { lsSave("case", this.checked ? "1" : ""); });
    }

    function lsKey(k) { return "admin_fr_" + k; }
    function lsSave(k, v) { try { localStorage.setItem(lsKey(k), v); } catch(e) {} }
    function lsLoad(k, def) { try { return localStorage.getItem(lsKey(k)) || def; } catch(e) { return def; } }

    function openModal() {
        buildModal();
        getModal().style.display = "";
        /* localStorage 복원 */
        var findEl    = document.getElementById("admin_fr_find");
        var replaceEl = document.getElementById("admin_fr_replace");
        var wholeEl   = document.getElementById("admin_fr_whole");
        var caseEl    = document.getElementById("admin_fr_case");
        if (findEl)    findEl.value      = lsLoad("find", "");
        if (replaceEl) replaceEl.value   = lsLoad("replace", "");
        if (wholeEl)   wholeEl.checked   = lsLoad("substring", "1") === "1";
        if (caseEl)    caseEl.checked    = lsLoad("case", "") === "1";
        resetPreview();
        setTimeout(function () {
            if (findEl) { findEl.focus(); findEl.select(); }
        }, 50);
    }

    function closeModal() {
        var modal = getModal();
        if (modal) modal.style.display = "none";
    }

    function resetPreview() {
        var preview  = document.getElementById("admin_fr_preview");
        var applyBtn = document.getElementById("admin_fr_apply_btn");
        if (preview)  { preview.hidden = true; preview.innerHTML = ""; }
        if (applyBtn) applyBtn.hidden = true;
        document.querySelectorAll(".admin_fr_cell_match").forEach(function (el) {
            el.classList.remove("admin_fr_cell_match","admin_fr_cell_match_pk");
        });
    }

    function getOpts() {
        return {
            findText:      (document.getElementById("admin_fr_find") ? document.getElementById("admin_fr_find").value : "").trim(),
            replaceText:   document.getElementById("admin_fr_replace") ? document.getElementById("admin_fr_replace").value : "",
            matchWhole:    document.getElementById("admin_fr_whole")  ? !document.getElementById("admin_fr_whole").checked  : true,
            caseSensitive: document.getElementById("admin_fr_case")   ? document.getElementById("admin_fr_case").checked   : false,
        };
    }

    var _lastScanResults = [];

    function runPreview() {
        resetPreview();
        var opts = getOpts();
        if (!opts.findText) { showNotice("찾을 텍스트를 입력하세요.", "error"); return; }

        var all      = scanTables(opts);
        var saveable = all.filter(function (r) { return r.saveable; });
        var skipped  = all.filter(function (r) { return !r.saveable; });
        var pkItems  = saveable.filter(function (r) { return r.pk; });
        _lastScanResults = saveable;

        saveable.forEach(function (r) {
            r.cell.classList.add("admin_fr_cell_match");
            if (r.pk) r.cell.classList.add("admin_fr_cell_match_pk");
        });

        var byTable = {};
        saveable.forEach(function (r) {
            var key = r.table.dataset.entityType || r.table.id || "unknown";
            byTable[key] = (byTable[key] || 0) + 1;
        });
        var tableRows = Object.keys(byTable).map(function (k) {
            return "<tr><td>" + esc(k) + "</td><td>" + byTable[k] + "건</td></tr>";
        }).join("");

        var preview  = document.getElementById("admin_fr_preview");
        var applyBtn = document.getElementById("admin_fr_apply_btn");

        if (saveable.length === 0) {
            preview.innerHTML = "<div class=\"admin_fr_preview_none\">매칭 셀 없음" +
                (skipped.length ? " (저장 불가 셀 " + skipped.length + "개 제외)" : "") + ".</div>";
            preview.hidden = false;
            return;
        }

        preview.innerHTML =
            "<div class=\"admin_fr_preview_summary\">" +
              "<strong>변경될 셀: " + saveable.length + "개</strong>" +
              (pkItems.length ? "<span class=\"admin_fr_pk_warn\"> (PK/FK 포함 " + pkItems.length + "건 ⚠️)</span>" : "") +
              (skipped.length ? "<span class=\"admin_fr_skip_note\"> · 저장 불가(파생) 셀 " + skipped.length + "개 제외</span>" : "") +
            "</div>" +
            "<table class=\"admin_fr_table_summary\">" +
              "<thead><tr><th>entity_type</th><th>건수</th></tr></thead>" +
              "<tbody>" + tableRows + "</tbody>" +
            "</table>";
        preview.hidden = false;
        applyBtn.hidden = false;
    }

    async function runApply() {
        var opts    = getOpts();
        var results = _lastScanResults;
        if (!results.length) return;

        var applyBtn = document.getElementById("admin_fr_apply_btn");
        var scanBtn  = document.getElementById("admin_fr_scan_btn");
        applyBtn.disabled = true;
        scanBtn.disabled  = true;
        applyBtn.textContent = "적용 중…";

        var updates = results.map(function (r) {
            return {
                entity_type: r.entityType,
                entity_id:   r.entityId,
                field_name:  r.fieldName,
                value: applyReplace(r.originalValue, opts.findText, opts.replaceText, opts.matchWhole, opts.caseSensitive),
            };
        });

        var successCount = 0;
        var errorMsg = "";
        for (var i = 0; i < updates.length; i += CHUNK_SIZE) {
            try {
                await sendBulkUpdate(updates.slice(i, i + CHUNK_SIZE));
                successCount += Math.min(CHUNK_SIZE, updates.length - i);
            } catch (err) {
                errorMsg = err.message;
                break;
            }
        }

        updates.slice(0, successCount).forEach(function (upd, idx) {
            var r = results[idx];
            r.cell.classList.remove("admin_fr_cell_match","admin_fr_cell_match_pk");
            renderCellValue(r.cell, upd.value);
        });

        applyBtn.disabled = false;
        scanBtn.disabled  = false;
        applyBtn.textContent = "적용";

        if (errorMsg) {
            showNotice(successCount + "/" + updates.length + "건 완료\n" + errorMsg, "error");
        } else {
            showNotice(successCount + "/" + updates.length + "건 완료", "success");
            closeModal();
            resetPreview();
            _lastScanResults = [];
        }
    }

    /* ===== 고급기능 ===== */

    function getMenu() { return document.getElementById(MENU_ID); }

    function showAdminAdvNotice(message, level) {
        if (typeof window.showCenterNonModalV2 === "function") {
            window.showCenterNonModalV2(message, level || "info");
            return;
        }
        if (typeof window.openMessageModal === "function") {
            window.openMessageModal(message);
            return;
        }
        window.alert(message);
    }

    async function runAdminE2eTest(button) {
        if (button.disabled) return;
        button.disabled = true;
        try {
            var response = await fetch("/admin/qc/e2e-fill", {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    Accept: "application/json",
                },
                credentials: "same-origin",
            });
            var data = await response.json().catch(function () { return {}; });
            var ok = response.ok && data && data.ok;
            showAdminAdvNotice((data && data.message) || "E2E TEST 요청 처리 실패", ok ? "success" : "error");
        } catch (_error) {
            showAdminAdvNotice("E2E TEST 요청 중 네트워크 오류가 발생했습니다.", "error");
        } finally {
            window.setTimeout(function () { button.disabled = false; }, 1200);
        }
    }

    function toggleAllCardCompact(button) {
        var cardButtons = Array.from(document.querySelectorAll(".card_compact_toggle_btn"));
        if (!cardButtons.length) {
            showAdminAdvNotice("COMPACT 대상 카드가 없습니다.", "guide");
            return;
        }
        var shouldCompact = document.querySelectorAll(".card.compact_mode").length !== cardButtons.length;
        cardButtons.forEach(function (cardButton) {
            var card = cardButton.closest(".card");
            var isCompact = card && card.classList.contains("compact_mode");
            if ((shouldCompact && !isCompact) || (!shouldCompact && isCompact)) {
                cardButton.click();
            }
        });
        button.textContent = shouldCompact ? "히스토리 폭" : "COMPACT";
    }

    function buildMenu() {
        if (getMenu()) return;
        var menu = document.createElement("div");
        menu.id        = MENU_ID;
        menu.className = "admin_adv_menu";
        menu.setAttribute("role", "menu");
        menu.style.display = "none";
        menu.innerHTML =
            "<div class=\"admin_adv_menu_header\">고급편집메뉴</div>" +
            "<button type=\"button\" class=\"admin_adv_menu_item\" id=\"admin_adv_find_replace_btn\">" +
              "<span class=\"admin_adv_menu_icon\">&#8644;</span> 일괄치환" +
            "</button>";
        document.body.appendChild(menu);

        document.getElementById("admin_adv_find_replace_btn").addEventListener("click", function () {
            closeMenu();
            openModal();
        });

        document.addEventListener("mousedown", function (e) {
            var m = getMenu();
            if (m && m.style.display !== "none" && !m.contains(e.target)) closeMenu();
        }, true);
    }

    function openMenu() {
        buildMenu();
        var menu = getMenu();
        menu.style.display   = "";
        menu.style.left      = "50%";
        menu.style.top       = "50%";
        menu.style.transform = "translate(-50%, -50%)";
        setTimeout(function () {
            var btn = document.getElementById("admin_adv_find_replace_btn");
            if (btn) btn.focus();
        }, 30);
    }

    function closeMenu() {
        var menu = getMenu();
        if (menu) menu.style.display = "none";
    }

    /* BACKTICK key toggle (Korean IME: event.key may not be ` so also check keyCode 192) */
    document.addEventListener("keydown", function (event) {
        var isBT = event.key === BACKTICK || event.keyCode === 192;
        if (!isBT) return;
        var tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        event.preventDefault();
        var menu = getMenu();
        if (menu && menu.style.display !== "none") closeMenu();
        else openMenu();
    });

    /* ESC */
    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        var modal = getModal();
        if (modal && modal.style.display !== "none") { closeModal(); return; }
        closeMenu();
    });

    window.openAdminFindReplace = openModal;
    window.openAdminAdvEditMenu = openMenu;
})();
