(function () {
    "use strict";

    var ROOT_SELECTOR = "[data-integrity-sheet-root]";
    var STATE_KEY = "integrity_sheet_view_state_v1";
    var TABLE_DEFS = [
        { key: "case", label: "Case" },
        { key: "result", label: "Result" },
        { key: "release", label: "Release/Round" },
        { key: "defect", label: "Defect" },
        { key: "evidence", label: "Evidence" },
    ];
    var FLAG_META = {
        case_id_invalid: { label: "비정상 ID", tone: "danger" },
        procedure_missing: { label: "Procedure 없음", tone: "danger" },
        topology_mismatch: { label: "토폴로지 불일치", tone: "warning" },
        topology_unclassified: { label: "UNCLASSIFIED", tone: "warning" },
        evidence_missing: { label: "증거 없음", tone: "muted" },
        combo_unclassified: { label: "연결구성 미분류", tone: "warning" },
        round_missing: { label: "Round 누락", tone: "danger" },
        legacy_ap_text: { label: "AP 레거시", tone: "warning" },
        orphan_visible_round: { label: "Visible Round 고아", tone: "danger" },
        opened_without_blocked_result: { label: "결함/결과 상태 불일치", tone: "danger" },
        missing_result: { label: "연결 Result 없음", tone: "danger" },
    };
    var COLUMN_ORDER = {
        case: ["id", "title", "status", "test_category", "procedure_count", "result_count", "case_topology", "dominant_result_topology", "candidate_topologies", "remark"],
        result: ["id", "run_id", "case_id", "status", "combo", "case_topology", "evidence_count", "remark"],
        release: ["id", "upstream_release_id", "release_stage", "status", "test_round_id", "release_visible", "run_count", "remark"],
        defect: ["id", "result_id", "status", "result_status", "severity", "priority", "assigned_to", "expected_resolution_date", "remark"],
        evidence: ["id", "result_id", "procedure_result_id", "defect_id", "evidence_type", "file_name", "file_path", "file_hash", "captured_at", "remark"],
    };

    function log(msg, data, level) {
        if (window.clientLog) {
            window.clientLog("sheetView: " + msg, data, level);
        }
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function loadState() {
        try {
            return JSON.parse(window.uiStateGetItem ? window.uiStateGetItem(STATE_KEY) || "{}" : "{}");
        } catch (err) {
            return {};
        }
    }

    function saveState(state) {
        if (!window.uiStateSetItem) {
            return;
        }
        window.uiStateSetItem(STATE_KEY, JSON.stringify(state));
    }

    function defaultState() {
        return {
            activeTable: "result",
            problemOnly: true,
            query: "",
            sortBy: "id",
            sortDir: "asc",
        };
    }

    function normalizeState(raw) {
        var state = Object.assign(defaultState(), raw || {});
        if (!TABLE_DEFS.some(function (item) { return item.key === state.activeTable; })) {
            state.activeTable = "result";
        }
        if (state.sortDir !== "desc") {
            state.sortDir = "asc";
        }
        return state;
    }

    function formatValue(value) {
        if (value == null) {
            return "";
        }
        if (typeof value === "object") {
            return JSON.stringify(value);
        }
        return String(value);
    }

    function formatRemarkHtml(value) {
        var text = formatValue(value);
        if (!text) {
            return "";
        }
        return text.split(/\r?\n/).filter(function (line) {
            return line.trim() !== "";
        }).map(function (line) {
            var match = line.match(/^(\[[^\]]+\])\s*(.*)$/);
            if (match) {
                return '<div class="integrity_sheet_remark_line">' +
                    '<span class="integrity_sheet_remark_tag">' + escapeHtml(match[1]) + "</span>" +
                    '<span class="integrity_sheet_remark_value">' + escapeHtml(match[2]) + "</span>" +
                    "</div>";
            }
            return '<div class="integrity_sheet_remark_line">' + escapeHtml(line) + "</div>";
        }).join("");
    }

    function requestJson(url, options) {
        return fetch(url, options).then(function (response) {
            return response.json().catch(function () {
                return { detail: "Invalid JSON response" };
            }).then(function (data) {
                if (!response.ok) {
                    throw new Error(data.detail || ("HTTP " + response.status));
                }
                return data;
            });
        });
    }

    function buildDiffText(preview) {
        var lines = ["변경 미리보기"];
        (preview.diff || []).forEach(function (item) {
            lines.push("- " + item.field + ": " + formatValue(item.from) + " -> " + formatValue(item.to));
        });
        if (!preview.diff || !preview.diff.length) {
            lines.push("- 변경 없음");
        }
        return lines.join("\n");
    }

    function isEditableField(payload, fieldName) {
        var editable = payload && payload.meta && Array.isArray(payload.meta.editable_fields)
            ? payload.meta.editable_fields
            : [];
        return editable.indexOf(fieldName) >= 0;
    }

    function findRowById(payload, rowId) {
        return (payload.rows || []).find(function (row) {
            return String(row.id || "") === String(rowId || "");
        }) || null;
    }

    function getProblemFlags(row) {
        return Object.keys(row.flags || {}).filter(function (flagName) {
            return !!row.flags[flagName];
        });
    }

    function buildBadge(flagName) {
        var meta = FLAG_META[flagName] || { label: flagName, tone: "muted" };
        return '<span class="integrity_sheet_badge is-' + meta.tone + '">' + escapeHtml(meta.label) + "</span>";
    }

    function rowTone(row) {
        var flags = getProblemFlags(row);
        if (flags.some(function (flagName) { return (FLAG_META[flagName] || {}).tone === "danger"; })) {
            return "danger";
        }
        if (flags.some(function (flagName) { return (FLAG_META[flagName] || {}).tone === "warning"; })) {
            return "warning";
        }
        if (flags.some(function (flagName) { return (FLAG_META[flagName] || {}).tone === "muted"; })) {
            return "muted";
        }
        return "";
    }

    function compareValues(a, b) {
        var aText = formatValue(a).toLowerCase();
        var bText = formatValue(b).toLowerCase();
        if (aText < bText) return -1;
        if (aText > bText) return 1;
        return 0;
    }

    function getColumns(tableKey, rows) {
        var preferred = COLUMN_ORDER[tableKey] || [];
        var dynamic = rows.length ? Object.keys(rows[0]).filter(function (key) {
            return key !== "flags";
        }) : [];
        var all = preferred.concat(dynamic);
        return all.filter(function (key, index) {
            return key !== "flags" && all.indexOf(key) === index;
        });
    }

    function buildSummary(summary) {
        var html = "";
        html += '<span class="integrity_sheet_stat">rows ' + escapeHtml(summary.row_count || 0) + "</span>";
        Object.keys(summary.flag_counts || {}).forEach(function (flagName) {
            var meta = FLAG_META[flagName] || { label: flagName, tone: "muted" };
            html += '<span class="integrity_sheet_stat is-' + meta.tone + '">' + escapeHtml(meta.label) + " " + escapeHtml(summary.flag_counts[flagName]) + "</span>";
        });
        if (summary.parsed_combo_count != null) {
            html += '<span class="integrity_sheet_stat">parsed combo ' + escapeHtml(summary.parsed_combo_count) + "</span>";
        }
        if (summary.rounds_without_release_count != null) {
            html += '<span class="integrity_sheet_stat is-danger">round without release ' + escapeHtml(summary.rounds_without_release_count) + "</span>";
        }
        if (summary.missing_evidence_result_count != null) {
            html += '<span class="integrity_sheet_stat is-muted">result without evidence ' + escapeHtml(summary.missing_evidence_result_count) + "</span>";
        }
        return html;
    }

    function matchesQuery(row, query) {
        if (!query) {
            return true;
        }
        var needle = query.toLowerCase();
        return Object.keys(row).some(function (key) {
            if (key === "flags") {
                return getProblemFlags(row).join(" ").toLowerCase().indexOf(needle) >= 0;
            }
            return formatValue(row[key]).toLowerCase().indexOf(needle) >= 0;
        });
    }

    function renderTable(root, payload, state) {
        var rows = (payload.rows || []).slice();
        if (state.problemOnly) {
            rows = rows.filter(function (row) { return getProblemFlags(row).length > 0; });
        }
        if (state.query) {
            rows = rows.filter(function (row) { return matchesQuery(row, state.query); });
        }
        rows.sort(function (left, right) {
            var compared = compareValues(left[state.sortBy], right[state.sortBy]);
            return state.sortDir === "desc" ? -compared : compared;
        });
        var columns = getColumns(payload.table, payload.rows || []);
        var headHtml = columns.map(function (key) {
            var active = state.sortBy === key;
            var mark = active ? (state.sortDir === "desc" ? "▼" : "▲") : "";
            return '<th data-sheet-sort="' + escapeHtml(key) + '">' + escapeHtml(key) + '<span class="integrity_sheet_sort_mark">' + mark + "</span></th>";
        }).join("");
        var bodyHtml = rows.map(function (row) {
            var flags = getProblemFlags(row);
            var tone = rowTone(row);
            var cells = columns.map(function (key) {
                var value = row[key];
                var text = formatValue(value);
                var cls = key === "remark" || key === "candidate_topologies" ? "integrity_sheet_cell_pre" : "";
                var bodyHtml = escapeHtml(text);
                var editable = isEditableField(payload, key);
                if (key === "remark") {
                    cls = "integrity_sheet_cell_pre integrity_sheet_remark";
                    bodyHtml = formatRemarkHtml(value);
                }
                return '<td' +
                    (editable ? ' class="is-editable" data-sheet-row-id="' + escapeHtml(row.id) + '" data-sheet-field="' + escapeHtml(key) + '"' : "") +
                    '><div class="' + cls + '">' + bodyHtml + "</div></td>";
            }).join("");
            return '<tr class="' + (tone ? "has-" + tone : "") + '"><td><div class="integrity_sheet_badges">' +
                (flags.length ? flags.map(buildBadge).join("") : '<span class="integrity_sheet_badge">OK</span>') +
                "</div></td>" + cells + "</tr>";
        }).join("");
        if (!bodyHtml) {
            bodyHtml = '<tr><td colspan="' + String(columns.length + 1) + '" class="integrity_sheet_empty">조건에 맞는 행이 없습니다.</td></tr>';
        }
        root.querySelector("[data-sheet-summary]").innerHTML = buildSummary(payload.summary || {});
        root.querySelector("[data-sheet-create-evidence]").hidden = !(payload.meta && payload.meta.create_supported);
        root.querySelector("[data-sheet-table-wrap]").innerHTML =
            '<table class="integrity_sheet_table">' +
            "<thead><tr><th>flags</th>" + headHtml + "</tr></thead>" +
            "<tbody>" + bodyHtml + "</tbody>" +
            "</table>";
    }

    function renderTabs(root, state, cache) {
        root.querySelector("[data-sheet-tabs]").innerHTML = TABLE_DEFS.map(function (item) {
            var payload = cache[item.key];
            var flagCounts = payload && payload.summary && payload.summary.flag_counts ? payload.summary.flag_counts : {};
            var issueCount = Object.keys(flagCounts).reduce(function (sum, key) { return sum + Number(flagCounts[key] || 0); }, 0);
            return '<button type="button" class="integrity_sheet_tab_btn' + (state.activeTable === item.key ? " is-active" : "") +
                '" data-sheet-table="' + item.key + '">' + escapeHtml(item.label) +
                '<span class="integrity_sheet_tab_meta">' + escapeHtml(payload ? payload.summary.row_count : "…") +
                (issueCount ? " / issue " + issueCount : "") + "</span></button>";
        }).join("");
    }

    function setLoading(root, text) {
        root.querySelector("[data-sheet-table-wrap]").innerHTML = '<div class="integrity_sheet_loading">' + escapeHtml(text) + "</div>";
    }

    function setError(root, text) {
        root.querySelector("[data-sheet-table-wrap]").innerHTML = '<div class="integrity_sheet_error">' + escapeHtml(text) + "</div>";
    }

    function fetchSheet(tableKey) {
        return requestJson("/admin/api/sheet/" + encodeURIComponent(tableKey));
    }

    function previewSheetPatch(tableKey, rowId, changes) {
        return requestJson("/admin/api/sheet/" + encodeURIComponent(tableKey) + "/" + encodeURIComponent(rowId), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: "preview",
                changes: changes,
                reason: "sheet_inline_edit",
            }),
        });
    }

    function applySheetPatch(tableKey, rowId, changes, previewHash) {
        return requestJson("/admin/api/sheet/" + encodeURIComponent(tableKey) + "/" + encodeURIComponent(rowId), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: "apply",
                changes: changes,
                preview_hash: previewHash,
                reason: "sheet_inline_edit",
            }),
        });
    }

    function previewEvidenceCreate(payload) {
        return requestJson("/admin/api/sheet/evidence", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(Object.assign({ mode: "preview", reason: "sheet_evidence_create" }, payload)),
        });
    }

    function applyEvidenceCreate(payload, previewHash) {
        return requestJson("/admin/api/sheet/evidence", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(Object.assign({
                mode: "apply",
                preview_hash: previewHash,
                reason: "sheet_evidence_create",
            }, payload)),
        });
    }

    function promptEvidencePayload() {
        var resultId = window.prompt("result_id");
        if (!resultId) return null;
        var evidenceType = window.prompt("evidence_type", "screenshot");
        if (!evidenceType) return null;
        var filePath = window.prompt("file_path");
        if (!filePath) return null;
        return {
            result_id: resultId,
            procedure_result_id: window.prompt("procedure_result_id", "") || "",
            defect_id: window.prompt("defect_id", "") || "",
            evidence_type: evidenceType,
            file_name: window.prompt("file_name", "") || "",
            file_path: filePath,
            file_hash: window.prompt("file_hash", "") || "",
            captured_at: window.prompt("captured_at", "") || "",
            remark: window.prompt("remark", "") || "",
        };
    }

    function mount(root) {
        if (!(root instanceof HTMLElement) || root.dataset.sheetViewInit === "1") {
            return;
        }
        root.dataset.sheetViewInit = "1";
        root.innerHTML =
            '<div class="integrity_sheet_root">' +
            '  <div class="integrity_sheet_toolbar">' +
            '    <div class="integrity_sheet_tabs" data-sheet-tabs></div>' +
            '    <div class="integrity_sheet_controls">' +
            '      <input type="search" class="integrity_sheet_search" data-sheet-query placeholder="행/플래그 검색" />' +
            '      <label class="integrity_sheet_toggle"><input type="checkbox" data-sheet-problem-only /> 문제 있는 행만 보기</label>' +
            '      <button type="button" class="project_standard_button" data-sheet-create-evidence hidden>+ Evidence</button>' +
            '      <button type="button" class="project_standard_button" data-sheet-refresh>새로고침</button>' +
            "    </div>" +
            "  </div>" +
            '  <div class="integrity_sheet_summary" data-sheet-summary></div>' +
            '  <div class="integrity_sheet_table_wrap" data-sheet-table-wrap></div>' +
            "</div>";

        var state = normalizeState(loadState());
        var cache = Object.create(null);
        var queryInput = root.querySelector("[data-sheet-query]");
        var problemOnlyInput = root.querySelector("[data-sheet-problem-only]");
        queryInput.value = state.query;
        problemOnlyInput.checked = !!state.problemOnly;

        function persist() {
            saveState(state);
        }

        function refreshActive(force) {
            renderTabs(root, state, cache);
            if (!force && cache[state.activeTable]) {
                renderTable(root, cache[state.activeTable], state);
                return Promise.resolve();
            }
            setLoading(root, state.activeTable + " 시트를 불러오는 중…");
            return fetchSheet(state.activeTable)
                .then(function (payload) {
                    cache[state.activeTable] = payload;
                    renderTabs(root, state, cache);
                    renderTable(root, payload, state);
                    log("loaded " + state.activeTable, { row_count: payload.summary && payload.summary.row_count });
                })
                .catch(function (err) {
                    setError(root, state.activeTable + " 시트 로드 실패: " + err.message);
                    log("load failed " + state.activeTable, String(err), "error");
                });
        }

        root.addEventListener("click", function (event) {
            var tabButton = event.target.closest("[data-sheet-table]");
            if (tabButton && root.contains(tabButton)) {
                state.activeTable = tabButton.dataset.sheetTable || "result";
                persist();
                refreshActive(false);
                return;
            }
            var sortButton = event.target.closest("[data-sheet-sort]");
            if (sortButton && root.contains(sortButton)) {
                var nextSort = sortButton.dataset.sheetSort || "id";
                if (state.sortBy === nextSort) {
                    state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
                } else {
                    state.sortBy = nextSort;
                    state.sortDir = "asc";
                }
                persist();
                if (cache[state.activeTable]) {
                    renderTable(root, cache[state.activeTable], state);
                }
                return;
            }
            if (event.target.closest("[data-sheet-refresh]")) {
                refreshActive(true);
                return;
            }
            if (event.target.closest("[data-sheet-create-evidence]")) {
                var evidencePayload = promptEvidencePayload();
                if (!evidencePayload) {
                    return;
                }
                previewEvidenceCreate(evidencePayload)
                    .then(function (preview) {
                        if (!window.confirm(buildDiffText(preview))) {
                            return null;
                        }
                        return applyEvidenceCreate(evidencePayload, preview.preview_hash);
                    })
                    .then(function (result) {
                        if (!result) {
                            return;
                        }
                        log("evidence created", result);
                        return refreshActive(true);
                    })
                    .catch(function (err) {
                        window.alert("Evidence 저장 실패: " + err.message);
                        log("evidence create failed", String(err), "error");
                    });
            }
        });

        root.addEventListener("dblclick", function (event) {
            var cell = event.target.closest("td[data-sheet-row-id][data-sheet-field]");
            if (!cell || !root.contains(cell)) {
                return;
            }
            var activePayload = cache[state.activeTable];
            if (!activePayload) {
                return;
            }
            var rowId = cell.dataset.sheetRowId || "";
            var fieldName = cell.dataset.sheetField || "";
            var row = findRowById(activePayload, rowId);
            if (!row) {
                return;
            }
            var currentValue = formatValue(row[fieldName]);
            var nextValue = window.prompt(fieldName + " 수정", currentValue);
            if (nextValue === null || nextValue === currentValue) {
                return;
            }
            var changes = {};
            changes[fieldName] = nextValue;
            previewSheetPatch(state.activeTable, rowId, changes)
                .then(function (preview) {
                    if (!window.confirm(buildDiffText(preview))) {
                        return null;
                    }
                    return applySheetPatch(state.activeTable, rowId, changes, preview.preview_hash);
                })
                .then(function (result) {
                    if (!result) {
                        return;
                    }
                    log("row updated", result);
                    return refreshActive(true);
                })
                .catch(function (err) {
                    window.alert("시트 저장 실패: " + err.message);
                    log("sheet update failed", String(err), "error");
                });
        });

        queryInput.addEventListener("input", function () {
            state.query = queryInput.value.trim();
            persist();
            if (cache[state.activeTable]) {
                renderTable(root, cache[state.activeTable], state);
            }
        });
        problemOnlyInput.addEventListener("change", function () {
            state.problemOnly = !!problemOnlyInput.checked;
            persist();
            if (cache[state.activeTable]) {
                renderTable(root, cache[state.activeTable], state);
            }
        });

        renderTabs(root, state, cache);
        refreshActive(false);
    }

    function init() {
        document.querySelectorAll(ROOT_SELECTOR).forEach(mount);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
